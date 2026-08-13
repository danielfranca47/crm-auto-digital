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

# Limiares de confiança abaixo dos quais uma extração é descartada. O prompt já
# pede esses mesmos números à LLM (ver bloco "Regras" em extract_fields_llm) —
# aqui é onde eles passam a ser verificados de fato, em vez de só sugeridos.
_PROFILE_FIELD_CONFIDENCE_THRESHOLD = 0.4
_DEFAULT_FIELD_CONFIDENCE_THRESHOLD = 0.6


def _field_questions(ai_profile: Dict[str, Any]) -> Dict[str, str]:
    """Mapa key -> pergunta/label configurada em ai_profile.qualification_fields.

    Sem isso, a LLM extractora só vê o nome da chave (ex.:
    "custom_pergunta_de_endereco") e tem que adivinhar o que ela significa —
    causa raiz de extrações alucinadas a partir de menções tangenciais ao tema."""
    qual_fields = ai_profile.get("qualification_fields")
    if not isinstance(qual_fields, list):
        return {}
    questions: Dict[str, str] = {}
    for field in qual_fields:
        if not isinstance(field, dict):
            continue
        key = field.get("key")
        if not isinstance(key, str):
            continue
        question = field.get("question") or field.get("label")
        if question:
            questions[key] = str(question)
    return questions


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

    _custom_fields = list(fields_schema.keys()) if fields_schema else []
    _custom_fields_str = ", ".join(_custom_fields) if _custom_fields else "(nenhum)"
    _field_questions_map = _field_questions(ai_profile)
    _custom_field_questions = {
        key: _field_questions_map[key] for key in _custom_fields if key in _field_questions_map
    }

    prompt = (
        f"Você é um extractor de campos de qualificação para um CRM de vendas.\n\n"
        f"CAMPO PRIORITÁRIO A EXTRAIR: {current_field or '(todos)'}\n"
        f"CAMPOS JÁ PREENCHIDOS (não sobrescrever a menos que haja evidência forte de correção):\n"
        f"{json.dumps(filled_fields, ensure_ascii=False)}\n\n"
        + (f"NICHO DO NEGÓCIO: {niche}\n" if niche else "")
        + (f"PÚBLICO-ALVO: {target_audience}\n\n" if target_audience else "\n")
        + "Regras:\n"
        f"- Priorize a extração de {current_field or 'todos os campos'}\n"
        f"- CAMPOS OBRIGATÓRIOS DO PERFIL [{_custom_fields_str}], com a pergunta configurada que cada um representa:\n"
        f"  {json.dumps(_custom_field_questions, ensure_ascii=False)}\n"
        "  Para cada campo, pergunte-se: 'o lead deu alguma informação real que responde a essa pergunta "
        "específica?'. Se sim, extraia (mesmo que a resposta seja informal, breve ou incompleta). Se o lead "
        "só mencionou o produto/serviço em si, ou o assunto em geral, sem dar a informação pedida, isso NÃO "
        "é uma resposta — retorne null e confidence 0.0. Exemplo: citar o nome do produto NÃO responde 'pra "
        "que você vai usar o produto'; dizer 'é pra hospedar convidados' SIM responde.\n"
        "  Limiar: confidence >= 0.4 é suficiente para extrair.\n"
        "- Para campos de contexto padrão (não listados acima), extraia APENAS se houver evidência CLARA e DIRETA. Limiar: confidence >= 0.6.\n"
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

    # Gate por confiança: o prompt acima pede um limiar por campo (0.4 para
    # campos do perfil, 0.6 para os de contexto padrão), mas isso só tinha
    # efeito se a LLM decidisse seguir — nada verificava depois. Chave sem
    # confidence numérica é tratada como reprovada (fail-closed).
    profile_fields = set(fields_schema.keys()) if fields_schema else set()
    gated_extracted: Dict[str, Any] = {}
    for key, value in extracted.items():
        threshold = (
            _PROFILE_FIELD_CONFIDENCE_THRESHOLD
            if key in profile_fields
            else _DEFAULT_FIELD_CONFIDENCE_THRESHOLD
        )
        field_confidence = confidence.get(key)
        if isinstance(field_confidence, (int, float)) and not isinstance(field_confidence, bool) and field_confidence >= threshold:
            gated_extracted[key] = value

    return {
        "extracted": gated_extracted,
        "confidence": confidence,
        "evidence": evidence,
        "raw": raw,
    }
