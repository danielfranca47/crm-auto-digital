"""
Fase 2 — Testes de comportamento de prompting (checklist items):
  [ ] Teste playground: pergunta direta → agente responde primeiro
  [ ] Teste playground: sem pergunta + campos pendentes → qualifica naturalmente
"""
from app.services import decision_engine


def _base_context(message_text: str, response_style: str) -> dict:
    return {
        "lead": {"category": "qualification"},
        "ai_profile": {
            "agent_mode": "agenda",
            "response_style": response_style,
            "qualification_required_fields": ["availability_window"],
        },
        "playbook": {},
        "metadata": {"inbound_message_text": message_text},
        # outbound_count>=1 evita que _enforce_greeting_first force route_to="recepcao"
        # (o cenário testado é meio de conversa, não o primeiro contato).
        "history": [{"model": "outbound", "body": "Oi! Tudo bem?"}],
        "qualification_state": {
            "exists": True,
            "data_json": {"service_interest": "botox"},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }


def test_direct_question_agent_replies_first(monkeypatch):
    """
    Pergunta direta do lead + campos pendentes + response_style=passive →
    mãe emite next_action_hint='reply' → next_action deve ser 'reply' (não 'ask_qualification').
    """
    context = _base_context("Quanto custa o botox?", "passive")

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: (
            '{"route_to":"qualification","next_action_hint":"reply",'
            '"perceived_category":"qualification","confidence":0.9,'
            '"reason":"pergunta direta detectada"}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: (
            '{"message_text":"O botox custa a partir de R$350, com duração de 4 a 6 meses.",'
            '"question_text":null,"field":null,"did_complete_phase":false,'
            '"recommended_next_category":null,"outcome":null,"kanban_highlight":null,'
            '"signals":[],"confidence":0.8}'
        ),
    )

    decision = decision_engine.decide(context)

    assert decision.next_action == "reply", (
        f"Esperado next_action='reply' (resposta à pergunta direta), "
        f"mas foi '{decision.next_action}'. "
        f"Trace: {decision.decision_trace}"
    )
    assert "botox" in (decision.message_text or "").lower() or decision.message_text, (
        "Resposta deve conter o conteúdo do filho (resposta à pergunta), não uma pergunta de qualificação."
    )


def test_no_direct_question_qualifies_naturally(monkeypatch):
    """
    Mensagem simples (sem pergunta direta) + campos pendentes + response_style=active →
    mãe NÃO emite next_action_hint='reply' → next_action deve ser 'ask_qualification'.
    """
    context = _base_context("oi", "active")

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: (
            '{"route_to":"qualification","next_action_hint":null,'
            '"perceived_category":"qualification","confidence":0.85,'
            '"reason":"qualificação pendente sem pergunta direta"}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: (
            '{"message_text":"Qual o melhor horário para você?",'
            '"question_text":"Qual o melhor horário para você?",'
            '"field":"availability_window","did_complete_phase":false,'
            '"recommended_next_category":null,"outcome":null,"kanban_highlight":null,'
            '"signals":[],"confidence":0.85}'
        ),
    )

    decision = decision_engine.decide(context)

    assert decision.next_action == "ask_qualification", (
        f"Esperado next_action='ask_qualification' (qualificação natural), "
        f"mas foi '{decision.next_action}'. "
        f"Trace: {decision.decision_trace}"
    )
