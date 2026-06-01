from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.api.auth import create_access_token
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()

ADMIN_TOKEN_EXPIRE_HOURS = 8


class AdminLoginRequest(BaseModel):
    secret: str


class AdminToken(BaseModel):
    access_token: str
    token_type: str


class UserAdminOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    status: str
    created_at: datetime
    enabled_extensions: Optional[List[str]] = None
    plan_name: Optional[str] = None
    plan_code: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_period_end: Optional[datetime] = None

    class Config:
        orm_mode = True


class ExtensionsUpdate(BaseModel):
    enabled_extensions: List[str]


class CreateUserRequest(BaseModel):
    email: str
    name: Optional[str] = None


@router.post("/login", response_model=AdminToken)
async def admin_login(body: AdminLoginRequest):
    if not settings.ADMIN_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin não configurado")
    if body.secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    token = create_access_token(
        data={"sub": "admin", "role": "admin"},
        expires_delta=timedelta(hours=ADMIN_TOKEN_EXPIRE_HOURS),
    )
    return {"access_token": token, "token_type": "bearer"}


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Acesso negado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        role: str = payload.get("role")
        token_type: str = payload.get("type")
        if role != "admin" or token_type != "access":
            raise exc
    except JWTError:
        raise exc
    return payload


@router.get("/users", response_model=List[UserAdminOut])
async def admin_list_users(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    query = db.query(models.User)
    if search:
        query = query.filter(
            models.User.email.ilike(f"%{search}%") | models.User.name.ilike(f"%{search}%")
        )
    users = query.order_by(models.User.id).limit(200).all()

    result = []
    for u in users:
        profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == u.id).first()
        sub = (
            db.query(models.Subscription)
            .filter(
                models.Subscription.user_id == u.id,
                models.Subscription.status == "active",
            )
            .first()
        )
        result.append(UserAdminOut(
            id=u.id,
            email=u.email,
            name=u.name,
            status=u.status,
            created_at=u.created_at,
            enabled_extensions=profile.enabled_extensions if profile else None,
            plan_name=sub.plan.name if sub and sub.plan else None,
            plan_code=sub.plan.code if sub and sub.plan else None,
            subscription_status=sub.status if sub else None,
            subscription_period_end=sub.current_period_end if sub else None,
        ))
    return result


@router.patch("/users/{user_id}/extensions")
async def admin_set_extensions(
    user_id: int,
    payload: ExtensionsUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    from datetime import datetime
    profile.enabled_extensions = payload.enabled_extensions
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return {"ok": True, "enabled_extensions": profile.enabled_extensions}


@router.get("/stats")
async def admin_get_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
) -> Dict[str, Any]:
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    active_subs = (
        db.query(func.count(models.Subscription.id))
        .filter(models.Subscription.status == "active")
        .scalar()
        or 0
    )
    instances_total = db.query(func.count(models.WhatsappConnection.id)).scalar() or 0
    instances_online = (
        db.query(func.count(models.WhatsappConnection.id))
        .filter(models.WhatsappConnection.status.in_(["active", "connected"]))
        .scalar()
        or 0
    )
    instances_offline = instances_total - instances_online

    subs_by_plan = (
        db.query(models.Plan.name, func.count(models.Subscription.id).label("count"))
        .join(models.Subscription, models.Subscription.plan_id == models.Plan.id)
        .filter(models.Subscription.status == "active")
        .group_by(models.Plan.name)
        .all()
    )

    return {
        "total_users": total_users,
        "active_subscriptions": active_subs,
        "instances_total": instances_total,
        "instances_online": instances_online,
        "instances_offline": instances_offline,
        "subscriptions_by_plan": [{"plan": r[0], "count": r[1]} for r in subs_by_plan],
    }


@router.get("/instances")
async def admin_list_instances(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
) -> List[Dict[str, Any]]:
    connections = (
        db.query(models.WhatsappConnection)
        .join(models.User, models.User.id == models.WhatsappConnection.user_id)
        .order_by(models.WhatsappConnection.updated_at.desc())
        .all()
    )
    return [
        {
            "id": conn.id,
            "instance_id": conn.instance_id,
            "user_id": conn.user_id,
            "user_email": conn.user.email,
            "phone_e164": conn.phone_e164,
            "provider": conn.provider,
            "status": conn.status,
            "created_at": conn.created_at.isoformat() if conn.created_at else None,
            "updated_at": conn.updated_at.isoformat() if conn.updated_at else None,
        }
        for conn in connections
    ]


@router.post("/instances/{instance_id}/reconnect")
async def admin_reconnect_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
) -> Dict[str, Any]:
    conn = (
        db.query(models.WhatsappConnection)
        .filter(models.WhatsappConnection.instance_id == instance_id)
        .first()
    )
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instância não encontrada")

    if not settings.UAZAPI_BASE_URL:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="UAZAPI_BASE_URL não configurado")

    try:
        from app.services.uazapi_admin import connect_instance, redact_instance_token
        from app.utils.crypto import decrypt_secret

        plain_token = decrypt_secret(conn.instance_token_encrypted)
        result = await connect_instance(
            base_url=settings.UAZAPI_BASE_URL,
            instance_token=plain_token,
            instance_id=conn.instance_id,
        )
        return {"ok": True, "result": redact_instance_token(result)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
) -> Dict[str, Any]:
    """Admin cria conta para um cliente. Gera senha temporária e envia por email."""
    import secrets as _secrets
    from app.api.auth import get_password_hash

    existing = db.query(models.User).filter(models.User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email já registado")

    # Gera senha temporária legível (ex.: xK9mP2aQ)
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    temp_password = "".join(_secrets.choice(alphabet) for _ in range(8))

    new_user = models.User(
        email=body.email,
        name=body.name,
        password_hash=get_password_hash(temp_password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    email_sent = False
    try:
        from app.services.email_service import render_welcome_email, send_email
        base_url = (settings.CRM_PUBLIC_BASE_URL or "http://localhost:8080").rstrip("/")
        login_url = f"{base_url}/login"
        html, text = render_welcome_email(body.name, temp_password, login_url)
        send_email(
            to=body.email,
            subject="Bem-vindo ao AutoDigital CRM — acesso criado",
            html=html,
            text=text,
        )
        email_sent = True
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Erro ao enviar email de boas-vindas: %s", exc)

    return {
        "ok": True,
        "user_id": new_user.id,
        "email": new_user.email,
        "email_sent": email_sent,
    }
