"""Garante que o conteúdo comercial (tabela de preços, objeções, diferenciais, promoção,
pagamento, FAQ de pré-compromisso) chega à Filha de apresentação pelo bloco único de
referência (`knowledge_reference`) em qualquer turno e template, sem regras "usar APENAS
se…" por categoria — e que o turno único de aquecimento comercial
(`_auto_promoted_from_qual`) continua a mostrá-lo sem o repetir no bloco.

Ver docs/architecture/knowledge-base.md e docs/architecture/pipeline-phases.md, secção
"Estágio de aquecimento e appointment_mode"."""

from app.services.decision_engine import _build_child_prompt_apresentation
from app.services.orchestrator_models import MotherDecision

_PRICING_TEXT = "Plano Escritório - R$ 1.297/mês: qualificação de leads, até 1.000 conversas/mês."


def _context(appointment_mode="commercial", template_key="hybrid_scheduler", knowledge_media=None):
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
        "knowledge_reference": [
            {"heading": "Tabela de Serviços e Preços", "content": _PRICING_TEXT, "category": "service_pricing_table"},
        ],
        "knowledge_media": knowledge_media or {},
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


def _prompt(context, mother=None):
    return _build_child_prompt_apresentation(
        context, context["metadata"]["inbound_message_text"], mother or _mother_not_promoted()
    )


def test_pricing_available_via_reference_block_outside_warming_turn():
    prompt = _prompt(_context())
    assert prompt.count(_PRICING_TEXT) == 1
    assert "BASE DE CONHECIMENTO DO NEGÓCIO" in prompt
    assert "usar APENAS" not in prompt


def test_pricing_available_in_exploratory_mode_and_other_templates():
    for context in (_context(appointment_mode="exploratory"), _context(template_key="sdr_padrao")):
        assert _PRICING_TEXT in _prompt(context)


def test_commercial_mode_keeps_in_person_payment_rule_outside_warming_turn():
    assert "o pagamento é sempre presencial" in _prompt(_context())
    assert "o pagamento é sempre presencial" not in _prompt(_context(appointment_mode="exploratory"))


def test_category_with_media_leaves_reference_block_and_gets_media_note():
    context = _context(knowledge_media={"service_pricing_table": [{"url": "https://x/tabela.png"}]})
    prompt = _prompt(context)
    assert _PRICING_TEXT not in prompt
    assert "TABELA DE SERVIÇOS E PREÇOS: conteúdo disponível em mídia" in prompt


def test_warming_turn_shows_commercial_content_once():
    """Turno único de transição (qualification -> apresentation, sem missing_fields):
    o bloco MODO COMERCIAL mostra a tabela e o bloco de referência não a repete."""
    context = _context()
    context["ai_profile"]["qualification_required_fields"] = []
    mother_promoted = MotherDecision(
        route_to="qualification",
        perceived_category="qualification",
        confidence=0.9,
        reason="qualificação completa",
    )
    prompt = _prompt(context, mother_promoted)
    assert "MODO COMERCIAL" in prompt
    assert prompt.count(_PRICING_TEXT) == 1
