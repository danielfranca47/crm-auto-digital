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
    ai_profile = context.get("ai_profile") or {}
    inbound = str(metadata.get("inbound_message_text") or "")

    schema = dict(DEFAULT_FIELD_SCHEMA)
    schema.update(fields_schema or {})

    # Contexto de nicho para extração mais precisa (Tarefa 2.2)
    niche = str(ai_profile.get("niche") or "")
    target_audience = str(ai_profile.get("target_audience") or "")

    # Derivar current_field e filled_fields a partir do qualification_state
    qual_state = context.get("qualification_state")
    qual_data: Dict[str, Any] = {}
    if isinstance(qual_state, dict) and qual_state.get("exists") is not False:
        raw_data = qual_state.get("data_json")
        if isinstance(raw_data, dict):
            qual_data = raw_data
    filled_fields = {
        k: v for k, v in qual_data.items()
        if v is not None and v != "" and v != [] and v != {}
    }
    current_field = next(
        (f for f in (fields_schema or {}) if f not in filled_fields),
        None,
    )

    prompt = (
        f"Você é um extractor de campos de qualificação para um CRM de vendas.\n\n"
        f"CAMPO PRIORITÁRIO A EXTRAIR: {current_field or '(todos)'}\n"
        f"CAMPOS JÁ PREENCHIDOS (não sobrescrever a menos que haja evidência forte de correção):\n"
        f"{json.dumps(filled_fields, ensure_ascii=False)}\n\n"
        + (f"NICHO DO NEGÓCIO: {niche}\n" if niche else "")
        + (f"PÚBLICO-ALVO: {target_audience}\n\n" if target_audience else "\n")
        + "Regras:\n"
        f"- Priorize a extração de {current_field or 'todos os campos'}\n"
        "- Para os demais campos, extraia APENAS se houver evidência CLARA e DIRETA\n"
        "- confidence < 0.6 = não extrair (retornar null para o campo)\n"
        "- Nunca infira valores — extraia apenas do texto\n"
        "- Se o lead disse algo ambíguo, retorne confidence baixa, não invente interpretação\n\n"
        f"Schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Inbound: {inbound}\n"
        f"Histórico: {_history_text(history)}\n\n"
        'Retorne SOMENTE JSON válido: {"extracted": {}, "confidence": {}, "evidence": {}}'
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
