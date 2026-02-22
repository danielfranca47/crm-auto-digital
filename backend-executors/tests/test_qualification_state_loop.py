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


def test_with_state_exists_infer_extracted_fields_is_not_called(monkeypatch):
    context = {
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "qualification_state": {
            "exists": True,
            "data_json": {"service_interest": "botox"},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    monkeypatch.setattr(
        decision_engine,
        "infer_extracted_fields",
        lambda _ctx: (_ for _ in ()).throw(RuntimeError("should not be called")),
    )
    mode_ctx = decision_engine._build_mode_contract_context(context)
    assert mode_ctx["missing_fields_source"] == "state"


def test_state_absent_and_flag_off_returns_state_unavailable_without_heuristic(monkeypatch):
    context = {
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "qualification_state": {"exists": False},
    }
    monkeypatch.setattr(decision_engine.settings, "qualification_heuristic_fallback", 0)
    monkeypatch.setattr(
        decision_engine,
        "infer_extracted_fields",
        lambda _ctx: (_ for _ in ()).throw(RuntimeError("heuristic should be disabled")),
    )

    mode_ctx = decision_engine._build_mode_contract_context(context)
    assert mode_ctx["missing_fields_source"] == "state_unavailable"
    assert mode_ctx["missing_fields"] == mode_ctx["required_fields"]


def test_state_absent_extractor_upsert_then_final_source_is_state(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "eu decido"},
        "history": [],
        "job": {"payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {"exists": False},
    }
    monkeypatch.setattr(decision_engine.settings, "qualification_heuristic_fallback", 1)
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.field_extractor,
        "extract_fields_llm",
        lambda _ctx, _schema: {
            "extracted": {"decision_role": "owner"},
            "confidence": {"decision_role": 0.91},
            "evidence": {"decision_role": "eu decido"},
            "raw": "{}",
        },
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"ok","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    monkeypatch.setattr(
        decision_engine.crm_client,
        "upsert_lead_qualification_state",
        lambda **kwargs: {
            "exists": True,
            "data_json": {"decision_role": "owner"},
            "attempts_json": {},
            "last_questioned_field": kwargs.get("patch", {}).get("last_questioned_field"),
        },
    )
    monkeypatch.setattr(
        decision_engine.crm_client,
        "increment_lead_qualification_attempt",
        lambda **kwargs: {
            "exists": True,
            "data_json": {"decision_role": "owner"},
            "attempts_json": {kwargs.get("field"): 1},
            "last_questioned_field": kwargs.get("field"),
        },
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}
    assert trace.get("qualification_missing_fields_source") == "state"
    assert "decision_role" not in (trace.get("missing_fields") or [])


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


def test_t1_missing_fields_empty_never_ask_qualification(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "ok"},
        "history": [],
        "job": {"payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {
                "decision_role": "owner",
                "service_interest": "botox",
                "urgency": "alta",
                "constraints": "sem restrições",
                "availability_window": "amanhã 10h",
                "budget_or_price_acceptance": "ok",
            },
            "attempts_json": {},
            "last_questioned_field": "urgency_level",
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"vamos agendar a apresentação?","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert decision.next_action != "ask_qualification"
    assert trace.get("effective_route_to") == "apresentation"
    assert trace.get("qualification_auto_promoted") is True
    assert trace.get("anti_loop_rule1_applied") is True


def test_t2_filled_field_not_selected_as_current_field(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "job": {"payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {
                "decision_role": "owner",
            },
            "attempts_json": {},
            "last_questioned_field": None,
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
        "upsert_lead_qualification_state",
        lambda **kwargs: {
            "exists": True,
            "data_json": {"decision_role": "owner"},
            "attempts_json": {},
            "last_questioned_field": kwargs.get("patch", {}).get("last_questioned_field"),
        },
    )
    monkeypatch.setattr(
        decision_engine.crm_client,
        "increment_lead_qualification_attempt",
        lambda **kwargs: {
            "exists": True,
            "data_json": {"decision_role": "owner"},
            "attempts_json": {kwargs.get("field"): 1},
            "last_questioned_field": kwargs.get("field"),
        },
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"qual seu nível de urgência?","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert "decision_role" not in (trace.get("missing_fields") or [])
    assert trace.get("current_field") != "decision_role"
    assert "decision_role" in (trace.get("filled_fields") or [])


def test_t3_rule3_blocks_return_to_qualification_when_already_apresentation(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "apresentation"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "ok"},
        "history": [],
        "job": {"payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    seen = {"route": None}

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )

    def _fake_child(route, _prompt):
        seen["route"] = route
        return '{"message_text":"vamos seguir com apresentação","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", _fake_child)

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert seen["route"] == "apresentation"
    assert trace.get("anti_loop_rule3_applied") is True
    assert trace.get("effective_route_to") == "apresentation"
    assert decision.next_action == "reply"
    assert decision.message_text
