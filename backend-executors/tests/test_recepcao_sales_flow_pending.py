"""Fase 1 de sales-flow-guardrail-p0-recepcao.md — espelha
test_pre_agendamento_sales_flow_pending.py para p0 (recepção), com 2 adaptações estruturais:
"engajado com recepção" usa o sinal invertido (lead ainda não passou de qualification, já que
current_category=="recepcao" nunca é persistido) e um teto de 1 turno extra além do forçado por
_enforce_greeting_first (a Filha Recepção é desenhada para um único turno)."""
import pytest

from app.services.decision_engine import _enforce_recepcao_sales_flow_pending
from app.services.orchestrator_models import MotherDecision
from app.services import decision_engine


def _sales_flow_p0_pending() -> dict:
    return {
        "enabled": True,
        "phases": [
            {
                "id": "p0",
                "blocks": [
                    {
                        "id": "kw0",
                        "typeId": "kw_trigger",
                        "keywords": "aceito",
                        "fire_once": True,
                    }
                ],
            }
        ],
    }


def _mother_decision(route_to: str, reason: str = "mother chose it") -> MotherDecision:
    return MotherDecision(route_to=route_to, confidence=0.85, reason=reason)


def _history(outbound_count: int) -> list:
    return [{"model": "outbound", "text": f"msg {i}"} for i in range(outbound_count)]


def test_enforce_recepcao_pending_blocks_mother_route_jump():
    """Mesma classe de bug que p2/p3a tinham antes de ser corrigidos: a Mãe decide sozinha
    pular p0 inteira num único turno (route_to='qualification') sem o gatilho sequencial de p0
    ter disparado. O guardrail deve forçar a rota de volta para 'recepcao'."""
    context = {
        "lead": {"category": "qualification", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p0_pending()},
        "history": _history(1),
    }
    mother_decision = _mother_decision("qualification")

    result = _enforce_recepcao_sales_flow_pending(mother_decision, context)

    assert result.route_to == "recepcao"
    assert "sales_flow_recepcao_pending_forced_route" in result.reason
    assert "kw0" in result.reason


def test_enforce_recepcao_pending_allows_jump_once_all_sequential_triggers_fired():
    context = {
        "lead": {"category": "qualification", "triggers_fired": '["kw0"]'},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p0_pending()},
        "history": _history(1),
    }
    mother_decision = _mother_decision("qualification")

    result = _enforce_recepcao_sales_flow_pending(mother_decision, context)

    assert result.route_to == "qualification"


def test_enforce_recepcao_pending_noop_without_sales_flow_configured():
    context = {
        "lead": {"category": "qualification", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": {"enabled": False, "phases": []}},
        "history": _history(1),
    }
    mother_decision = _mother_decision("qualification")

    result = _enforce_recepcao_sales_flow_pending(mother_decision, context)

    assert result.route_to == "qualification"


def test_enforce_recepcao_pending_ignores_other_current_categories():
    """Só age quando o lead ainda não passou de 'qualification' — um lead já maduro
    (ex.: 'apresentation') não deve ser reengajado por uma pendência de p0."""
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p0_pending()},
        "history": _history(1),
    }
    mother_decision = _mother_decision("qualification")

    result = _enforce_recepcao_sales_flow_pending(mother_decision, context)

    assert result.route_to == "qualification"


def test_enforce_recepcao_pending_respects_outbound_turn_cap():
    """A Filha Recepção é de turno único — depois do teto de turnos, o guardrail falha aberto
    mesmo com gatilho pendente, para não repetir a saudação em plena conversa real."""
    context = {
        "lead": {"category": "qualification", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p0_pending()},
        "history": _history(2),
    }
    mother_decision = _mother_decision("qualification")

    result = _enforce_recepcao_sales_flow_pending(mother_decision, context)

    assert result.route_to == "qualification"


def test_enforce_recepcao_pending_ignores_route_not_in_allowed_advance():
    """'recepcao' só tem 'qualification' como destino legítimo em _ALLOWED_ADVANCE — outras
    rotas não são o alvo deste guardrail."""
    context = {
        "lead": {"category": "qualification", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "consultivo", "sales_flow": _sales_flow_p0_pending()},
        "history": _history(1),
    }
    mother_decision = _mother_decision("apresentation")

    result = _enforce_recepcao_sales_flow_pending(mother_decision, context)

    assert result.route_to == "apresentation"


# --- Testes de integração via decision_engine.decide() ---

def _compose_context(*, triggers_fired: str, sales_flow: dict) -> dict:
    return {
        "lead": {"id": 40, "user_id": 99, "category": "qualification", "triggers_fired": triggers_fired},
        "ai_profile": {
            "agent_mode": "consultivo",
            "template_key": "consultor_especialista",
            "sales_flow": sales_flow,
            # Campo obrigatório não preenchido: garante missing_fields não-vazio, para o
            # auto-promote de qualificação completa (Regra 1/3 anti-loop, ortogonal a este
            # guardrail) não mascarar a asserção sobre o prompt de p0/recepção.
            "qualification_fields": [{"key": "service_interest", "mode": "required"}],
        },
        "playbook": {},
        "metadata": {"inbound_message_text": "aceito, quero saber mais"},
        "history": [
            {"model": "outbound", "text": "Oi! Bem-vindo(a)! Você aceita receber novidades por aqui?"},
            {"model": "inbound", "text": "aceito, quero saber mais"},
        ],
    }


def _mock_mother_qualification(monkeypatch):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p, **_kwargs: (
            '{"route_to":"qualification","perceived_category":"qualification",'
            '"confidence":0.9,"reason":"teste"}'
        ),
    )


def _mock_child_result(monkeypatch):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: (
            '{"message_text":"Perfeito, vamos continuar.","confidence":0.8}'
        ),
    )


def test_p0_pending_trigger_forces_recepcao_prompt(monkeypatch):
    context = _compose_context(triggers_fired="[]", sales_flow=_sales_flow_p0_pending())
    _mock_mother_qualification(monkeypatch)
    _mock_child_result(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.decision_trace["prompt_function_used"] == "_build_child_prompt_recepcao"


def test_p0_trigger_already_fired_advances_normally(monkeypatch):
    context = _compose_context(triggers_fired='["kw0"]', sales_flow=_sales_flow_p0_pending())
    _mock_mother_qualification(monkeypatch)
    _mock_child_result(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.decision_trace["prompt_function_used"] == "_build_child_prompt_qualification"


def test_no_sequential_trigger_in_p0_behaves_like_baseline(monkeypatch):
    context = _compose_context(
        triggers_fired="[]",
        sales_flow={"enabled": True, "phases": [{"id": "p0", "blocks": []}]},
    )
    _mock_mother_qualification(monkeypatch)
    _mock_child_result(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.decision_trace["prompt_function_used"] == "_build_child_prompt_qualification"
