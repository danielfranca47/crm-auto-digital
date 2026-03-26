"""Playbook definitions and helper for AI responses (ETAPA 1 MVP)."""
from typing import Any, Dict

# Defaults para o estágio de aquecimento do hybrid_scheduler (Tarefa 3.8)
DEFAULT_SOCIAL_PROOF = (
    "Um profissional com o seu perfil já utilizou essa abordagem e conseguiu resultados expressivos. "
    "Posso te contar mais detalhes na nossa conversa."
)
DEFAULT_SESSION_PREVIEW = (
    "Na sessão de aproximadamente 1h, vamos mapear sua situação atual, identificar os principais pontos de melhoria "
    "e sair com um plano de ação claro para você."
)

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
    # Playbook para Agent 2 (closer) — recuperação de carrinho abandonado.
    # 3 mensagens escalonadas por tentativa: lembrete neutro → benefício+objeção → urgência.
    "closer_agressivo_cart_recovery": {
        "max_chars": 280,
        "response_style": "direct",
        "default_next_action": "reply",
        "qualification_questions": [],
        "tone_rule": "objetivo e direto, sem ser agressivo — recuperar pagamento pendente após link enviado",
        "followup_attempts": {
            1: {
                "tone": "neutral_reminder",
                "instruction": (
                    "Lembrete neutro: o pedido está reservado e o link ainda está disponível. "
                    "Sem pressão — apenas informa e pergunta se há alguma dúvida que impeça o pagamento."
                ),
            },
            2: {
                "tone": "benefit_objection",
                "instruction": (
                    "Reforce o benefício principal do produto/serviço e antecipe a objeção mais comum do nicho. "
                    "Tom amigável, resolva a dúvida que está impedindo o pagamento."
                ),
            },
            3: {
                "tone": "urgency",
                "instruction": (
                    "Urgência máxima: a oferta expira hoje. "
                    "CTA direto para o link de pagamento. Não reabra qualificação."
                ),
            },
        },
    },
    # Playbook principal para Agent 3 (hybrid_scheduler) — coaches, terapeutas e consultores solo.
    # Tom: pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo.
    # Inclui estágio de aquecimento (warming) entre qualificação e proposta de agenda.
    "hybrid_scheduler": {
        "max_chars": 400,
        "response_style": "personal",
        "default_next_action": "reply",
        "qualification_questions": [
            "Qual é o principal desafio que você quer resolver?",
            "Já tentou outras abordagens antes? Como foi?",
        ],
        "tone_rule": "pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo",
        "warming": {
            "trigger": "after_qualification_approved",
            "steps": ["social_proof", "session_preview"],
            # templates resolvidos em runtime a partir de ai_profile.warming_social_proof
            # e ai_profile.warming_session_preview; os defaults estão nas constantes acima
        },
    },
    # Playbook de follow-up para Agent 3 — ramificações por outcome pós-apresentação.
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
    # hybrid_scheduler agora tem playbook próprio (com estágio warming).
    # hybrid_scheduler_followup continua disponível para contexto específico de follow-up.
    playbook = PLAYBOOKS.get(key)
    if playbook is None:
        return dict(PLAYBOOKS["sdr_padrao"])
    return dict(playbook)
