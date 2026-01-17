from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services import uazapi_admin
from app.services import whatsapp_connections as connections_service

router = APIRouter(prefix="", tags=["whatsapp_instances"])


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


class WebhookPayload(BaseModel):
    url: str
    instance_id: Optional[str] = None
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


@router.post("/whatsapp-instances/init")
async def init_instance(
    payload: InstanceInitPayload,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    admin_token = settings.UAZAPI_ADMIN_TOKEN or ""
    payload_data = payload.dict(exclude={"user_id"}, exclude_unset=True)
    extra_payload = _format_admin_payload({k: v for k, v in payload_data.items() if k != "instance_id"})

    try:
        raw = await uazapi_admin.init_instance(
            base_url=base_url,
            admin_token=admin_token,
            instance_id=payload.instance_id,
            payload=extra_payload,
        )
    except uazapi_admin.UazapiAdminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    instance_id, instance_token, phone_e164 = _parse_instance_payload(
        raw, fallback_instance_id=payload.instance_id
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
        provider="uazapi",
    )
    return raw


@router.post("/whatsapp-instances/connect")
async def connect_instance(
    payload: InstanceConnectPayload,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    admin_token = settings.UAZAPI_ADMIN_TOKEN or ""
    payload_data = payload.dict(exclude={"user_id"}, exclude_unset=True)
    extra_payload = _format_admin_payload({k: v for k, v in payload_data.items() if k != "instance_id"})

    try:
        raw = await uazapi_admin.connect_instance(
            base_url=base_url,
            admin_token=admin_token,
            instance_id=payload.instance_id,
            payload=extra_payload,
        )
    except uazapi_admin.UazapiAdminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    instance_id, instance_token, phone_e164 = _parse_instance_payload(
        raw, fallback_instance_id=payload.instance_id
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
        provider="uazapi",
    )
    return raw


@router.get("/whatsapp-instances/status")
async def status_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    admin_token = settings.UAZAPI_ADMIN_TOKEN or ""

    try:
        raw = await uazapi_admin.get_status(
            base_url=base_url,
            admin_token=admin_token,
            instance_id=instance_id,
        )
    except uazapi_admin.UazapiAdminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    status_value = None
    if isinstance(raw, dict):
        status_value = raw.get("status") or raw.get("instanceStatus")
        if not status_value and isinstance(raw.get("instance"), dict):
            status_value = raw["instance"].get("status") or raw["instance"].get("instanceStatus")

    if status_value:
        connection = connections_service.get_connection_by_instance(db, instance_id)
        if connection:
            connection.status = status_value
            db.add(connection)
            db.commit()
            db.refresh(connection)

    return raw


@router.post("/whatsapp-instances/webhook")
async def configure_webhook(
    payload: WebhookPayload,
    _: str = Depends(_require_service_token),
):
    base_url = settings.UAZAPI_BASE_URL or ""
    admin_token = settings.UAZAPI_ADMIN_TOKEN or ""
    payload_data = payload.dict(
        by_alias=True,
        exclude_unset=True,
    )
    extra_payload = _format_admin_payload(
        {
            key: value
            for key, value in payload_data.items()
            if key not in {"url", "instance_id", "events", "globalWebhook"}
        }
    )

    try:
        raw = await uazapi_admin.configure_webhook(
            base_url=base_url,
            admin_token=admin_token,
            url=payload.url,
            instance_id=payload.instance_id,
            events=payload.events,
            global_webhook=payload.global_webhook,
            payload=extra_payload,
        )
    except uazapi_admin.UazapiAdminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return raw
