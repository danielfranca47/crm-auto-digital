from datetime import datetime, timezone

import pytest

from app.services import decision_engine, meeting_date_guard
from app.services.decision_engine import (
    _build_child_prompt_apresentation,
    _build_child_prompt_recepcao,
    _local_greeting,
    _local_time_fact_line,
)
from app.services.orchestrator_models import MotherDecision

# 26/10/2026 é segunda-feira; Lisboa está em UTC+0 (horário de inverno desde 25/10).
_MORNING_UTC = datetime(2026, 10, 26, 10, 55, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "now_utc, tz_name, expected",
    [
        (_MORNING_UTC, "Europe/Lisbon", "Bom dia"),
        (datetime(2026, 10, 26, 15, 0, tzinfo=timezone.utc), "Europe/Lisbon", "Boa tarde"),
        (datetime(2026, 10, 26, 21, 0, tzinfo=timezone.utc), "Europe/Lisbon", "Boa noite"),
        (_MORNING_UTC, "America/Sao_Paulo", "Bom dia"),  # 07h55 locais
        (datetime(2026, 10, 26, 4, 59, tzinfo=timezone.utc), "Europe/Lisbon", "Boa noite"),
        (datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc), "Europe/Lisbon", "Boa tarde"),
        (datetime(2026, 10, 26, 20, 0, tzinfo=timezone.utc), "Europe/Lisbon", "Boa noite"),
        (_MORNING_UTC, "Fuso/Invalido", "Bom dia"),  # fuso inválido → UTC
        (_MORNING_UTC, None, "Bom dia"),
    ],
)
def test_local_greeting_by_timezone(now_utc, tz_name, expected):
    assert _local_greeting({"timezone": tz_name}, now_utc) == expected


def test_fact_line_has_weekday_date_and_time():
    line = _local_time_fact_line({"timezone": "America/Sao_Paulo"}, _MORNING_UTC)
    assert "segunda-feira, 26/10, 07h55" in line
    assert "manhã" in line
    assert '"Bom dia"' in line


@pytest.fixture
def morning_clock(monkeypatch):
    real = meeting_date_guard.local_now
    monkeypatch.setattr(
        decision_engine.meeting_date_guard,
        "local_now",
        lambda tz_name, now_utc=None: real(tz_name, now_utc or _MORNING_UTC),
    )


def _context():
    return {
        "lead": {"id": 1, "category": None},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler", "timezone": "Europe/Lisbon"},
        "playbook": {},
        "metadata": {},
        "history": [],
    }


def test_recepcao_prompt_gets_local_time_and_greeting_example(morning_clock):
    prompt = _build_child_prompt_recepcao(
        _context(),
        "Gostaria de mais informações sobre as Massagens",
        MotherDecision(route_to="recepcao", confidence=0.9, reason="saudação"),
    )
    assert "AGORA (hora local do negócio): segunda-feira, 26/10, 10h55" in prompt
    assert 'message_text: "Bom dia! Obrigado pelo contato."' in prompt


def test_apresentation_greeting_header_uses_local_period(morning_clock):
    prompt = _build_child_prompt_apresentation(
        _context(),
        "Olá",
        MotherDecision(route_to="apresentation", confidence=0.9, reason="saudação", next_action_hint="greet"),
    )
    assert "AGORA (hora local do negócio)" in prompt
    assert "'Bom dia!'" in prompt
    assert "Boa noite!" not in prompt
