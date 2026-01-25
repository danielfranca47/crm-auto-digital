import logging
import os
from typing import Any, Dict

import httpx
from fastapi import HTTPException

CORE_API_BASE = os.getenv("CORE_API_BASE", "").rstrip("/")
logger = logging.getLogger(__name__)


def _get_core_base() -> str:
    if not CORE_API_BASE:
        raise RuntimeError("CORE_API_BASE não configurado")
    return CORE_API_BASE


def _extract_core_error(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        return str(payload)[:500]

    text = resp.text or ""
    return text.strip()[:500] or "Sem detalhes"


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


def fetch_core_ai_profile_resolve(user_id: int) -> Dict[str, Any] | None:
    """Consulta o backend-core via service token para resolver o AIProfile de um usuário."""

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id obrigatório")

    base = _get_core_base()
    url = f"{base}/ai-profiles/resolve"
    headers = _service_headers()

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"user_id": user_id}, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code == 404:
        return None
    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Token de serviço inválido para resolver AIProfile")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Falha ao resolver AIProfile no core")

    data = resp.json()
    if not isinstance(data, dict) or "user_id" not in data:
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    return data


def _service_headers() -> Dict[str, str]:
    token = os.getenv("CORE_SERVICE_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="CORE_SERVICE_TOKEN não configurado")
    return {"X-Service-Token": token}


def fetch_core_whatsapp_connection_me(token: str) -> Dict[str, Any] | None:
    """
    Consulta o backend-core em /whatsapp-connections/me para recuperar a conexão do usuário.
    Retorna None em caso de 404 (sem conexão).
    """

    if not token:
        raise HTTPException(status_code=401, detail="Token ausente")

    base = _get_core_base()
    url = f"{base}/whatsapp-connections/me"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=401, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code == 404:
        return None

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Falha ao consultar WhatsApp no backend-core")

    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=401, detail="Resposta inesperada do backend-core")

    return data


def init_core_whatsapp_instance(user_id: int, instance_id: str) -> Dict[str, Any]:
    base = _get_core_base()
    url = f"{base}/whatsapp-instances/init"
    headers = _service_headers()
    payload = {"user_id": user_id, "instance_id": instance_id}

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code >= 400:
        detail = _extract_core_error(resp)
        raise HTTPException(
            status_code=502,
            detail=f"Core WhatsApp init falhou (status={resp.status_code}): {detail}",
        )

    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    return data


def connect_core_whatsapp_instance(user_id: int, instance_id: str) -> Dict[str, Any]:
    base = _get_core_base()
    url = f"{base}/whatsapp-instances/connect"
    headers = _service_headers()
    payload = {"user_id": user_id, "instance_id": instance_id}

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code >= 400:
        detail = _extract_core_error(resp)
        raise HTTPException(
            status_code=502,
            detail=f"Core WhatsApp connect falhou (status={resp.status_code}): {detail}",
        )

    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    return data


def status_core_whatsapp_instance(instance_id: str) -> Dict[str, Any]:
    if not instance_id:
        raise HTTPException(status_code=400, detail="instance_id obrigatório")

    base = _get_core_base()
    url = f"{base}/whatsapp-instances/status"
    headers = _service_headers()
    params = {"instance_id": instance_id}

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(url, headers=headers, params=params)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code >= 400:
        detail = _extract_core_error(resp)
        raise HTTPException(
            status_code=502,
            detail=f"Core WhatsApp status falhou (status={resp.status_code}): {detail}",
        )

    data = resp.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    return data


def set_core_whatsapp_webhook(
    instance_id: str,
    url: str,
    events: list[str] | None = None,
    globalWebhook: bool = False,
    enabled: bool = True,
) -> Dict[str, Any]:
    if not instance_id:
        raise HTTPException(status_code=400, detail="instance_id obrigatório")
    if not url:
        raise HTTPException(status_code=400, detail="url obrigatório")

    payload = {
        "url": url,
        "instance_id": instance_id,
        "events": events or ["messages"],
        "globalWebhook": globalWebhook,
        "enabled": enabled,
    }

    base = _get_core_base()
    url_path = f"{base}/whatsapp-instances/webhook"
    headers = _service_headers()

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(url_path, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code == 401:
        raise HTTPException(status_code=502, detail="Token de serviço inválido para webhook WhatsApp")
    if resp.status_code >= 400:
        detail = _extract_core_error(resp)
        raise HTTPException(
            status_code=502,
            detail=f"Core WhatsApp webhook falhou (status={resp.status_code}): {detail}",
        )

    data = resp.json()
    if isinstance(data, list):
        logger.info(
            "Core WhatsApp webhook response type=list items=%s preview=%s",
            len(data),
            str(data)[:200],
        )
        return {"items": data}
    if not isinstance(data, dict):
        logger.warning(
            "Core WhatsApp webhook unexpected payload type=%s preview=%s",
            type(data).__name__,
            str(data)[:200],
        )
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    logger.info(
        "Core WhatsApp webhook response type=dict keys=%s",
        ",".join(sorted(data.keys())),
    )
    return data


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
