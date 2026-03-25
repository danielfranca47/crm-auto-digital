"""Normalização canônica de telefones para E.164."""

from __future__ import annotations

import re

_CALLING_CODES = {
    "BR": "55",
    "PT": "351",
    "US": "1",
    "ES": "34",
    "FR": "33",
    "IT": "39",
    "DE": "49",
    "UK": "44",
    "GB": "44",
    "NL": "31",
    "IE": "353",
}


class PhoneNormalizationError(ValueError):
    """Erro de normalização/validação de telefone."""


def _apply_br_mobile_legacy_rule(candidate: str) -> str:
    """
    Regra BR para reduzir duplicidade celular legado (sem 9º dígito).

    - E.164 começando com +55 e 10 dígitos nacionais (DDD 2 + assinante 8)
    - Se assinante começar com 6..9, insere 9 após DDD
    - Se começar com 2..5, mantém como fixo
    """

    if not candidate.startswith("+55"):
        return candidate

    national = candidate[3:]
    if len(national) != 10:
        return candidate

    ddd = national[:2]
    subscriber = national[2:]
    if not subscriber:
        return candidate

    first = subscriber[0]
    if first in {"6", "7", "8", "9"}:
        return f"+55{ddd}9{subscriber}"
    return candidate


def normalize_to_e164(raw_phone: str | None, country_code: str | None = None) -> str:
    """
    Retorna telefone em E.164 (ex: +5511999999999).

    Regras mínimas:
    - remove espaços/sinais e caracteres inválidos
    - aceita +... e mantém
    - aceita 00... e converte para +...
    - sem + exige country_code conhecido
    - valida somente '+' seguido de dígitos
    - valida comprimento de dígitos (8..15)
    - aplica canônico BR para celular legado sem 9
    """

    if raw_phone is None:
        return ""

    text = str(raw_phone).strip()
    if not text:
        return ""

    cleaned = re.sub(r"[\s\-()]+", "", text)
    cleaned = re.sub(r"[^0-9+]+", "", cleaned)

    if cleaned.startswith("00") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned[2:]

    if cleaned.startswith("+"):
        candidate = "+" + re.sub(r"[^0-9]+", "", cleaned[1:])
    else:
        digits = re.sub(r"\D+", "", cleaned)
        if not digits:
            return ""
        if not country_code:
            raise PhoneNormalizationError("country_code obrigatório quando telefone não iniciar com '+'")

        cc = str(country_code).strip().upper()
        calling_code = _CALLING_CODES.get(cc)
        if not calling_code:
            raise PhoneNormalizationError("country_code inválido")

        candidate = f"+{calling_code}{digits}"

    candidate = _apply_br_mobile_legacy_rule(candidate)

    if not re.fullmatch(r"\+[0-9]+", candidate):
        raise PhoneNormalizationError("Telefone inválido")

    digits_len = len(candidate[1:])
    if digits_len < 8 or digits_len > 15:
        raise PhoneNormalizationError("Telefone inválido")

    return candidate
