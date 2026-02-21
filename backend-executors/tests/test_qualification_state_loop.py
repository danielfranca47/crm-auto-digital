from app.services import decision_engine


def test_state_based_missing_fields_excludes_filled_field():
    context = {
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "qualification_state": {
            "exists": True,
            "data_json": {"decision_role": "owner", "service_interest": "botox"},
            "attempts_json": {},
            "last_questioned_field": "decision_role",
        },
    }

    mode_ctx = decision_engine._build_mode_contract_context(context)
    assert mode_ctx["missing_fields_source"] == "state"
    assert "decision_role" not in mode_ctx["missing_fields"]


def test_after_state_has_decision_role_missing_fields_do_not_include_it():
    context = {
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "eu decido"},
        "history": [],
        "qualification_state": {
            "exists": True,
            "data_json": {"decision_role": "owner"},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }
    mode_ctx = decision_engine._build_mode_contract_context(context)
    assert "decision_role" not in mode_ctx["missing_fields"]


def test_anti_loop_triggers_handoff_after_two_attempts(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "ok"},
        "history": [],
        "job": {"payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {},
            "attempts_json": {"service_interest": 1},
            "last_questioned_field": "service_interest",
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.field_extractor,
        "extract_fields_llm",
        lambda _ctx, _schema: {"extracted": {}, "confidence": {}, "evidence": {}, "raw": "{}"},
    )

    monkeypatch.setattr(
        decision_engine.crm_client,
        "increment_lead_qualification_attempt",
        lambda **kwargs: {
            "data_json": {},
            "attempts_json": {"service_interest": 2},
            "last_questioned_field": "service_interest",
        },
    )
    monkeypatch.setattr(
        decision_engine.crm_client,
        "upsert_lead_qualification_state",
        lambda **kwargs: {
            "data_json": {},
            "attempts_json": {"service_interest": 2},
            "last_questioned_field": "service_interest",
        },
    )

    decision = decision_engine.decide(context)
    assert decision.next_action == "handoff"
    assert "qualification_loop_handoff" in decision.reason
