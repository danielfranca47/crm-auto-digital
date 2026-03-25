from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

import httpx


logger = logging.getLogger(__name__)


class UazapiAdminError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None, retry_after: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.retry_after = retry_after


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


def _ensure_instance_token(instance_token: str) -> str:
    if not instance_token:
        raise UazapiAdminError("UAZAPI_INSTANCE_TOKEN is not configured")
    return instance_token


def _first_value(data: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def _first_string(data: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _normalize_status(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, bool):
        return "connected" if value else "disconnected"
    if isinstance(value, dict):
        for key in ("status", "state"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        connected = value.get("connected")
        logged_in = value.get("loggedIn")
        if isinstance(connected, bool) or isinstance(logged_in, bool):
            return "connected" if (connected or logged_in) else "disconnected"
    return None


def extract_instance_details(
    payload: Dict[str, Any],
    *,
    fallback_instance_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    instance_field = payload.get("instance")
    instance_payload = instance_field if isinstance(instance_field, dict) else {}

    instance_id = _first_string(payload, ["name", "instanceId", "instance"]) or _first_string(
        instance_payload, ["name", "instanceId", "instance"]
    )
    if not instance_id:
        instance_id = _first_string(payload, ["id"]) or _first_string(instance_payload, ["id"])
    if not instance_id and isinstance(instance_field, str) and instance_field.strip():
        instance_id = instance_field
    if not instance_id:
        instance_id = fallback_instance_id

    instance_token = _first_value(payload, ["instance_token", "instanceToken", "token"]) or _first_value(
        instance_payload, ["instance_token", "instanceToken", "token"]
    )

    phone_e164 = _first_value(payload, ["phone", "phone_e164", "phoneNumber", "number"]) or _first_value(
        instance_payload, ["phone", "phone_e164", "phoneNumber", "number"]
    )

    return instance_id, instance_token, phone_e164


def extract_connection_meta(payload: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    instance_payload = payload.get("instance") if isinstance(payload.get("instance"), dict) else {}
    status_value = _normalize_status(_first_value(payload, ["status", "instanceStatus"]))
    if status_value is None:
        status_value = _normalize_status(_first_value(instance_payload, ["status", "instanceStatus"]))
    qr_code = _first_value(payload, ["qrcode", "qrCode", "qr_code"]) or _first_value(
        instance_payload, ["qrcode", "qrCode", "qr_code"]
    )
    pair_code = _first_value(payload, ["paircode", "pairCode", "pair_code"]) or _first_value(
        instance_payload, ["paircode", "pairCode", "pair_code"]
    )
    return status_value, qr_code, pair_code


def _redact_keys(data: Any, keys: set[str]) -> Any:
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            if key in keys:
                continue
            redacted[key] = _redact_keys(value, keys)
        return redacted
    if isinstance(data, list):
        return [_redact_keys(item, keys) for item in data]
    return data


def redact_instance_token(payload: Dict[str, Any]) -> Dict[str, Any]:
    keys = {"instance_token", "instanceToken", "token"}
    return _redact_keys(payload, keys)


def _mask_token_in_text(text: str, token: str) -> str:
    if not text or not token:
        return text
    return text.replace(token, "***")


async def _request(
    *,
    base_url: str,
    token: str,
    method: str,
    path: str,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    header_name: str = "admintoken",
    validate_token: bool = True,
) -> Dict[str, Any]:
    base = _ensure_base_url(base_url)
    if validate_token:
        token = _ensure_admin_token(token)
    url = f"{base}{path}"
    headers = {header_name: token, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(method, url, headers=headers, json=json, params=params)
    except httpx.TimeoutException as exc:
        raise UazapiAdminTimeoutError("Uazapi admin request timed out") from exc
    except httpx.RequestError as exc:
        raise UazapiAdminError("Uazapi admin request failed") from exc

    if response.is_error:
        body = response.text
        masked_body = _mask_token_in_text(body, token)
        retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
        logger.info(
            "Uazapi admin error status=%s retry_after=%s body=%s",
            response.status_code,
            retry_after,
            masked_body,
        )
        raise UazapiAdminError(
            f"Uazapi admin error status={response.status_code}",
            status_code=response.status_code,
            body=body,
            retry_after=retry_after,
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
    body = {"name": instance_id, "instanceId": instance_id}
    if payload:
        body.update(payload)
    return await _request(
        base_url=base_url,
        token=admin_token,
        method="POST",
        path="/instance/init",
        json=body,
    )


async def connect_instance(
    *,
    base_url: str,
    instance_token: str,
    instance_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body = {"name": instance_id, "instanceId": instance_id}
    if payload:
        body.update(payload)
    return await _request(
        base_url=base_url,
        token=_ensure_instance_token(instance_token),
        method="POST",
        path="/instance/connect",
        json=body,
        header_name="token",
        validate_token=False,
    )


async def get_status(
    *,
    base_url: str,
    instance_token: str,
    instance_id: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    query = {"name": instance_id, "instanceId": instance_id}
    if params:
        query.update(params)
    return await _request(
        base_url=base_url,
        token=_ensure_instance_token(instance_token),
        method="GET",
        path="/instance/status",
        params=query,
        header_name="token",
        validate_token=False,
    )


async def configure_webhook(
    *,
    base_url: str,
    admin_token: str,
    url: str,
    instance_id: Optional[str] = None,
    events: Optional[list[str]] = None,
    global_webhook: bool = False,
    instance_token: Optional[str] = None,
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
    if global_webhook:
        token = _ensure_admin_token(admin_token)
        header_name = "admintoken"
    else:
        token = _ensure_instance_token(instance_token or "")
        header_name = "token"

    return await _request(
        base_url=base_url,
        token=token,
        method="POST",
        path=path,
        json=body,
        header_name=header_name,
        validate_token=False,
    )
