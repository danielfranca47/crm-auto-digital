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
        "text": {"format": {"type": "json_object"}},
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(settings.llm_api_base, headers=headers, json=payload)
    if response.status_code != 200:
        truncated = response.text[:1000]
        logger.warning("LLM response error status=%s body=%s", response.status_code, truncated)
    response.raise_for_status()
    return _extract_output_text(response.json())
