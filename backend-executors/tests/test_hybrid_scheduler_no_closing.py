from app.services import decision_engine


def _base_context(category: str, text: str):
    return {
        "lead": {"id": 3, "category": category},
        "ai_profile": {
            "template_key": "hybrid_scheduler",
            "agent_mode": "agenda",
            "requires_handoff": True,
        },
        "playbook": {},
        "metadata": {"inbound_message_text": text},
        "history": [{"model": "outbound", "content": "Você confirma para essa hora?"}],
        "job": {"id": 1, "payload": {"lead_id": 3, "user_id": 1}},
    }


def test_booking_confirmation_does_not_escalate_to_silent_closing(monkeypatch):
    """Reproduz o bug real: lead confirma horário ('sim') em agendamento, Mãe
    decide route_to=closing, requires_handoff=true dispararia guardrail_sdr_escalate_closing
    (bot mudo) se não houvesse o enforcement de hybrid_scheduler."""
    context = _base_context("agendamento", "sim")

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"confirmacao de horario"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"Combinado! Te espero amanha as 12h.","did_complete_phase":true,"recommended_next_category":"follow-up","outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("guardrail_sdr_escalate_closing") is not True
    assert decision.next_action != "ignore"
    assert decision.message_text != ""
    assert trace.get("mother_route_to") == "agendamento"
    assert "hybrid_scheduler_closing_disabled:agendamento" in (decision.reason or "")


def test_closing_signal_from_apresentation_falls_back_to_apresentation(monkeypatch):
    """Quando ainda não há fase de agendamento ativa (current_category=apresentation),
    o fallback deve ser apresentation, não agendamento."""
    context = _base_context("apresentation", "quero fechar")

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"fechar"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"Posso te ajudar com mais alguma coisa antes de marcarmos?","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("guardrail_sdr_escalate_closing") is not True
    assert trace.get("mother_route_to") == "apresentation"
    assert "hybrid_scheduler_closing_disabled:apresentation" in (decision.reason or "")


def test_non_hybrid_scheduler_agent_still_escalates_closing(monkeypatch):
    """Regressão: agentes fora de hybrid_scheduler continuam a escalar/silenciar
    normalmente quando chegam a closing (comportamento intencional, fora de escopo)."""
    context = _base_context("agendamento", "sim")
    context["ai_profile"] = {
        "template_key": "sdr_padrao",
        "agent_mode": "agenda",
        "requires_handoff": True,
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"confirmacao de horario"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"ok","did_complete_phase":true,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("guardrail_sdr_escalate_closing") is True
    assert decision.next_action == "ignore"
    assert decision.message_text == ""
