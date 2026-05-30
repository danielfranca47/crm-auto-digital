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


async def send_media(
    *, base_url: str, token: str, number: str, media_url: str, media_type: str, caption: str = "", delay_ms: int = 0
) -> Dict[str, Any]:
    # UazAPI v2: endpoint unificado /send/media com campo type e file (não url)
    # Tipos suportados: image, video, videoplay, document, audio, myaudio, ptt, ptv, sticker
    base = base_url.rstrip("/")
    if not base:
        raise UazapiClientError("UAZAPI_BASE_URL is not configured")
    url = f"{base}/send/media"
    headers = {"token": token, "Content-Type": "application/json"}
    payload: Dict[str, Any] = {
        "number": number,
        "type": media_type.lower(),
        "file": media_url,
    }
    if caption:
        payload["text"] = caption  # campo 'text' (não 'caption') na UazAPI v2
    if delay_ms > 0:
        payload["delay"] = delay_ms

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise UazapiTimeoutError("Uazapi media request timed out") from exc
    except httpx.RequestError as exc:
        raise UazapiClientError("Uazapi media request failed") from exc

    if response.is_error:
        body = response.text
        raise UazapiClientError(
            f"Uazapi media error status={response.status_code}",
            status_code=response.status_code,
            body=body,
        )

    try:
        return response.json()
    except ValueError as exc:
        raise UazapiClientError("Uazapi returned invalid JSON for media") from exc


async def send_text(*, base_url: str, token: str, number: str, text: str, delay_ms: int = 0) -> Dict[str, Any]:
    base = base_url.rstrip("/")
    if not base:
        raise UazapiClientError("UAZAPI_BASE_URL is not configured")
    url = f"{base}/send/text"
    headers = {"token": token, "Content-Type": "application/json"}
    payload: Dict[str, Any] = {"number": number, "text": text}
    if delay_ms > 0:
        payload["delay"] = delay_ms

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
