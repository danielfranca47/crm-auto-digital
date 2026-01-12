from __future__ import annotations

import logging
import re
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


def _mask_number(value: str) -> str:
    if not value:
        return ""
    suffix = value[-4:] if len(value) > 4 else value
    return f"***{suffix}"


@router.post("/whatsapp/send", response_model=WhatsAppSendResponse)
async def send_whatsapp(
    payload: WhatsAppSendRequest,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    provider = (payload.provider or "").lower()
    if provider != "uazapi":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="provider_not_supported")

    connection = connections_service.get_connection_by_instance(db, payload.instance_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if connection.status != "active":
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
