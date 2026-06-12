"""Garante que a anexação de mídia na fase de apresentação passa a ser
controlada pelo campo ChildResult.media_keys_to_send (seleção contextual
feita pela LLM filha) em vez de anexar todas as mídias disponíveis."""

from app.services.decision_engine import compose_decision_output
from app.services.orchestrator_models import ChildResult, MotherDecision


def _context_with_media(text: str, knowledge_media: dict):
    return {
        "lead": {"category": "apresentation"},
        "ai_profile": {"agent_mode": "agenda", "appointment_mode": "commercial"},
        "playbook": {},
        "metadata": {"inbound_message_text": text},
        "history": [],
        "knowledge_media": knowledge_media,
        "lead_detected_language": "pt",
    }


_PRICING_MEDIA = {
    "service_pricing_table": [
        {"media_url": "https://cdn/pricing-1.png", "media_type": "image",
         "language": "pt", "send_order": 0},
        {"media_url": "https://cdn/pricing-2.png", "media_type": "image",
         "language": "pt", "send_order": 1},
    ],
    "payment_policy": [
        {"media_url": "https://cdn/payment.png", "media_type": "image",
         "language": "pt", "send_order": 0},
    ],
}


def _mother_apres():
    return MotherDecision(
        route_to="apresentation",
        perceived_category="apresentation",
        confidence=0.9,
        reason="lead perguntou sobre preço",
        next_action_hint="reply",
    )


def _child(media_keys=None):
    return ChildResult(
        message_text="Claro, segue o material.",
        did_complete_phase=False,
        recommended_next_category=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        media_keys_to_send=media_keys,
        confidence=0.8,
    )


def test_no_media_when_child_returns_empty_list():
    context = _context_with_media("oi, boa tarde", _PRICING_MEDIA)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=[]),
    )
    assert not decision.pre_send_media


def test_no_media_when_lead_asked_schedule_only():
    context = _context_with_media("qual o horário de atendimento?", _PRICING_MEDIA)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=[]),
    )
    assert not decision.pre_send_media


def test_pricing_media_only_when_child_selects_it():
    context = _context_with_media("quanto custa?", _PRICING_MEDIA)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=["service_pricing_table"]),
    )
    urls = [m.get("media_url") for m in (decision.pre_send_media or [])]
    assert urls == ["https://cdn/pricing-1.png", "https://cdn/pricing-2.png"]


def test_payment_media_only_when_child_selects_it():
    context = _context_with_media("aceita MB Way?", _PRICING_MEDIA)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=["payment_policy"]),
    )
    urls = [m.get("media_url") for m in (decision.pre_send_media or [])]
    assert urls == ["https://cdn/payment.png"]


def test_strict_fallback_when_child_omits_field():
    context = _context_with_media("qualquer coisa", _PRICING_MEDIA)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=None),
    )
    assert not decision.pre_send_media


def test_no_proactive_media_on_auto_promoted_qualification():
    """Primeiro turno pós auto-promoção qualification→apresentation não deve
    anexar service_pricing_table se o lead não pediu. A filha é responsável
    por declarar [] neste caso."""
    context = {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda", "appointment_mode": "commercial"},
        "playbook": {},
        "metadata": {"inbound_message_text": "tenho interesse"},
        "history": [],
        "knowledge_media": _PRICING_MEDIA,
        "lead_detected_language": "pt",
        "qualification_state": {
            "exists": True,
            "data_json": {
                "service_interest": "massagem",
                "urgency_level": "media",
                "decision_role": "owner",
                "main_constraint": "tempo",
                "availability_window": "terça",
                "budget_range": "50",
            },
            "attempts_json": {},
            "last_questioned_field": "budget_range",
        },
    }
    mother = MotherDecision(
        route_to="qualification",
        perceived_category="qualification",
        confidence=0.9,
        reason="qualificação completa",
    )
    decision = compose_decision_output(
        context=context,
        mother_decision=mother,
        child_result=_child(media_keys=[]),
    )
    assert not decision.pre_send_media


def test_decision_trace_reports_child_media_keys():
    context = _context_with_media("quanto custa?", _PRICING_MEDIA)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=["service_pricing_table"]),
    )
    trace = decision.decision_trace or {}
    assert trace.get("child_media_keys_to_send") == ["service_pricing_table"]


def test_unknown_key_from_child_is_ignored():
    context = _context_with_media("quanto custa?", _PRICING_MEDIA)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=["categoria_inexistente"]),
    )
    assert not decision.pre_send_media


def test_language_filter_still_applies():
    knowledge_media = {
        "service_pricing_table": [
            {"media_url": "https://cdn/en.png", "media_type": "image",
             "language": "en", "send_order": 0},
            {"media_url": "https://cdn/pt.png", "media_type": "image",
             "language": "pt", "send_order": 1},
        ],
    }
    context = _context_with_media("quanto custa?", knowledge_media)
    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child(media_keys=["service_pricing_table"]),
    )
    urls = [m.get("media_url") for m in (decision.pre_send_media or [])]
    assert urls == ["https://cdn/pt.png"]
