# backend/auth_mvp.py
import os, datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext


router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
ACCESS_MIN = int(os.getenv("ACCESS_EXPIRE_MIN", "120"))

# origem "principal" (1ª da APP_BASE_URL) decide cookies
primary = os.getenv("APP_BASE_URL", "http://localhost:5173").split(",")[0].strip()
SECURE = primary.startswith("https://")
SAMESITE = "none" if SECURE else "lax"

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_HASH = os.getenv("ADMIN_PASSWORD_HASH")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
ACCESS_COOKIE = "access_token"

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    email: EmailStr
    role: str = "admin"

def set_access_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        httponly=True,
        secure=SECURE,
        samesite=SAMESITE,
        path="/",
        max_age=ACCESS_MIN * 60,
    )

def make_access_token(sub: str) -> str:
    now = dt.datetime.utcnow()
    payload = {"sub": sub, "role": "admin", "type": "access", "iat": now, "exp": now + dt.timedelta(minutes=ACCESS_MIN)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_access(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Token inválido") from e

@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response):
    if not ADMIN_EMAIL or not ADMIN_HASH:
        raise HTTPException(500, "Credenciais de admin não configuradas (ENV).")
    if body.email.lower() != ADMIN_EMAIL.lower() or not pwd_ctx.verify(body.password, ADMIN_HASH):
        raise HTTPException(401, "Credenciais inválidas")
    token = make_access_token(ADMIN_EMAIL)
    set_access_cookie(response, token)
    return UserOut(email=ADMIN_EMAIL)

@router.get("/me", response_model=UserOut)
def me(request: Request):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(401, "Não autenticado")
    payload = decode_access(token)
    if payload.get("type") != "access":
        raise HTTPException(401, "Token inválido")
    return UserOut(email=payload.get("sub", ADMIN_EMAIL))

@router.post("/logout")
def logout(response: Response):
    # Apaga o cookie replicando atributos importantes
    response.delete_cookie(
        ACCESS_COOKIE,
        path="/",
        secure=SECURE,
        samesite=SAMESITE,
        # sem domain -> host-only (igual ao set_cookie)
    )
    return {"ok": True}