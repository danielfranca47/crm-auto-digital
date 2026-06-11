import base64
import datetime
import hashlib
import hmac
import logging
import time
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.api.auth import get_current_user
from app.config import settings
from app.db import engine
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["Google Calendar"])

_SCOPES = " ".join([
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
])


# ── Helpers ─────────────────────────────────────────────────────────────────

def _require_google_configured() -> None:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not settings.GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=503,
            detail="Google Calendar OAuth não configurado (variáveis GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI ausentes)",
        )


def _make_state(user_id: int) -> str:
    ts = int(time.time())
    payload = f"{user_id}:{ts}"
    sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _verify_state(state: str, max_age: int = 600) -> int:
    try:
        decoded = base64.urlsafe_b64decode(state.encode()).decode()
        user_id_str, ts_str, sig = decoded.split(":", 2)
        payload = f"{user_id_str}:{ts_str}"
        expected_sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()[:20]
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("bad signature")
        if int(time.time()) - int(ts_str) > max_age:
            raise ValueError("state expired")
        return int(user_id_str)
    except (HTTPException, ValueError):
        raise HTTPException(status_code=400, detail="Estado OAuth inválido ou expirado")
    except Exception:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido")


def _save_google_tokens(
    user_id: int,
    access_token: str,
    refresh_token: Optional[str],
    expiry: Optional[str],
    google_email: Optional[str],
) -> None:
    with engine.begin() as conn:
        if refresh_token:
            conn.execute(
                text(
                    "UPDATE users SET google_access_token = :at, google_refresh_token = :rt, "
                    "google_token_expiry = :exp, google_email = :ge WHERE id = :uid"
                ),
                {"at": access_token, "rt": refresh_token, "exp": expiry, "ge": google_email, "uid": user_id},
            )
        else:
            conn.execute(
                text(
                    "UPDATE users SET google_access_token = :at, "
                    "google_token_expiry = :exp WHERE id = :uid"
                ),
                {"at": access_token, "exp": expiry, "uid": user_id},
            )


def _clear_google_tokens(user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET google_access_token = NULL, google_refresh_token = NULL, "
                "google_token_expiry = NULL, google_calendar_id = NULL, google_email = NULL "
                "WHERE id = :uid"
            ),
            {"uid": user_id},
        )


def _get_user_google_data(user_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT google_access_token, google_refresh_token, google_token_expiry, "
                "google_calendar_id, google_email FROM users WHERE id = :uid"
            ),
            {"uid": user_id},
        ).fetchone()
        if not row:
            return {}
        return dict(row._mapping)


def _verify_service_token(x_service_token: Optional[str]) -> None:
    if not settings.CORE_SERVICE_TOKEN or x_service_token != settings.CORE_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


# ── Endpoints públicos / autenticados ────────────────────────────────────────

@router.get("/calendar/url")
async def get_oauth_url(current_user: User = Depends(get_current_user)):
    """Returns the Google OAuth2 authorization URL for the current user."""
    _require_google_configured()
    state = _make_state(current_user.id)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"url": url}


@router.get("/calendar/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """OAuth2 callback: troca o code por tokens e redireciona para o frontend."""
    _require_google_configured()
    frontend_url = (settings.CRM_FRONTEND_URL or "http://localhost:8080").rstrip("/")

    if error or not code or not state:
        logger.warning("google_oauth_callback_error error=%s", error)
        return RedirectResponse(url=f"{frontend_url}/minha-conta?google_error=1")

    try:
        user_id = _verify_state(state)
    except HTTPException:
        return RedirectResponse(url=f"{frontend_url}/minha-conta?google_error=1")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()
    except Exception as exc:
        logger.error("google_token_exchange_failed user_id=%s error=%s", user_id, exc)
        return RedirectResponse(url=f"{frontend_url}/minha-conta?google_error=1")

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    expiry_iso: Optional[str] = None
    if expires_in:
        expiry_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=int(expires_in))
        expiry_iso = expiry_dt.isoformat()

    google_email: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_resp.status_code == 200:
                google_email = userinfo_resp.json().get("email")
    except Exception:
        pass

    _save_google_tokens(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expiry=expiry_iso,
        google_email=google_email,
    )
    logger.info("google_calendar_connected user_id=%s email=%s", user_id, google_email)
    return RedirectResponse(url=f"{frontend_url}/minha-conta?google_connected=1")


@router.get("/calendar/status")
async def get_calendar_status(current_user: User = Depends(get_current_user)):
    """Retorna se o utilizador tem o Google Calendar conectado."""
    data = _get_user_google_data(current_user.id)
    connected = bool(data.get("google_access_token"))
    return {
        "connected": connected,
        "email": data.get("google_email") if connected else None,
    }


@router.delete("/calendar")
async def disconnect_calendar(current_user: User = Depends(get_current_user)):
    """Remove os tokens do Google Calendar do utilizador."""
    _clear_google_tokens(current_user.id)
    return {"disconnected": True}


# ── Service-to-service (backend-crm usa estes endpoints) ─────────────────────

@router.get("/tokens/{user_id}")
def get_user_tokens(
    user_id: int,
    x_service_token: Optional[str] = Header(None),
):
    """Service-to-service: devolve os tokens Google do utilizador para o backend-crm."""
    _verify_service_token(x_service_token)
    data = _get_user_google_data(user_id)
    if not data.get("google_access_token"):
        raise HTTPException(status_code=404, detail="user has no google calendar tokens")
    return {
        "access_token": data["google_access_token"],
        "refresh_token": data.get("google_refresh_token"),
        "token_expiry": data.get("google_token_expiry"),
        "calendar_id": data.get("google_calendar_id") or "primary",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
    }


@router.put("/tokens/{user_id}")
def update_user_token(
    user_id: int,
    payload: dict,
    x_service_token: Optional[str] = Header(None),
):
    """Service-to-service: actualiza o access token após refresh automático."""
    _verify_service_token(x_service_token)
    new_access_token = payload.get("access_token")
    new_expiry = payload.get("token_expiry")
    if not new_access_token:
        raise HTTPException(status_code=400, detail="access_token required")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET google_access_token = :at, google_token_expiry = :exp WHERE id = :uid"),
            {"at": new_access_token, "exp": new_expiry, "uid": user_id},
        )
    return {"updated": True}
