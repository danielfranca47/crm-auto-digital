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


def test_rule3_keyword_override_removed_falls_back_to_anti_loop(monkeypatch):
    """O override por palavras-chave (legado) foi removido — mesmo com mensagem
    contendo keywords fortes de agendamento e template de agendamento, o lead em
    'apresentation' deve cair no anti-loop estrutural, não mais ser desviado
    directamente para 'pre-agendamento'/'agendamento' por pattern matching de texto.
    """
    context = {
        "lead": {"id": 11, "user_id": 99, "category": "apresentation"},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {"template_key": "hybrid_scheduler"},
        "metadata": {"inbound_message_text": "Posso marcar para amanhã às 15h?"},
        "history": [
            {"model": "outbound", "text": "Oi! Tudo bem?"},
            {"model": "inbound", "text": "Tudo sim"},
        ],
        "job": {"payload": {"lead_id": 11, "user_id": 99}},
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


def test_ask_qualification_message_is_deterministic_for_current_field(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "job": {"payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {"service_interest": "botox"},
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
            "data_json": {"service_interest": "botox"},
            "attempts_json": {},
            "last_questioned_field": kwargs.get("patch", {}).get("last_questioned_field"),
        },
    )
    monkeypatch.setattr(
        decision_engine.crm_client,
        "increment_lead_qualification_attempt",
        lambda **kwargs: {
            "exists": True,
            "data_json": {"service_interest": "botox"},
            "attempts_json": {kwargs.get("field"): 1},
            "last_questioned_field": kwargs.get("field"),
        },
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"pergunta errada de outro campo","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert decision.next_action == "ask_qualification"
    assert trace.get("current_field") == "urgency"
    assert trace.get("question_field_used") == "urgency"
    assert decision.message_text == decision.message_text




def test_field_mismatch_repair_uses_second_attempt(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "job": {"id": 555, "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {"service_interest": "botox"},
            "attempts_json": {},
            "last_questioned_field": None,
            "asked_questions_json": [],
            "last_question_text": "",
        },
    }
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", lambda _p: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}')
    monkeypatch.setattr(decision_engine.field_extractor, "extract_fields_llm", lambda _c, _s: {"extracted": {}, "confidence": {}, "evidence": {}, "raw": "{}"})

    calls = {"n": 0}
    def _child(_route, _prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"question_text":"qual seu serviço?","field":"service_interest","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.7}'
        return '{"question_text":"qual o seu nível de urgência agora?","field":"urgency","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'
    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", _child)
    monkeypatch.setattr(decision_engine.crm_client, "upsert_lead_qualification_state", lambda **kwargs: context["qualification_state"])
    monkeypatch.setattr(decision_engine.crm_client, "increment_lead_qualification_attempt", lambda **kwargs: context["qualification_state"])

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}
    assert decision.next_action == "ask_qualification"
    assert trace.get("current_field") == "urgency"
    assert trace.get("question_field_used") == "urgency"
    assert decision.message_text == "qual o seu nível de urgência agora?"


def test_anti_repetition_triggers_retry(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "job": {"id": 777, "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {"service_interest": "botox"},
            "attempts_json": {},
            "last_questioned_field": "urgency",
            "asked_questions_json": [{"field": "urgency", "question_text": "qual o seu nível de urgência agora?", "created_at": "2026-01-01T00:00:00", "attempt": 1}],
            "last_question_text": "qual o seu nível de urgência agora?",
        },
    }
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", lambda _p: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}')
    monkeypatch.setattr(decision_engine.field_extractor, "extract_fields_llm", lambda _c, _s: {"extracted": {}, "confidence": {}, "evidence": {}, "raw": "{}"})

    calls={"n":0}
    def _child(_route, _prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            return '{"question_text":"qual o seu nível de urgência agora?","field":"urgency","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'
        return '{"question_text":"em quanto tempo você quer começar?","field":"urgency","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'
    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", _child)
    monkeypatch.setattr(decision_engine.crm_client, "upsert_lead_qualification_state", lambda **kwargs: context["qualification_state"])
    monkeypatch.setattr(decision_engine.crm_client, "increment_lead_qualification_attempt", lambda **kwargs: context["qualification_state"])

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}
    assert decision.next_action == "ask_qualification"
    assert trace.get("question_field_used") == "urgency"
    assert decision.message_text == "em quanto tempo você quer começar?"


def test_current_field_recalculated_when_extractor_fills_previous_field(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "eu decido"},
        "history": [],
        "job": {"id": 888, "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {"exists": True, "data_json": {"service_interest": "botox"}, "attempts_json": {}, "last_questioned_field": None},
    }
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", lambda _p: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}')
    monkeypatch.setattr(decision_engine.field_extractor, "extract_fields_llm", lambda _c, _s: {"extracted": {"urgency": "alta"}, "confidence": {}, "evidence": {}, "raw": "{}"})
    monkeypatch.setattr(decision_engine.crm_client, "upsert_lead_qualification_state", lambda **kwargs: {"exists": True, "data_json": {"service_interest": "botox", "urgency": "alta"}, "attempts_json": {}, "last_questioned_field": kwargs.get("patch",{}).get("last_questioned_field")})
    monkeypatch.setattr(decision_engine.crm_client, "increment_lead_qualification_attempt", lambda **kwargs: {"exists": True, "data_json": {"service_interest": "botox", "urgency": "alta"}, "attempts_json": {kwargs.get("field"): 1}, "last_questioned_field": kwargs.get("field")})
    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", lambda _r, _p: '{"question_text":"você decide sozinho?","field":"decision_role","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}')

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}
    assert trace.get("current_field") == "decision_role"
    assert trace.get("question_field_used") == "decision_role"


def test_fallback_safe_when_repair_fails_twice(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "job": {"id": 999, "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {"exists": True, "data_json": {"service_interest": "botox"}, "attempts_json": {}, "last_questioned_field": None},
    }
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", lambda _p: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}')
    monkeypatch.setattr(decision_engine.field_extractor, "extract_fields_llm", lambda _c, _s: {"extracted": {}, "confidence": {}, "evidence": {}, "raw": "{}"})
    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", lambda _r, _p: '{"question_text":"texto ruim","field":"service_interest","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.4}')
    monkeypatch.setattr(decision_engine.crm_client, "upsert_lead_qualification_state", lambda **kwargs: context["qualification_state"])
    monkeypatch.setattr(decision_engine.crm_client, "increment_lead_qualification_attempt", lambda **kwargs: context["qualification_state"])

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}
    assert decision.next_action == "ask_qualification"
    assert trace.get("qualification_validation_status") == "fallback"
    assert decision.message_text.startswith("Pode me confirmar:")



def test_auto_promote_never_uses_qualification_fallback_message(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {"agent_mode": "consultivo"},
        "playbook": {},
        "metadata": {"inbound_message_text": "300 reais"},
        "history": [],
        "job": {"id": 200, "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {
                "service_interest": "botox",
                "urgency": "alta",
                "decision_role": "owner",
                "constraints": "sem restrição",
                "availability_window": "amanhã 10h",
                "budget_or_price_acceptance": "300 reais",
            },
            "attempts_json": {},
            "last_questioned_field": "budget_or_price_acceptance",
            "asked_questions_json": [],
            "last_question_text": "",
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )

    seen = {"route": None}

    def _child(route, _prompt):
        seen["route"] = route
        return '{"message_text":"Perfeito, vamos para a próxima etapa da apresentação.","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", _child)

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert seen["route"] == "apresentation"
    assert trace.get("effective_route_to") == "apresentation"
    assert decision.next_action == "reply"
    assert not decision.message_text.startswith("Pode me confirmar:")


def test_optional_custom_field_is_captured_but_does_not_affect_missing_fields(monkeypatch):
    """Fase 1 de qualificacao-flexivel-score-generalizado.md: campos `mode="optional"`
    passam a ser capturados pelo extractor (fields_schema deixa de se limitar a
    required_fields), mas continuam fora de missing_fields/current_field/anti-loop —
    só required_fields determina o que bloqueia o avanço."""
    captured_patch = {}

    def _fake_upsert(**kwargs):
        captured_patch.update(kwargs.get("patch") or {})
        return {
            "exists": True,
            "data_json": {"custom_uso_do_produto": "uso diário"},
            "attempts_json": {},
            "last_questioned_field": "service_interest",
        }

    incremented = {}

    def _fake_increment(**kwargs):
        incremented["field"] = kwargs.get("field")
        return {
            "exists": True,
            "data_json": {"custom_uso_do_produto": "uso diário"},
            "attempts_json": {kwargs.get("field"): 1},
            "last_questioned_field": kwargs.get("field"),
        }

    context = {
        "lead": {"id": 10, "user_id": 99, "category": "qualification"},
        "ai_profile": {
            "agent_mode": "consultivo",
            "qualification_fields": [
                {"key": "service_interest", "mode": "required"},
                {"key": "custom_uso_do_produto", "mode": "optional"},
            ],
        },
        "playbook": {},
        "metadata": {"inbound_message_text": "uso todo dia"},
        # outbound_count>=1 é necessário para _enforce_greeting_first não forçar recepcao
        # neste teste (a saudação já foi feita — cenário é meio de conversa).
        "history": [
            {"model": "outbound", "body": "Oi! Me conta o que você busca?"},
            {"model": "inbound", "body": "quero saber sobre o produto"},
        ],
        "job": {"id": 777, "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": "service_interest",
        },
    }
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p: '{"route_to":"qualification","perceived_category":"qualification","confidence":0.9,"reason":"teste"}',
    )
    monkeypatch.setattr(
        decision_engine.field_extractor,
        "extract_fields_llm",
        lambda _c, _s: {"extracted": {"custom_uso_do_produto": "uso diário"}, "confidence": {}, "evidence": {}, "raw": "{}"},
    )
    monkeypatch.setattr(decision_engine.crm_client, "upsert_lead_qualification_state", _fake_upsert)
    monkeypatch.setattr(decision_engine.crm_client, "increment_lead_qualification_attempt", _fake_increment)
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _r, _p: '{"question_text":"O que você busca?","field":"service_interest","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision_engine.decide(context)

    # Capturado e persistido mesmo sendo opcional (antes da Fase 1, era descartado).
    assert captured_patch.get("data_json", {}).get("custom_uso_do_produto") == "uso diário"

    # Mas não conta como progresso no campo obrigatório pendente — o anti-loop
    # continua avaliando só required_fields, então o contador de tentativas avança
    # normalmente para "service_interest".
    assert incremented.get("field") == "service_interest"
