from app.services.decision_engine import compose_decision_output
from app.services.orchestrator_models import ChildResult, MotherDecision


def _base_context(agent_mode: str, text: str = "oi"):
    return {
        "lead": {"category": "apresentation"},
        "ai_profile": {"agent_mode": agent_mode},
        "playbook": {},
        "metadata": {"inbound_message_text": text},
        "history": [],
    }


def test_consultivo_never_returns_won():
    context = _base_context("consultivo")
    mother = MotherDecision(route_to="closing", perceived_category="closing", confidence=0.8, reason="teste")
    child = ChildResult(
        message_text="ok",
        did_complete_phase=True,
        recommended_next_category="closing",
        outcome="won",
        kanban_highlight="green",
        signals=[],
        confidence=0.9,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    assert decision.outcome is None


def test_agenda_blocks_closing_without_booking_fields():
    context = _base_context("agenda", text="quero fechar")
    mother = MotherDecision(route_to="closing", perceived_category="closing", confidence=0.8, reason="fechar")
    child = ChildResult(
        message_text="ok",
        did_complete_phase=False,
        recommended_next_category="closing",
        outcome=None,
        kanban_highlight=None,
        signals=[],
        confidence=0.7,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    assert decision.suggested_category == "qualification"
    assert "guardrail_agenda_missing_booking" in decision.reason
