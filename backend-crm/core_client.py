import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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


def fetch_core_ai_profile_by_webhook_secret(secret: str) -> Dict[str, Any] | None:
    """Resolve o AI profile pelo payment_webhook_secret. Retorna None se não encontrado."""

    if not secret:
        return None

    base = _get_core_base()
    url = f"{base}/ai-profiles/resolve-by-secret"
    headers = _service_headers()

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"token": secret}, headers=headers)
    except httpx.RequestError as exc:
        logger.warning("fetch_core_ai_profile_by_webhook_secret network_error=%s", exc)
        return None

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        logger.warning("fetch_core_ai_profile_by_webhook_secret status=%s", resp.status_code)
        return None

    data = resp.json()
    if not isinstance(data, dict) or "user_id" not in data:
        return None
    return data


def fetch_core_ai_profile_by_id(ai_profile_id: int, user_id: int) -> Dict[str, Any]:
    """
    Busca um AiProfile específico pelo ID via service token.
    Valida que pertence ao user_id — lança HTTPException(403) se não pertencer.
    Lança HTTPException(404) se não encontrado.
    """
    if not ai_profile_id:
        raise HTTPException(status_code=400, detail="ai_profile_id obrigatório")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id obrigatório")

    base = _get_core_base()
    url = f"{base}/ai-profiles/{ai_profile_id}"
    headers = _service_headers()

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers, params={"user_id": user_id})
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="AI Profile não encontrado")
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="ai_profile_id não pertence ao utilizador")
    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Token de serviço inválido para consultar AIProfile")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Falha ao consultar AIProfile no core")

    data = resp.json()
    if not isinstance(data, dict) or "user_id" not in data:
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
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




def _raise_whatsapp_core_error(resp: httpx.Response, action: str) -> None:
    detail = _extract_core_error(resp)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
        headers = {"Retry-After": retry_after} if retry_after else None
        raise HTTPException(
            status_code=429,
            detail=f"Core WhatsApp {action} falhou (status=429): {detail}",
            headers=headers,
        )
    raise HTTPException(
        status_code=502,
        detail=f"Core WhatsApp {action} falhou (status={resp.status_code}): {detail}",
    )
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
        _raise_whatsapp_core_error(resp, "init")

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
        _raise_whatsapp_core_error(resp, "connect")

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
        _raise_whatsapp_core_error(resp, "status")

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
    exclude_messages: list[str] | None = None,
    include_messages: list[str] | None = None,
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
    if exclude_messages is not None:
        payload["excludeMessages"] = exclude_messages
    if include_messages is not None:
        payload["includeMessages"] = include_messages

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


def validate_admin_token(token: str) -> bool:
    """Valida um JWT de admin chamando /admin/stats no backend-core. Retorna True se válido."""
    if not token:
        return False
    base = _get_core_base()
    url = f"{base}/admin/stats"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
        return resp.status_code == 200
    except httpx.RequestError:
        return False


_admin_bearer = HTTPBearer(auto_error=False)


async def require_crm_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_admin_bearer),
) -> dict:
    """Dependency FastAPI: valida JWT de admin via backend-core."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authorization header ausente")
    if not validate_admin_token(credentials.credentials):
        raise HTTPException(
            status_code=401,
            detail="Acesso negado — JWT admin inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"token": credentials.credentials}


def fetch_core_admin_ai_profiles() -> List[Dict[str, Any]]:
    """Busca todos os AI profiles via service token (usado pelo admin do CRM)."""
    base = _get_core_base()
    url = f"{base}/ai-profiles/admin/all"
    headers = _service_headers()
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Falha ao listar AI profiles no core")
    data = resp.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    return data


def fetch_core_admin_ai_profile_user(user_id: int) -> Dict[str, Any] | None:
    """Busca o AI profile de um usuário via service token para uso no admin do CRM."""
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
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Falha ao buscar AI profile no core")
    data = resp.json()
    return data if isinstance(data, dict) else None


def fetch_core_admin_users() -> List[Dict[str, Any]]:
    """Busca lista de usuários (id, email, name) via service token para cruzar com AI profiles."""
    base = _get_core_base()
    url = f"{base}/users/admin/list"
    headers = _service_headers()
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data if isinstance(data, list) else []


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


def fetch_core_whatsapp_token(instance_id: str) -> Optional[str]:
    """Resolve o instance_token (decriptado) de uma conexão WhatsApp pelo instance_id.
    Retorna None se a instância não existir ou não tiver token."""
    if not instance_id:
        return None
    base = _get_core_base()
    url = f"{base}/whatsapp-connections/resolve-token"
    headers = _service_headers()
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"instance_id": instance_id}, headers=headers)
    except httpx.RequestError:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data.get("instance_token") if isinstance(data, dict) else None


def fetch_core_whatsapp_connection_by_user(user_id: int) -> Dict[str, Any]:
    """Consulta o core para resolver a conexão WhatsApp atual pelo user_id."""

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id obrigatório")

    base = _get_core_base()
    url = f"{base}/whatsapp-connections/resolve-by-user"
    headers = _service_headers()

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"user_id": user_id}, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao contatar backend-core: {exc}") from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Conexão WhatsApp não encontrada para o usuário")
    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="Token de serviço inválido para resolver conexão WhatsApp")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Falha ao resolver conexão WhatsApp no core")

    data = resp.json()
    if not isinstance(data, dict) or "instance_id" not in data or "provider" not in data:
        raise HTTPException(status_code=502, detail="Resposta inesperada do backend-core")
    return data
