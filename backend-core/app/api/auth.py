import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    status: str
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        token_type: str = payload.get("type")
        if user_id is None or email is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    new_user = models.User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        name=user_in.name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    try:
        from app.services.email_service import render_register_welcome_email, send_email
        login_url = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/login"
        html, text = render_register_welcome_email(new_user.name, login_url)
        send_email(to=new_user.email, subject="Bem-vindo ao Digital Pro", html=html, text=text)
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning("Email de boas-vindas não enviado: %s", exc)

    return new_user


@router.post("/login", response_model=Token)
async def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ── Password reset ────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


RESET_TOKEN_TTL_HOURS = 2


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Envia email com link de recuperação. Sempre retorna 200 para não revelar se o email existe."""
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user:
        return {"ok": True}

    # Invalidar tokens anteriores não usados para este utilizador
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id,
        models.PasswordResetToken.used_at == None,  # noqa: E711
    ).delete()

    token_value = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=RESET_TOKEN_TTL_HOURS)
    token = models.PasswordResetToken(
        user_id=user.id,
        token=token_value,
        expires_at=expires,
    )
    db.add(token)
    db.commit()

    try:
        from app.services.email_service import render_reset_email, send_email
        base_url = (settings.CRM_FRONTEND_URL or "http://localhost:8080").rstrip("/")
        reset_url = f"{base_url}/reset-password?token={token_value}"
        html, text = render_reset_email(reset_url)
        send_email(to=user.email, subject="Recuperação de senha — Digital Pro", html=html, text=text)
    except Exception as exc:
        # Não falha a request se o email não conseguir enviar — o token já foi criado
        import logging
        logging.getLogger(__name__).error("Erro ao enviar email de reset: %s", exc)

    return {"ok": True}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == body.token,
    ).first()

    if not token or token.used_at is not None or token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link expirado ou inválido",
        )

    user = db.query(models.User).filter(models.User.id == token.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilizador não encontrado")

    user.password_hash = get_password_hash(body.new_password)
    token.used_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    body: ChangePasswordRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta",
        )
    current_user.password_hash = get_password_hash(body.new_password)
    db.commit()
    return {"ok": True}
