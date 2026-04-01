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
    "offer_presented",
    "checkout_sent",
    "presentation_variant",
    "offer_item_name",
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

    price_yes_terms = ["aceito", "ok o preço", "ok o preco", "fechado no preço", "pode ser esse valor"]
    price_no_terms = ["caro", "muito caro", "fora do orçamento", "fora do orcamento", "não consigo pagar", "nao consigo pagar"]
    price_any_terms = ["preço", "preco", "valor", "custa"]
    if any(k in text for k in price_yes_terms):
        extracted["price_acceptance"] = "yes"
        extracted["budget_or_price_acceptance"] = True
    elif any(k in text for k in price_no_terms):
        extracted["price_acceptance"] = "no"
        extracted["budget_or_price_acceptance"] = True
    elif any(k in text for k in price_any_terms):
        extracted["price_acceptance"] = "unsure"
        extracted["budget_or_price_acceptance"] = True

    if any(k in text for k in ["eu decido", "decisor", "falar com", "meu sócio", "minha sócia", "aprovação", "aprovacao"]):
        extracted["decision_role"] = True

    if any(k in text for k in ["urgente", "hoje", "amanhã", "amanha", "semana que vem", "quanto antes"]):
        extracted["urgency"] = True

    if any(k in text for k in ["só de manhã", "so de manha", "não posso", "nao posso", "só à tarde", "so a tarde", "restrição", "restricao"]):
        extracted["constraints"] = True

    if any(k in text for k in ["me chama", "próximo passo", "proximo passo", "pode me ligar", "vamos seguir"]):
        extracted["next_step"] = True
        if _DAY_OR_TIME_RE.search(text):
            extracted["next_step_with_time"] = True

    return extracted


def compute_missing_fields(
    agent_mode_normalized: str,
    extracted: Dict[str, Any],
    required_fields_override: List[str] | None = None,
) -> List[str]:
    if required_fields_override is not None:
        required = required_fields_override
    else:
        required = MIN_REQUIRED_FIELDS.get(agent_mode_normalized, MIN_REQUIRED_FIELDS["agenda"])
    missing: List[str] = []
    has_next_step_with_time = bool(extracted.get("next_step_with_time"))

    for field in required:
        if field == "availability_window" and agent_mode_normalized == "consultivo" and has_next_step_with_time:
            continue
        if extracted.get(field):
            continue
        missing.append(field)
    return missing


def required_fields_for_mode(
    agent_mode_normalized: str,
    required_fields_override: List[str] | None = None,
) -> List[str]:
    if required_fields_override is not None:
        return list(required_fields_override)
    return list(MIN_REQUIRED_FIELDS.get(agent_mode_normalized, MIN_REQUIRED_FIELDS["agenda"]))
