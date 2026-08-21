from app.services import decision_engine


def _context(message_text: str):
    return {
        "lead": {"category": None},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {},
        "metadata": {"inbound_message_text": message_text},
        "history": [],
        "qualification_state": {
            "exists": False,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }


def test_compound_greeting_stays_in_recepcao_and_requeues_pending_text(monkeypatch):
    """1º contato com saudação + pedido comercial: a rota permanece recepcao (sem
    override em-turno) e o pedido pendente vira um system_action requeue_pending_message,
    em vez de a Mãe tentar adivinhar a rota comercial ou a Filha prometer 'vou verificar'."""
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: (
            '{"route_to":"recepcao","perceived_category":null,"confidence":0.9,'
            '"reason":"saudação composta"}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: (
            '{"message_text":"Olá! Tudo bem?","should_ask":false,"question_text":"",'
            '"field":null,"did_complete_phase":false,"confidence":0.95,"signals":[],'
            '"pending_commercial_text":"gostaria de agendar uma sessão para amanhã às 15h"}'
        ),
    )

    decision = decision_engine.decide(
        _context("oi, gostaria de agendar uma sessão para amanhã às 15h")
    )
    trace = decision.decision_trace or {}

    assert trace.get("mother_route_to") == "recepcao"
    assert trace.get("effective_route_to") == "recepcao"
    assert decision.message_text == "Olá! Tudo bem?"
    assert decision.system_actions == [
        {
            "type": "requeue_pending_message",
            "message_text": "gostaria de agendar uma sessão para amanhã às 15h",
        }
    ]


def test_pure_greeting_has_no_requeue_action(monkeypatch):
    """Saudação pura, sem pedido embutido: nenhum system_action de reenfileiramento."""
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: (
            '{"route_to":"recepcao","perceived_category":null,"confidence":0.9,"reason":"saudação pura"}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: (
            '{"message_text":"Olá! Seja bem-vindo.","did_complete_phase":false,'
            '"recommended_next_category":null,"outcome":null,"kanban_highlight":null,'
            '"signals":[],"confidence":0.9,"pending_commercial_text":null}'
        ),
    )

    decision = decision_engine.decide(_context("oi"))
    trace = decision.decision_trace or {}

    assert trace.get("effective_route_to") == "recepcao"
    assert not (decision.system_actions or [])
