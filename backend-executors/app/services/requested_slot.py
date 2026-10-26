"""Horário pedido pelo lead + verificação da agenda, para dar à Filha como facto.

Com serviço + dia + hora na mesma mensagem, o LLM respondia em ~metade dos casos "esse horário
não está disponível" com a agenda vazia (teste real, conta Sensi Vitae): tinha de cruzar sozinho
HORÁRIOS JÁ OCUPADOS, a grelha de disponibilidade e as instruções da conta. Aqui o código lê a
hora e o dia pedidos e verifica a agenda (`calendar_busy_slots`); a Filha recebe o resultado
como facto. O horário de atendimento do profissional é texto livre — continua a ser a IA a
decidir se a sessão cabe nele.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.services import meeting_date_guard
from app.services.meeting_scheduler import _has_conflict

# "11h", "11 h", "14h30", "15:00". Duração ("de 1h", "1h30 de massagem") e limites
# ("depois das 19h", "a partir das 15h") não são um horário pedido.
_TIME_RE = re.compile(r"(?<![\d/:])(\d{1,2})(?:\s*h\s*(\d{2})?|:(\d{2}))(?![\d/])", re.IGNORECASE)
_NOT_A_SLOT_BEFORE = re.compile(
    r"(depois\s+d[ao]s?|a\s+partir\s+d[ao]s?|antes\s+d[ao]s?|at[eé]\s+[àa]s?|ap[oó]s\s+[ao]s?|"
    r"entre\s+[ao]s?|\bde|\bcom)\s*$",
    re.IGNORECASE,
)
_EARLIEST_HOUR, _LATEST_HOUR = 6, 23  # "1h", "2h" são durações, não horas de sessão


@dataclass
class RequestedSlot:
    start: datetime  # no fuso do perfil
    end: datetime
    free: bool
    conflicts: List[Tuple[datetime, datetime]] = field(default_factory=list)


def _tz(tz_name: Optional[str]):
    try:
        return ZoneInfo(str(tz_name)) if tz_name else timezone.utc
    except Exception:
        return timezone.utc


def requested_time(text: str) -> Optional[time]:
    """Hora pedida na mensagem, só quando é uma e inequívoca."""
    found = set()
    for m in _TIME_RE.finditer(text or ""):
        if _NOT_A_SLOT_BEFORE.search(text[max(0, m.start() - 14):m.start()]):
            continue
        hour, minute = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
        if not (_EARLIEST_HOUR <= hour <= _LATEST_HOUR) or minute > 59:
            continue
        found.add(time(hour, minute))
    return found.pop() if len(found) == 1 else None


def find_requested_slot(
    inbound_text: str,
    earlier_messages: List[str],
    *,
    tz_name: Optional[str],
    busy_slots: Iterable[Dict[str, Any]],
    duration_minutes: int,
    exclude_lead_id: Optional[int] = None,
    now_utc: Optional[datetime] = None,
) -> Optional[RequestedSlot]:
    """Horário pedido na mensagem atual (hora explícita) no dia dito nela — ou, sem dia, no
    último dia falado na conversa (`earlier_messages`, do mais recente para o mais antigo).
    None quando não há um horário inequívoco ou ele já passou."""
    wanted_time = requested_time(inbound_text)
    if wanted_time is None:
        return None
    reference = meeting_date_guard.latest_day_word([inbound_text]) or meeting_date_guard.latest_day_word(
        earlier_messages
    )
    if not reference:
        return None
    now = now_utc or datetime.now(timezone.utc)
    tz = _tz(tz_name)
    day = meeting_date_guard.resolve_day_reference(reference, meeting_date_guard.local_today(tz_name, now))
    if day is None:
        return None
    start = datetime.combine(day, wanted_time, tzinfo=tz)
    if start <= now:
        return None
    end = start + timedelta(minutes=duration_minutes)
    slots = list(busy_slots or [])
    conflicts = []
    for slot in slots:
        if _has_conflict([slot], start, end, exclude_lead_id=exclude_lead_id):
            try:
                conflicts.append((
                    datetime.fromisoformat(str(slot.get("start_at"))).astimezone(tz),
                    datetime.fromisoformat(str(slot.get("end_at"))).astimezone(tz),
                ))
            except (TypeError, ValueError):
                continue
    return RequestedSlot(start=start, end=end, free=not conflicts, conflicts=conflicts)


def _fmt_hour(value: datetime) -> str:
    return f"{value.hour}h{value.minute:02d}" if value.minute else f"{value.hour}h"


def build_agenda_fact_block(slot: Optional[RequestedSlot]) -> str:
    """Bloco para o FIM do prompt da Filha (vence instruções anteriores mais vagas)."""
    if slot is None:
        return ""
    weekday = meeting_date_guard.WEEKDAY_NAMES_PT[slot.start.weekday()]
    asked = f"{weekday}, {slot.start.strftime('%d/%m')}, às {_fmt_hour(slot.start)}"
    if slot.free:
        return (
            "\nVERIFICAÇÃO DA AGENDA FEITA PELO SISTEMA (facto — não volte a deduzir):\n"
            f"O lead pediu {asked}. A agenda NÃO tem nenhum compromisso nesse horário: não está "
            "ocupado nem reservado.\n"
            "- Se a sessão cabe no horário de atendimento do profissional (instruções do negócio), "
            "aceite este horário — avance para o passo seguinte do roteiro (pedir o dado que falta "
            "ou resumir a marcação), sem oferecer outro horário.\n"
            "- A única razão para não aceitar é a sessão não caber no horário de atendimento; nesse "
            "caso diga exatamente esse motivo e proponha o horário válido mais próximo.\n"
            "- Não escreva que este horário está ocupado, indisponível, sem vaga ou já reservado — "
            "seria falso e o cliente perde-se.\n"
        )
    busy = "; ".join(f"{_fmt_hour(s)}–{_fmt_hour(e)}" for s, e in slot.conflicts)
    return (
        "\nVERIFICAÇÃO DA AGENDA FEITA PELO SISTEMA (facto — não volte a deduzir):\n"
        f"O lead pediu {asked}. Esse horário colide com um compromisso já marcado ({busy}). "
        "Diga que esse horário já está ocupado e proponha o horário livre mais próximo que caiba "
        "no horário de atendimento.\n"
    )
