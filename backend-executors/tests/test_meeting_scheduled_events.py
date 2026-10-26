from datetime import datetime, timezone

from app.schemas.decision import DecisionOutput
from app.services import meeting_scheduler


class FakeCRMClient:
    def __init__(self):
        self.created = []
        self.bot_disabled_calls = []
        self.logged = []

    def create_lead_appointment(
        self, *, lead_id, title, description, appointment_type, start_at, end_at=None, source=None
    ):
        self.created.append(
            {"lead_id": lead_id, "title": title, "start_at": start_at, "end_at": end_at, "source": source}
        )
        return {"id": 1}

    def set_lead_bot_disabled(self, lead_id, disabled, reason=None):
        self.bot_disabled_calls.append((lead_id, disabled, reason))
        return {"status": "ok"}

    def log_meeting_scheduled(self, *, lead_id, user_id=None, job_id=None, reason):
        self.logged.append((lead_id, user_id, job_id, reason))
        return {"status": "ok"}


def _context(candidate_iso: str):
    return {
        "lead": {"id": 99, "user_id": 10},
        "job": {"id": 123, "payload": {"lead_id": 99, "user_id": 10}},
        "ai_profile": {"agent_mode": "agenda", "timezone": "UTC"},
        "metadata": {"inbound_message_text": ""},
        "history": [],
        "calendar_busy_slots": [],
    }, candidate_iso


def _decision(candidate_iso: str):
    return DecisionOutput(
        next_action="reply",
        message_text="ok",
        reason="meeting_scheduled|confirmou horário",
        decision_trace={
            "meeting_scheduled": True,
            "child_signals_structured": {
                "meeting_proposed": True,
                "meeting_datetime_candidate": candidate_iso,
            },
        },
    )


def test_handle_meeting_scheduled_populates_events_when_provided():
    client = FakeCRMClient()
    context, candidate = _context("2099-03-05T17:00:00")
    events = []

    meeting_scheduler.handle_meeting_scheduled(
        context,
        _decision(candidate),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
        is_playground=True,
        events=events,
    )

    assert len(client.created) == 1
    assert events == [
        {"action": "created", "start_at": client.created[0]["start_at"], "end_at": client.created[0]["end_at"]}
    ]


def test_handle_meeting_scheduled_without_events_param_does_not_raise():
    """Contrato usado pelo fluxo real do WhatsApp (app/runners/whatsapp.py) — não passa
    `events`. Precisa continuar a funcionar exatamente como antes."""
    client = FakeCRMClient()
    context, candidate = _context("2099-03-05T17:00:00")

    result = meeting_scheduler.handle_meeting_scheduled(
        context,
        _decision(candidate),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
    )

    assert result is None
    assert len(client.created) == 1


def test_handle_meeting_scheduled_no_candidate_creates_nothing():
    """Mãe sinaliza meeting_scheduled=true mas a Filha não confirmou nenhum horário (ex.:
    negou o horário pedido) — não deve criar compromisso nenhum, nem adivinhar via heurística
    de texto. Ver docs/implementations/fix-compromisso-fantasma-negacao-horario-disponivel.md."""
    client = FakeCRMClient()
    context, _ = _context(None)

    result = meeting_scheduler.handle_meeting_scheduled(
        context,
        _decision(None),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
    )

    assert result is None
    assert client.created == []
    assert client.logged == [(99, 10, 123, "missing_start_at")]


class _CRMError(Exception):
    def __init__(self, status_code):
        super().__init__(f"status={status_code}")
        self.status_code = status_code


class RejectingCRMClient(FakeCRMClient):
    def __init__(self, status_code):
        super().__init__()
        self.status_code = status_code

    def create_lead_appointment(self, **kwargs):
        raise _CRMError(self.status_code)


def test_create_conflict_409_returns_conflict_message_without_disabling_bot(monkeypatch):
    """O CRM recusa com 409 um horário que os busy_slots davam como livre: o cliente recebe a
    mensagem de conflito (antes: exceção → 502 no Playground / worker terminado no WhatsApp)."""
    monkeypatch.setattr(meeting_scheduler, "_generate_conflict_message", lambda ai_profile, logger=None: None)
    client = RejectingCRMClient(409)
    context, candidate = _context("2099-03-05T17:00:00")
    events = []

    message = meeting_scheduler.handle_meeting_scheduled(
        context,
        _decision(candidate),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
        is_playground=True,
        events=events,
    )

    assert message == meeting_scheduler.MEETING_CONFLICT_MESSAGE
    assert client.bot_disabled_calls == []
    assert events == []
    assert [entry[3] for entry in client.logged] == ["conflict_on_create"]


def test_create_other_failure_propagates_without_disabling_bot():
    """Falha que não é conflito: a marcação não ficou gravada — sobe para o runner reagendar o job."""
    import pytest

    client = RejectingCRMClient(500)
    context, candidate = _context("2099-03-05T17:00:00")

    with pytest.raises(_CRMError):
        meeting_scheduler.handle_meeting_scheduled(
            context,
            _decision(candidate),
            client=client,
            now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
            is_playground=True,
        )
    assert client.bot_disabled_calls == []
