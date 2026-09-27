"""Base de conhecimento de referência (context["knowledge_reference"]): categorias de
referência (perfil da empresa, FAQs, políticas, preços, objeções…) e conteúdo extra do
utilizador (texto livre / uploads) chegam à LLM em todas as fases de conversa, num bloco
único e sem regras "usar APENAS quando…" por categoria; cada fase só exclui o que recebe
por outro caminho. Ver docs/architecture/knowledge-base.md."""

import pytest

from app.services.decision_engine import (
    _build_child_prompt_agendamento,
    _build_child_prompt_apresentation,
    _build_child_prompt_closing,
    _build_child_prompt_follow_up,
    _build_child_prompt_pre_agendamento,
    _build_child_prompt_qualification,
    _build_knowledge_reference_block,
)
from app.services.orchestrator_models import MotherDecision

_PROFILE = "Somos a Clínica Exemplo, massoterapia em São Paulo desde 2015."
_EXTRA = "Atendemos também ao domicílio na zona sul, com taxa de deslocamento de R$ 30."


def _context(phase="qualification"):
    return {
        "lead": {"id": 1, "category": phase},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {"template_key": "hybrid_scheduler"},
        "metadata": {"inbound_message_text": "vocês atendem ao domicílio?"},
        "history": [{"model": "inbound", "text": "vocês atendem ao domicílio?"}],
        "knowledge_items": {},
        "knowledge_media": {},
        "knowledge_reference": [
            {"heading": "Perfil da Empresa", "content": _PROFILE},
            {"heading": "Atendimento ao domicílio", "content": _EXTRA},
        ],
        "lead_detected_language": "pt",
    }


def _mother(route_to):
    return MotherDecision(route_to=route_to, perceived_category=route_to, confidence=0.9, reason="teste")


def test_block_renders_headings_content_and_single_instruction():
    block = _build_knowledge_reference_block(_context())
    assert "## Perfil da Empresa\n" + _PROFILE in block
    assert "## Atendimento ao domicílio\n" + _EXTRA in block
    assert block.count("COMO USAR A BASE DE CONHECIMENTO") == 1


@pytest.mark.parametrize("reference", [None, [], [{"heading": "Vazio", "content": "   "}], ["lixo"]])
def test_block_empty_without_usable_content(reference):
    context = _context()
    context["knowledge_reference"] = reference
    assert _build_knowledge_reference_block(context) == ""


def test_block_missing_heading_gets_default():
    context = _context()
    context["knowledge_reference"] = [{"content": _EXTRA}]
    assert "## Informação adicional\n" + _EXTRA in _build_knowledge_reference_block(context)


@pytest.mark.parametrize(
    "builder, phase",
    [
        (_build_child_prompt_qualification, "qualification"),
        (_build_child_prompt_apresentation, "apresentation"),
        (_build_child_prompt_follow_up, "follow-up"),
        (_build_child_prompt_closing, "closing"),
        (_build_child_prompt_pre_agendamento, "pre-agendamento"),
        (_build_child_prompt_agendamento, "agendamento"),
    ],
)
def test_reference_reaches_every_conversation_phase(builder, phase):
    context = _context(phase)
    prompt = builder(context, context["metadata"]["inbound_message_text"], _mother(phase))
    assert _PROFILE in prompt
    assert _EXTRA in prompt


_FAQ = "A sessão dura 50 minutos, mais 10 de conversa inicial."
_PRICE = "Massagem relaxante — 60min: R$ 180"


def _context_with_faq_and_price(phase):
    context = _context(phase)
    context["knowledge_reference"] = [
        {"heading": "FAQ do Serviço", "content": _FAQ, "category": "service_faq"},
        {"heading": "Tabela de Serviços e Preços", "content": _PRICE, "category": "service_pricing_table"},
    ]
    context["knowledge_items"] = {"service_pricing_table": _PRICE}
    return context


def test_block_skips_excluded_categories():
    block = _build_knowledge_reference_block(
        _context_with_faq_and_price("closing"), exclude_categories=("service_pricing_table",)
    )
    assert _FAQ in block
    assert _PRICE not in block


def test_block_instruction_treats_objections_as_non_factual():
    assert "Uma objeção" in _build_knowledge_reference_block(_context())


def test_qualification_gets_faq_but_withholds_price():
    context = _context_with_faq_and_price("qualification")
    prompt = _build_child_prompt_qualification(context, "quanto tempo dura?", _mother("qualification"))
    assert _FAQ in prompt
    assert _PRICE not in prompt


def test_qualification_answers_from_knowledge_base_not_only_custom_instructions():
    context = _context_with_faq_and_price("qualification")
    prompt = _build_child_prompt_qualification(context, "quanto tempo dura?", _mother("qualification"))
    assert "custom_instructions e a base de conhecimento" in prompt
    assert "usando apenas custom_instructions" not in prompt


@pytest.mark.parametrize(
    "builder, phase",
    [
        (_build_child_prompt_apresentation, "apresentation"),
        (_build_child_prompt_follow_up, "follow-up"),
        (_build_child_prompt_closing, "closing"),
        (_build_child_prompt_pre_agendamento, "pre-agendamento"),
    ],
)
def test_faq_and_price_reach_later_phases_without_apenas_rules(builder, phase):
    context = _context_with_faq_and_price(phase)
    prompt = builder(context, "quanto custa?", _mother(phase))
    assert prompt.count(_FAQ) == 1
    assert prompt.count(_PRICE) == 1
    assert "usar APENAS" not in prompt


def test_scheduling_keeps_price_table_only_in_services_block():
    context = _context_with_faq_and_price("agendamento")
    prompt = _build_child_prompt_agendamento(context, "pode ser amanhã?", _mother("agendamento"))
    assert _FAQ in prompt
    assert prompt.count(_PRICE) == 1
    assert "SERVIÇOS E DURAÇÕES DISPONÍVEIS" in prompt


def test_followup_does_not_promise_media_it_never_sends():
    context = _context_with_faq_and_price("follow-up")
    context["knowledge_media"] = {"service_faq": [{"url": "https://x/faq.pdf"}]}
    prompt = _build_child_prompt_follow_up(context, "e quanto tempo dura?", _mother("follow-up"))
    assert _FAQ in prompt
    assert "enviado automaticamente" not in prompt


@pytest.mark.parametrize("response_style", ["active", "passive"])
@pytest.mark.parametrize("disclosure", [None, "after_qualification", "valor-desconhecido"])
def test_qualification_withholds_price_by_default(response_style, disclosure):
    context = _context_with_faq_and_price("qualification")
    context["ai_profile"]["response_style"] = response_style
    if disclosure is not None:
        context["ai_profile"]["qualification_price_disclosure"] = disclosure
    prompt = _build_child_prompt_qualification(context, "quanto custa?", _mother("qualification"))
    assert _PRICE not in prompt
    assert "os valores são apresentados logo a seguir" in prompt
    assert "exclusivas da fase de apresentação" not in prompt


@pytest.mark.parametrize("response_style", ["active", "passive"])
def test_qualification_answers_price_when_operator_chooses_on_request(response_style):
    context = _context_with_faq_and_price("qualification")
    context["ai_profile"]["response_style"] = response_style
    context["ai_profile"]["qualification_price_disclosure"] = "on_request"
    prompt = _build_child_prompt_qualification(context, "quanto custa?", _mother("qualification"))
    assert prompt.count(_PRICE) == 1
    assert "responde com os valores da base de conhecimento" in prompt
    assert "os valores são apresentados logo a seguir" not in prompt
