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


def _build_context(message_text="2024-11-10 15:30"):
    return {
        "lead": {"id": 99, "user_id": 10},
        "job": {"id": 123, "payload": {"lead_id": 99, "user_id": 10}},
        "ai_profile": {"agent_mode": "sdr_scheduler", "timezone": "UTC"},
        "metadata": {"inbound_message_text": message_text},
        "history": [],
    }


def _build_decision():
    return DecisionOutput(
        next_action="reply",
        message_text="ok",
        questions=[],
        reason="meeting_scheduled|confirmou horário",
        decision_trace={"meeting_scheduled": True},
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
    future = (datetime.utcnow() + timedelta(days=2)).isoformat()
    client = FakeCRMClient(
        appointments=[{"start_at": future, "type": "meeting", "status": "pending"}]
    )
    meeting_scheduler.handle_meeting_scheduled(
        _build_context(),
        _build_decision(),
        client=client,
    )
    assert client.bot_disabled_calls == [(99, True, "meeting_scheduled")]
    assert client.created == []


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
