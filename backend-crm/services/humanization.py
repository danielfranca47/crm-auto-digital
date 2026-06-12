"""Funções de humanização de comportamento do agente."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo


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


# ---------------------------------------------------------------------------
# Janela de disponibilidade (4c/4d)
# ---------------------------------------------------------------------------

_DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

_BUSINESS_HOURS: Dict[int, tuple] = {
    0: ("09:00", "18:00"),
    1: ("09:00", "18:00"),
    2: ("09:00", "18:00"),
    3: ("09:00", "18:00"),
    4: ("09:00", "18:00"),
}


def _parse_schedule(ai_profile: Dict[str, Any]) -> Dict[int, tuple]:
    """Converte availability_schedule JSON em dict {weekday_int: (start, end)}."""
    raw = ai_profile.get("availability_schedule") or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    schedule: Dict[int, tuple] = {}
    for key, val in data.items():
        idx = _DAY_MAP.get(key.lower())
        if idx is not None and val:
            parts = str(val).split("-")
            if len(parts) == 2:
                schedule[idx] = (parts[0].strip(), parts[1].strip())
    return schedule


def _parse_hm(t: str) -> tuple:
    h, m = map(int, t.split(":"))
    return h, m


def next_available_at(ai_profile: Dict[str, Any], now_utc: datetime) -> Optional[datetime]:
    """Retorna o próximo instante (UTC naive) em que o agente pode responder,
    ou None se já estiver dentro da janela ou se o modo for 24h."""
    mode = (ai_profile.get("availability_mode") or "24h").lower()
    if mode == "24h":
        return None

    tz_name = ai_profile.get("timezone") or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    now_aware = now_utc.replace(tzinfo=timezone.utc)
    now_local = now_aware.astimezone(tz)

    schedule = _BUSINESS_HOURS if mode == "business_hours" else _parse_schedule(ai_profile)
    if not schedule:
        return None  # sem janela configurada → não bloquear

    wd = now_local.weekday()
    if wd in schedule:
        sh, sm = _parse_hm(schedule[wd][0])
        eh, em = _parse_hm(schedule[wd][1])
        start_today = now_local.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end_today = now_local.replace(hour=eh, minute=em, second=0, microsecond=0)
        if start_today <= now_local < end_today:
            return None  # dentro da janela

    # Fora da janela — encontrar próxima abertura (até 7 dias à frente)
    for delta_days in range(1, 8):
        candidate = now_local + timedelta(days=delta_days)
        wd_c = candidate.weekday()
        if wd_c in schedule:
            sh, sm = _parse_hm(schedule[wd_c][0])
            next_open = candidate.replace(hour=sh, minute=sm, second=0, microsecond=0)
            return next_open.astimezone(timezone.utc).replace(tzinfo=None)

    return None  # nenhum dia disponível encontrado → não bloquear


def compute_scheduled_at(ai_profile: Dict[str, Any], is_first_message: bool) -> Optional[datetime]:
    """Combina delay de humanização + janela de horário.
    Retorna o scheduled_at final para o job (None = execução imediata)."""
    delay_secs = compute_reply_delay(ai_profile, is_first_message)
    base = datetime.utcnow() + timedelta(seconds=delay_secs) if delay_secs else datetime.utcnow()

    window_start = next_available_at(ai_profile, base)
    if window_start and window_start > base:
        return window_start  # aguardar até a janela abrir
    if delay_secs:
        return base
    return None
