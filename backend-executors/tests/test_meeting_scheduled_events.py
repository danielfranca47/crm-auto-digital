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
