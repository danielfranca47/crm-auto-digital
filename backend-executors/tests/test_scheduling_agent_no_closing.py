import pytest

from app.services import decision_engine


def _base_context(category: str, text: str, template_key: str = "hybrid_scheduler"):
    return {
        "lead": {"id": 3, "category": category},
        "ai_profile": {
            "template_key": template_key,
            "agent_mode": "agenda",
            "requires_handoff": True,
        },
        "playbook": {},
        "metadata": {"inbound_message_text": text},
        "history": [{"model": "outbound", "content": "Você confirma para essa hora?"}],
        "job": {"id": 1, "payload": {"lead_id": 3, "user_id": 1}},
    }


@pytest.mark.parametrize("template_key", ["hybrid_scheduler", "sdr_padrao"])
def test_booking_confirmation_does_not_escalate_to_silent_closing(monkeypatch, template_key):
    """Reproduz o bug real: lead confirma horário ('sim') em agendamento, Mãe
    decide route_to=closing, requires_handoff=true dispararia guardrail_sdr_escalate_closing
    (bot mudo) se não houvesse o enforcement de agentes de agendamento."""
    context = _base_context("agendamento", "sim", template_key=template_key)

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"confirmacao de horario"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: '{"message_text":"Combinado! Te espero amanha as 12h.","did_complete_phase":true,"recommended_next_category":"follow-up","outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("guardrail_sdr_escalate_closing") is not True
    assert decision.next_action != "ignore"
    assert decision.message_text != ""
    assert trace.get("mother_route_to") == "agendamento"
    assert "scheduling_agent_closing_disabled:agendamento" in (decision.reason or "")


@pytest.mark.parametrize("template_key", ["hybrid_scheduler", "sdr_padrao"])
def test_closing_signal_from_apresentation_falls_back_to_apresentation(monkeypatch, template_key):
    """Quando ainda não há fase de agendamento ativa (current_category=apresentation),
    o fallback deve ser apresentation, não agendamento."""
    context = _base_context("apresentation", "quero fechar", template_key=template_key)

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"fechar"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: '{"message_text":"Posso te ajudar com mais alguma coisa antes de marcarmos?","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("guardrail_sdr_escalate_closing") is not True
    assert trace.get("mother_route_to") == "apresentation"
    assert "scheduling_agent_closing_disabled:apresentation" in (decision.reason or "")


def test_non_scheduling_agent_still_escalates_closing(monkeypatch):
    """Regressão: agentes fora de sdr_padrao/hybrid_scheduler (ex.: closer_agressivo,
    consultor_especialista) continuam a escalar/silenciar normalmente quando chegam
    a closing (comportamento intencional, fora de escopo)."""
    context = _base_context("agendamento", "sim", template_key="closer_agressivo")

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"confirmacao de horario"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: '{"message_text":"ok","did_complete_phase":true,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("guardrail_sdr_escalate_closing") is True
    assert decision.next_action == "ignore"
    assert decision.message_text == ""
