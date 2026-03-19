from app.services import decision_engine


def test_mother_route_forced_to_qualification_when_missing_fields(monkeypatch):
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda"},
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
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"apresentation","perceived_category":"qualification","confidence":0.9,"reason":"vamos avançar"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"field":"availability_window","question_text":"Qual melhor horário para você?","message_text":"Qual melhor horário para você?","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("mother_route_to") == "qualification"
    assert trace.get("effective_route_to") == "qualification"
    assert decision.next_action == "ask_qualification"
    assert "qualification_incomplete_forced_route" in (decision.reason or "")


def test_mother_route_kept_when_qualification_is_complete(monkeypatch):
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {},
        "metadata": {"inbound_message_text": "podemos agendar"},
        "history": [],
        "qualification_state": {
            "exists": True,
            "data_json": {
                "service_interest": "botox",
                "availability_window": "amanhã 10h",
                "location_preference": "presencial",
                "price_acceptance": "yes",
            },
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"apresentation","perceived_category":"qualification","confidence":0.9,"reason":"agendamento"}',
    )
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt: '{"message_text":"Perfeito, vamos agendar.","did_complete_phase":false,"recommended_next_category":"apresentation","outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}',
    )

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert trace.get("mother_route_to") == "apresentation"
    assert trace.get("effective_route_to") == "apresentation"
    assert decision.next_action == "reply"
