"""Normalização de telefones para fluxo de webhooks WhatsApp."""

from __future__ import annotations

import re

from services.phone_normalizer import PhoneNormalizationError, normalize_to_e164


def normalize_phone(raw: str | None) -> str:
    """
    Normaliza para E.164.

    Compatibilidade inbound:
    - tenta normalização direta (esperando '+' ou '00')
    - se vier sem '+', tenta interpretar como número internacional cru (prefixa '+')
    """

    if not raw:
        return ""

    try:
        return normalize_to_e164(raw)
    except PhoneNormalizationError:
        digits = re.sub(r"\D+", "", str(raw or ""))
        if not digits:
            return ""
        try:
            return normalize_to_e164(f"+{digits}")
        except PhoneNormalizationError:
            return ""
