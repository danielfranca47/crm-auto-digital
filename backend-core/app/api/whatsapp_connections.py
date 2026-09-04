from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.services import whatsapp_connections as service
from app.utils.crypto import SecretEncryptionError, decrypt_secret
from .auth import get_current_user

router = APIRouter(prefix="", tags=["whatsapp_connections"])


class WhatsappConnectionBase(BaseModel):
    instance_id: str
    phone_e164: Optional[str] = None
    status: Optional[str] = "active"


class WhatsappConnectionCreate(WhatsappConnectionBase):
    instance_token: str
    provider: Optional[str] = "uazapi"


class WhatsappConnectionUpdate(WhatsappConnectionBase):
    instance_token: Optional[str] = None
    provider: Optional[str] = "uazapi"


class WhatsappConnectionOut(BaseModel):
    id: int
    user_id: int
    provider: str
    instance_id: str
    phone_e164: Optional[str]
    status: str
    disconnect_alert_sent_at: Optional[datetime] = None
    token_masked: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ResolveResponse(BaseModel):
    user_id: int
    provider: str
    connection_status: str
    phone_e164: Optional[str] = None
    allow_orion: Optional[bool] = None
    max_ia_conversas_monthly: Optional[int] = None


class ResolveByUserResponse(ResolveResponse):
    instance_id: str


class ResolveTokenResponse(BaseModel):
    instance_id: str
    provider: str
    instance_token: str
    phone_e164: Optional[str] = None
    user_id: int


async def _require_service_token(x_service_token: str = Header(None)) -> str:
    expected = settings.CORE_SERVICE_TOKEN
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    return x_service_token


def _format_connection_response(connection: models.WhatsappConnection) -> WhatsappConnectionOut:
    return WhatsappConnectionOut(
        id=connection.id,
        user_id=connection.user_id,
        provider=connection.provider,
        instance_id=connection.instance_id,
        phone_e164=connection.phone_e164,
        status=connection.status,
        disconnect_alert_sent_at=connection.disconnect_alert_sent_at,
        token_masked=service.mask_token(connection.instance_token_encrypted),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.get("/whatsapp-connections/me", response_model=WhatsappConnectionOut)
async def get_my_whatsapp_connection(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    connection = service.get_connection_for_user(db, current_user.id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return _format_connection_response(connection)


@router.post("/whatsapp-connections/me", response_model=WhatsappConnectionOut, status_code=status.HTTP_200_OK)
async def upsert_my_whatsapp_connection(
    payload: WhatsappConnectionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing_other = service.get_connection_by_instance(db, payload.instance_id)
    if existing_other and existing_other.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instance already linked to another user",
        )

    connection = service.upsert_connection(
        db=db,
        user_id=current_user.id,
        instance_id=payload.instance_id,
        instance_token=payload.instance_token,
        phone_e164=payload.phone_e164,
        status=payload.status,
        provider=payload.provider or "uazapi",
    )
    return _format_connection_response(connection)


@router.put("/whatsapp-connections/me", response_model=WhatsappConnectionOut, status_code=status.HTTP_200_OK)
async def update_my_whatsapp_connection(
    payload: WhatsappConnectionUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing_other = service.get_connection_by_instance(db, payload.instance_id)
    if existing_other and existing_other.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instance already linked to another user",
        )

    try:
        connection = service.upsert_connection_optional_token(
            db=db,
            user_id=current_user.id,
            instance_id=payload.instance_id,
            instance_token=payload.instance_token,
            phone_e164=payload.phone_e164,
            status=payload.status,
            provider=payload.provider or "uazapi",
        )
    except ValueError as exc:
        if str(exc) == "instance_token_required":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="instance_token_required",
            )
        raise
    return _format_connection_response(connection)


@router.get("/whatsapp-connections/resolve", response_model=ResolveResponse)
async def resolve_connection(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    connection = service.get_connection_by_instance(db, instance_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    orion_limits = service.get_orion_limits(db, connection.user_id)
    connection_status = service.normalize_connection_status_for_crm(connection.status)

    return ResolveResponse(
        user_id=connection.user_id,
        provider=connection.provider,
        connection_status=connection_status,
        phone_e164=connection.phone_e164,
        allow_orion=orion_limits.get("allow_orion"),
        max_ia_conversas_monthly=orion_limits.get("max_ia_conversas_monthly"),
    )


@router.get("/whatsapp-connections/resolve-by-user", response_model=ResolveByUserResponse)
async def resolve_connection_by_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id obrigatório")

    connection = service.get_connection_for_user(db, user_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    orion_limits = service.get_orion_limits(db, connection.user_id)
    connection_status = service.normalize_connection_status_for_crm(connection.status)

    return ResolveByUserResponse(
        user_id=connection.user_id,
        provider=connection.provider,
        instance_id=connection.instance_id,
        connection_status=connection_status,
        phone_e164=connection.phone_e164,
        allow_orion=orion_limits.get("allow_orion"),
        max_ia_conversas_monthly=orion_limits.get("max_ia_conversas_monthly"),
    )


@router.get("/whatsapp-connections/resolve-token", response_model=ResolveTokenResponse)
async def resolve_connection_token(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    connection = service.get_connection_by_instance(db, instance_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    if service.normalize_connection_status_for_crm(connection.status) != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Connection inactive")

    if not connection.instance_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Missing instance token",
        )

    try:
        token_plain = decrypt_secret(connection.instance_token_encrypted)
    except SecretEncryptionError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to decrypt instance token",
        )

    return ResolveTokenResponse(
        instance_id=connection.instance_id,
        provider=connection.provider,
        instance_token=token_plain,
        phone_e164=connection.phone_e164,
        user_id=connection.user_id,
    )
