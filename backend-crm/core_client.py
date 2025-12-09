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
