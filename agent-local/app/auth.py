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
