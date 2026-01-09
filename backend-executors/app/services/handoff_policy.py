from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.clients import crm_client
from app.schemas.decision import DecisionOutput


HANDOFF_TEMPLATES = {
    "virtual_assistant": "Sou a assistente virtual e vou encaminhar você para alguém do nosso time. Pode aguardar um instante?",
    "human_agent": "Entendi. Vou te conectar com alguém do time agora. Só um instante.",
    "user_clone": "Perfeito. Já vou chamar alguém aqui e te retorno em instantes.",
}

IGNORE_REPLY = "Certo! Me diga como posso ajudar 🙂"


def _safe_get(data: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def apply(
    context: Dict[str, Any],
    decision: DecisionOutput,
    logger: Optional[logging.Logger] = None,
) -> DecisionOutput:
    if decision.next_action != "handoff":
        return decision

    ai_profile = context.get("ai_profile") or {}
    lead = context.get("lead") or {}
    job = context.get("job") or {}
    payload = job.get("payload") or {}
    metadata = context.get("metadata") or {}

    identity_mode = ai_profile.get("identity_mode") or "human_agent"
    handoff_policy = ai_profile.get("handoff_policy") or "keep_active_notify"
    handoff_custom_text = ai_profile.get("handoff_custom_text")

    message_text = (
        str(handoff_custom_text).strip()
        if handoff_custom_text
        else HANDOFF_TEMPLATES.get(identity_mode, HANDOFF_TEMPLATES["human_agent"])
    )

    user_id = _safe_get(lead, "user_id") or _safe_get(payload, "user_id")
    lead_id = _safe_get(lead, "id") or _safe_get(payload, "lead_id")
    job_id = _safe_get(job, "id") or _safe_get(payload, "job_id")
    message_id = _safe_get(metadata, "message_id") or _safe_get(payload, "message_id")

    if handoff_policy == "disable_bot":
        if logger:
            logger.info(
                "handoff policy=disable_bot lead_id=%s user_id=%s job_id=%s message_id=%s identity_mode=%s",
                lead_id,
                user_id,
                job_id,
                message_id,
                identity_mode,
            )
        if lead_id is not None:
            crm_client.set_lead_bot_disabled(
                int(lead_id),
                True,
                reason="handoff_requested",
            )
        if user_id is not None and lead_id is not None and job_id is not None:
            crm_client.log_handoff_requested(
                user_id=int(user_id),
                lead_id=int(lead_id),
                job_id=int(job_id),
                message_id=message_id,
                reason=decision.reason,
                policy=handoff_policy,
                identity_mode=identity_mode,
            )
        return DecisionOutput(
            next_action="handoff",
            message_text=message_text,
            questions=[],
            reason=decision.reason,
        )

    if handoff_policy == "keep_active_notify":
        if logger:
            logger.info(
                "handoff policy=keep_active_notify lead_id=%s user_id=%s job_id=%s message_id=%s identity_mode=%s",
                lead_id,
                user_id,
                job_id,
                message_id,
                identity_mode,
            )
        if user_id is not None and lead_id is not None and job_id is not None:
            crm_client.log_handoff_requested(
                user_id=int(user_id),
                lead_id=int(lead_id),
                job_id=int(job_id),
                message_id=message_id,
                reason=decision.reason,
                policy=handoff_policy,
                identity_mode=identity_mode,
            )
        return DecisionOutput(
            next_action="handoff",
            message_text=message_text,
            questions=[],
            reason=decision.reason,
        )

    if logger:
        logger.info(
            "handoff policy=ignore override lead_id=%s user_id=%s job_id=%s message_id=%s identity_mode=%s",
            lead_id,
            user_id,
            job_id,
            message_id,
            identity_mode,
        )
    return DecisionOutput(
        next_action="reply",
        message_text=IGNORE_REPLY,
        questions=[],
        reason="policy_ignore_override",
    )
