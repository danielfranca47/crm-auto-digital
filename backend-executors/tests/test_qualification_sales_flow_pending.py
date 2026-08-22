"""Fase 1 de sales-flow-fase-pendente-guardrail.md — gatilhos sequenciais pendentes em
p1 (Qualificação) bloqueiam os 3 pontos de auto-promoção para apresentação, do mesmo jeito
que _enforce_apresentation_sales_flow_pending já faz para p2. Ver decision_engine.py:
_phase_pending_sequential_triggers() e os 3 gates em decide()/compose_decision_output()."""
from app.services import decision_engine


def _sales_flow_p1_pending(fired: bool = False) -> dict:
    return {
        "enabled": True,
        "phases": [
            {
                "id": "p1",
                "blocks": [
                    {
                        "id": "kw1",
                        "typeId": "kw_trigger",
                        "keywords": "novidade",
                        "fire_once": True,
                    }
                ],
            }
        ],
    }


def _context(*, category: str, triggers_fired: str, sales_flow: dict, mother_route_to: str = "qualification") -> dict:
    return {
        "lead": {"id": 10, "user_id": 99, "category": category, "triggers_fired": triggers_fired},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi, tudo bem?"},
        # entrada com um "outbound" prévio evita que _enforce_greeting_first force recepcao
        # e mascare o guardrail sob teste.
        "history": [{"model": "outbound", "text": "Oi! Seja bem-vindo."}],
        "job": {"id": 1, "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }


def test_p1_pending_trigger_blocks_qualification_auto_promote(monkeypatch):
    context = _context(
        category="qualification",
        triggers_fired="[]",
        sales_flow=_sales_flow_p1_pending(),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p, **_kwargs: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: '{"message_text":"Que bom te ver por aqui!","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )
    monkeypatch.setattr(
        decision_engine.field_extractor,
        "extract_fields_llm",
        lambda _c, _s: {"extracted": {}, "confidence": {}, "evidence": {}, "raw": "{}"},
    )
    monkeypatch.setattr(decision_engine.crm_client, "upsert_lead_qualification_state", lambda **kwargs: context["qualification_state"])
    monkeypatch.setattr(decision_engine.crm_client, "increment_lead_qualification_attempt", lambda **kwargs: context["qualification_state"])

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("effective_route_to") == "qualification"
    assert trace.get("qualification_auto_promoted") is not True


def test_p1_trigger_already_fired_promotes_normally(monkeypatch):
    context = _context(
        category="qualification",
        triggers_fired='["kw1"]',
        sales_flow=_sales_flow_p1_pending(),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p, **_kwargs: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: '{"message_text":"Vamos falar dos serviços.","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("effective_route_to") == "apresentation"
    assert trace.get("qualification_auto_promoted") is True


def test_no_sequential_trigger_in_p1_behaves_like_baseline(monkeypatch):
    context = _context(
        category="qualification",
        triggers_fired="[]",
        sales_flow={"enabled": True, "phases": [{"id": "p1", "blocks": []}]},
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p, **_kwargs: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: '{"message_text":"Vamos falar dos serviços.","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("effective_route_to") == "apresentation"
    assert trace.get("qualification_auto_promoted") is True


def test_is_upper_stage_escape_valve_preserved_with_p1_pending(monkeypatch):
    context = _context(
        category="apresentation",
        triggers_fired="[]",
        sales_flow=_sales_flow_p1_pending(),
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p, **_kwargs: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: '{"message_text":"Vamos seguir com a apresentação.","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("effective_route_to") == "apresentation"
