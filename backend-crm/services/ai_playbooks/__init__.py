"""Playbook definitions and helper for AI responses (ETAPA 1 MVP)."""
from typing import Any, Dict

PLAYBOOKS: Dict[str, Dict[str, Any]] = {
    "sdr_padrao": {
        "max_chars": 350,
        "response_style": "balanced",
        "default_next_action": "reply",
        "qualification_questions": [
            "Qual é o principal objetivo da sua empresa ao usar nosso produto?",
            "Qual o tamanho da sua equipe atualmente?",
        ],
    },
    "consultor_especialista": {
        "max_chars": 700,
        "response_style": "consultive",
        "default_next_action": "reply",
        "qualification_questions": [
            "Quais desafios específicos você enfrenta hoje?",
            "Qual é o público-alvo principal?",
        ],
    },
    "closer_agressivo": {
        "max_chars": 350,
        "response_style": "direct",
        "default_next_action": "reply",
        "qualification_questions": [
            "Quando pretende implementar a solução?",
            "Quem decide a compra na sua empresa?",
        ],
    },
}


def get_playbook(template_key: str | None) -> Dict[str, Any]:
    """Return a playbook matching the template_key or fallback to the default SDR playbook."""
    key = template_key or "sdr_padrao"
    if key == "closer_agressivo_controlado":
        key = "closer_agressivo"
    playbook = PLAYBOOKS.get(key)
    if playbook is None:
        return dict(PLAYBOOKS["sdr_padrao"])
    return dict(playbook)
