from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.providers import uazapi_client
from app.services import whatsapp_connections as connections_service
from app.utils.crypto import SecretEncryptionError, decrypt_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["whatsapp_send"])


class WhatsAppSendRequest(BaseModel):
    provider: str = Field(default="uazapi")
    instance_id: str
    number: str
    text: str
    in_reply_to_message_id: Optional[str] = None
    delay_ms: int = 0


class WhatsAppSendMediaRequest(BaseModel):
    provider: str = Field(default="uazapi")
    instance_id: str
    number: str
    media_url: str
    media_type: str = Field(default="image")  # image | video | audio | document
    caption: Optional[str] = None
    delay_ms: int = 0


class WhatsAppSendResponse(BaseModel):
    provider: str
    provider_message_id: Optional[str]
    raw: Dict[str, Any]


def _require_service_token(x_service_token: str = Header(None)) -> str:
    expected = settings.CORE_SERVICE_TOKEN
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    return x_service_token


def _sanitize_number(value: str) -> str:
    return re.sub(r"[\s\-\+\(\)]", "", value or "")


_E164_DIGITS_RE = re.compile(r"^[1-9]\d{7,14}$")


def _is_valid_e164_digits(sanitized: str) -> bool:
    """Valida o número já sanitizado (sem '+', só dígitos) como E.164: 8 a 15
    dígitos, sem zero à esquerda — mesma faixa usada por
    backend-crm/services/phone_normalizer.py. Não reimplementa a normalização
    completa (country code, regra do 9º dígito BR); é só uma checagem de
    guarda antes da chamada paga à UazAPI.
    """
    return bool(_E164_DIGITS_RE.fullmatch(sanitized))


def _mask_number(value: str) -> str:
    if not value:
        return ""
    suffix = value[-4:] if len(value) > 4 else value
    return f"***{suffix}"


def _build_stub_message_id() -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    token = secrets.token_hex(3)
    return f"stub-{timestamp}-{token}"


@router.post("/whatsapp/send", response_model=WhatsAppSendResponse)
async def send_whatsapp(
    payload: WhatsAppSendRequest,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    provider = (payload.provider or "uazapi").lower()
    if provider != "uazapi":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="provider_not_supported")

    if settings.core_whatsapp_stub:
        logger.info(
            "whatsapp stub enabled provider=%s instance_id=%s number=%s",
            provider,
            payload.instance_id,
            _mask_number(_sanitize_number(payload.number)),
        )
        return WhatsAppSendResponse(
            provider=provider,
            provider_message_id=_build_stub_message_id(),
            raw={"stub": True, "status": "ok", "echo": payload.dict()},
        )

    connection = connections_service.get_connection_by_instance(db, payload.instance_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    normalized_status = connections_service.normalize_connection_status_for_crm(connection.status)
    if normalized_status != "active":
        logger.info(
            "whatsapp send blocked connection_status=%s normalized_status=%s",
            connection.status,
            normalized_status,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Connection inactive")

    try:
        token_plain = decrypt_secret(connection.instance_token_encrypted)
    except SecretEncryptionError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to decrypt instance token",
        )

    base_url = settings.UAZAPI_BASE_URL or ""
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="UAZAPI_BASE_URL not configured",
        )

    sanitized_number = _sanitize_number(payload.number)
    if not _is_valid_e164_digits(sanitized_number):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_number_format")
    logger.info(
        "whatsapp send provider=%s instance_id=%s number=%s",
        provider,
        payload.instance_id,
        _mask_number(sanitized_number),
    )

    try:
        raw = await uazapi_client.send_text(
            base_url=base_url,
            token=token_plain,
            number=sanitized_number,
            text=payload.text,
            delay_ms=payload.delay_ms,
        )
    except uazapi_client.UazapiTimeoutError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="provider_timeout")
    except uazapi_client.UazapiClientError as exc:
        if exc.status_code in {401, 403}:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="provider_auth_failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="provider_request_failed")

    provider_message_id = None
    if isinstance(raw, dict):
        provider_message_id = raw.get("messageid") or raw.get("id")

    return WhatsAppSendResponse(
        provider=provider,
        provider_message_id=provider_message_id,
        raw=raw,
    )


@router.post("/whatsapp/send-media", response_model=WhatsAppSendResponse)
async def send_whatsapp_media(
    payload: WhatsAppSendMediaRequest,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    provider = (payload.provider or "uazapi").lower()
    if provider != "uazapi":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="provider_not_supported")

    if settings.core_whatsapp_stub:
        logger.info(
            "whatsapp media stub enabled provider=%s instance_id=%s number=%s media_type=%s",
            provider,
            payload.instance_id,
            _mask_number(_sanitize_number(payload.number)),
            payload.media_type,
        )
        return WhatsAppSendResponse(
            provider=provider,
            provider_message_id=_build_stub_message_id(),
            raw={"stub": True, "status": "ok", "echo": payload.dict()},
        )

    connection = connections_service.get_connection_by_instance(db, payload.instance_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    normalized_status = connections_service.normalize_connection_status_for_crm(connection.status)
    if normalized_status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Connection inactive")

    try:
        token_plain = decrypt_secret(connection.instance_token_encrypted)
    except SecretEncryptionError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to decrypt instance token",
        )

    base_url = settings.UAZAPI_BASE_URL or ""
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="UAZAPI_BASE_URL not configured",
        )

    sanitized_number = _sanitize_number(payload.number)
    if not _is_valid_e164_digits(sanitized_number):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_number_format")
    logger.info(
        "whatsapp send-media provider=%s instance_id=%s number=%s media_type=%s",
        provider,
        payload.instance_id,
        _mask_number(sanitized_number),
        payload.media_type,
    )

    try:
        raw = await uazapi_client.send_media(
            base_url=base_url,
            token=token_plain,
            number=sanitized_number,
            media_url=payload.media_url,
            media_type=payload.media_type,
            caption=payload.caption or "",
            delay_ms=payload.delay_ms,
        )
    except uazapi_client.UazapiTimeoutError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="provider_timeout")
    except uazapi_client.UazapiClientError as exc:
        if exc.status_code in {401, 403}:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="provider_auth_failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="provider_request_failed")

    provider_message_id = None
    if isinstance(raw, dict):
        provider_message_id = raw.get("messageid") or raw.get("id")

    return WhatsAppSendResponse(
        provider=provider,
        provider_message_id=provider_message_id,
        raw=raw,
    )
