"""Routers de webhooks externos (WhatsApp inbound)."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Query

from services.phone_normalizer import PhoneNormalizationError, normalize_to_e164
from services.whatsapp_inbound.inbound_handler import InboundWebhookPayload, handle_inbound

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)


_GROUP_JID_SUFFIX = "@g.us"


def _is_group_marker(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().endswith(_GROUP_JID_SUFFIX)


def _has_group_jid(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_norm = str(key).strip().lower()
            if key_norm in {"remotejid", "chatid", "id"} and _is_group_marker(value):
                return True
            if _has_group_jid(value):
                return True
    elif isinstance(payload, list):
        for item in payload:
            if _has_group_jid(item):
                return True
    elif _is_group_marker(payload):
        return True
    return False


def is_group_message_payload(payload: Dict[str, Any]) -> bool:
    chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}

    if chat.get("isGroup") is True:
        return True
    if data.get("isGroup") is True or bool(data.get("groupId")):
        return True
    if message.get("isGroup") is True or bool(message.get("groupId")):
        return True

    if _has_group_jid(payload):
        return True

    if chat and message and chat.get("type") == "group":
        return True

    return False


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
        try:
            return normalize_to_e164(value)
        except PhoneNormalizationError:
            digits = re.sub(r"\D+", "", str(value))
            if not digits:
                return ""
            try:
                return normalize_to_e164(f"+{digits}")
            except PhoneNormalizationError:
                return ""

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

    is_group = is_group_message_payload(payload)
    if is_group:
        logger.info(
            "uazapi webhook ignored group_message instance=%s sender=%s message_id=%s",
            instance_id,
            sender,
            message_id,
        )
        return {"status": "ignored", "reason": "group_message"}

    inbound_payload = {
        "instance_id": instance_id,
        "from": sender,
        "message_text": message_text,
        "message_id": message_id,
        "timestamp": message.get("messageTimestamp") or data.get("messageTimestamp"),
        "provider": "uazapi",
        "is_group": is_group,
    }

    return handle_inbound(inbound_payload)
