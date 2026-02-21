from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services import llm_service


DEFAULT_FIELD_SCHEMA: Dict[str, str] = {
    "service_interest": "string|object|null",
    "urgency": "low|medium|high|null",
    "decision_role": "owner|partner|employee|other|null",
    "constraints": "string|null",
    "availability_window": "string|null",
    "budget_or_price_acceptance": "string|number|object|null",
}


def _extract_json_payload(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _history_text(history: List[Dict[str, Any]]) -> str:
    rows = history[-6:]
    return "\n".join(f"{item.get('model') or 'unknown'}: {item.get('body') or ''}" for item in rows)


def extract_fields_llm(context: Dict[str, Any], fields_schema: Dict[str, str]) -> Dict[str, Any]:
    metadata = context.get("metadata") or {}
    history = context.get("history") or []
    inbound = str(metadata.get("inbound_message_text") or "")

    schema = dict(DEFAULT_FIELD_SCHEMA)
    schema.update(fields_schema or {})

    prompt = (
        "Você é um extractor de campos de qualificação. Retorne SOMENTE JSON válido:\n"
        "{\n"
        '  "extracted": {"field": "value"},\n'
        '  "confidence": {"field": 0.0},\n'
        '  "evidence": {"field": "trecho curto"}\n'
        "}\n"
        "Regras:\n"
        "- Extraia APENAS com base no texto disponível.\n"
        "- Se não houver evidência, não invente campo.\n"
        "- confidence entre 0 e 1 por campo.\n"
        f"- schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"- inbound_message_text: {inbound}\n"
        f"- history: {_history_text(history)}\n"
    )

    raw = llm_service.generate_decision_text(prompt)
    payload = _extract_json_payload(raw)
    extracted = payload.get("extracted") if isinstance(payload.get("extracted"), dict) else {}
    confidence = payload.get("confidence") if isinstance(payload.get("confidence"), dict) else {}
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}

    return {
        "extracted": extracted,
        "confidence": confidence,
        "evidence": evidence,
        "raw": raw,
    }
