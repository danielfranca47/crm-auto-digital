from __future__ import annotations

from typing import Any, Dict

import httpx


class UazapiClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class UazapiTimeoutError(UazapiClientError):
    pass


async def send_text(*, base_url: str, token: str, number: str, text: str) -> Dict[str, Any]:
    base = base_url.rstrip("/")
    if not base:
        raise UazapiClientError("UAZAPI_BASE_URL is not configured")
    url = f"{base}/send/text"
    headers = {"token": token, "Content-Type": "application/json"}
    payload = {"number": number, "text": text}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise UazapiTimeoutError("Uazapi request timed out") from exc
    except httpx.RequestError as exc:
        raise UazapiClientError("Uazapi request failed") from exc

    if response.is_error:
        body = response.text
        raise UazapiClientError(
            f"Uazapi error status={response.status_code}",
            status_code=response.status_code,
            body=body,
        )

    try:
        return response.json()
    except ValueError as exc:
        raise UazapiClientError("Uazapi returned invalid JSON") from exc
