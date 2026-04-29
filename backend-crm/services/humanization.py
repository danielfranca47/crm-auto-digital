"""Funções de humanização de comportamento do agente."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


def compute_reply_delay(ai_profile: Dict[str, Any], is_first_message: bool) -> int:
    """Retorna delay em segundos sorteado entre min e max do AI Profile (0 = sem delay)."""
    if is_first_message:
        lo = int(ai_profile.get("first_reply_delay_min_seconds") or 0)
        hi = int(ai_profile.get("first_reply_delay_max_seconds") or 0)
    else:
        lo = int(ai_profile.get("reply_delay_min_seconds") or 0)
        hi = int(ai_profile.get("reply_delay_max_seconds") or 0)

    if lo <= 0 and hi <= 0:
        return 0
    if hi <= lo:
        return max(lo, 0)
    return random.randint(lo, hi)


def scheduled_at_from_delay(delay_seconds: int) -> Optional[datetime]:
    """Converte delay em segundos para datetime absoluto (None = execução imediata)."""
    if delay_seconds <= 0:
        return None
    return datetime.utcnow() + timedelta(seconds=delay_seconds)


def compute_typing_ms(text: str) -> int:
    """Calcula duração do 'Digitando...' em ms: 40ms/char, mínimo 1s, máximo 8s."""
    return min(max(len(text) * 40, 1000), 8000)


def split_by_punctuation(text: str, min_chars: int = 15) -> list[str]:
    """Divide texto em partes por marcadores de sentença (. ! ? …).

    Parágrafos duplos (\\n\\n) sempre criam quebra independente de tamanho.
    Frases curtas (< min_chars) são fundidas com a próxima para evitar bolhas triviais.
    """
    import re

    if not text or not text.strip():
        return []
    normalized = text.strip().replace("...", "…")
    paras = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    if len(paras) > 1:
        return paras
    raw = re.split(r"(?<=[.!?…])\s+", normalized)
    parts: list[str] = []
    buffer = ""
    for i, frag in enumerate(raw):
        candidate = (buffer + " " + frag).strip() if buffer else frag.strip()
        if len(candidate) < min_chars and i < len(raw) - 1:
            buffer = candidate
        else:
            parts.append(candidate)
            buffer = ""
    if buffer:
        parts.append(buffer)
    return [p for p in parts if p]
