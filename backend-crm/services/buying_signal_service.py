"""Detecção de sinais de compra — Agent 1 (Tarefa 3.7)."""

from __future__ import annotations

import unicodedata
from typing import List

BUYING_SIGNAL_DEFAULTS: List[str] = [
    "quanto custa",
    "qual o valor",
    "como assino",
    "qual o contrato",
    "como faço para contratar",
    "aceita cartão",
    "tem parcelamento",
    "quando começa",
    "qual o prazo",
    "me manda a proposta",
]


def _normalize(text: str) -> str:
    """Lowercase + remove acentos para comparação case/accent-insensitive."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def detect_buying_signals(message_text: str, keywords_list: List[str] | None = None) -> bool:
    """Retorna True se message_text contém alguma keyword de compra.

    Usa keywords_list quando fornecida (configuração do AI Profile).
    Cai para BUYING_SIGNAL_DEFAULTS quando keywords_list é None ou vazia.
    """
    keywords = keywords_list if keywords_list else BUYING_SIGNAL_DEFAULTS
    normalized_msg = _normalize(message_text or "")
    for kw in keywords:
        if _normalize(kw) in normalized_msg:
            return True
    return False
