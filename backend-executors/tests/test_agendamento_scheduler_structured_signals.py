from app.services.decision_engine import _build_child_prompt_agendamento, compose_decision_output
from app.services.orchestrator_models import ChildResult, MotherDecision


def _base_context(agent_mode: str = "agenda", template_key: str = "hybrid_scheduler"):
    return {
        "lead": {"id": 1, "category": "agendamento"},
        "ai_profile": {
            "agent_mode": agent_mode,
            "template_key": template_key,
            "timezone": "America/Sao_Paulo",
        },
        "playbook": {"template_key": template_key},
        "metadata": {"inbound_message_text": "Pode ser às 9h"},
        "history": [],
    }


def test_compose_includes_structured_scheduler_fields_when_candidate_present():
    context = _base_context(agent_mode="agenda", template_key="hybrid_scheduler")
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    child = ChildResult(
        message_text="Perfeito, ficou para amanhã às 9h.",
        did_complete_phase=False,
        recommended_next_category=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        signals_structured={"meeting_datetime_candidate": "2026-03-06T09:00:00"},
        confidence=0.8,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}

    assert structured.get("meeting_proposed") is True
    assert structured.get("meeting_datetime_candidate") == "2026-03-06T09:00:00"


def test_compose_defaults_scheduler_fields_when_missing():
    context = _base_context(agent_mode="agenda", template_key="hybrid_scheduler")
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    child = ChildResult(
        message_text="Qual horário prefere para amanhã?",
        did_complete_phase=False,
        recommended_next_category=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        signals_structured=None,
        confidence=0.8,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}

    assert structured.get("meeting_proposed") is False
    assert structured.get("meeting_datetime_candidate") is None


def test_compose_does_not_force_for_non_scheduling_template():
    context = _base_context(agent_mode="direto", template_key="closer_agressivo")
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    child = ChildResult(
        message_text="Confirmado.",
        did_complete_phase=False,
        recommended_next_category=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        signals_structured={"meeting_datetime_candidate": "2026-03-06T09:00:00"},
        confidence=0.8,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}

    assert "meeting_proposed" not in structured
    assert structured.get("meeting_datetime_candidate") == "2026-03-06T09:00:00"


def test_agendamento_prompt_instructs_scheduler_structured_meeting_fields():
    context = _base_context(agent_mode="agenda", template_key="hybrid_scheduler")
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")

    prompt = _build_child_prompt_agendamento(context, "Pode ser às 9h então", mother)

    assert "meeting_proposed" in prompt
    assert "meeting_datetime_candidate" in prompt
    assert "ai_profile.timezone" in prompt
