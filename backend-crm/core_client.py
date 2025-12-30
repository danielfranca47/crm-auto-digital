import os
from typing import Any, Dict

import httpx
from fastapi import HTTPException

CORE_API_BASE = os.getenv("CORE_API_BASE", "").rstrip("/")


def _get_core_base() -> str:
    if not CORE_API_BASE:
        raise RuntimeError("CORE_API_BASE não configurado")
    return CORE_API_BASE


def fetch_core_user(token: str) -> Dict[str, Any]:
    """
    Consulta o backend-core em /users/me usando o bearer token fornecido.
    Lança HTTPException(401) em caso de erro de autenticação ou rede.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Token ausente")

    base = _get_core_base()
    url = f"{base}/users/me"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=401, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    data = resp.json()
    if not isinstance(data, dict) or "id" not in data or "email" not in data:
        raise HTTPException(status_code=401, detail="Resposta inesperada do backend-core")

    return data


def fetch_core_entitlements(token: str) -> Dict[str, Any]:
    """
    Consulta o backend-core em /me/entitlements para recuperar status de assinatura,
    produtos e limites consolidados.
    """

    if not token:
        raise HTTPException(status_code=401, detail="Token ausente")

    base = _get_core_base()
    url = f"{base}/me/entitlements"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=401, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Falha ao validar assinatura no backend-core")

    data = resp.json()
    if not isinstance(data, dict) or "products" not in data:
        raise HTTPException(status_code=401, detail="Resposta inesperada do backend-core")

    return data


def fetch_core_ai_profile(token: str) -> Dict[str, Any] | None:
    """
    Consulta o backend-core em /ai-profiles/me para recuperar o perfil de IA do usuário.
    Retorna None em caso de 404 (perfil não configurado).
    """

    if not token:
        raise HTTPException(status_code=401, detail="Token ausente")

    base = _get_core_base()
    url = f"{base}/ai-profiles/me"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=401, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code == 404:
        return None

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Falha ao consultar AI Profile no backend-core")

    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=401, detail="Resposta inesperada do backend-core")

    return data


def _service_headers() -> Dict[str, str]:
    token = os.getenv("CORE_SERVICE_TOKEN")
    if not token:
        raise HTTPException(status_code=401, detail="CORE_SERVICE_TOKEN não configurado")
    return {"X-Service-Token": token}


def fetch_core_whatsapp_connection_resolve(instance_id: str) -> Dict[str, Any]:
    """Consulta o core para resolver o dono de uma instância WhatsApp."""

    if not instance_id:
        raise HTTPException(status_code=400, detail="instance_id obrigatório")

    base = _get_core_base()
    url = f"{base}/whatsapp-connections/resolve"
    headers = _service_headers()

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"instance_id": instance_id}, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Instância não encontrada no core")
    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Token de serviço inválido para resolver instância")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Falha ao resolver instância no core")

    data = resp.json()
    if not isinstance(data, dict) or "user_id" not in data:
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    return data
