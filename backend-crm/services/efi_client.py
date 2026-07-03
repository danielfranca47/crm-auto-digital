"""Cliente HTTP para a API de Cobranças da Efí Bank (assinaturas recorrentes)."""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_PROD_BASE = "https://cobrancas.api.efipay.com.br"
_SANDBOX_BASE = "https://cobrancas-h.api.efipay.com.br"

_token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def _is_sandbox() -> bool:
    return os.environ.get("EFI_SANDBOX", "true").strip().lower() in {"1", "true", "yes"}


def _base_url() -> str:
    return _SANDBOX_BASE if _is_sandbox() else _PROD_BASE


async def _get_access_token() -> str:
    """Obtém (e cacheia em memória) o access_token OAuth2 client_credentials."""
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["access_token"]

    client_id = os.environ.get("EFI_CLIENT_ID", "")
    client_secret = os.environ.get("EFI_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("EFI_CLIENT_ID/EFI_CLIENT_SECRET não configurados")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_base_url()}/v1/authorize",
            json={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {basic}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    logger.info("efi_client: novo access_token obtido (sandbox=%s)", _is_sandbox())
    return _token_cache["access_token"]


async def _request(method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
    token = await _get_access_token()
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Content-Type", "application/json")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request(method, f"{_base_url()}{path}", headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()


async def create_plan(name: str, interval: int = 1, repeats: Optional[int] = None) -> Dict[str, Any]:
    """Cria um plano de assinatura recorrente. repeats=None → repetições ilimitadas."""
    body: Dict[str, Any] = {"name": name, "interval": interval}
    if repeats is not None:
        body["repeats"] = repeats
    result = await _request("POST", "/v1/plan", json=body)
    return result["data"]


async def create_subscription_link(
    plan_id: int,
    item_name: str,
    value_cents: int,
    notification_url: str,
    custom_id: Optional[str] = None,
    link_valid_days: int = 30,
) -> str:
    """Gera um link de checkout hospedado da Efí para uma nova assinatura do plano informado."""
    from datetime import date, timedelta

    metadata: Dict[str, str] = {"notification_url": notification_url}
    if custom_id:
        metadata["custom_id"] = custom_id
    expire_at = (date.today() + timedelta(days=link_valid_days)).isoformat()
    body = {
        "items": [{"name": item_name, "value": value_cents, "amount": 1}],
        "metadata": metadata,
        "settings": {
            "payment_method": "credit_card",
            "request_delivery_address": False,
            "expire_at": expire_at,
        },
    }
    result = await _request("POST", f"/v1/plan/{plan_id}/subscription/one-step/link", json=body)
    return result["data"]["payment_url"]


async def resolve_notification(token: str) -> List[Dict[str, Any]]:
    """Consulta os detalhes de uma notificação recebida (token do POST em /webhooks/efi)."""
    result = await _request("GET", f"/v1/notification/{token}")
    return result.get("data", [])


async def get_charge(charge_id: int) -> Dict[str, Any]:
    """Detalha uma cobrança — inclui status, custom_id (plan_code) e dados do cliente uma vez paga."""
    result = await _request("GET", f"/v1/charge/{charge_id}")
    return result["data"]


async def get_subscription(subscription_id: int) -> Dict[str, Any]:
    """Detalha uma assinatura — custom_id (plan_code) e histórico de cobranças associadas."""
    result = await _request("GET", f"/v1/subscription/{subscription_id}")
    return result["data"]
