"""Fase 3 de sales-flow-fase-pendente-guardrail.md — espelha a Fase 2 (p2/apresentation)
para p3a (pré-agendamento), só relevante para o modo `agenda` (único que visita p3a). Cobre
os dois caminhos que podiam avançar a categoria sem checar gatilhos sequenciais pendentes:
o `route_to` da Mãe (`_enforce_pre_agendamento_sales_flow_pending`, novo — mesma classe de
bug que p2 tinha antes de ser corrigido) e o sinal `did_complete_phase` da Filha
(`pre_agendamento_complete_auto_advance` em `compose_decision_output`)."""
import pytest

from app.services.decision_engine import _enforce_pre_agendamento_sales_flow_pending
from app.services.orchestrator_models import MotherDecision
from app.services import decision_engine


def _sales_flow_p3a_pending() -> dict:
    return {
        "enabled": True,
        "phases": [
            {
                "id": "p3a",
                "blocks": [
                    {
                        "id": "kw3a",
                        "typeId": "kw_trigger",
                        "keywords": "confirmar horario",
                        "fire_once": True,
                    }
                ],
            }
        ],
    }


def _mother_decision(route_to: str, reason: str = "mother chose it") -> MotherDecision:
    return MotherDecision(route_to=route_to, confidence=0.8, reason=reason)


def test_enforce_pre_agendamento_pending_blocks_mother_route_jump():
    """Mesma classe de bug que p2 tinha antes de ser corrigido: a Mãe decide sozinha pular
    p3a inteira num único turno (route_to='agendamento') sem o gatilho sequencial de p3a ter
    disparado. O guardrail deve forçar a rota de volta para 'pre-agendamento'."""
    context = {
        "lead": {"category": "pre-agendamento", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3a_pending()},
    }
    mother_decision = _mother_decision("agendamento")

    result = _enforce_pre_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "pre-agendamento"
    assert "sales_flow_pre_agendamento_pending_forced_route" in result.reason
    assert "kw3a" in result.reason


@pytest.mark.parametrize("target_route", ["agendamento", "follow-up"])
def test_enforce_pre_agendamento_pending_blocks_any_allowed_advance_target(target_route):
    """Cobre qualquer salto permitido a partir de 'pre-agendamento' (_ALLOWED_ADVANCE)."""
    context = {
        "lead": {"category": "pre-agendamento", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3a_pending()},
    }
    mother_decision = _mother_decision(target_route)

    result = _enforce_pre_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "pre-agendamento"


def test_enforce_pre_agendamento_pending_allows_jump_once_all_sequential_triggers_fired():
    context = {
        "lead": {"category": "pre-agendamento", "triggers_fired": '["kw3a"]'},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3a_pending()},
    }
    mother_decision = _mother_decision("agendamento")

    result = _enforce_pre_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "agendamento"


def test_enforce_pre_agendamento_pending_ignores_other_current_categories():
    """Só age quando o lead está atualmente em 'pre-agendamento'."""
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3a_pending()},
    }
    mother_decision = _mother_decision("pre-agendamento")

    result = _enforce_pre_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "pre-agendamento"


def test_enforce_pre_agendamento_pending_noop_without_sales_flow_configured():
    context = {
        "lead": {"category": "pre-agendamento", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": {"enabled": False, "phases": []}},
    }
    mother_decision = _mother_decision("agendamento")

    result = _enforce_pre_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "agendamento"


def test_enforce_pre_agendamento_pending_uses_phases_triggered_when_category_lags():
    context = {
        "lead": {
            "category": "apresentation",
            "triggers_fired": "[]",
            "phases_triggered": '["p3a"]',
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3a_pending()},
    }
    mother_decision = _mother_decision("agendamento")

    result = _enforce_pre_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "pre-agendamento"


# --- Gate em pre_agendamento_complete_auto_advance (compose_decision_output) ---

def _compose_context(*, triggers_fired: str, sales_flow: dict) -> dict:
    return {
        "lead": {"id": 30, "user_id": 99, "category": "pre-agendamento", "triggers_fired": triggers_fired},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler", "sales_flow": sales_flow},
        "playbook": {},
        "metadata": {"inbound_message_text": "amanha as 14h funciona pra mim"},
        "history": [
            {"model": "outbound", "text": "Que dia funcionaria melhor pra você?"},
            {"model": "inbound", "text": "amanha as 14h funciona pra mim"},
        ],
    }


def _mock_mother_pre_agendamento(monkeypatch):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p, **_kwargs: (
            '{"route_to":"pre-agendamento","perceived_category":"pre-agendamento",'
            '"confidence":0.9,"reason":"teste"}'
        ),
    )


def _mock_child_completes_pre_agendamento(monkeypatch):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: (
            '{"message_text":"Perfeito, vou confirmar o horário.","did_complete_phase":true,'
            '"recommended_next_category":"agendamento","outcome":null,'
            '"kanban_highlight":null,"signals":[],"confidence":0.8}'
        ),
    )


def test_p3a_pending_trigger_blocks_pre_agendamento_complete_auto_advance(monkeypatch):
    context = _compose_context(triggers_fired="[]", sales_flow=_sales_flow_p3a_pending())
    _mock_mother_pre_agendamento(monkeypatch)
    _mock_child_completes_pre_agendamento(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.suggested_category == "pre-agendamento"


def test_p3a_trigger_already_fired_advances_normally(monkeypatch):
    context = _compose_context(triggers_fired='["kw3a"]', sales_flow=_sales_flow_p3a_pending())
    _mock_mother_pre_agendamento(monkeypatch)
    _mock_child_completes_pre_agendamento(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.suggested_category == "agendamento"


def test_no_sequential_trigger_in_p3a_behaves_like_baseline(monkeypatch):
    context = _compose_context(
        triggers_fired="[]",
        sales_flow={"enabled": True, "phases": [{"id": "p3a", "blocks": []}]},
    )
    _mock_mother_pre_agendamento(monkeypatch)
    _mock_child_completes_pre_agendamento(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.suggested_category == "agendamento"
