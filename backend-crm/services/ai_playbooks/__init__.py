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
    # Playbook para Agent 3 (hybrid_scheduler) — coaches, terapeutas e consultores solo.
    # Tom: pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo.
    # As 3 ramificações de outcome são usadas pelo decision_engine para personalizar o prompt.
    "hybrid_scheduler_followup": {
        "max_chars": 400,
        "response_style": "personal",
        "default_next_action": "reply",
        "qualification_questions": [],
        "tone_rule": "pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo",
        "followup_outcomes": {
            "interested_not_closed": {
                "instruction": (
                    "Tom de continuidade. Retome o contexto da sessão/reunião anterior, "
                    "remova a objeção específica que foi levantada e ofereça uma nova data concreta para avançar."
                ),
            },
            "reschedule_needed": {
                "instruction": (
                    "Tom leve e sem pressão. O lead não compareceu ou pediu remarcação. "
                    "Ofereça diretamente 2-3 horários disponíveis e encerre com uma pergunta fechada."
                ),
            },
            "converted": {
                "instruction": (
                    "Tom de boas-vindas e onboarding. Parabenize, confirme o próximo passo, "
                    "envie o link de pagamento ou instrução de acesso. Não reabra vendas."
                ),
            },
        },
    },
}


def get_playbook(template_key: str | None) -> Dict[str, Any]:
    """Return a playbook matching the template_key or fallback to the default SDR playbook."""
    key = template_key or "sdr_padrao"
    if key == "closer_agressivo_controlado":
        key = "closer_agressivo"
    if key == "hybrid_scheduler":
        key = "hybrid_scheduler_followup"
    playbook = PLAYBOOKS.get(key)
    if playbook is None:
        return dict(PLAYBOOKS["sdr_padrao"])
    return dict(playbook)
