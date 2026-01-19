"""Routers de webhooks externos (WhatsApp inbound)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException

from services.whatsapp_inbound.inbound_handler import InboundWebhookPayload, handle_inbound

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)


@router.post("/whatsapp/inbound")
def whatsapp_inbound_webhook(
    payload: InboundWebhookPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    expected_secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="CRM_WEBHOOK_SECRET não configurado")
    if not x_webhook_secret or x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    return handle_inbound(payload.model_dump(by_alias=True))


@router.post("/whatsapp/uazapi")
def whatsapp_uazapi_webhook(
    payload: Dict[str, Any],
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    expected_secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="CRM_WEBHOOK_SECRET não configurado")
    if not x_webhook_secret or x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    event = payload.get("event")
    instance_id = payload.get("instance")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

    sender = data.get("sender")
    message_id = data.get("messageId") or data.get("id")
    message_type = data.get("messageType")
    message_text = data.get("text")
    from_me = data.get("fromMe") is True

    logger.info(
        "uazapi webhook event=%s instance=%s sender=%s message_id=%s",
        event,
        instance_id,
        sender,
        message_id,
    )

    if event != "messages":
        return {"status": "ignored", "reason": "event_not_messages"}
    if from_me:
        return {"status": "ignored", "reason": "from_me"}
    if message_type and message_type != "text":
        return {"status": "ignored", "reason": "not_text"}
    if not message_text:
        return {"status": "ignored", "reason": "missing_text"}
    if not instance_id or not sender or not message_id:
        raise HTTPException(status_code=400, detail="Payload Uazapi incompleto")

    inbound_payload = {
        "instance_id": instance_id,
        "from": sender,
        "message_text": message_text,
        "message_id": message_id,
        "timestamp": data.get("messageTimestamp"),
        "provider": "uazapi",
    }

    return handle_inbound(inbound_payload)
