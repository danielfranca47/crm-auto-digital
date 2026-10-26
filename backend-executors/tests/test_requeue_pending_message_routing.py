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


def _decide_with_child(monkeypatch, child_json: str, message_text: str):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: (
            '{"route_to":"recepcao","perceived_category":null,"confidence":0.9,'
            '"reason":"saudação composta"}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service, "generate_child_result", lambda _route, _prompt, **_kwargs: child_json
    )
    return decision_engine.decide(_context(message_text))


def test_lead_already_answered_drops_trailing_owner_question(monkeypatch):
    """Lead já escolheu a opção da pergunta da Fase 0: o código tira a pergunta final que o
    modelo repetiu, e o pedido continua a ser reenfileirado."""
    decision = _decide_with_child(
        monkeypatch,
        '{"lead_already_answered":"Val","message_text":"Olá! Sou a Lara, atendente do Sensi Vitae. '
        'Qual terapeuta você tem interesse, a Val ou o Daniel?","confidence":0.95,'
        '"pending_commercial_text":"gostaria de saber mais sobre as massagens da val"}',
        "ola, gostaria de saber mais sobre as massagens da val",
    )
    assert decision.message_text == "Olá! Sou a Lara, atendente do Sensi Vitae."
    assert decision.system_actions == [
        {"type": "requeue_pending_message", "message_text": "gostaria de saber mais sobre as massagens da val"}
    ]


def test_without_lead_already_answered_question_is_kept(monkeypatch):
    decision = _decide_with_child(
        monkeypatch,
        '{"lead_already_answered":null,"message_text":"Olá! Sou a Lara. Val ou Daniel?","confidence":0.95,'
        '"pending_commercial_text":null}',
        "olá",
    )
    assert decision.message_text == "Olá! Sou a Lara. Val ou Daniel?"


def test_drop_trailing_question_keeps_text_when_only_question():
    assert decision_engine._drop_trailing_question("Val ou Daniel?") == "Val ou Daniel?"
    assert decision_engine._drop_trailing_question("Olá! Sou a Ana.\nRita ou Paulo?") == "Olá! Sou a Ana."
    assert decision_engine._drop_trailing_question("Olá! Sou a Ana.") == "Olá! Sou a Ana."


def test_recepcao_question_text_does_not_replace_greeting(monkeypatch):
    """A Filha Recepção pôs uma pergunta do roteiro em question_text (should_ask=true): a
    resposta continua a ser o cumprimento de message_text, e o pedido segue reenfileirado."""
    decision = _decide_with_child(
        monkeypatch,
        '{"lead_already_answered":null,"message_text":"Bom dia! Sou a Lara, do Sensi Vitae.",'
        '"should_ask":true,"question_text":"Posso enviar a nossa tabela de preços?","confidence":0.95,'
        '"pending_commercial_text":"quanto custa a massagem relaxante de 1h?"}',
        "Bom dia, quanto custa a massagem relaxante de 1h?",
    )
    assert decision.message_text == "Bom dia! Sou a Lara, do Sensi Vitae."
    assert decision.system_actions == [
        {"type": "requeue_pending_message", "message_text": "quanto custa a massagem relaxante de 1h?"}
    ]


def test_recepcao_promise_after_greeting_is_dropped_when_request_is_pending(monkeypatch):
    """Lead fez um pedido sem cumprimentar: a Filha anunciou "Vou passar as informações…". O
    pedido segue para a 2.ª decisão, por isso a promessa sai e fica só o cumprimento."""
    decision = _decide_with_child(
        monkeypatch,
        '{"lead_already_answered":null,"message_text":"Boa noite! Sou a Lara, do Sensi Vitae. '
        'Vou passar as informações sobre as massagens para você.","confidence":0.95,'
        '"pending_commercial_text":"Gostaria de mais informações sobre as Massagens"}',
        "Gostaria de mais informações sobre as Massagens",
    )
    assert decision.message_text == "Boa noite! Sou a Lara, do Sensi Vitae."
    assert (decision.decision_trace or {}).get("recepcao_promise_stripped") is True
    assert decision.system_actions == [
        {"type": "requeue_pending_message", "message_text": "Gostaria de mais informações sobre as Massagens"}
    ]


def test_recepcao_without_pending_request_keeps_message(monkeypatch):
    decision = _decide_with_child(
        monkeypatch,
        '{"lead_already_answered":null,"message_text":"Boa noite! Sou a Lara, do Sensi Vitae. Como posso ajudar?",'
        '"confidence":0.95,"pending_commercial_text":null}',
        "Olá",
    )
    assert decision.message_text == "Boa noite! Sou a Lara, do Sensi Vitae. Como posso ajudar?"
    assert "recepcao_promise_stripped" not in (decision.decision_trace or {})


def test_recepcao_only_promise_falls_back_to_greeting(monkeypatch):
    decision = _decide_with_child(
        monkeypatch,
        '{"lead_already_answered":null,"message_text":"Vou enviar a nossa tabela de preços.",'
        '"confidence":0.95,"pending_commercial_text":"queria saber os preços"}',
        "queria saber os preços",
    )
    assert decision.message_text in ("Bom dia!", "Boa tarde!", "Boa noite!")


def test_recepcao_owner_question_survives_promise_guardrail(monkeypatch):
    """A pergunta pedida pelas instruções da Fase 0 não é promessa: fica."""
    decision = _decide_with_child(
        monkeypatch,
        '{"lead_already_answered":null,"message_text":"Olá! Sou a Lara.\\nJá lhe envio os detalhes.\\n'
        'Qual terapeuta prefere, Val ou Daniel?","confidence":0.95,'
        '"pending_commercial_text":"queria marcar uma massagem"}',
        "olá, queria marcar uma massagem",
    )
    assert decision.message_text == "Olá! Sou a Lara.\nQual terapeuta prefere, Val ou Daniel?"


def test_drop_promise_sentences_variants():
    f = decision_engine._drop_promise_sentences
    assert f("Boa noite! Vou ajudar com as informações que precisa.") == "Boa noite!"
    assert f("Bom dia! Estou aqui para ajudar.") == "Bom dia! Estou aqui para ajudar."
    assert f("¡Hola! Te paso la información enseguida.") == "¡Hola!"
    assert f("Hi! I'll send you our price list.") == "Hi!"
    assert f("Vou já ajudar.") == ""
