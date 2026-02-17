from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core_client import (
    connect_core_whatsapp_instance,
    fetch_core_whatsapp_connection_me,
    init_core_whatsapp_instance,
    set_core_whatsapp_webhook,
    status_core_whatsapp_instance,
)
from security_core import CurrentUser, require_crm_access

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp Connect"])
logger = logging.getLogger(__name__)

_QR_KEYS = {"qrcode", "qrCode", "qr_code"}


class QRPayload(BaseModel):
    kind: Optional[str] = Field(default=None, description="base64|text|url|null")
    value: Optional[str] = None


class ConnectResponse(BaseModel):
    instance_id: str
    status: Optional[str] = None
    qr: QRPayload
    raw: Optional[Dict[str, Any]] = None


class StatusResponse(BaseModel):
    instance_id: str
    status: Optional[str] = None
    phone_e164: Optional[str] = None
    last_updated: Optional[str] = None


def _find_first_string(data: Dict[str, Any], keys: set[str]) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _find_in_payload(payload: Any, keys: set[str]) -> Optional[str]:
    if isinstance(payload, dict):
        direct = _find_first_string(payload, keys)
        if direct:
            return direct
        for value in payload.values():
            found = _find_in_payload(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_in_payload(item, keys)
            if found:
                return found
    return None


def _extract_status_flags(raw: Dict[str, Any]) -> tuple[Optional[bool], Optional[bool], Optional[str], Optional[str]]:
    status_payload = raw.get("status") if isinstance(raw.get("status"), dict) else {}
    logged_in = (
        raw.get("loggedIn")
        if isinstance(raw.get("loggedIn"), bool)
        else raw.get("logged_in")
        if isinstance(raw.get("logged_in"), bool)
        else status_payload.get("loggedIn")
        if isinstance(status_payload.get("loggedIn"), bool)
        else status_payload.get("logged_in")
        if isinstance(status_payload.get("logged_in"), bool)
        else None
    )
    connected = (
        raw.get("connected")
        if isinstance(raw.get("connected"), bool)
        else status_payload.get("connected")
        if isinstance(status_payload.get("connected"), bool)
        else None
    )
    jid = raw.get("jid") or status_payload.get("jid")
    instance_payload = raw.get("instance") if isinstance(raw.get("instance"), dict) else {}
    instance_status = instance_payload.get("status")
    if isinstance(instance_status, str):
        instance_status = instance_status.strip().lower()
    else:
        instance_status = None
    return logged_in, connected, jid, instance_status


def _normalize_status(raw: Dict[str, Any]) -> Optional[str]:
    logged_in, connected, jid, instance_status = _extract_status_flags(raw)

    if logged_in is True:
        return "connected"
    if connected is True and logged_in is False:
        return "connecting"
    if instance_status in {"connecting", "disconnected"}:
        return instance_status
    if connected is False and logged_in is False:
        return "disconnected"
    if isinstance(instance_status, str):
        return instance_status
    return None


def _infer_qr_kind(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        return "url"
    if re.fullmatch(r"[A-Za-z0-9+/=\n\r]+", value) and len(value) > 80:
        return "base64"
    return "text"


def _extract_qr(raw: Dict[str, Any]) -> QRPayload:
    qr_value = _find_in_payload(raw, _QR_KEYS)
    if not qr_value:
        return QRPayload(kind=None, value=None)
    kind = _infer_qr_kind(qr_value)
    return QRPayload(kind=kind, value=qr_value)


def _extract_phone(raw: Dict[str, Any]) -> Optional[str]:
    phone_keys = {"phone", "phone_e164", "phoneNumber", "number"}
    return _find_in_payload(raw, phone_keys)


def _generate_instance_id(user_id: int) -> str:
    suffix = uuid4().hex[:8]
    return f"crm-{user_id}-{suffix}"


def _resolve_instance_id(current_user: CurrentUser) -> Optional[Dict[str, Any]]:
    connection = fetch_core_whatsapp_connection_me(current_user.token or "")
    return connection


def _build_webhook_url() -> str:
    base = os.getenv("CRM_PUBLIC_BASE_URL")
    if not base:
        raise HTTPException(status_code=500, detail="CRM_PUBLIC_BASE_URL não configurado")
    secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="CRM_WEBHOOK_SECRET não configurado")
    return f"{base.rstrip('/')}/webhooks/whatsapp/uazapi?secret={secret}"


def _mask_webhook_url(url: str) -> str:
    if "secret=" not in url:
        return url
    base, _ = url.split("secret=", 1)
    return f"{base}secret=***"


def _set_whatsapp_webhook(*, user_id: int, instance_id: str, request_id: str) -> None:
    webhook_url = _build_webhook_url()
    masked = _mask_webhook_url(webhook_url)
    logger.info(
        "whatsapp webhook set user_id=%s instance_id=%s request_id=%s url=%s",
        user_id,
        instance_id,
        request_id,
        masked,
    )
    set_core_whatsapp_webhook(
        instance_id,
        webhook_url,
        ["messages", "connection"],
        False,
        True,
        ["wasSentByApi", "isGroupYes"],
    )
    logger.info(
        "whatsapp webhook success user_id=%s instance_id=%s request_id=%s",
        user_id,
        instance_id,
        request_id,
    )


@router.post("/connect", response_model=ConnectResponse)
def connect_whatsapp(current_user: CurrentUser = Depends(require_crm_access)):
    request_id = uuid4().hex
    connection = _resolve_instance_id(current_user)
    if connection:
        instance_id = connection.get("instance_id")
    else:
        instance_id = _generate_instance_id(current_user.id)
        logger.info(
            "whatsapp connect init user_id=%s instance_id=%s request_id=%s",
            current_user.id,
            instance_id,
            request_id,
        )
        init_core_whatsapp_instance(current_user.id, instance_id)

    if not instance_id:
        raise HTTPException(status_code=502, detail="Falha ao obter instance_id para WhatsApp")

    logger.info(
        "whatsapp connect start user_id=%s instance_id=%s request_id=%s",
        current_user.id,
        instance_id,
        request_id,
    )
    try:
        raw = connect_core_whatsapp_instance(current_user.id, instance_id)
    except HTTPException as exc:
        if exc.status_code and exc.status_code >= 500:
            logger.warning(
                "whatsapp connect failed user_id=%s instance_id=%s request_id=%s detail=%s",
                current_user.id,
                instance_id,
                request_id,
                exc.detail,
            )
            new_instance_id = _generate_instance_id(current_user.id)
            logger.info(
                "whatsapp reinit user_id=%s old_instance_id=%s new_instance_id=%s request_id=%s",
                current_user.id,
                instance_id,
                new_instance_id,
                request_id,
            )
            init_core_whatsapp_instance(current_user.id, new_instance_id)
            raw = connect_core_whatsapp_instance(current_user.id, new_instance_id)
            instance_id = new_instance_id
        else:
            raise

    status_value = _normalize_status(raw)
    qr = _extract_qr(raw)
    logged_in, connected, jid, instance_status = _extract_status_flags(raw)
    logger.info(
        "whatsapp connect success user_id=%s instance_id=%s request_id=%s status=%s connected=%s logged_in=%s jid_present=%s instance_status=%s",
        current_user.id,
        instance_id,
        request_id,
        status_value,
        connected,
        logged_in,
        bool(jid),
        instance_status,
    )
    _set_whatsapp_webhook(user_id=current_user.id, instance_id=instance_id, request_id=request_id)

    return ConnectResponse(instance_id=instance_id, status=status_value, qr=qr, raw=raw)


@router.get("/status", response_model=StatusResponse)
def whatsapp_status(current_user: CurrentUser = Depends(require_crm_access)):
    request_id = uuid4().hex
    connection = _resolve_instance_id(current_user)
    if not connection:
        raise HTTPException(status_code=404, detail="Conexão WhatsApp não encontrada")

    instance_id = connection.get("instance_id")
    if not instance_id:
        raise HTTPException(status_code=404, detail="instance_id não encontrado no core")

    logger.info(
        "whatsapp status start user_id=%s instance_id=%s request_id=%s",
        current_user.id,
        instance_id,
        request_id,
    )
    try:
        raw = status_core_whatsapp_instance(instance_id)
    except HTTPException as exc:
        if exc.status_code and exc.status_code >= 500:
            logger.warning(
                "whatsapp status failed user_id=%s instance_id=%s request_id=%s detail=%s",
                current_user.id,
                instance_id,
                request_id,
                exc.detail,
            )
            return StatusResponse(
                instance_id=instance_id,
                status="disconnected",
                phone_e164=None,
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
        raise

    status_value = _normalize_status(raw) or connection.get("status")
    phone_e164 = _extract_phone(raw) or connection.get("phone_e164")
    logged_in, connected, jid, instance_status = _extract_status_flags(raw)
    logger.info(
        "whatsapp status success user_id=%s instance_id=%s request_id=%s status=%s connected=%s logged_in=%s jid_present=%s instance_status=%s",
        current_user.id,
        instance_id,
        request_id,
        status_value,
        connected,
        logged_in,
        bool(jid),
        instance_status,
    )

    return StatusResponse(
        instance_id=instance_id,
        status=status_value,
        phone_e164=phone_e164,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/qr/refresh", response_model=ConnectResponse)
def refresh_qr(current_user: CurrentUser = Depends(require_crm_access)):
    request_id = uuid4().hex
    connection = _resolve_instance_id(current_user)
    if not connection or not connection.get("instance_id"):
        raise HTTPException(status_code=404, detail="Conexão WhatsApp não encontrada")

    instance_id = connection.get("instance_id")
    logger.info(
        "whatsapp qr refresh user_id=%s instance_id=%s request_id=%s",
        current_user.id,
        instance_id,
        request_id,
    )
    raw = connect_core_whatsapp_instance(current_user.id, instance_id)
    _set_whatsapp_webhook(user_id=current_user.id, instance_id=instance_id, request_id=request_id)
    status_value = _normalize_status(raw)
    qr = _extract_qr(raw)
    logged_in, connected, jid, instance_status = _extract_status_flags(raw)
    logger.info(
        "whatsapp qr refresh success user_id=%s instance_id=%s request_id=%s status=%s connected=%s logged_in=%s jid_present=%s instance_status=%s",
        current_user.id,
        instance_id,
        request_id,
        status_value,
        connected,
        logged_in,
        bool(jid),
        instance_status,
    )

    return ConnectResponse(instance_id=instance_id, status=status_value, qr=qr, raw=raw)
