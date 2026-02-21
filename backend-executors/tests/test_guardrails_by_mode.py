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


def test_mother_agent_mode_conflict_does_not_override_system_consultivo():
    context = _base_context("consultivo", text="quero fechar")
    mother = MotherDecision(
        route_to="closing",
        perceived_category="closing",
        confidence=0.8,
        reason="fechar",
        agent_mode="agenda",
    )
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
    trace = decision.decision_trace or {}
    assert trace.get("agent_mode_normalized") == "consultivo"
    assert trace.get("mother_agent_mode_raw") == "agenda"
    assert trace.get("mother_agent_mode_conflict") is True


def test_mother_agent_mode_conflict_does_not_override_system_agenda():
    context = _base_context("agenda", text="quero fechar")
    mother = MotherDecision(
        route_to="closing",
        perceived_category="closing",
        confidence=0.8,
        reason="fechar",
        agent_mode="consultivo",
    )
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
    trace = decision.decision_trace or {}
    assert trace.get("agent_mode_normalized") == "agenda"
    assert trace.get("mother_agent_mode_raw") == "consultivo"
    assert trace.get("mother_agent_mode_conflict") is True


def test_qualification_complete_auto_promotes_to_apresentation():
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "tenho interesse"},
        "history": [],
        "qualification_state": {
            "exists": True,
            "data_json": {
                "service_interest": "botox",
                "urgency_level": "alta",
                "decision_role": "owner",
                "main_constraint": "tempo",
                "availability_window": "terça",
                "budget_range": "R$ 1.000",
            },
            "attempts_json": {},
            "last_questioned_field": "budget_range",
        },
    }
    mother = MotherDecision(
        route_to="qualification",
        perceived_category="qualification",
        confidence=0.9,
        reason="faltam dados",
    )
    child = ChildResult(
        message_text="Perfeito! Quer agendar uma avaliação?",
        did_complete_phase=False,
        recommended_next_category=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        confidence=0.8,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    trace = decision.decision_trace or {}
    assert decision.next_action == "reply"
    assert decision.suggested_category == "apresentation"
    assert trace.get("qualification_auto_promoted") is True
    assert trace.get("effective_route_to") == "apresentation"
    assert "qualification_complete_auto_promote:apresentation" in (decision.category_reason or "")
