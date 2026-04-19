from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.api.auth import create_access_token
from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()

ADMIN_TOKEN_EXPIRE_HOURS = 8


class AdminLoginRequest(BaseModel):
    secret: str


class AdminToken(BaseModel):
    access_token: str
    token_type: str


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
