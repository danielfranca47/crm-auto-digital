import logging
import smtplib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.auth import get_current_user
from app.config import settings
from app.db import engine
from app.models.user import User
from app.utils.crypto import SecretEncryptionError, decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["SMTP Accounts"])


# ── Modelos ──────────────────────────────────────────────────────────────────

class SmtpAccountIn(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    from_name: Optional[str] = None


class SmtpAccountStatusOut(BaseModel):
    connected: bool
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    from_name: Optional[str] = None
    verified_at: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _verify_service_token(x_service_token: Optional[str]) -> None:
    if not settings.CORE_SERVICE_TOKEN or x_service_token != settings.CORE_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


def _get_user_smtp_data(user_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT smtp_host, smtp_port, smtp_username, smtp_password_encrypted, "
                "smtp_from_name, smtp_verified_at FROM users WHERE id = :uid"
            ),
            {"uid": user_id},
        ).fetchone()
        if not row:
            return {}
        return dict(row._mapping)


def _save_smtp_account(
    user_id: int,
    host: str,
    port: int,
    username: str,
    password_encrypted: str,
    from_name: Optional[str],
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET smtp_host = :host, smtp_port = :port, smtp_username = :user, "
                "smtp_password_encrypted = :pwd, smtp_from_name = :from_name, "
                "smtp_verified_at = :verified_at WHERE id = :uid"
            ),
            {
                "host": host,
                "port": str(port),
                "user": username,
                "pwd": password_encrypted,
                "from_name": from_name,
                "verified_at": datetime.utcnow().isoformat(),
                "uid": user_id,
            },
        )


def _clear_smtp_account(user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET smtp_host = NULL, smtp_port = NULL, smtp_username = NULL, "
                "smtp_password_encrypted = NULL, smtp_from_name = NULL, smtp_verified_at = NULL "
                "WHERE id = :uid"
            ),
            {"uid": user_id},
        )


def _test_smtp_login(host: str, port: int, username: str, password: str) -> None:
    """Tenta autenticar (sem enviar nada). Levanta HTTPException 400 com mensagem clara em caso de falha."""
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        try:
            server.login(username, password)
        finally:
            server.quit()
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=400,
            detail="Usuário ou senha recusados pelo servidor. Se for Gmail, confirme que a verificação em "
                   "2 etapas está ativada e use uma senha de app (não a senha normal da conta).",
        )
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Não foi possível conectar ao servidor SMTP informado: {exc}",
        )


# ── Endpoints autenticados (utilizador) ──────────────────────────────────────

@router.put("/me/smtp", response_model=SmtpAccountStatusOut)
async def save_smtp_account(
    payload: SmtpAccountIn,
    current_user: User = Depends(get_current_user),
):
    """Testa a credencial SMTP (login, sem enviar nada) e só persiste se a autenticação for bem-sucedida."""
    _test_smtp_login(payload.host, payload.port, payload.username, payload.password)

    try:
        encrypted = encrypt_secret(payload.password)
    except SecretEncryptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    _save_smtp_account(
        user_id=current_user.id,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password_encrypted=encrypted,
        from_name=payload.from_name,
    )
    logger.info("smtp_account_connected user_id=%s host=%s", current_user.id, payload.host)

    data = _get_user_smtp_data(current_user.id)
    return SmtpAccountStatusOut(
        connected=True,
        host=data.get("smtp_host"),
        port=int(data["smtp_port"]) if data.get("smtp_port") else None,
        username=data.get("smtp_username"),
        from_name=data.get("smtp_from_name"),
        verified_at=data.get("smtp_verified_at"),
    )


@router.get("/me/smtp/status", response_model=SmtpAccountStatusOut)
async def get_smtp_status(current_user: User = Depends(get_current_user)):
    data = _get_user_smtp_data(current_user.id)
    connected = bool(data.get("smtp_password_encrypted"))
    return SmtpAccountStatusOut(
        connected=connected,
        host=data.get("smtp_host") if connected else None,
        port=int(data["smtp_port"]) if connected and data.get("smtp_port") else None,
        username=data.get("smtp_username") if connected else None,
        from_name=data.get("smtp_from_name") if connected else None,
        verified_at=data.get("smtp_verified_at") if connected else None,
    )


@router.delete("/me/smtp")
async def disconnect_smtp_account(current_user: User = Depends(get_current_user)):
    _clear_smtp_account(current_user.id)
    return {"disconnected": True}


# ── Service-to-service (backend-crm/backend-executors usam este endpoint) ───

@router.get("/{user_id}/smtp-credentials", include_in_schema=False)
def get_user_smtp_credentials(
    user_id: int,
    x_service_token: Optional[str] = Header(None),
):
    """Service-to-service: devolve a credencial SMTP decriptada do usuário."""
    _verify_service_token(x_service_token)
    data = _get_user_smtp_data(user_id)
    if not data.get("smtp_password_encrypted"):
        raise HTTPException(status_code=404, detail="user has no smtp account configured")
    try:
        password = decrypt_secret(data["smtp_password_encrypted"])
    except SecretEncryptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "host": data["smtp_host"],
        "port": int(data["smtp_port"]),
        "username": data["smtp_username"],
        "password": password,
        "from_name": data.get("smtp_from_name"),
    }
