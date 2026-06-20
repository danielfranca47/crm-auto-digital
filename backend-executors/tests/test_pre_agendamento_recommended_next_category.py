from app.services import decision_engine

_BASE_CONTEXT = {
    "lead": {"category": "pre-agendamento"},
    "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
    "playbook": {},
    "metadata": {"inbound_message_text": "amanhã às 14h funciona pra mim"},
    "history": [
        {"model": "outbound", "body": "Que dia funcionaria melhor pra você?"},
        {"model": "inbound", "body": "amanhã às 14h funciona pra mim"},
    ],
}


def _mock_mother(monkeypatch):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: (
            '{"route_to":"pre-agendamento","perceived_category":"pre-agendamento",'
            '"confidence":0.8,"reason":"ok"}'
        ),
    )


def _mock_child(monkeypatch, *, recommended, did_complete_phase):
    recommended_value = "null" if recommended is None else f'"{recommended}"'
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: (
            '{"message_text":"ok","did_complete_phase":'
            f"{str(did_complete_phase).lower()},"
            f'"recommended_next_category":{recommended_value},'
            '"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'
        ),
    )


def test_pre_agendamento_recommends_agendamento_advances_category(monkeypatch):
    """Filha sinaliza dia/hora específicos resolvidos (Fase 3, M3-bug) — categoria avança
    para agendamento mesmo a Mãe tendo decidido pre-agendamento neste turno."""
    _mock_mother(monkeypatch)
    _mock_child(monkeypatch, recommended="agendamento", did_complete_phase=True)

    decision = decision_engine.decide(dict(_BASE_CONTEXT))

    assert decision.suggested_category == "agendamento"


def test_pre_agendamento_incomplete_does_not_advance(monkeypatch):
    """did_complete_phase=false — recomendação é ignorada, categoria permanece em
    pre-agendamento (sem avanço indevido para agendamento)."""
    _mock_mother(monkeypatch)
    _mock_child(monkeypatch, recommended="agendamento", did_complete_phase=False)

    decision = decision_engine.decide(dict(_BASE_CONTEXT))

    assert decision.suggested_category == "pre-agendamento"


def test_pre_agendamento_recommends_follow_up_does_not_auto_advance(monkeypatch):
    """Só 'agendamento' é aceite como avanço a partir de pre-agendamento — qualquer outro
    valor (fora do schema desta filha) é ignorado pelo guardrail, sem avanço indevido."""
    _mock_mother(monkeypatch)
    _mock_child(monkeypatch, recommended="follow-up", did_complete_phase=True)

    decision = decision_engine.decide(dict(_BASE_CONTEXT))

    assert decision.suggested_category == "pre-agendamento"
