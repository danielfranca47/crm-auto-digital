"""Garante que o conteúdo comercial do hybrid_scheduler (modo commercial) —
tabela de preços, objeções, diferenciais, promoção, pagamento, FAQ de
pré-compromisso — continua disponível à Filha de apresentação sob demanda em
qualquer turno, mesmo fora do turno único de aquecimento (`_auto_promoted_from_qual`).

Ver docs/architecture/pipeline-phases.md, secção "Estágio de aquecimento e
appointment_mode" — o aquecimento proativo não repete, mas o conteúdo (com
instrução "usar APENAS se pedido") continua acessível, mesmo padrão já usado
para objections_faq/service_faq."""

from app.services.decision_engine import _build_child_prompt_apresentation
from app.services.orchestrator_models import MotherDecision

_PRICING_TEXT = "Plano Escritório - R$ 1.297/mês: qualificação de leads, até 1.000 conversas/mês."


def _context(appointment_mode="commercial", template_key="hybrid_scheduler"):
    return {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {
            "agent_mode": "agenda",
            "template_key": template_key,
            "appointment_mode": appointment_mode,
        },
        "playbook": {"template_key": template_key},
        "metadata": {"inbound_message_text": "quanto custa o plano Escritório?"},
        "history": [
            {"model": "outbound", "text": "Oi! Seja bem-vindo(a)."},
            {"model": "inbound", "text": "quero saber mais"},
        ],
        "knowledge_items": {"service_pricing_table": _PRICING_TEXT},
        "knowledge_media": {},
        "lead_detected_language": "pt",
    }


def _mother_not_promoted():
    """Turno posterior ao de transição: route_to já é apresentation diretamente."""
    return MotherDecision(
        route_to="apresentation",
        perceived_category="apresentation",
        confidence=0.9,
        reason="lead perguntou preço de novo",
    )


def test_pricing_available_on_demand_outside_warming_turn():
    context = _context()
    prompt = _build_child_prompt_apresentation(
        context, context["metadata"]["inbound_message_text"], _mother_not_promoted()
    )
    assert _PRICING_TEXT in prompt
    assert "APENAS se o lead pedir preço" in prompt


def test_pricing_not_leaked_without_commercial_appointment_mode():
    context = _context(appointment_mode="exploratory")
    prompt = _build_child_prompt_apresentation(
        context, context["metadata"]["inbound_message_text"], _mother_not_promoted()
    )
    assert _PRICING_TEXT not in prompt


def test_pricing_not_leaked_for_other_templates():
    context = _context(template_key="sdr_padrao")
    prompt = _build_child_prompt_apresentation(
        context, context["metadata"]["inbound_message_text"], _mother_not_promoted()
    )
    assert _PRICING_TEXT not in prompt


def test_warming_turn_still_uses_full_commercial_injection():
    """Turno único de transição (qualification -> apresentation, sem missing_fields)
    continua produzindo o bloco MODO COMERCIAL completo, como antes desta mudança."""
    context = _context()
    context["ai_profile"]["qualification_required_fields"] = []
    mother_promoted = MotherDecision(
        route_to="qualification",
        perceived_category="qualification",
        confidence=0.9,
        reason="qualificação completa",
    )
    prompt = _build_child_prompt_apresentation(
        context, context["metadata"]["inbound_message_text"], mother_promoted
    )
    assert "MODO COMERCIAL" in prompt
    assert _PRICING_TEXT in prompt
