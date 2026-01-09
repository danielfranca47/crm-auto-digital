from __future__ import annotations

import json
import logging
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _stub_response() -> str:
    payload = {
        "next_action": "reply",
        "message_text": "Olá! Como posso ajudar?",
        "questions": [],
        "reason": "stub_no_key",
    }
    return json.dumps(payload, ensure_ascii=False)


def generate_decision_text(prompt: str) -> str:
    if not settings.llm_api_key:
        return _stub_response()

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": settings.llm_model,
        "input": prompt,
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(settings.llm_api_base, headers=headers, json=payload)
    if response.status_code != 200:
        truncated = response.text[:1000]
        logger.warning("LLM response error status=%s body=%s", response.status_code, truncated)
    response.raise_for_status()
    return response.text
