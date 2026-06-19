from app.services import decision_engine


def test_compound_follow_through_routes_directly_to_commercial_child(monkeypatch):
    """Saudação composta (cumprimento + pedido) deve pular a filha recepção e
    responder já com o conteúdo comercial, em vez de travar prometendo 'verificar'."""
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi, gostaria de agendar uma sessão para amanhã às 15h"},
        "history": [],
        "qualification_state": {
            "exists": False,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: (
            '{"route_to":"recepcao","perceived_category":"apresentation","confidence":0.9,'
            '"reason":"saudação composta","compound_follow_through":"apresentation"}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: (
            '{"message_text":"Olá! Temos horário às 15h amanhã, posso confirmar?",'
            '"did_complete_phase":false,"recommended_next_category":null,"outcome":null,'
            '"kanban_highlight":null,"signals":[],"confidence":0.8}'
        ),
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("mother_route_to") == "recepcao"
    assert trace.get("effective_route_to") == "apresentation"
    assert trace.get("prompt_function_used") == "_build_child_prompt_apresentation"
    assert decision.message_text == "Olá! Temos horário às 15h amanhã, posso confirmar?"


def test_perceived_category_fallback_routes_when_compound_follow_through_missing(monkeypatch):
    """Observado em teste manual real: o modelo às vezes sinaliza a intenção comercial
    via perceived_category em vez de compound_follow_through. Como perceived_category
    difere da categoria atual do lead (qualification -> agendamento), deve ser tratado
    como o mesmo sinal de saudação composta."""
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi, gostaria de agendar uma sessão para amanhã às 15h"},
        "history": [],
        "qualification_state": {
            "exists": False,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: (
            '{"route_to":"recepcao","perceived_category":"agendamento","confidence":1.0,'
            '"reason":"O cliente já mencionou dia e hora específica para agendar."}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: (
            '{"message_text":"Olá! Temos horário às 15h amanhã, posso confirmar?",'
            '"did_complete_phase":false,"recommended_next_category":null,"outcome":null,'
            '"kanban_highlight":null,"signals":[],"confidence":0.8}'
        ),
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("mother_route_to") == "recepcao"
    assert trace.get("effective_route_to") == "agendamento"
    assert trace.get("prompt_function_used") == "_build_child_prompt_agendamento"


def test_pure_greeting_without_compound_follow_through_stays_in_recepcao(monkeypatch):
    """Saudação pura (sem compound_follow_through) continua a usar a filha recepção,
    sem nenhuma alteração de comportamento prévia."""
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "qualification_state": {
            "exists": False,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: (
            '{"route_to":"recepcao","perceived_category":null,"confidence":0.9,"reason":"saudação pura"}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: (
            '{"message_text":"Olá! Seja bem-vindo.","did_complete_phase":false,'
            '"recommended_next_category":null,"outcome":null,"kanban_highlight":null,'
            '"signals":[],"confidence":0.9}'
        ),
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("mother_route_to") == "recepcao"
    assert trace.get("effective_route_to") == "recepcao"
    assert trace.get("prompt_function_used") == "_build_child_prompt_recepcao"
