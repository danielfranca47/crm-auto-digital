"""Fase 1 de sales-flow-guardrail-fases-restantes.md — espelha
test_pre_agendamento_sales_flow_pending.py para p3b (agendamento). Cobre o `route_to` da Mãe
via `_enforce_agendamento_sales_flow_pending` (novo — mesma classe de bug que p2/p3a tinham
antes de ser corrigidas). Diferente de p3a, p3b não tem um gate equivalente em
`compose_decision_output` (`*_complete_auto_advance`) — a única condição de saída hoje é o
`route_to` bruto da Mãe via `_ALLOWED_ADVANCE`, coberta pelos testes abaixo."""
import pytest

from app.services.decision_engine import _enforce_agendamento_sales_flow_pending
from app.services.orchestrator_models import MotherDecision


def _sales_flow_p3b_pending() -> dict:
    return {
        "enabled": True,
        "phases": [
            {
                "id": "p3b",
                "blocks": [
                    {
                        "id": "kw3b",
                        "typeId": "kw_trigger",
                        "keywords": "confirmado",
                        "fire_once": True,
                    }
                ],
            }
        ],
    }


def _mother_decision(route_to: str, reason: str = "mother chose it") -> MotherDecision:
    return MotherDecision(route_to=route_to, confidence=0.8, reason=reason)


def test_enforce_agendamento_pending_blocks_mother_route_jump():
    """A Mãe decide sozinha pular p3b inteira num único turno (route_to='follow-up') sem o
    gatilho sequencial de p3b ter disparado. O guardrail deve forçar a rota de volta para
    'agendamento'."""
    context = {
        "lead": {"category": "agendamento", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3b_pending()},
    }
    mother_decision = _mother_decision("follow-up")

    result = _enforce_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "agendamento"
    assert "sales_flow_agendamento_pending_forced_route" in result.reason
    assert "kw3b" in result.reason


@pytest.mark.parametrize("target_route", ["follow-up"])
def test_enforce_agendamento_pending_blocks_any_allowed_advance_target(target_route):
    """Cobre qualquer salto permitido a partir de 'agendamento' (_ALLOWED_ADVANCE) que a Mãe
    consiga de fato emitir. 'client-list' também está em _ALLOWED_ADVANCE["agendamento"], mas
    não é testado aqui: MotherDecision.route_to (Literal, orchestrator_models.py) nem aceita
    esse valor — ValidationError ao tentar construir. Achado confirmado nesta implementação,
    registrado em "Ajustes Possíveis Pós-Implementação" (bug de client-list fora de
    _STAGE_INDEX, agora sabido mais amplo do que só apply_mother_category_guardrails)."""
    context = {
        "lead": {"category": "agendamento", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3b_pending()},
    }
    mother_decision = _mother_decision(target_route)

    result = _enforce_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "agendamento"


def test_enforce_agendamento_pending_allows_jump_once_all_sequential_triggers_fired():
    context = {
        "lead": {"category": "agendamento", "triggers_fired": '["kw3b"]'},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3b_pending()},
    }
    mother_decision = _mother_decision("follow-up")

    result = _enforce_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "follow-up"


def test_enforce_agendamento_pending_ignores_other_current_categories():
    """Só age quando o lead está atualmente em 'agendamento'."""
    context = {
        "lead": {"category": "pre-agendamento", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3b_pending()},
    }
    mother_decision = _mother_decision("agendamento")

    result = _enforce_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "agendamento"


def test_enforce_agendamento_pending_noop_without_sales_flow_configured():
    context = {
        "lead": {"category": "agendamento", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": {"enabled": False, "phases": []}},
    }
    mother_decision = _mother_decision("follow-up")

    result = _enforce_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "follow-up"


def test_enforce_agendamento_pending_uses_phases_triggered_when_category_lags():
    context = {
        "lead": {
            "category": "pre-agendamento",
            "triggers_fired": "[]",
            "phases_triggered": '["p3b"]',
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_p3b_pending()},
    }
    mother_decision = _mother_decision("follow-up")

    result = _enforce_agendamento_sales_flow_pending(mother_decision, context)

    assert result.route_to == "agendamento"
