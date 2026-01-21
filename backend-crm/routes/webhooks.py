"""Routers de webhooks externos (WhatsApp inbound)."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Query

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
    secret: str | None = Query(default=None),
):
    expected_secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="CRM_WEBHOOK_SECRET não configurado")
    if (x_webhook_secret != expected_secret) and (secret != expected_secret):
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    def _normalize_e164(value: str | None) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"[\s\-()]+", "", str(value).strip())
        cleaned = re.sub(r"[^0-9+]+", "", cleaned)
        if cleaned.startswith("00") and not cleaned.startswith("+"):
            cleaned = "+" + cleaned[2:]
        if cleaned.startswith("+"):
            return cleaned
        digits = re.sub(r"[^0-9]+", "", cleaned)
        if not digits:
            return ""
        return f"+{digits}"

    event = payload.get("event") or payload.get("EventType") or payload.get("type")
    instance_id = payload.get("instance") or payload.get("instanceName")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}

    def _resolve_sender_e164() -> str:
        chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
        chat_phone = chat.get("phone")
        sender_phone = data.get("sender") or message.get("sender_pn")
        return _normalize_e164(chat_phone) or _normalize_e164(sender_phone)

    sender = _resolve_sender_e164()
    message_id = data.get("messageId") or data.get("id") or message.get("messageid") or message.get("id")
    message_type = data.get("messageType") or message.get("type") or message.get("messageType")
    message_text = data.get("text") or message.get("text") or message.get("content")
    from_me = data.get("fromMe") is True or message.get("fromMe") is True

    logger.info(
        "uazapi webhook event=%s instance=%s sender=%s message_id=%s",
        event,
        instance_id,
        sender,
        message_id,
    )

    if event not in {"messages", "message"}:
        return {"status": "ignored", "reason": "event_not_messages"}
    if from_me:
        return {"status": "ignored", "reason": "from_me"}
    if message_type and message_type != "text":
        return {"status": "ignored", "reason": "not_text"}
    if not message_text:
        return {"status": "ignored", "reason": "missing_text"}
    if not instance_id or not sender or not message_id:
        detail = "Payload Uazapi incompleto"
        if not sender:
            detail = "Payload Uazapi incompleto (sender inválido)"
        raise HTTPException(status_code=400, detail=detail)

    inbound_payload = {
        "instance_id": instance_id,
        "from": sender,
        "message_text": message_text,
        "message_id": message_id,
        "timestamp": message.get("messageTimestamp") or data.get("messageTimestamp"),
        "provider": "uazapi",
    }

    return handle_inbound(inbound_payload)
