from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.config import settings
from .auth import UserOut, get_current_user

router = APIRouter(prefix="/users", tags=["users"])


async def _require_service_token(x_service_token: str = Header(None)) -> str:
    expected = settings.CORE_SERVICE_TOKEN
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    return x_service_token


class UserAdminOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    enabled_extensions: Optional[List[str]] = None

    class Config:
        orm_mode = True


@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/admin/list", response_model=List[UserAdminOut])
async def admin_list_users(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    """Admin: lista todos os usuários com seus perfis de IA (requer service token)."""
    query = db.query(models.User)
    if search:
        query = query.filter(models.User.email.ilike(f"%{search}%"))
    users = query.order_by(models.User.id).limit(100).all()

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
