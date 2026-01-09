from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from app.core.config import settings


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
        "prompt": prompt,
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(settings.llm_api_base, headers=headers, json=payload)
    response.raise_for_status()
    return response.text
