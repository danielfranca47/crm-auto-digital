from app.services.decision_engine import _build_child_prompt_apresentation, compose_decision_output
from app.services.orchestrator_models import ChildResult, MotherDecision


def _base_context(agent_mode: str = "agenda", template_key: str = "sdr_padrao"):
    return {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {
            "agent_mode": agent_mode,
            "template_key": template_key,
            "timezone": "America/Sao_Paulo",
        },
        "playbook": {"template_key": template_key},
        "metadata": {"inbound_message_text": "Quero agendar"},
        "history": [],
    }


def test_compose_includes_structured_scheduler_fields_when_candidate_present():
    context = _base_context(agent_mode="agenda", template_key="sdr_padrao")
    mother = MotherDecision(route_to="apresentation", perceived_category="apresentation", confidence=0.9, reason="ok")
    child = ChildResult(
        message_text="Perfeito, ficou para quinta 17h.",
        did_complete_phase=False,
        recommended_next_category=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        signals_structured={"meeting_datetime_candidate": "2026-03-05T17:00:00"},
        confidence=0.8,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}

    assert structured.get("meeting_proposed") is True
    assert structured.get("meeting_datetime_candidate") == "2026-03-05T17:00:00"


def test_compose_defaults_scheduler_fields_when_missing():
    context = _base_context(agent_mode="agenda", template_key="sdr_padrao")
    mother = MotherDecision(route_to="apresentation", perceived_category="apresentation", confidence=0.9, reason="ok")
    child = ChildResult(
        message_text="Qual melhor dia para você?",
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


def test_compose_does_not_force_scheduler_fields_for_sales_variant():
    context = _base_context(agent_mode="direto", template_key="closer_agressivo")
    context["ai_profile"]["presentation_variant"] = "sales"
    mother = MotherDecision(route_to="apresentation", perceived_category="apresentation", confidence=0.9, reason="ok")
    child = ChildResult(
        message_text="Oferta enviada",
        did_complete_phase=False,
        recommended_next_category=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        signals_structured={"offer_presented": True, "checkout_sent": False},
        confidence=0.8,
    )

    decision = compose_decision_output(context=context, mother_decision=mother, child_result=child)
    structured = (decision.decision_trace or {}).get("child_signals_structured") or {}

    assert "meeting_proposed" not in structured
    assert "meeting_datetime_candidate" not in structured


def test_presentation_prompt_instructs_scheduler_structured_meeting_fields():
    context = _base_context(agent_mode="agenda", template_key="hybrid_scheduler")
    mother = MotherDecision(route_to="apresentation", perceived_category="apresentation", confidence=0.9, reason="ok")

    prompt = _build_child_prompt_apresentation(context, "Podemos marcar quinta?", mother)

    assert "meeting_proposed" in prompt
    assert "meeting_datetime_candidate" in prompt
    assert "ai_profile.timezone" in prompt
