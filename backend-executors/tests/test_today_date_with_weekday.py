from datetime import datetime, timedelta

from app.services.decision_engine import (
    _WEEKDAY_NAMES_PT,
    _build_child_prompt_agendamento,
    _build_child_prompt_apresentation,
    _build_child_prompt_pre_agendamento,
    _calendar_lookup_table_pt,
)
from app.services.orchestrator_models import MotherDecision

_NO_SELF_CALC_MSG = "NUNCA calcule a data ou o dia da semana por conta própria"


def test_weekday_names_table_matches_known_dates():
    assert _WEEKDAY_NAMES_PT[datetime(2026, 6, 21).weekday()] == "domingo"
    assert _WEEKDAY_NAMES_PT[datetime(2026, 6, 22).weekday()] == "segunda-feira"
    assert _WEEKDAY_NAMES_PT[datetime(2026, 6, 25).weekday()] == "quinta-feira"
    assert _WEEKDAY_NAMES_PT[datetime(2026, 6, 27).weekday()] == "sábado"


def test_calendar_lookup_table_has_today_marker_and_correct_sequence():
    table = _calendar_lookup_table_pt(days_ahead=14)
    lines = table.split("\n")
    assert len(lines) == 15
    assert lines[0].endswith("[hoje]")

    today = datetime.utcnow()
    for offset, line in enumerate(lines):
        expected_day = today + timedelta(days=offset)
        expected_date = expected_day.strftime("%Y-%m-%d")
        expected_weekday = _WEEKDAY_NAMES_PT[expected_day.weekday()]
        assert line.startswith(f"{expected_date} ({expected_weekday})")


def _base_context(template_key: str = "hybrid_scheduler"):
    return {
        "lead": {"id": 1, "category": "agendamento"},
        "ai_profile": {"agent_mode": "agenda", "template_key": template_key, "timezone": "America/Sao_Paulo"},
        "playbook": {"template_key": template_key},
        "metadata": {"inbound_message_text": "Pode ser quinta-feira?"},
        "history": [],
    }


def test_agendamento_prompt_uses_calendar_table_not_self_calc():
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    prompt = _build_child_prompt_agendamento(_base_context(), "Pode ser quinta-feira?", mother)
    assert "tabela_de_dias" in prompt
    assert _NO_SELF_CALC_MSG in prompt


def test_apresentation_prompt_uses_calendar_table_not_self_calc():
    mother = MotherDecision(route_to="apresentation", perceived_category="apresentation", confidence=0.9, reason="ok")
    prompt = _build_child_prompt_apresentation(_base_context(), "Pode ser quinta-feira?", mother)
    assert "tabela_de_dias" in prompt
    assert _NO_SELF_CALC_MSG in prompt


def test_pre_agendamento_prompt_uses_calendar_table_not_self_calc():
    mother = MotherDecision(route_to="pre-agendamento", perceived_category="pre-agendamento", confidence=0.9, reason="ok")
    prompt = _build_child_prompt_pre_agendamento(_base_context(), "Acho que sábado", mother)
    assert "tabela_de_dias" in prompt
    assert _NO_SELF_CALC_MSG in prompt
