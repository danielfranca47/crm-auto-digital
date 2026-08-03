from app.services import decision_engine
from app.services.orchestrator_models import MotherDecision


def _mother() -> MotherDecision:
    return MotherDecision(
        route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="teste"
    )


def _context(*, calendar_busy_slots=None, timezone="America/Sao_Paulo"):
    return {
        "lead": {"id": 1, "category": "agendamento"},
        "ai_profile": {
            "agent_mode": "agenda",
            "template_key": "hybrid_scheduler",
            "timezone": timezone,
        },
        "playbook": {"template_key": "hybrid_scheduler"},
        "history": [],
        "calendar_busy_slots": calendar_busy_slots,
    }


def test_format_busy_slots_block_converts_to_profile_timezone():
    slots = [{"start_at": "2026-06-20T14:00:00+00:00", "end_at": "2026-06-20T15:00:00+00:00"}]
    text = decision_engine._format_busy_slots_block(slots, "America/Sao_Paulo")
    assert "20/06 11:00" in text
    assert "12:00" in text


def test_format_busy_slots_block_empty_returns_empty_string():
    assert decision_engine._format_busy_slots_block([], "America/Sao_Paulo") == ""
    assert decision_engine._format_busy_slots_block(None, "America/Sao_Paulo") == ""


def test_format_busy_slots_block_sorts_chronologically():
    slots = [
        {"start_at": "2026-06-22T10:00:00+00:00", "end_at": "2026-06-22T11:00:00+00:00"},
        {"start_at": "2026-06-21T10:00:00+00:00", "end_at": "2026-06-21T11:00:00+00:00"},
    ]
    text = decision_engine._format_busy_slots_block(slots, "UTC")
    assert text.index("21/06") < text.index("22/06")


def test_format_busy_slots_block_skips_malformed_entry():
    slots = [
        {"start_at": "not-a-date", "end_at": "also-not-a-date"},
        {"start_at": "2026-06-20T14:00:00+00:00", "end_at": "2026-06-20T15:00:00+00:00"},
    ]
    text = decision_engine._format_busy_slots_block(slots, "UTC")
    assert text.count("\n") == 0
    assert "20/06" in text


def test_format_busy_slots_block_invalid_timezone_falls_back_to_utc():
    slots = [{"start_at": "2026-06-20T14:00:00+00:00", "end_at": "2026-06-20T15:00:00+00:00"}]
    text = decision_engine._format_busy_slots_block(slots, "Not/A_Real_Timezone")
    assert "14:00" in text


def test_agendamento_prompt_includes_busy_block_when_present():
    context = _context(
        calendar_busy_slots=[{"start_at": "2026-06-20T14:00:00+00:00", "end_at": "2026-06-20T15:00:00+00:00"}]
    )
    prompt = decision_engine._build_child_prompt_agendamento(context, "amanha as 11h", _mother())
    assert "HORÁRIOS JÁ OCUPADOS" in prompt
    assert "20/06 11:00" in prompt


def test_agendamento_prompt_states_agenda_free_when_empty():
    context = _context(calendar_busy_slots=[])
    prompt = decision_engine._build_child_prompt_agendamento(context, "amanha as 11h", _mother())
    assert "nenhum compromisso encontrado" in prompt
    assert "agenda está livre no período consultado" in prompt


def test_agendamento_prompt_states_agenda_free_when_absent():
    context = _context(calendar_busy_slots=None)
    prompt = decision_engine._build_child_prompt_agendamento(context, "amanha as 11h", _mother())
    assert "nenhum compromisso encontrado" in prompt
    assert "agenda está livre no período consultado" in prompt
