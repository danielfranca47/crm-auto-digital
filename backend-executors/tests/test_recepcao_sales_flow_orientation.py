"""Filha Recepção com orientações da Fase 0 do Fluxo de Venda: as instruções do dono entram
no meio do prompt, com prioridade sobre o modelo de boas-vindas, e a regra "não faz
perguntas" fica condicional. Sem orientação, o prompt continua o de sempre."""

from app.services.decision_engine import _build_child_prompt_recepcao
from app.services.orchestrator_models import MotherDecision

_ORIENT = "Apresente-se como Lara e pergunte qual terapeuta: Val ou Daniel"


def _mother() -> MotherDecision:
    return MotherDecision(route_to="recepcao", confidence=0.9, reason="saudação")


def _context(blocks: list) -> dict:
    return {
        "lead": {"id": 1, "category": "qualification", "triggers_fired": "[]", "phases_triggered": "[]"},
        "ai_profile": {
            "agent_mode": "agenda",
            "brand_name": "Sensi Vitae",
            "sales_flow": {"enabled": True, "phases": [{"id": "p0", "blocks": blocks}]},
        },
        "history": [],
        "metadata": {},
    }


def _p0_blocks(strict: bool = False) -> list:
    return [
        {"id": "pt", "typeId": "phase_trigger"},
        {"id": "or", "typeId": "orientacao", "content": _ORIENT, "strict": strict},
    ]


def test_without_orientation_prompt_keeps_greeting_only_rules():
    prompt = _build_child_prompt_recepcao(_context([]), "olá", _mother(), is_phase_entry=True)
    assert "INSTRUÇÕES DO DONO DO NEGÓCIO" not in prompt
    assert "- Não faz perguntas de qualificação neste turno." in prompt
    assert '"message_text": "<cumprimento caloroso — máximo 2-3 linhas>"' in prompt


def test_orientation_goes_before_json_with_priority_and_question_rule_changes():
    prompt = _build_child_prompt_recepcao(_context(_p0_blocks()), "olá", _mother(), is_phase_entry=True)
    owner_at = prompt.index("INSTRUÇÕES DO DONO DO NEGÓCIO PARA ESTE TURNO")
    json_at = prompt.index("Retorne SOMENTE JSON válido")
    assert owner_at < prompt.index(_ORIENT) < json_at
    assert prompt.count(_ORIENT) == 1  # não volta a ser colado no fim
    assert "4. Cumpre as INSTRUÇÕES DO DONO DO NEGÓCIO" in prompt
    assert "- Não faz perguntas de qualificação neste turno." not in prompt
    assert "Só faz a pergunta que as instruções do dono pedirem" in prompt
    assert '"message_text": "<cumprimento + o que as instruções do dono pedem>"' in prompt


def test_strict_orientation_keeps_literal_label_inside_owner_block():
    prompt = _build_child_prompt_recepcao(_context(_p0_blocks(strict=True)), "olá", _mother(), is_phase_entry=True)
    owner_at = prompt.index("INSTRUÇÕES DO DONO DO NEGÓCIO PARA ESTE TURNO")
    assert owner_at < prompt.index("SEGUIR À RISCA") < prompt.index("Retorne SOMENTE JSON válido")


def test_orientation_block_shows_question_already_answered_example():
    prompt = _build_child_prompt_recepcao(
        _context(_p0_blocks()), "ola, gostaria de saber mais sobre as massagens da val", _mother(), is_phase_entry=True
    )
    owner_at = prompt.index("INSTRUÇÕES DO DONO DO NEGÓCIO PARA ESTE TURNO")
    answered_at = prompt.index("Quando a mensagem do lead já responde à pergunta da instrução")
    assert owner_at < answered_at < prompt.index("Retorne SOMENTE JSON válido")
    assert '❌ message_text: "Olá! Sou a Ana. Qual profissional você prefere, Rita ou Paulo?"' in prompt
    assert '"lead_already_answered":' in prompt


def test_without_orientation_no_question_already_answered_example():
    prompt = _build_child_prompt_recepcao(_context([]), "olá", _mother(), is_phase_entry=True)
    assert "Quando a mensagem do lead já responde à pergunta da instrução" not in prompt
    assert "lead_already_answered" not in prompt


def test_strict_orientation_allows_skipping_question_already_answered():
    prompt = _build_child_prompt_recepcao(_context(_p0_blocks(strict=True)), "olá", _mother(), is_phase_entry=True)
    assert "a menos que a mensagem do lead já a responda: aí omita a pergunta" in prompt


def test_orientation_not_fired_outside_phase_entry_keeps_default_prompt():
    prompt = _build_child_prompt_recepcao(_context(_p0_blocks()), "olá", _mother(), is_phase_entry=False)
    assert "INSTRUÇÕES DO DONO DO NEGÓCIO" not in prompt
    assert "- Não faz perguntas de qualificação neste turno." in prompt
