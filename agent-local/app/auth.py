"""Autenticação contra o backend-core: login, registo, verificação de assinatura."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests


class AuthError(Exception):
    pass


def _get_core_url() -> str:
    """URL do backend-core. Pode ser sobrescrito via CORE_BASE_URL ou config.json."""
    if url := os.environ.get("CORE_BASE_URL"):
        return url.rstrip("/")

    config_file = Path(__file__).parent.parent / "config.json"
    if config_file.exists():
        import json
        try:
            cfg = json.loads(config_file.read_text(encoding="utf-8"))
            if cfg.get("core_base_url"):
                return cfg["core_base_url"].rstrip("/")
        except Exception:
            pass

    return "http://localhost:8001"


def login(email: str, password: str) -> dict:
    """Autentica com email+senha. Retorna dict com access_token, subscription_status, name, email."""
    base = _get_core_url()
    try:
        resp = requests.post(
            f"{base}/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
    except requests.ConnectionError:
        raise AuthError("Não foi possível conectar ao servidor. Verifique a sua ligação à internet.")
    except requests.Timeout:
        raise AuthError("O servidor demorou demasiado a responder. Tente novamente.")

    if resp.status_code == 401:
        raise AuthError("Email ou senha incorretos.")
    if resp.status_code == 400:
        detail = resp.json().get("detail", "Dados inválidos.")
        raise AuthError(detail)
    if not resp.ok:
        raise AuthError(f"Erro do servidor ({resp.status_code}). Tente mais tarde.")

    token = resp.json()["access_token"]
    entitlements = check_subscription(token)

    name = _get_user_name(token, base) or email.split("@")[0]

    return {
        "access_token": token,
        "subscription_status": entitlements["subscription_status"],
        "name": name,
        "email": email,
    }


def register(name: str, email: str, password: str, whatsapp: str) -> dict:
    """Cria conta no backend-core. Retorna dict com access_token, subscription_status, name, email."""
    base = _get_core_url()
    try:
        resp = requests.post(
            f"{base}/auth/register",
            json={"name": name, "email": email, "password": password},
            timeout=15,
        )
    except requests.ConnectionError:
        raise AuthError("Não foi possível conectar ao servidor. Verifique a sua ligação à internet.")
    except requests.Timeout:
        raise AuthError("O servidor demorou demasiado a responder. Tente novamente.")

    if resp.status_code == 400:
        detail = resp.json().get("detail", "Dados inválidos.")
        if "already registered" in detail.lower():
            raise AuthError("Este email já está registado. Faça login.")
        raise AuthError(detail)
    if not resp.ok:
        raise AuthError(f"Erro ao criar conta ({resp.status_code}). Tente mais tarde.")

    token_data = login(email, password)
    token_data["whatsapp"] = whatsapp
    return token_data


def check_subscription(token: str) -> dict:
    """Verifica entitlements. Retorna {'subscription_status': 'active'|'inactive'|'expired'}."""
    base = _get_core_url()
    try:
        resp = requests.get(
            f"{base}/me/entitlements",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except requests.ConnectionError:
        raise AuthError("Sem ligação ao servidor.")
    except requests.Timeout:
        raise AuthError("Timeout ao verificar assinatura.")

    if resp.status_code == 401:
        raise AuthError("Sessão expirada. Faça login novamente.")
    if not resp.ok:
        raise AuthError(f"Erro ao verificar assinatura ({resp.status_code}).")

    data = resp.json()
    return {"subscription_status": data.get("subscription_status", "inactive")}


# ── Passwordless (OTP) ────────────────────────────────────────────────────────

def request_access(email: str) -> dict:
    """Verifica se email existe. Retorna {'status': 'existing_user'|'new_user'}."""
    base = _get_core_url()
    try:
        resp = requests.post(
            f"{base}/auth/request-access",
            json={"email": email},
            timeout=15,
        )
    except requests.ConnectionError:
        raise AuthError("Sem ligação ao servidor. Verifique a internet.")
    except requests.Timeout:
        raise AuthError("O servidor demorou a responder. Tente novamente.")

    if not resp.ok:
        detail = resp.json().get("detail", "Erro do servidor.")
        raise AuthError(detail)

    return resp.json()


def register_passwordless(name: str, email: str, whatsapp: str, sector: str) -> dict:
    """Cria conta sem senha e solicita envio de OTP. Retorna {'status': 'ok'}."""
    base = _get_core_url()
    try:
        resp = requests.post(
            f"{base}/auth/register-passwordless",
            json={"name": name, "email": email, "whatsapp": whatsapp or None, "sector": sector or None},
            timeout=15,
        )
    except requests.ConnectionError:
        raise AuthError("Sem ligação ao servidor.")
    except requests.Timeout:
        raise AuthError("Timeout. Tente novamente.")

    if not resp.ok:
        detail = resp.json().get("detail", "Erro ao criar conta.")
        raise AuthError(detail)

    return resp.json()


def verify_otp(email: str, code: str) -> dict:
    """Valida OTP e retorna sessão completa (access_token, subscription_status, name, email)."""
    base = _get_core_url()
    try:
        resp = requests.post(
            f"{base}/auth/verify-otp",
            json={"email": email, "code": code},
            timeout=15,
        )
    except requests.ConnectionError:
        raise AuthError("Sem ligação ao servidor.")
    except requests.Timeout:
        raise AuthError("Timeout. Tente novamente.")

    if resp.status_code == 400:
        raise AuthError(resp.json().get("detail", "Código inválido ou expirado."))
    if not resp.ok:
        raise AuthError(f"Erro do servidor ({resp.status_code}).")

    body = resp.json()
    token = body["access_token"]
    entitlements = check_subscription(token)
    name = _get_user_name(token, base) or email.split("@")[0]

    result = {
        "access_token": token,
        "subscription_status": entitlements["subscription_status"],
        "name": name,
        "email": email,
    }
    if body.get("refresh_token"):
        result["refresh_token"] = body["refresh_token"]
    return result


def refresh_access_token(refresh_token: str) -> str:
    """Troca um refresh token (30d) por um novo access token (24h). Silencioso."""
    base = _get_core_url()
    try:
        resp = requests.post(
            f"{base}/auth/token/refresh",
            json={"refresh_token": refresh_token},
            timeout=15,
        )
    except requests.ConnectionError:
        raise AuthError("Sem ligação ao servidor.")
    except requests.Timeout:
        raise AuthError("Timeout ao renovar sessão.")

    if resp.status_code == 401:
        raise AuthError("Sessão expirada. Faça login novamente.")
    if not resp.ok:
        raise AuthError(f"Erro ao renovar sessão ({resp.status_code}).")

    return resp.json()["access_token"]


def _get_user_name(token: str, base: str) -> Optional[str]:
    try:
        resp = requests.get(
            f"{base}/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("name") or resp.json().get("email")
    except Exception:
        pass
    return None
