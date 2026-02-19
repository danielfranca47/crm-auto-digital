from __future__ import annotations

import re
from typing import Any, Dict, List

QUAL_FIELDS = {
    "service_interest",
    "availability_window",
    "location_preference",
    "budget_or_price_acceptance",
    "decision_role",
    "urgency",
    "constraints",
    "next_step",
}

SIGNALS_SCHEMA = {
    "intent_level",
    "urgency_level",
    "price_acceptance",
    "meeting_scheduled",
    "handoff_requested",
    "missing_fields",
    "stop_reason",
}

MIN_REQUIRED_FIELDS = {
    "consultivo": [
        "service_interest",
        "urgency",
        "decision_role",
        "constraints",
        "availability_window",
        "budget_or_price_acceptance",
    ],
    "agenda": [
        "service_interest",
        "availability_window",
        "location_preference",
        "price_acceptance",
    ],
    "direto": [
        "service_interest",
        "availability_window",
        "price_acceptance",
    ],
}


_DAY_OR_TIME_RE = re.compile(
    r"\b(\d{1,2}h|\d{1,2}:\d{2}|hoje|amanh[ãa]|segunda|ter[cç]a|quarta|quinta|sexta|s[áa]bado|domingo|semana)\b",
    flags=re.IGNORECASE,
)


def _text_from_context(context: Dict[str, Any]) -> str:
    metadata = context.get("metadata") or {}
    lead = context.get("lead") or {}
    history = context.get("history") or []
    parts: List[str] = [
        str(metadata.get("inbound_message_text") or ""),
        str(lead.get("notes") or ""),
    ]
    for item in history[-6:]:
        parts.append(str(item.get("body") or ""))
    return "\n".join(part for part in parts if part)


def infer_extracted_fields(context: Dict[str, Any]) -> Dict[str, Any]:
    text = _text_from_context(context).lower()
    extracted: Dict[str, Any] = {}

    if any(k in text for k in ["quero", "interesse", "serviço", "servico", "procedimento", "produto"]):
        extracted["service_interest"] = True

    if _DAY_OR_TIME_RE.search(text):
        extracted["availability_window"] = True

    if any(k in text for k in ["bairro", "cidade", "presencial", "online", "endereço", "endereco", "local"]):
        extracted["location_preference"] = True

    if any(k in text for k in ["preço", "preco", "valor", "custa", "caro", "barato", "aceito", "ok o preço", "ok o preco"]):
        extracted["price_acceptance"] = True
        extracted["budget_or_price_acceptance"] = True

    if any(k in text for k in ["eu decido", "decisor", "falar com", "meu sócio", "minha sócia", "aprovação", "aprovacao"]):
        extracted["decision_role"] = True

    if any(k in text for k in ["urgente", "hoje", "amanhã", "amanha", "semana que vem", "quanto antes"]):
        extracted["urgency"] = True

    if any(k in text for k in ["só de manhã", "so de manha", "não posso", "nao posso", "só à tarde", "so a tarde", "restrição", "restricao"]):
        extracted["constraints"] = True

    if any(k in text for k in ["me chama", "próximo passo", "proximo passo", "pode me ligar", "vamos seguir"]):
        extracted["next_step"] = True

    return extracted


def compute_missing_fields(agent_mode_normalized: str, extracted: Dict[str, Any]) -> List[str]:
    required = MIN_REQUIRED_FIELDS.get(agent_mode_normalized, MIN_REQUIRED_FIELDS["agenda"])
    missing: List[str] = []
    has_next_step = bool(extracted.get("next_step"))

    for field in required:
        if field == "availability_window" and agent_mode_normalized == "consultivo" and has_next_step:
            continue
        if extracted.get(field):
            continue
        missing.append(field)
    return missing


def required_fields_for_mode(agent_mode_normalized: str) -> List[str]:
    return list(MIN_REQUIRED_FIELDS.get(agent_mode_normalized, MIN_REQUIRED_FIELDS["agenda"]))
