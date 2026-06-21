from app.services.decision_engine import _build_mother_prompt


def _context(template_key: str = "hybrid_scheduler"):
    return {
        "lead": {"id": 1, "category": "qualification"},
        "ai_profile": {"agent_mode": "agenda", "template_key": template_key},
        "playbook": {"template_key": template_key},
        "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        "history": [],
    }


def test_mother_prompt_includes_day_hour_checklist_for_compound_greeting():
    prompt = _build_mother_prompt(_context(), "Oi, gostaria de agendar uma sessão para amanhã às 16h")

    assert "REGRA CRÍTICA — dia+hora específicos NUNCA vão para \"pre-agendamento\"" in prompt
    assert "Ela contém um DIA" in prompt
    assert "Ela contém uma HORA" in prompt
    assert "ERRADO seria escolher" in prompt
