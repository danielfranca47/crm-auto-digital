from app.services.decision_engine import _build_child_prompt_recepcao
from app.services.orchestrator_models import ChildResult, MotherDecision


def _context():
    return {
        "lead": {"id": 1, "category": None},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {},
        "metadata": {},
        "history": [],
    }


def _mother_decision():
    return MotherDecision(route_to="recepcao", confidence=0.9, reason="saudação")


def test_recepcao_prompt_instructs_pending_commercial_extraction():
    prompt = _build_child_prompt_recepcao(
        _context(),
        "Olá, boa tarde, gostaria de agendar horário para hoje às 17:30",
        _mother_decision(),
    )

    assert "pending_commercial_text" in prompt
    # Regra de "não promete verificar" continua no prompt, só a redação mudou de uma
    # instrução direta para um bloco "O QUE VOCÊ NÃO FAZ" orientado a exemplos.
    assert "não promete verificar" in prompt
    assert "VÁRIAS LINHAS" in prompt


def test_child_result_accepts_pending_commercial_text():
    result = ChildResult.model_validate(
        {
            "message_text": "Olá! Seja bem-vindo.",
            "confidence": 0.95,
            "pending_commercial_text": "gostaria de agendar horário para hoje às 17:30",
        }
    )

    assert result.pending_commercial_text == "gostaria de agendar horário para hoje às 17:30"


def test_child_result_defaults_pending_commercial_text_to_none():
    result = ChildResult.model_validate({"message_text": "Olá! Seja bem-vindo.", "confidence": 0.95})

    assert result.pending_commercial_text is None
