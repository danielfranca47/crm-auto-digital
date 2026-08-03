from app.services.decision_engine import _build_child_prompt_agendamento
from app.services.orchestrator_models import MotherDecision


def _base_context(scheduling_offer_style: str | None = None):
    ai_profile = {
        "agent_mode": "agenda",
        "template_key": "hybrid_scheduler",
        "timezone": "America/Sao_Paulo",
        "availability_schedule": '{"mon":"09:00-18:00","tue":"09:00-18:00"}',
    }
    if scheduling_offer_style is not None:
        ai_profile["scheduling_offer_style"] = scheduling_offer_style
    return {
        "lead": {"id": 1, "category": "agendamento"},
        "ai_profile": ai_profile,
        "playbook": {"template_key": "hybrid_scheduler"},
        "metadata": {"inbound_message_text": "Pode ser às 9h"},
        "history": [],
    }


def _mother():
    return MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")


def test_default_style_instructs_always_offering_alternatives():
    prompt = _build_child_prompt_agendamento(_base_context(), "Pode ser às 9h então", _mother())
    assert "proponha 2-3 horários concretos" in prompt
    assert "confirme esse horário" not in prompt


def test_offer_alternatives_explicit_instructs_always_offering_alternatives():
    prompt = _build_child_prompt_agendamento(_base_context("offer_alternatives"), "Pode ser às 9h então", _mother())
    assert "proponha 2-3 horários concretos" in prompt


def test_confirm_exact_instructs_direct_confirmation():
    prompt = _build_child_prompt_agendamento(_base_context("confirm_exact"), "Pode ser às 9h então", _mother())
    assert "REGRA CRÍTICA — CONFIRMAÇÃO DIRETA" in prompt
    assert "NÃO INVENTE conflito que não está listado" in prompt
    assert "confirme-o directamente nesta resposta" in prompt


def test_confirm_exact_with_empty_calendar_states_agenda_is_free():
    context = _base_context("confirm_exact")
    context["calendar_busy_slots"] = []
    prompt = _build_child_prompt_agendamento(context, "Pode ser às 9h então", _mother())
    assert "nenhum compromisso encontrado" in prompt
    assert "a agenda está livre no período consultado" in prompt
