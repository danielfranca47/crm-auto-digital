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
