from app.contracts.qualification_contract import compute_missing_fields, required_fields_for_mode
from app.services.decision_engine import _build_mode_contract_context, _normalize_agent_mode


def test_compute_missing_fields_consultivo_next_step_satisfies_availability():
    extracted = {
        "service_interest": True,
        "urgency": True,
        "decision_role": True,
        "constraints": True,
        "next_step": True,
        "next_step_with_time": True,
        "budget_or_price_acceptance": True,
    }
    assert compute_missing_fields("consultivo", extracted) == []


def test_compute_missing_fields_consultivo_next_step_without_time_still_requires_availability():
    extracted = {
        "service_interest": True,
        "urgency": True,
        "decision_role": True,
        "constraints": True,
        "next_step": True,
        "budget_or_price_acceptance": True,
    }
    missing = compute_missing_fields("consultivo", extracted)
    assert "availability_window" in missing


def test_compute_missing_fields_agenda_requires_booking_fields():
    extracted = {
        "service_interest": True,
    }
    missing = compute_missing_fields("agenda", extracted)
    assert "availability_window" in missing
    assert "location_preference" in missing
    assert "price_acceptance" in missing


def test_compute_missing_fields_direto_minimal():
    extracted = {
        "service_interest": True,
        "availability_window": True,
    }
    missing = compute_missing_fields("direto", extracted)
    assert missing == ["price_acceptance"]


def test_closer_legacy_normalizes_to_direto_and_required_fields_follow_mode():
    context = {
        "ai_profile": {"agent_mode": "closer"},
        "playbook": {},
        "metadata": {},
    }
    assert _normalize_agent_mode(context) == "direto"
    mode_ctx = _build_mode_contract_context(context)
    assert mode_ctx["required_fields"] == required_fields_for_mode("direto")
