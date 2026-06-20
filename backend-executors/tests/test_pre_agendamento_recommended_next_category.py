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


def test_direct_jump_to_agendamento_advances_category_despite_stage_clamp(monkeypatch):
    """Fase 5 (M3-bug real, reproduzido ao vivo no lead #273): quando a Mãe vai direto para
    'agendamento' sem o lead ter passado por 'pre-agendamento' (ex.: dia/hora já na 1ª
    mensagem), o clamp de salto único (_ALLOWED_ADVANCE) bloquearia o avanço e prenderia a
    categoria em 'apresentation' para sempre — o gate is_phase_entry do M3 nunca veria
    lead.category alcançar 'agendamento', e o appointment nunca seria criado em turno
    nenhum. A categoria deve avançar mesmo assim, confiando em effective_route_to (este
    turno em si continua a ser is_phase_entry=True, correctamente deferindo a criação real —
    é o turno SEGUINTE que passa a ver lead.category já em 'agendamento')."""
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {},
        "metadata": {"inbound_message_text": "amanhã às 15h funciona pra mim"},
        "history": [
            {"model": "outbound", "body": "Olá! Seja bem-vindo."},
            {"model": "inbound", "body": "amanhã às 15h funciona pra mim"},
        ],
    }
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: (
            '{"route_to":"agendamento","perceived_category":"agendamento",'
            '"confidence":0.9,"reason":"ok","signals":{"meeting_scheduled":true}}'
        ),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: (
            '{"message_text":"Ótimo, vou agendar para amanhã às 15h.",'
            '"did_complete_phase":false,"recommended_next_category":null,"outcome":null,'
            '"kanban_highlight":null,"signals":[],"confidence":0.8}'
        ),
    )

    decision = decision_engine.decide(dict(context))
    trace = decision.decision_trace or {}

    assert trace.get("effective_route_to") == "agendamento"
    assert decision.suggested_category == "agendamento"
    assert trace.get("is_phase_entry") is True
