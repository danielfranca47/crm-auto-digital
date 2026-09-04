from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.services import uazapi_admin
from app.services import whatsapp_connections as connections_service
from app.services.email_service import (
    render_whatsapp_disconnected_email,
    render_whatsapp_reconnected_email,
    send_email,
)
from app.utils.crypto import SecretEncryptionError, decrypt_secret

router = APIRouter(prefix="", tags=["whatsapp_instances"])
logger = logging.getLogger(__name__)

_DISCONNECT_EMAIL_COOLDOWN = timedelta(minutes=30)


async def _require_service_token(x_service_token: str = Header(None)) -> str:
    expected = settings.CORE_SERVICE_TOKEN
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    return x_service_token


class InstanceInitPayload(BaseModel):
    user_id: int
    instance_id: str

    class Config:
        extra = "allow"


class InstanceConnectPayload(BaseModel):
    user_id: int
    instance_id: str

    class Config:
        extra = "allow"


class InstanceStatusPayload(BaseModel):
    instance_id: str

    class Config:
        extra = "allow"


class ConnectionEventPayload(BaseModel):
    instance_id: str
    raw: Dict[str, Any]


class WebhookPayload(BaseModel):
    url: str
    instance_id: Optional[str] = None
    instance: Optional[str] = None
    instance_token: Optional[str] = None
    events: Optional[list[str]] = None
    global_webhook: bool = Field(False, alias="globalWebhook")

    class Config:
        allow_population_by_field_name = True
        extra = "allow"


def _parse_instance_payload(
    payload: Dict[str, Any],
    *,
    fallback_instance_id: str,
) -> tuple[str, Optional[str], Optional[str]]:
    instance_id, instance_token, phone_e164 = uazapi_admin.extract_instance_details(
        payload,
        fallback_instance_id=fallback_instance_id,
    )
    if not instance_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Uazapi response missing instance id",
        )
    return instance_id, instance_token, phone_e164


def _format_admin_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in data.items()
        if value is not None
    }


def _normalize_instance_id(instance_id: str) -> str:
    normalized = instance_id.strip()
    if " " in normalized:
        normalized = re.sub(r"\s+", "-", normalized)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="instance_id inválido: use apenas letras, números, hífen ou underscore",
        )
    return normalized


def _resolve_instance_token(db: Session, instance_id: str) -> str:
    connection = connections_service.get_connection_by_instance(db, instance_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if not connection.instance_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing instance token",
        )
    try:
        return decrypt_secret(connection.instance_token_encrypted)
    except SecretEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to decrypt instance token",
        ) from exc




def _raise_uazapi_http_error(exc: uazapi_admin.UazapiAdminError) -> None:
    if exc.status_code == 429:
        headers = {}
        if exc.retry_after:
            headers["Retry-After"] = exc.retry_after
        raise HTTPException(status_code=429, detail=str(exc), headers=headers or None) from exc
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


def _log_connect_attempt(*, endpoint: str, instance_id: str, status_code: int, elapsed_ms: float) -> None:
    logger.info(
        "event=whatsapp_connect_attempt endpoint=%s instance_id=%s status=%s elapsed_ms=%.1f",
        endpoint,
        instance_id,
        status_code,
        elapsed_ms,
    )
@router.post("/whatsapp-instances/init")
async def init_instance(
    payload: InstanceInitPayload,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    admin_token = settings.UAZAPI_ADMIN_TOKEN or ""
    normalized_instance_id = _normalize_instance_id(payload.instance_id)
    payload_data = payload.dict(exclude={"user_id", "instance_id"}, exclude_unset=True)
    extra_payload = _format_admin_payload({k: v for k, v in payload_data.items() if k != "instance_id"})

    started = time.perf_counter()
    try:
        raw = await uazapi_admin.init_instance(
            base_url=base_url,
            admin_token=admin_token,
            instance_id=normalized_instance_id,
            payload=extra_payload,
        )
    except uazapi_admin.UazapiAdminError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        _log_connect_attempt(endpoint="init", instance_id=normalized_instance_id, status_code=exc.status_code or 502, elapsed_ms=elapsed_ms)
        _raise_uazapi_http_error(exc)

    elapsed_ms = (time.perf_counter() - started) * 1000
    _log_connect_attempt(endpoint="init", instance_id=normalized_instance_id, status_code=200, elapsed_ms=elapsed_ms)

    instance_id, instance_token, phone_e164 = _parse_instance_payload(
        raw, fallback_instance_id=normalized_instance_id
    )
    status_value, _, _ = uazapi_admin.extract_connection_meta(raw)
    if not isinstance(instance_id, str):
        logger.info("Uazapi init invalid instance_id payload=%s", uazapi_admin.redact_instance_token(raw))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Uazapi response invalid instance id",
        )
    if status_value is not None and not isinstance(status_value, str):
        logger.info("Uazapi init invalid status payload=%s", uazapi_admin.redact_instance_token(raw))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Uazapi response invalid status",
        )
    if not instance_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Uazapi response missing instance token",
        )

    connections_service.upsert_connection(
        db=db,
        user_id=payload.user_id,
        instance_id=instance_id,
        instance_token=instance_token,
        phone_e164=phone_e164,
        status=status_value,
        provider="uazapi",
    )
    return uazapi_admin.redact_instance_token(raw)


@router.post("/whatsapp-instances/connect")
async def connect_instance(
    payload: InstanceConnectPayload,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    normalized_instance_id = _normalize_instance_id(payload.instance_id)
    instance_token = _resolve_instance_token(db, normalized_instance_id)
    payload_data = payload.dict(exclude={"user_id", "instance_id"}, exclude_unset=True)
    extra_payload = _format_admin_payload({k: v for k, v in payload_data.items() if k != "instance_id"})

    started = time.perf_counter()
    try:
        raw = await uazapi_admin.connect_instance(
            base_url=base_url,
            instance_token=instance_token,
            instance_id=normalized_instance_id,
            payload=extra_payload,
        )
    except uazapi_admin.UazapiAdminError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        _log_connect_attempt(endpoint="connect", instance_id=normalized_instance_id, status_code=exc.status_code or 502, elapsed_ms=elapsed_ms)
        _raise_uazapi_http_error(exc)

    elapsed_ms = (time.perf_counter() - started) * 1000
    _log_connect_attempt(endpoint="connect", instance_id=normalized_instance_id, status_code=200, elapsed_ms=elapsed_ms)

    instance_id, instance_token, phone_e164 = _parse_instance_payload(
        raw, fallback_instance_id=normalized_instance_id
    )
    status_value, _, _ = uazapi_admin.extract_connection_meta(raw)
    if not isinstance(instance_id, str):
        logger.info("Uazapi connect invalid instance_id payload=%s", uazapi_admin.redact_instance_token(raw))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Uazapi response invalid instance id",
        )
    if status_value is not None and not isinstance(status_value, str):
        logger.info("Uazapi connect invalid status payload=%s", uazapi_admin.redact_instance_token(raw))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Uazapi response invalid status",
        )
    if not instance_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Uazapi response missing instance token",
        )

    connections_service.upsert_connection(
        db=db,
        user_id=payload.user_id,
        instance_id=instance_id,
        instance_token=instance_token,
        phone_e164=phone_e164,
        status=status_value,
        provider="uazapi",
    )
    return uazapi_admin.redact_instance_token(raw)


@router.get("/whatsapp-instances/status")
async def status_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    normalized_instance_id = _normalize_instance_id(instance_id)
    instance_token = _resolve_instance_token(db, normalized_instance_id)

    started = time.perf_counter()
    try:
        raw = await uazapi_admin.get_status(
            base_url=base_url,
            instance_token=instance_token,
            instance_id=normalized_instance_id,
        )
    except uazapi_admin.UazapiAdminError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        _log_connect_attempt(endpoint="status", instance_id=normalized_instance_id, status_code=exc.status_code or 502, elapsed_ms=elapsed_ms)
        _raise_uazapi_http_error(exc)

    elapsed_ms = (time.perf_counter() - started) * 1000
    _log_connect_attempt(endpoint="status", instance_id=normalized_instance_id, status_code=200, elapsed_ms=elapsed_ms)

    status_value, _, _ = uazapi_admin.extract_connection_meta(raw)

    if status_value:
        connection = connections_service.get_connection_by_instance(db, normalized_instance_id)
        if connection:
            connection.status = status_value
            db.add(connection)
            db.commit()
            db.refresh(connection)

    return uazapi_admin.redact_instance_token(raw)


@router.post("/whatsapp-instances/connection-event")
async def connection_event(
    payload: ConnectionEventPayload,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    """Recebe o evento 'connection' repassado pelo backend-crm a partir do
    webhook da UazAPI. Actualiza o status real da conexão e, se a transição
    for de activa para inactiva, avisa o dono da conta por email para
    reconectar (ver docs/implementations/alerta-desconexao-whatsapp.md)."""
    normalized_instance_id = _normalize_instance_id(payload.instance_id)
    connection = connections_service.get_connection_by_instance(db, normalized_instance_id)
    if not connection:
        return {"status": "ignored", "reason": "connection_not_found"}

    status_value, _, _ = uazapi_admin.extract_connection_meta(payload.raw)
    if not status_value:
        logger.info(
            "connection_event status not found instance_id=%s payload=%s",
            normalized_instance_id,
            uazapi_admin.redact_instance_token(payload.raw),
        )
        return {"status": "ignored", "reason": "status_not_found"}

    was_active = connections_service.normalize_connection_status_for_crm(connection.status) == "active"
    is_active = connections_service.normalize_connection_status_for_crm(status_value) == "active"

    connection.status = status_value
    db.add(connection)
    db.commit()
    db.refresh(connection)

    logger.info(
        "connection_event instance_id=%s status=%s was_active=%s is_active=%s",
        normalized_instance_id,
        status_value,
        was_active,
        is_active,
    )

    if was_active and not is_active:
        now = datetime.utcnow()
        last_email_at = connection.last_disconnect_email_at
        cooldown_expired = last_email_at is None or (now - last_email_at) >= _DISCONNECT_EMAIL_COOLDOWN

        if cooldown_expired:
            try:
                user = db.query(models.User).filter(models.User.id == connection.user_id).first()
                if user and user.email:
                    login_url = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/ai-profile"
                    html, text = render_whatsapp_disconnected_email(user.name, login_url)
                    send_email(
                        to=user.email,
                        subject="A tua Lara desconectou do WhatsApp — reconecta agora",
                        html=html,
                        text=text,
                    )
                connection.last_disconnect_email_at = now
            except Exception as exc:
                logger.warning(
                    "connection_event: falha ao enviar email de desconexão user_id=%s error=%s",
                    connection.user_id,
                    exc,
                )
        else:
            logger.info(
                "connection_event: cooldown ativo, email de desconexão suprimido instance_id=%s last_email_at=%s",
                normalized_instance_id,
                last_email_at,
            )

        connection.disconnect_alert_sent_at = now
        db.add(connection)
        db.commit()

    if not was_active and is_active and connection.disconnect_alert_sent_at:
        disconnect_email_was_sent = (
            connection.last_disconnect_email_at is not None
            and connection.last_disconnect_email_at >= connection.disconnect_alert_sent_at
        )
        if disconnect_email_was_sent:
            try:
                user = db.query(models.User).filter(models.User.id == connection.user_id).first()
                if user and user.email:
                    login_url = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/ai-profile"
                    html, text = render_whatsapp_reconnected_email(user.name, login_url)
                    send_email(
                        to=user.email,
                        subject="A tua Lara reconectou ao WhatsApp",
                        html=html,
                        text=text,
                    )
            except Exception as exc:
                logger.warning(
                    "connection_event: falha ao enviar email de reconexão user_id=%s error=%s",
                    connection.user_id,
                    exc,
                )
        else:
            logger.info(
                "connection_event: email de reconexão suprimido (desconexão correspondente também foi suprimida) instance_id=%s",
                normalized_instance_id,
            )
        connection.disconnect_alert_sent_at = None
        db.add(connection)
        db.commit()

    return {"status": "ok", "connection_status": status_value}


@router.post("/whatsapp-instances/webhook")
async def configure_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    admin_token = settings.UAZAPI_ADMIN_TOKEN or ""
    payload_data = payload.dict(
        by_alias=True,
        exclude_unset=True,
    )
    instance_id = payload.instance_id or payload.instance
    instance_token = payload.instance_token
    if not payload.global_webhook:
        if not instance_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="instance_id obrigatório para webhook por instância",
            )
        normalized_instance_id = _normalize_instance_id(instance_id)
        instance_id = normalized_instance_id
        if not instance_token:
            instance_token = _resolve_instance_token(db, normalized_instance_id)
    extra_payload = _format_admin_payload(
        {
            key: value
            for key, value in payload_data.items()
            if key not in {"url", "instance_id", "instance", "instance_token", "events", "globalWebhook"}
        }
    )

    try:
        raw = await uazapi_admin.configure_webhook(
            base_url=base_url,
            admin_token=admin_token,
            url=payload.url,
            instance_id=instance_id,
            events=payload.events,
            global_webhook=payload.global_webhook,
            instance_token=instance_token,
            payload=extra_payload,
        )
    except uazapi_admin.UazapiAdminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return uazapi_admin.redact_instance_token(raw)
