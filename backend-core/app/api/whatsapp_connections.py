from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.services import whatsapp_connections as service
from .auth import get_current_user

router = APIRouter(prefix="", tags=["whatsapp_connections"])


class WhatsappConnectionBase(BaseModel):
    instance_id: str
    phone_e164: Optional[str] = None
    status: Optional[str] = "active"


class WhatsappConnectionCreate(WhatsappConnectionBase):
    instance_token: str
    provider: Optional[str] = "uazapi"


class WhatsappConnectionOut(BaseModel):
    id: int
    user_id: int
    provider: str
    instance_id: str
    phone_e164: Optional[str]
    status: str
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


@router.get("/whatsapp-connections/resolve", response_model=ResolveResponse)
async def resolve_connection(
    instance_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    connection = service.get_connection_by_instance(db, instance_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    allow = service.allow_orion(db, connection.user_id)

    return ResolveResponse(
        user_id=connection.user_id,
        provider=connection.provider,
        connection_status=connection.status,
        phone_e164=connection.phone_e164,
        allow_orion=allow,
    )
