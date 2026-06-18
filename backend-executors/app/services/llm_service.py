from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 2
_RETRY_BACKOFF_SECONDS = 1.0


def _stub_response() -> str:
    payload = {
        "next_action": "reply",
        "message_text": "Olá! Como posso ajudar?",
        "questions": [],
        "reason": "stub_no_key",
    }
    return json.dumps(payload, ensure_ascii=False)


def _stub_mother_response() -> str:
    payload = {
        "route_to": "qualification",
        "confidence": 0.5,
        "reason": "stub_no_key",
    }
    return json.dumps(payload, ensure_ascii=False)


def _stub_child_response() -> str:
    payload = {
        "message_text": "Olá! Como posso ajudar?",
        "did_complete_phase": False,
        "recommended_next_category": None,
        "outcome": None,
        "kanban_highlight": None,
        "signals": [],
        "confidence": 0.5,
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_output_text(payload: Dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    output_items = payload.get("output")
    if not isinstance(output_items, list):
        raise ValueError("LLM response missing output")

    chunks: list[str] = []
    for item in output_items:
        contents = item.get("content") if isinstance(item, dict) else None
        if not isinstance(contents, list):
            continue
        for content in contents:
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                chunks.append(content["text"])

    if not chunks:
        raise ValueError("LLM response missing output_text")
    return "".join(chunks)


def _post_with_retry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST para a LLM API com retry curto para falhas transitórias.

    Re-tenta em httpx.RequestError (timeout/erro de rede) e em status codes
    retryable (429/500/502/503/504). Não re-tenta em 4xx não-retryable
    (400/401/403/422) — falha imediatamente, pois retry não resolveria.
    """
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    last_exc: Optional[Exception] = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(settings.llm_api_base, headers=headers, json=payload)
        except httpx.RequestError as exc:
            last_exc = exc
            logger.warning(
                "event=llm_request_error attempt=%s/%s exc_type=%s exc=%s",
                attempt, _MAX_ATTEMPTS, type(exc).__name__, exc,
            )
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF_SECONDS)
                continue
            raise
        if response.status_code != 200:
            truncated = response.text[:1000]
            logger.warning(
                "event=llm_response_error attempt=%s/%s status=%s body=%s",
                attempt, _MAX_ATTEMPTS, response.status_code, truncated,
            )
        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF_SECONDS)
            continue
        response.raise_for_status()
        return response.json()
    if last_exc:
        raise last_exc
    raise RuntimeError("llm request failed without exception")


def generate_decision_text(prompt: str) -> str:
    if not settings.llm_api_key:
        return _stub_response()
    payload: Dict[str, Any] = {
        "model": settings.llm_model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    return _extract_output_text(_post_with_retry(payload))


def generate_mother_route(prompt: str) -> str:
    if not settings.llm_api_key:
        return _stub_mother_response()
    payload: Dict[str, Any] = {
        "model": settings.llm_model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    return _extract_output_text(_post_with_retry(payload))


def generate_child_result(route: str, prompt: str) -> str:
    if not settings.llm_api_key:
        return _stub_child_response()
    payload: Dict[str, Any] = {
        "model": settings.llm_model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
        "metadata": {"route": route},
    }
    return _extract_output_text(_post_with_retry(payload))
