"""Fase 2 de sales-flow-guardrail-fases-restantes.md — espelha
test_agendamento_sales_flow_pending.py para p4 (follow-up). Cobre o `route_to` da Mãe via
`_enforce_followup_sales_flow_pending` (novo). Duas diferenças estruturais deliberadas em
relação ao padrão de p0/p2/p3a/p3b, ambas cobertas abaixo:

1. "Engajado com follow-up" usa SÓ `current_category == "follow-up"` — nunca
   `"p4" in phases_triggered` — para não disparar durante o check-in de relacionamento
   pós-venda (`followup_variant="client_checkin"`), que reusa a fase p4 sem mover
   `lead.category` para "follow-up" (o lead permanece em "client-list").
2. Não conflita com o subsistema de ticks agendados (`whatsapp.followup.tick`): o guardrail
   roda normalmente durante um tick, mas isso é inofensivo porque `route_for_child` já é
   forçado para "follow-up" incondicionalmente pelo mecanismo existente de
   `force_followup_route`, independente do que o guardrail decida sobre `route_to`.
"""
from app.services.decision_engine import _enforce_followup_sales_flow_pending
from app.services.orchestrator_models import MotherDecision
from app.services import decision_engine


def _sales_flow_p4_pending() -> dict:
    return {
        "enabled": True,
        "phases": [
            {
                "id": "p4",
                "blocks": [
                    {
                        "id": "kw4",
                        "typeId": "kw_trigger",
                        "keywords": "sim quero",
                        "fire_once": True,
                    }
                ],
            }
        ],
    }


def _mother_decision(route_to: str, reason: str = "mother chose it") -> MotherDecision:
    return MotherDecision(route_to=route_to, confidence=0.8, reason=reason)


def test_enforce_followup_pending_blocks_mother_route_jump():
    """A Mãe decide sozinha pular p4 inteira num único turno (route_to='closing') sem o
    gatilho sequencial de p4 ter disparado. O guardrail deve forçar a rota de volta para
    'follow-up'."""
    context = {
        "lead": {"category": "follow-up", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p4_pending()},
    }
    mother_decision = _mother_decision("closing")

    result = _enforce_followup_sales_flow_pending(mother_decision, context)

    assert result.route_to == "follow-up"
    assert "sales_flow_followup_pending_forced_route" in result.reason
    assert "kw4" in result.reason


def test_enforce_followup_pending_allows_jump_once_all_sequential_triggers_fired():
    context = {
        "lead": {"category": "follow-up", "triggers_fired": '["kw4"]'},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p4_pending()},
    }
    mother_decision = _mother_decision("closing")

    result = _enforce_followup_sales_flow_pending(mother_decision, context)

    assert result.route_to == "closing"


def test_enforce_followup_pending_ignores_other_current_categories():
    """Só age quando o lead está atualmente em 'follow-up'."""
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p4_pending()},
    }
    mother_decision = _mother_decision("follow-up")

    result = _enforce_followup_sales_flow_pending(mother_decision, context)

    assert result.route_to == "follow-up"


def test_enforce_followup_pending_noop_without_sales_flow_configured():
    context = {
        "lead": {"category": "follow-up", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": {"enabled": False, "phases": []}},
    }
    mother_decision = _mother_decision("closing")

    result = _enforce_followup_sales_flow_pending(mother_decision, context)

    assert result.route_to == "closing"


def test_enforce_followup_pending_ignores_phases_triggered_signal():
    """Diferença deliberada em relação a p0/p2/p3a/p3b: NÃO usa 'p4' in phases_triggered
    como sinal de engajamento (só current_category == 'follow-up'). Confirma que um lead com
    'p4' em phases_triggered mas category diferente de 'follow-up' não é afetado."""
    context = {
        "lead": {
            "category": "apresentation",
            "triggers_fired": "[]",
            "phases_triggered": '["p4"]',
        },
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p4_pending()},
    }
    mother_decision = _mother_decision("closing")

    result = _enforce_followup_sales_flow_pending(mother_decision, context)

    assert result.route_to == "closing"


def test_enforce_followup_pending_excludes_client_checkin_variant():
    """Caso central da exclusão: lead em client-list (check-in pós-venda,
    followup_variant='client_checkin'), já tendo passado por p4 antes de virar cliente
    (phases_triggered contém 'p4') e com gatilho p4 pendente configurado. O guardrail NÃO
    deve intervir — a categoria não é 'follow-up'."""
    context = {
        "lead": {
            "category": "client-list",
            "triggers_fired": "[]",
            "phases_triggered": '["p0", "p1", "p2", "p4"]',
        },
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p4_pending()},
        "metadata": {
            "followup_context": {"followup_variant": "client_checkin"},
        },
    }
    mother_decision = _mother_decision("closing")

    result = _enforce_followup_sales_flow_pending(mother_decision, context)

    assert result.route_to == "closing"


# --- Nível decide(): tick agendado não quebra com o guardrail presente ---

def test_followup_tick_route_priority_unaffected_by_pending_p4_trigger(monkeypatch):
    """O tick (whatsapp.followup.tick) força route_for_child='follow-up' incondicionalmente
    via _is_followup_tick_context/force_followup_route, independente do que
    _enforce_followup_sales_flow_pending decida sobre route_to. Regressão explícita: com um
    gatilho p4 pendente configurado, o tick continua chamando a Filha de follow-up
    normalmente."""
    context = {
        "lead": {
            "id": 10,
            "user_id": 99,
            "category": "follow-up",
            "triggers_fired": "[]",
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p4_pending()},
        "playbook": {},
        "metadata": {
            "inbound_message_text": "followup_tick_auto_trigger",
            "followup_context": {
                "followup_goal": "reschedule",
                "followup_variant": "hybrid_scheduler",
                "followup_attempts": 1,
            },
        },
        "history": [],
        "job": {"id": 123, "type": "whatsapp.followup.tick", "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt, **_kwargs: '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"lead confirmou"}',
    )

    calls = {}

    def _child(route: str, _prompt: str, **_kwargs):
        calls["route"] = route
        return '{"message_text":"mensagem follow-up","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", _child)

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert calls["route"] == "follow-up"
    assert trace.get("effective_route_to") == "follow-up"
    assert decision.next_action == "reply"
