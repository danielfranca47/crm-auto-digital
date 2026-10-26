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
    assert lines[1].endswith("[amanhã]")
    assert lines[2].endswith("[depois de amanhã]")

    today = datetime.utcnow()
    for offset, line in enumerate(lines):
        expected_day = today + timedelta(days=offset)
        expected_weekday = _WEEKDAY_NAMES_PT[expected_day.weekday()]
        assert line.startswith(
            f"{expected_weekday}, {expected_day.strftime('%d/%m')} → {expected_day.strftime('%Y-%m-%d')}"
        )


def test_calendar_lookup_table_uses_profile_timezone(monkeypatch):
    from datetime import date

    from app.services import meeting_date_guard

    monkeypatch.setattr(meeting_date_guard, "local_today", lambda tz, now=None: date(2026, 10, 25))
    lines = _calendar_lookup_table_pt(days_ahead=5, tz_name="Europe/Lisbon").split("\n")
    assert lines[0] == "domingo, 25/10 → 2026-10-25 [hoje]"
    assert lines[5] == "sexta-feira, 30/10 → 2026-10-30"


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


def test_agendamento_prompt_has_already_booked_block_only_when_meeting_scheduled():
    booked = MotherDecision(
        route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok",
        signals={"meeting_scheduled": True},
    )
    not_booked = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    assert "MARCAÇÃO JÁ GRAVADA NESTE TURNO" in _build_child_prompt_agendamento(_base_context(), "Pode confirmar", booked)
    assert "MARCAÇÃO JÁ GRAVADA NESTE TURNO" not in _build_child_prompt_agendamento(_base_context(), "Sexta?", not_booked)


def test_no_already_booked_block_on_phase_entry():
    # Entrada na fase: o meeting_scheduler adia a criação (gate M3) — anunciar "já marcado"
    # deixava o lead com uma confirmação de uma marcação que não existe.
    context = _base_context()
    context["lead"]["category"] = "pre-agendamento"
    booked = MotherDecision(
        route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok",
        signals={"meeting_scheduled": True},
    )
    assert "MARCAÇÃO JÁ GRAVADA NESTE TURNO" not in _build_child_prompt_agendamento(context, "Amanhã às 11h", booked)


def test_apresentation_sales_variant_gets_already_booked_block_when_meeting_scheduled():
    context = _base_context()
    context["lead"]["category"] = "apresentation"
    context["ai_profile"]["presentation_variant"] = "sales"
    booked = MotherDecision(
        route_to="apresentation", perceived_category="apresentation", confidence=0.9, reason="ok",
        signals={"meeting_scheduled": True},
    )
    prompt = _build_child_prompt_apresentation(context, "Sim, pode confirmar", booked)
    assert "MARCAÇÃO JÁ GRAVADA NESTE TURNO" in prompt
    # no fim do prompt, depois da regra sales "peça confirmação" e das instruções da conta
    assert prompt.rindex("MARCAÇÃO JÁ GRAVADA NESTE TURNO") > prompt.rindex("UM TURNO = UMA AÇÃO")


def test_pre_agendamento_prompt_uses_calendar_table_not_self_calc():
    mother = MotherDecision(route_to="pre-agendamento", perceived_category="pre-agendamento", confidence=0.9, reason="ok")
    prompt = _build_child_prompt_pre_agendamento(_base_context(), "Acho que sábado", mother)
    assert "tabela_de_dias" in prompt
    assert _NO_SELF_CALC_MSG in prompt
