from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import httpx


class UazapiAdminError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class UazapiAdminTimeoutError(UazapiAdminError):
    pass


def _ensure_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if not base:
        raise UazapiAdminError("UAZAPI_BASE_URL is not configured")
    return base


def _ensure_admin_token(admin_token: str) -> str:
    if not admin_token:
        raise UazapiAdminError("UAZAPI_ADMIN_TOKEN is not configured")
    return admin_token


def _first_value(data: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def extract_instance_details(
    payload: Dict[str, Any],
    *,
    fallback_instance_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    instance_payload = payload.get("instance") if isinstance(payload.get("instance"), dict) else {}

    instance_id = _first_value(payload, ["instance_id", "instanceId", "id"]) or _first_value(
        instance_payload, ["instance_id", "instanceId", "id"]
    )
    if not instance_id:
        instance_id = fallback_instance_id

    instance_token = _first_value(payload, ["instance_token", "instanceToken", "token"]) or _first_value(
        instance_payload, ["instance_token", "instanceToken", "token"]
    )

    phone_e164 = _first_value(payload, ["phone", "phone_e164", "phoneNumber", "number"]) or _first_value(
        instance_payload, ["phone", "phone_e164", "phoneNumber", "number"]
    )

    return instance_id, instance_token, phone_e164


async def _request(
    *,
    base_url: str,
    admin_token: str,
    method: str,
    path: str,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = _ensure_base_url(base_url)
    token = _ensure_admin_token(admin_token)
    url = f"{base}{path}"
    headers = {"admintoken": token, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(method, url, headers=headers, json=json, params=params)
    except httpx.TimeoutException as exc:
        raise UazapiAdminTimeoutError("Uazapi admin request timed out") from exc
    except httpx.RequestError as exc:
        raise UazapiAdminError("Uazapi admin request failed") from exc

    if response.is_error:
        body = response.text
        raise UazapiAdminError(
            f"Uazapi admin error status={response.status_code}",
            status_code=response.status_code,
            body=body,
        )

    try:
        return response.json()
    except ValueError as exc:
        raise UazapiAdminError("Uazapi admin returned invalid JSON") from exc


async def init_instance(
    *,
    base_url: str,
    admin_token: str,
    instance_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body = {"instanceId": instance_id}
    if payload:
        body.update(payload)
    return await _request(
        base_url=base_url,
        admin_token=admin_token,
        method="POST",
        path="/instance/init",
        json=body,
    )


async def connect_instance(
    *,
    base_url: str,
    admin_token: str,
    instance_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body = {"instanceId": instance_id}
    if payload:
        body.update(payload)
    return await _request(
        base_url=base_url,
        admin_token=admin_token,
        method="POST",
        path="/instance/connect",
        json=body,
    )


async def get_status(
    *,
    base_url: str,
    admin_token: str,
    instance_id: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    query = {"instanceId": instance_id}
    if params:
        query.update(params)
    return await _request(
        base_url=base_url,
        admin_token=admin_token,
        method="GET",
        path="/instance/status",
        params=query,
    )


async def configure_webhook(
    *,
    base_url: str,
    admin_token: str,
    url: str,
    instance_id: Optional[str] = None,
    events: Optional[list[str]] = None,
    global_webhook: bool = False,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"url": url, "excludeMessages": ["wasSentByApi"]}
    if instance_id:
        body["instanceId"] = instance_id
    if events is not None:
        body["events"] = events
    if payload:
        body.update(payload)

    path = "/globalWebhook" if global_webhook else "/webhook"
    return await _request(
        base_url=base_url,
        admin_token=admin_token,
        method="POST",
        path=path,
        json=body,
    )
