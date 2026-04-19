from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
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
    enabled_extensions: Optional[List[str]] = None

    class Config:
        orm_mode = True


class ExtensionsUpdate(BaseModel):
    enabled_extensions: List[str]


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
        query = query.filter(models.User.email.ilike(f"%{search}%"))
    users = query.order_by(models.User.id).limit(200).all()

    result = []
    for u in users:
        profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == u.id).first()
        result.append(UserAdminOut(
            id=u.id,
            email=u.email,
            name=getattr(u, "name", None),
            enabled_extensions=profile.enabled_extensions if profile else None,
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
