from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class UazapiClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class UazapiTimeoutError(UazapiClientError):
    pass


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_RETRY_BASE_BACKOFF_SECONDS = 0.5
_RETRY_AFTER_CAP_SECONDS = 3.0


def _resolve_retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if retry_after:
        try:
            seconds = float(retry_after)
        except ValueError:
            seconds = None
        if seconds is not None and seconds >= 0:
            return min(seconds, _RETRY_AFTER_CAP_SECONDS)
    return _RETRY_BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))


async def _request_with_retry(
    *,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float,
    timeout_error_message: str,
    request_error_message: str,
) -> httpx.Response:
    """POST com retry curto e exponencial em 429/500/502/503/504.

    Erros de rede/timeout não são re-tentados aqui (propagam imediatamente) —
    uma tentativa de timeout já consome o timeout inteiro por tentativa, e
    retentar estouraria o orçamento de tempo do chamador (executor → core →
    uazapi, ver docs/architecture/whatsapp-send-resiliencia.md). Retry cobre
    só respostas de erro rápidas do servidor (rate-limit e erros 5xx).
    """
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise UazapiTimeoutError(timeout_error_message) from exc
        except httpx.RequestError as exc:
            raise UazapiClientError(request_error_message) from exc

        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
            delay = _resolve_retry_delay(response, attempt)
            logger.warning(
                "event=uazapi_send_retry attempt=%s/%s status=%s delay=%.2f",
                attempt,
                _MAX_ATTEMPTS,
                response.status_code,
                delay,
            )
            await asyncio.sleep(delay)
            continue

        return response

    raise UazapiClientError("Uazapi request failed without response")


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

    response = await _request_with_retry(
        url=url,
        headers=headers,
        payload=payload,
        timeout=30.0,
        timeout_error_message="Uazapi media request timed out",
        request_error_message="Uazapi media request failed",
    )

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

    response = await _request_with_retry(
        url=url,
        headers=headers,
        payload=payload,
        timeout=20.0,
        timeout_error_message="Uazapi request timed out",
        request_error_message="Uazapi request failed",
    )

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
