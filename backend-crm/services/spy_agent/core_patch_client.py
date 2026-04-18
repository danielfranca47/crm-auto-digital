from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

CORE_API_BASE = os.getenv("CORE_API_BASE", "").rstrip("/")


def patch_ai_profile_via_service(user_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aplica PATCH parcial no AI Profile de um usuário via service token (server-to-server).
    Usa o endpoint PATCH /ai-profiles/patch-by-user/{user_id} do backend-core.
    """
    if not CORE_API_BASE:
        raise RuntimeError("CORE_API_BASE não configurado")

    service_token = os.getenv("CORE_SERVICE_TOKEN")
    if not service_token:
        raise RuntimeError("CORE_SERVICE_TOKEN não configurado")

    url = f"{CORE_API_BASE}/ai-profiles/patch-by-user/{user_id}"
    headers = {
        "X-Service-Token": service_token,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.patch(url, json=fields, headers=headers)
    except httpx.RequestError as exc:
        logger.error("[spy_agent:patch] network error user_id=%s: %s", user_id, exc)
        raise RuntimeError(f"Falha ao contatar backend-core: {exc}") from exc

    if not resp.is_success:
        logger.error("[spy_agent:patch] status=%s body=%s user_id=%s", resp.status_code, resp.text[:200], user_id)
        raise RuntimeError(f"Falha ao atualizar AI Profile: HTTP {resp.status_code}")

    return resp.json()
