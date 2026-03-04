from datetime import datetime, timezone
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


class FakeCRMClient:
    def __init__(self):
        self.created = []
        self.bot_disabled_calls = []

    def list_appointments(self, *, start, end, lead_id=None, status=None):
        return []

    def create_lead_appointment(self, **kwargs):
        self.created.append(kwargs)
        return {"id": 1}

    def set_lead_bot_disabled(self, lead_id, disabled, reason=None):
        self.bot_disabled_calls.append((lead_id, disabled, reason))
        return {"status": "ok"}

    def log_meeting_scheduled(self, *, lead_id, user_id=None, job_id=None, reason):
        return {"status": "ok", "reason": reason}


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_structured_candidate_creates_appointment_with_30_min_window():
    context = {
        "lead": {"id": 44, "user_id": 55},
        "job": {"id": 66, "payload": {"lead_id": 44, "user_id": 55}},
        "ai_profile": {"agent_mode": "agenda", "timezone": "America/Sao_Paulo"},
        "metadata": {"inbound_message_text": "texto irrelevante"},
        "history": [],
    }
    decision = DecisionOutput(
        next_action="reply",
        message_text="Perfeito, agendado.",
        reason="meeting_scheduled|confirmado",
        decision_trace={
            "meeting_scheduled": True,
            "child_signals_structured": {
                "meeting_proposed": True,
                "meeting_datetime_candidate": "2099-03-05T17:00:00",
            },
        },
    )

    client = FakeCRMClient()
    meeting_scheduler.handle_meeting_scheduled(context, decision, client=client)

    assert len(client.created) == 1
    payload = client.created[0]
    assert payload["start_at"].endswith("Z")
    assert payload["end_at"].endswith("Z")
    assert _parse_iso(payload["end_at"]) - _parse_iso(payload["start_at"]) == meeting_scheduler.timedelta(minutes=30)
    assert client.bot_disabled_calls == [(44, True, "meeting_scheduled")]


if __name__ == "__main__":
    test_structured_candidate_creates_appointment_with_30_min_window()
    print("OK: structured meeting candidate e2e smoke")
