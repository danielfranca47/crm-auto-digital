from datetime import datetime, timedelta, timezone

from app.schemas.decision import DecisionOutput
from app.services import meeting_scheduler


class FakeCRMClient:
    def __init__(self):
        self.cancel_calls = []
        self.reschedule_calls = []
        self.bot_disabled_calls = []

    def cancel_appointment(self, appointment_id):
        self.cancel_calls.append(appointment_id)
        return {"status": "ok"}

    def reschedule_appointment(self, appointment_id, *, start_at, end_at):
        self.reschedule_calls.append((appointment_id, start_at, end_at))
        return {"status": "ok"}

    def set_lead_bot_disabled(self, lead_id, disabled, reason=None):
        self.bot_disabled_calls.append((lead_id, disabled, reason))
        return {"status": "ok"}


class ConflictCRMClient(FakeCRMClient):
    def reschedule_appointment(self, appointment_id, *, start_at, end_at):
        from app.clients.crm_client import CRMClientError

        raise CRMClientError("conflito", status_code=409)


def _busy_slot(appointment_id, lead_id, start_at, end_at):
    return {"id": appointment_id, "lead_id": lead_id, "start_at": start_at, "end_at": end_at}


def _context(calendar_busy_slots):
    return {
        "lead": {"id": 1, "user_id": 10},
        "job": {"id": 999, "payload": {"lead_id": 1, "user_id": 10}},
        "ai_profile": {"timezone": "UTC"},
        "calendar_busy_slots": calendar_busy_slots,
    }


def _decision(signals_structured):
    return DecisionOutput(
        next_action="reply",
        message_text="ok",
        questions=[],
        reason="post_meeting_management",
        decision_trace={"child_signals_structured": signals_structured},
    )


def test_cancel_calls_cancel_appointment_and_reactivates_bot():
    client = FakeCRMClient()
    context = _context(
        [_busy_slot(42, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00")]
    )
    decision = _decision(
        {
            "meeting_cancel_requested": True,
            "meeting_reschedule_requested": False,
            "meeting_datetime_candidate": None,
        }
    )

    result = meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client
    )

    assert result is None
    assert client.cancel_calls == [42]
    assert client.bot_disabled_calls == [(1, False, "meeting_canceled")]
    assert client.reschedule_calls == []


def test_cancel_picks_soonest_appointment_when_multiple():
    client = FakeCRMClient()
    context = _context(
        [
            _busy_slot(2, 1, "2026-09-01T12:00:00+00:00", "2026-09-01T12:30:00+00:00"),
            _busy_slot(1, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00"),
        ]
    )
    decision = _decision(
        {"meeting_cancel_requested": True, "meeting_reschedule_requested": False}
    )

    meeting_scheduler.handle_meeting_cancel_or_reschedule(context, decision, client=client)

    assert client.cancel_calls == [1]


def test_reschedule_calls_reschedule_appointment_and_keeps_bot_disabled():
    client = FakeCRMClient()
    future = (datetime.now(timezone.utc) + timedelta(days=15)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    context = _context(
        [_busy_slot(42, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00")]
    )
    decision = _decision(
        {
            "meeting_cancel_requested": False,
            "meeting_reschedule_requested": True,
            "meeting_datetime_candidate": future.isoformat(),
        }
    )

    result = meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client
    )

    assert result is None
    assert len(client.reschedule_calls) == 1
    appointment_id, start_at, end_at = client.reschedule_calls[0]
    assert appointment_id == 42
    assert start_at.endswith("Z")
    assert end_at.endswith("Z")
    assert client.bot_disabled_calls == []


def test_reschedule_conflict_returns_correction_message(monkeypatch):
    monkeypatch.setattr(
        meeting_scheduler.llm_service, "generate_conflict_message", lambda _prompt, **_kwargs: ""
    )
    client = ConflictCRMClient()
    future = (datetime.now(timezone.utc) + timedelta(days=15)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    context = _context(
        [_busy_slot(42, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00")]
    )
    decision = _decision(
        {
            "meeting_cancel_requested": False,
            "meeting_reschedule_requested": True,
            "meeting_datetime_candidate": future.isoformat(),
        }
    )

    result = meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client
    )

    assert result == meeting_scheduler.MEETING_CONFLICT_MESSAGE


def test_no_signal_is_noop():
    client = FakeCRMClient()
    context = _context(
        [_busy_slot(42, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00")]
    )
    decision = _decision(
        {"meeting_cancel_requested": False, "meeting_reschedule_requested": False}
    )

    result = meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client
    )

    assert result is None
    assert client.cancel_calls == []
    assert client.reschedule_calls == []
    assert client.bot_disabled_calls == []


def test_no_matching_appointment_is_noop():
    client = FakeCRMClient()
    context = _context([])
    decision = _decision({"meeting_cancel_requested": True})

    result = meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client
    )

    assert result is None
    assert client.cancel_calls == []


def test_cancel_populates_events_when_provided():
    client = FakeCRMClient()
    context = _context(
        [_busy_slot(42, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00")]
    )
    decision = _decision(
        {"meeting_cancel_requested": True, "meeting_reschedule_requested": False}
    )
    events = []

    meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client, events=events
    )

    assert events == [
        {
            "action": "canceled",
            "start_at": "2026-08-10T12:00:00+00:00",
            "end_at": "2026-08-10T12:30:00+00:00",
        }
    ]


def test_reschedule_populates_events_when_provided():
    client = FakeCRMClient()
    future = (datetime.now(timezone.utc) + timedelta(days=15)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    context = _context(
        [_busy_slot(42, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00")]
    )
    decision = _decision(
        {
            "meeting_cancel_requested": False,
            "meeting_reschedule_requested": True,
            "meeting_datetime_candidate": future.isoformat(),
        }
    )
    events = []

    meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client, events=events
    )

    assert len(events) == 1
    assert events[0]["action"] == "rescheduled"
    assert events[0]["start_at"].endswith("Z")
    assert events[0]["end_at"].endswith("Z")


def test_conflict_does_not_populate_events(monkeypatch):
    monkeypatch.setattr(
        meeting_scheduler.llm_service, "generate_conflict_message", lambda _prompt, **_kwargs: ""
    )
    client = ConflictCRMClient()
    future = (datetime.now(timezone.utc) + timedelta(days=15)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    context = _context(
        [_busy_slot(42, 1, "2026-08-10T12:00:00+00:00", "2026-08-10T12:30:00+00:00")]
    )
    decision = _decision(
        {
            "meeting_cancel_requested": False,
            "meeting_reschedule_requested": True,
            "meeting_datetime_candidate": future.isoformat(),
        }
    )
    events = []

    meeting_scheduler.handle_meeting_cancel_or_reschedule(
        context, decision, client=client, events=events
    )

    assert events == []
