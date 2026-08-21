from datetime import datetime, timedelta, timezone
import os
import sys
import types

CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


def _install_fake_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _install_fake_decision_output():
    _install_fake_module("app.schemas")
    decision_module = _install_fake_module("app.schemas.decision")

    class DecisionOutput:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    decision_module.DecisionOutput = DecisionOutput


_install_fake_decision_output()

from app.schemas.decision import DecisionOutput
from app.services import meeting_scheduler


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class FakeCRMClient:
    def __init__(self, appointments=None):
        self.appointments = appointments or []
        self.bot_disabled_calls = []
        self.created = []
        self.logged = []

    def set_lead_bot_disabled(self, lead_id, disabled, reason=None):
        self.bot_disabled_calls.append((lead_id, disabled, reason))
        return {"status": "ok"}

    def list_appointments(self, *, start, end, lead_id=None, status=None):
        return list(self.appointments)

    def create_lead_appointment(
        self,
        *,
        lead_id,
        title,
        description,
        appointment_type,
        start_at,
        end_at=None,
    ):
        self.created.append(
            {
                "lead_id": lead_id,
                "title": title,
                "description": description,
                "type": appointment_type,
                "start_at": start_at,
                "end_at": end_at,
            }
        )
        return {"id": 1}

    def log_meeting_scheduled(self, *, lead_id, user_id=None, job_id=None, reason):
        self.logged.append((lead_id, user_id, job_id, reason))
        return {"status": "ok"}


def _build_context(message_text="2024-11-10 15:30", calendar_busy_slots=None):
    return {
        "lead": {"id": 99, "user_id": 10},
        "job": {"id": 123, "payload": {"lead_id": 99, "user_id": 10}},
        "ai_profile": {"agent_mode": "sdr_scheduler", "timezone": "UTC"},
        "metadata": {"inbound_message_text": message_text},
        "history": [],
        "calendar_busy_slots": calendar_busy_slots,
    }


def _build_decision():
    return DecisionOutput(
        next_action="reply",
        message_text="ok",
        questions=[],
        reason="meeting_scheduled|confirmou horário",
        decision_trace={"meeting_scheduled": True},
    )


def _build_decision_with_candidate(candidate_iso: str):
    """Usa o sinal estruturado (meeting_datetime_candidate) em vez de texto livre —
    determinístico, não depende de parsing de data nem do relógio real."""
    return DecisionOutput(
        next_action="reply",
        message_text="ok",
        questions=[],
        reason="meeting_scheduled|confirmou horário",
        decision_trace={
            "meeting_scheduled": True,
            "child_signals_structured": {
                "meeting_proposed": True,
                "meeting_datetime_candidate": candidate_iso,
            },
        },
    )


def test_handle_meeting_scheduled_creates_appointment():
    client = FakeCRMClient()
    meeting_scheduler.handle_meeting_scheduled(
        _build_context(),
        _build_decision(),
        client=client,
    )
    assert client.bot_disabled_calls == [(99, True, "meeting_scheduled")]
    assert len(client.created) == 1
    assert client.created[0]["start_at"].endswith("Z")
    assert client.created[0]["end_at"] and client.created[0]["end_at"].endswith("Z")
    assert _parse_iso(client.created[0]["end_at"]) > _parse_iso(client.created[0]["start_at"])
    assert client.logged == []


def test_handle_meeting_scheduled_idempotent():
    """Lead 99 já tem uma reunião futura (calendar_busy_slots) — não duplica."""
    future_start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    future_end = (datetime.now(timezone.utc) + timedelta(days=2, minutes=30)).isoformat()
    client = FakeCRMClient()
    context = _build_context(
        calendar_busy_slots=[{"lead_id": 99, "start_at": future_start, "end_at": future_end}]
    )
    meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision_with_candidate("2099-03-05T17:00:00"),
        client=client,
    )
    assert client.bot_disabled_calls == [(99, True, "meeting_scheduled")]
    assert client.created == []


def test_handle_meeting_scheduled_conflict_with_other_lead_blocks_creation(monkeypatch):
    """Outro lead (888) já ocupa o horário proposto — bloqueia e devolve fallback fixo
    quando a geração da mensagem via LLM falha (forçado para o teste ser determinístico,
    independente de haver LLM_API_KEY real configurada no .env local)."""
    def _raise(_prompt, **_kwargs):
        raise RuntimeError("forced failure for deterministic test")
    monkeypatch.setattr(meeting_scheduler.llm_service, "generate_conflict_message", _raise)

    client = FakeCRMClient()
    context = _build_context(
        calendar_busy_slots=[
            {
                "lead_id": 888,
                "start_at": "2099-03-05T17:10:00+00:00",
                "end_at": "2099-03-05T17:40:00+00:00",
            }
        ]
    )

    result = meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision_with_candidate("2099-03-05T17:00:00"),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
    )

    assert result == meeting_scheduler.MEETING_CONFLICT_MESSAGE
    assert client.created == []
    assert client.bot_disabled_calls == []
    assert client.logged == [(99, 10, 123, "conflict_detected")]


def test_handle_meeting_scheduled_conflict_uses_llm_generated_message(monkeypatch):
    """Quando a geração via LLM tem sucesso, a mensagem devolvida é a gerada, não o fallback."""
    monkeypatch.setattr(
        meeting_scheduler.llm_service,
        "generate_conflict_message",
        lambda _prompt, **_kwargs: "Esse horário já foi! Pode me dizer outro horário que funcione?",
    )

    client = FakeCRMClient()
    context = _build_context(
        calendar_busy_slots=[
            {
                "lead_id": 888,
                "start_at": "2099-03-05T17:10:00+00:00",
                "end_at": "2099-03-05T17:40:00+00:00",
            }
        ]
    )

    result = meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision_with_candidate("2099-03-05T17:00:00"),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
    )

    assert result == "Esse horário já foi! Pode me dizer outro horário que funcione?"
    assert client.created == []


def test_handle_meeting_scheduled_conflict_falls_back_when_llm_returns_empty(monkeypatch):
    """generate_conflict_message devolve "" (ex.: sem LLM_API_KEY) — cai no fallback fixo."""
    monkeypatch.setattr(
        meeting_scheduler.llm_service, "generate_conflict_message", lambda _prompt, **_kwargs: "",
    )

    client = FakeCRMClient()
    context = _build_context(
        calendar_busy_slots=[
            {
                "lead_id": 888,
                "start_at": "2099-03-05T17:10:00+00:00",
                "end_at": "2099-03-05T17:40:00+00:00",
            }
        ]
    )

    result = meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision_with_candidate("2099-03-05T17:00:00"),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
    )

    assert result == meeting_scheduler.MEETING_CONFLICT_MESSAGE


def test_handle_meeting_scheduled_no_conflict_creates_normally():
    """calendar_busy_slots presente mas sem sobreposição — cria normalmente."""
    client = FakeCRMClient()
    context = _build_context(
        calendar_busy_slots=[
            {
                "lead_id": 888,
                "start_at": "2099-03-06T09:00:00+00:00",
                "end_at": "2099-03-06T09:30:00+00:00",
            }
        ]
    )

    result = meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision_with_candidate("2099-03-05T17:00:00"),
        client=client,
        now_utc=datetime(2099, 3, 1, tzinfo=timezone.utc),
    )

    assert result is None
    assert len(client.created) == 1
    assert client.bot_disabled_calls == [(99, True, "meeting_scheduled")]


def test_handle_meeting_scheduled_skips_conflict_check_outside_window():
    """Horário proposto muito além da janela de calendar_busy_slots (30 dias) — não bloqueia."""
    client = FakeCRMClient()
    context = _build_context(calendar_busy_slots=[])

    result = meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision_with_candidate("2099-03-05T17:00:00"),
        client=client,
    )

    assert result is None
    assert len(client.created) == 1


def test_has_future_meeting_window():
    now = datetime.utcnow()
    appointments = [
        {"start_at": (now + timedelta(days=1)).isoformat(), "type": "meeting", "status": "pending"},
        {"start_at": (now + timedelta(days=10)).isoformat(), "type": "meeting", "status": "pending"},
    ]
    assert meeting_scheduler.has_future_meeting(appointments, now=now, window_days=7) is True


def test_handle_meeting_scheduled_human_datetime_with_timezone():
    client = FakeCRMClient()
    context = _build_context("amanhã 17h")
    context["ai_profile"]["timezone"] = "Europe/Lisbon"
    now = datetime(2025, 2, 10, 12, 0, tzinfo=timezone.utc)

    meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision(),
        client=client,
        now_utc=now,
    )

    assert len(client.created) == 1
    assert client.created[0]["start_at"].endswith("Z")
    assert client.created[0]["end_at"] and client.created[0]["end_at"].endswith("Z")
    assert _parse_iso(client.created[0]["end_at"]) > _parse_iso(client.created[0]["start_at"])
    assert client.bot_disabled_calls == [(99, True, "meeting_scheduled")]


def test_handle_meeting_scheduled_rejects_no_hour_expression():
    client = FakeCRMClient()
    context = _build_context("amanhã")
    context["ai_profile"]["timezone"] = "Europe/Lisbon"
    now = datetime(2025, 2, 10, 12, 0, tzinfo=timezone.utc)

    meeting_scheduler.handle_meeting_scheduled(
        context,
        _build_decision(),
        client=client,
        now_utc=now,
    )

    assert client.created == []
    assert client.bot_disabled_calls == []
    assert client.logged == [(99, 10, 123, "missing_start_at")]
