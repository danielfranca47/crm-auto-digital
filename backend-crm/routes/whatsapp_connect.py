from __future__ import annotations

import logging
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


def _normalize_status(raw: Dict[str, Any]) -> Optional[str]:
    def _normalize(value: Any) -> Optional[str]:
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
        if isinstance(value, bool):
            return "connected" if value else "disconnected"
        if isinstance(value, dict):
            for key in ("status", "state"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip().lower()
            connected = value.get("connected")
            logged_in = value.get("loggedIn")
            if isinstance(connected, bool) or isinstance(logged_in, bool):
                return "connected" if (connected or logged_in) else "disconnected"
        return None

    candidate = _normalize(raw.get("status")) or _normalize(raw.get("instanceStatus"))
    if candidate:
        return candidate
    instance_payload = raw.get("instance") if isinstance(raw.get("instance"), dict) else {}
    return _normalize(instance_payload.get("status")) or _normalize(instance_payload.get("instanceStatus")) or _normalize(
        instance_payload
    )


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


@router.post("/connect", response_model=ConnectResponse)
def connect_whatsapp(current_user: CurrentUser = Depends(require_crm_access)):
    connection = _resolve_instance_id(current_user)
    if connection:
        instance_id = connection.get("instance_id")
    else:
        instance_id = _generate_instance_id(current_user.id)
        logger.info("whatsapp connect init user_id=%s instance_id=%s", current_user.id, instance_id)
        init_core_whatsapp_instance(current_user.id, instance_id)

    if not instance_id:
        raise HTTPException(status_code=502, detail="Falha ao obter instance_id para WhatsApp")

    logger.info("whatsapp connect user_id=%s instance_id=%s", current_user.id, instance_id)
    raw = connect_core_whatsapp_instance(current_user.id, instance_id)
    status_value = _normalize_status(raw)
    qr = _extract_qr(raw)

    return ConnectResponse(instance_id=instance_id, status=status_value, qr=qr, raw=raw)


@router.get("/status", response_model=StatusResponse)
def whatsapp_status(current_user: CurrentUser = Depends(require_crm_access)):
    connection = _resolve_instance_id(current_user)
    if not connection:
        raise HTTPException(status_code=404, detail="Conexão WhatsApp não encontrada")

    instance_id = connection.get("instance_id")
    if not instance_id:
        raise HTTPException(status_code=404, detail="instance_id não encontrado no core")

    logger.info("whatsapp status user_id=%s instance_id=%s", current_user.id, instance_id)
    raw = status_core_whatsapp_instance(instance_id)
    status_value = _normalize_status(raw) or connection.get("status")
    phone_e164 = _extract_phone(raw) or connection.get("phone_e164")

    return StatusResponse(
        instance_id=instance_id,
        status=status_value,
        phone_e164=phone_e164,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/qr/refresh", response_model=ConnectResponse)
def refresh_qr(current_user: CurrentUser = Depends(require_crm_access)):
    connection = _resolve_instance_id(current_user)
    if not connection or not connection.get("instance_id"):
        raise HTTPException(status_code=404, detail="Conexão WhatsApp não encontrada")

    instance_id = connection.get("instance_id")
    logger.info("whatsapp qr refresh user_id=%s instance_id=%s", current_user.id, instance_id)
    raw = connect_core_whatsapp_instance(current_user.id, instance_id)
    status_value = _normalize_status(raw)
    qr = _extract_qr(raw)

    return ConnectResponse(instance_id=instance_id, status=status_value, qr=qr, raw=raw)
