"""Normalização leve de telefones para fluxo de webhooks WhatsApp."""

import re


def normalize_phone(raw: str | None) -> str:
    """
    Remove espaços e símbolos, preservando dígitos e sinal '+' inicial quando presente.
    Se vier com prefixo internacional começando em '00', converte para '+'.
    """

    if not raw:
        return ""

    text = str(raw).strip()
    if not text:
        return ""

    cleaned = re.sub(r"[\s\-()]+", "", text)
    cleaned = re.sub(r"[^0-9+]+", "", cleaned)

    if cleaned.startswith("00") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned[2:]

    if not cleaned.startswith("+"):
        return ""

    return cleaned
