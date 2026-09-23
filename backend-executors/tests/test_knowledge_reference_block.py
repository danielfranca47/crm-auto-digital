"""Base de conhecimento de referência (context["knowledge_reference"]): categorias de
referência sem bloco próprio (perfil da empresa, políticas, FAQ pré-reunião…) e conteúdo
extra do utilizador (texto livre / uploads) chegam à LLM em todas as fases de conversa —
antes nunca chegavam. Ver docs/architecture/knowledge-base.md."""

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
