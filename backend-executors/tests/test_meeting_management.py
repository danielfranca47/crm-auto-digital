import json
from datetime import datetime, timedelta, timezone

from app.schemas.decision import DecisionOutput
from app.services import decision_engine, llm_service, meeting_scheduler


def _base_context(message_text: str, calendar_busy_slots=None):
    return {
        "lead": {"id": 1, "user_id": 10, "category": "agendamento"},
        "job": {"id": 555, "payload": {"lead_id": 1, "user_id": 10}},
        "ai_profile": {
            "agent_mode": "agenda",
            "template_key": "hybrid_scheduler",
            "timezone": "America/Sao_Paulo",
        },
        "playbook": {"template_key": "hybrid_scheduler"},
        "metadata": {
            "inbound_message_text": message_text,
            "bot_disabled": True,
            "bot_disabled_reason": "meeting_scheduled",
        },
        "history": [],
        "calendar_busy_slots": calendar_busy_slots
        or [
            {
                "lead_id": 1,
                "start_at": "2026-03-06T12:00:00+00:00",
                "end_at": "2026-03-06T12:30:00+00:00",
            }
        ],
    }


def _child_payload(**signals_structured):
    return json.dumps(
        {
            "message_text": "ok",
            "did_complete_phase": False,
            "recommended_next_category": None,
            "outcome": None,
            "kanban_highlight": None,
            "signals": [],
            "signals_structured": signals_structured,
            "confidence": 0.7,
        }
    )


def test_prompt_includes_meeting_management_instructions():
    context = _base_context("preciso cancelar minha sessão")
    prompt = decision_engine._build_child_prompt_meeting_management(
        context, "preciso cancelar minha sessão"
    )
    assert "meeting_cancel_requested" in prompt
    assert "meeting_reschedule_requested" in prompt
    assert "REUNIÃO/SESSÃO JÁ CONFIRMADA" in prompt


def test_decide_post_meeting_management_detects_cancel(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "generate_child_result",
        lambda _route, _prompt: _child_payload(
            meeting_cancel_requested=True,
            meeting_reschedule_requested=False,
            meeting_datetime_candidate=None,
        ),
    )
    context = _base_context("preciso cancelar minha sessão de amanhã")
    decision = decision_engine.decide(context)

    assert decision.next_action == "reply"
    assert decision.suggested_category is None
    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}
    assert structured.get("meeting_cancel_requested") is True
    assert structured.get("meeting_reschedule_requested") is False


def test_decide_post_meeting_management_detects_reschedule(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "generate_child_result",
        lambda _route, _prompt: _child_payload(
            meeting_cancel_requested=False,
            meeting_reschedule_requested=True,
            meeting_datetime_candidate="2026-03-10T15:00:00",
        ),
    )
    context = _base_context("posso remarcar para terça às 15h?")
    decision = decision_engine.decide(context)

    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}
    assert structured.get("meeting_reschedule_requested") is True
    assert structured.get("meeting_datetime_candidate") == "2026-03-10T15:00:00"


def test_decide_post_meeting_management_neutral_message_minimal_reply(monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "generate_child_result",
        lambda _route, _prompt: _child_payload(
            meeting_cancel_requested=False,
            meeting_reschedule_requested=False,
            meeting_datetime_candidate=None,
        ),
    )
    context = _base_context("muito obrigada!")
    decision = decision_engine.decide(context)

    assert decision.next_action == "reply"
    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}
    assert structured.get("meeting_cancel_requested") is False
    assert structured.get("meeting_reschedule_requested") is False


def test_decide_keeps_blocking_other_bot_disabled_reasons(monkeypatch):
    called = {"yes": False}

    def _fail(*_a, **_k):
        called["yes"] = True
        return _child_payload()

    monkeypatch.setattr(llm_service, "generate_child_result", _fail)
    context = _base_context("oi")
    context["metadata"]["bot_disabled_reason"] = "handoff_requested"

    decision = decision_engine.decide(context)

    assert decision.next_action == "ignore"
    assert decision.reason == "bot_disabled"
    assert called["yes"] is False


def test_decide_post_meeting_management_llm_failure_falls_back_to_ignore(monkeypatch):
    monkeypatch.setattr(
        llm_service, "generate_child_result", lambda _route, _prompt: "not json"
    )
    context = _base_context("preciso cancelar")
    decision = decision_engine.decide(context)

    assert decision.next_action == "ignore"
    assert decision.reason == "meeting_management_llm_failure"


def _build_decision(signals_structured):
    return DecisionOutput(
        next_action="reply",
        message_text="ok",
        questions=[],
        reason="post_meeting_management",
        decision_trace={"child_signals_structured": signals_structured},
    )


def test_extract_cancel_reschedule_signal_cancel():
    context = _base_context("preciso cancelar")
    decision = _build_decision(
        {
            "meeting_cancel_requested": True,
            "meeting_reschedule_requested": False,
            "meeting_datetime_candidate": None,
        }
    )
    signal = meeting_scheduler._extract_cancel_reschedule_signal(context, decision)

    assert signal.lead_id == 1
    assert signal.cancel_requested is True
    assert signal.reschedule_requested is False
    assert signal.new_start_at is None


def test_extract_cancel_reschedule_signal_reschedule():
    future = (datetime.now(timezone.utc) + timedelta(days=10)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    context = _base_context("posso remarcar?")
    decision = _build_decision(
        {
            "meeting_cancel_requested": False,
            "meeting_reschedule_requested": True,
            "meeting_datetime_candidate": future.isoformat(),
        }
    )
    signal = meeting_scheduler._extract_cancel_reschedule_signal(context, decision)

    assert signal.reschedule_requested is True
    assert signal.new_start_at is not None
    assert signal.new_start_at.date() == future.date()
