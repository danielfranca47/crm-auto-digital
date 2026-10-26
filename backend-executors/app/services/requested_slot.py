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
from app.services.meeting_scheduler import _ensure_aware, _has_conflict

# "11h", "11 h", "14h30", "15:00". Duração ("de 1h", "1h30 de massagem") e limites
# ("depois das 19h", "a partir das 15h") não são um horário pedido.
_TIME_RE = re.compile(r"(?<![\d/:])(\d{1,2})(?:\s*h\s*(\d{2})?|:(\d{2}))(?![\d/])", re.IGNORECASE)
_NOT_A_SLOT_BEFORE = re.compile(
    r"(depois\s+d[ao]s?|a\s+partir\s+d[ao]s?|antes\s+d[ao]s?|at[eé]\s+[àa]s?|ap[oó]s\s+[ao]s?|"
    r"entre\s+[ao]s?|\bde|\bcom)\s*$",
    re.IGNORECASE,
)
_EARLIEST_HOUR, _LATEST_HOUR = 6, 23  # "1h", "2h" são durações, não horas de sessão
_DURATION_MIN_RE = re.compile(r"\b(\d{2,3})\s*min", re.IGNORECASE)
_DURATION_H_RE = re.compile(r"\bde\s+(\d)\s*h(?:ora)?s?\s*(\d{2})?(?!\d)", re.IGNORECASE)
_DURATION_WORDS = (
    (re.compile(r"\b(uma|1)\s+hora\s+e\s+meia\b", re.IGNORECASE), 90),
    (re.compile(r"\b(uma|1)\s+hora\b", re.IGNORECASE), 60),
    (re.compile(r"\bmeia\s+hora\b", re.IGNORECASE), 30),
)


@dataclass
class RequestedSlot:
    start: datetime  # no fuso do perfil
    end: datetime
    free: bool
    conflicts: List[Tuple[datetime, datetime]] = field(default_factory=list)
    duration_known: bool = False  # duração dita pelo lead (senão é a duração por omissão do perfil)


def requested_duration(messages: List[str]) -> Optional[int]:
    """Duração da sessão dita pelo lead ("60 minutos", "de 1h30", "uma hora"), na mensagem mais
    recente que a mencione."""
    for text in messages:
        text = text or ""
        m = _DURATION_MIN_RE.search(text)
        if m and 10 <= int(m.group(1)) <= 240:
            return int(m.group(1))
        m = _DURATION_H_RE.search(text)
        if m and 1 <= int(m.group(1)) <= 3:
            return int(m.group(1)) * 60 + int(m.group(2) or 0)
        for pattern, minutes in _DURATION_WORDS:
            if pattern.search(text):
                return minutes
    return None


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
    lead_messages: Optional[List[str]] = None,
) -> Optional[RequestedSlot]:
    """Horário pedido na mensagem atual (hora explícita) no dia dito nela — ou, sem dia, no
    último dia falado na conversa (`earlier_messages`, do mais recente para o mais antigo).
    A duração é a que o lead disse (`lead_messages`, mais recente primeiro) ou, sem isso,
    `duration_minutes`. None quando não há um horário inequívoco ou ele já passou."""
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
    said_duration = requested_duration([inbound_text] + list(lead_messages or []))
    end = start + timedelta(minutes=said_duration or duration_minutes)
    slots = list(busy_slots or [])
    conflicts = []
    for slot in slots:
        if _has_conflict([slot], start, end, exclude_lead_id=exclude_lead_id):
            try:
                # sem fuso = UTC, como em _has_conflict (eventos importados do Google podem vir assim)
                conflicts.append((
                    _ensure_aware(datetime.fromisoformat(str(slot.get("start_at"))), "UTC").astimezone(tz),
                    _ensure_aware(datetime.fromisoformat(str(slot.get("end_at"))), "UTC").astimezone(tz),
                ))
            except (TypeError, ValueError):
                continue
    return RequestedSlot(
        start=start, end=end, free=not conflicts, conflicts=conflicts, duration_known=said_duration is not None
    )


def _fmt_hour(value: datetime) -> str:
    return f"{value.hour}h{value.minute:02d}" if value.minute else f"{value.hour}h"


def _fmt_minutes(value: int) -> str:
    hour, minute = divmod(value, 60)
    return f"{hour}h{minute:02d}" if minute else f"{hour}h"


def _ranges_text(ranges: List[Tuple[int, int]]) -> str:
    return " e ".join(f"{_fmt_minutes(a)}–{_fmt_minutes(b)}" for a, b in ranges)


def _hours_verdict_block(slot: RequestedSlot, verdict, asked: str, ends: str) -> str:
    """Bloco com o veredicto completo (agenda + horário de atendimento), decidido em código."""
    weekday = meeting_date_guard.WEEKDAY_NAMES_PT[slot.start.weekday()]
    header = (
        "\nVERIFICAÇÃO DO HORÁRIO PEDIDO (feita pelo sistema — é um facto, não volte a deduzir):\n"
        f"O lead pediu {asked}; {ends}.\n"
        "- Agenda: nenhum compromisso nesse intervalo.\n"
    )
    if verdict.fits:
        who = " e ".join(verdict.fitting)
        hours = "; ".join(f"{n}: {weekday} {_ranges_text(verdict.checked[n])}" for n in verdict.fitting)
        return (
            header
            + f"- Horário de atendimento: a sessão cabe ({hours}).\n"
            f"→ O horário está LIVRE com {who}. Aceite-o: avance para o passo seguinte do roteiro "
            "(pedir o dado que falta ou resumir a marcação), sem oferecer outro horário e sem dizer que "
            "está ocupado, indisponível ou sem vaga.\n"
        )
    open_today = {n: r for n, r in verdict.checked.items() if r}
    if not open_today:
        who = " nem ".join(verdict.checked) if len(verdict.checked) > 1 else next(iter(verdict.checked))
        reason = f"{weekday} não há atendimento ({who})"
    else:
        reason = "; ".join(f"{n} atende {weekday} {_ranges_text(r)}" for n, r in open_today.items())
        reason = f"{reason}, e esta sessão não cabe nesse horário"
    suggestion = (
        f" e proponha {_fmt_hour(datetime.combine(slot.start.date(), verdict.suggestion))} com "
        f"{verdict.suggestion_for} (início mais próximo que cabe)"
        if verdict.suggestion
        else " e proponha outro dia em que haja atendimento"
    )
    return (
        header
        + f"- Horário de atendimento: FORA — {reason}.\n"
        f"→ Diga ao lead que esse horário está fora do horário de atendimento{suggestion}. Não diga "
        "que está ocupado: o motivo é o horário de atendimento.\n"
    )


def build_agenda_fact_block(
    slot: Optional[RequestedSlot],
    hours_verdict=None,
    *,
    alternative: Optional[Tuple[time, str]] = None,
    hours_known: bool = False,
) -> str:
    """Bloco para o FIM do prompt da Filha (vence instruções anteriores mais vagas).
    `hours_verdict` (professional_hours.check) quando o horário de atendimento foi lido; sem
    ele, a Filha confere o horário de atendimento sozinha. Com o horário ocupado e o horário de
    atendimento lido (`hours_known`), `alternative` (professional_hours.nearest_free_start) é o
    horário a propor — None quando nesse dia não há nenhum."""
    if slot is None:
        return ""
    weekday = meeting_date_guard.WEEKDAY_NAMES_PT[slot.start.weekday()]
    asked = f"{weekday}, {slot.start.strftime('%d/%m')}, às {_fmt_hour(slot.start)}"
    minutes = int((slot.end - slot.start).total_seconds() // 60)
    ends = (
        f"a sessão de {minutes} min terminaria às {_fmt_hour(slot.end)}"
        if slot.duration_known
        else f"com {minutes} min (duração ainda por confirmar) a sessão terminaria às {_fmt_hour(slot.end)}"
    )
    if slot.free and hours_verdict is not None:
        return _hours_verdict_block(slot, hours_verdict, asked, ends)
    if slot.free:
        # A ordem importa: dito só "a agenda está livre", a IA passou a aceitar sessões que
        # acabavam depois do fim do horário do profissional (teste real: Val às 17h para 1h).
        return (
            "\nVERIFICAÇÃO DO HORÁRIO PEDIDO (o sistema verificou a agenda; o horário de atendimento "
            "é você que confere):\n"
            f"O lead pediu {asked}; {ends}.\n"
            "1. Horário de atendimento — confira nas instruções do negócio a que horas o profissional "
            "começa e termina nesse dia da semana. Se a sessão começa antes do início ou termina "
            "depois do fim (ex.: terminaria às 18h e o profissional atende até às 17h), ela NÃO cabe: "
            "diga que está fora do horário de atendimento e proponha o último início que caiba.\n"
            "2. Agenda — o sistema confirmou que NÃO há nenhum compromisso nesse intervalo: o horário "
            "não está ocupado nem reservado. Nunca diga que está ocupado, sem vaga, indisponível ou já "
            "reservado — seria falso e o cliente perde-se.\n"
            "3. Se cabe no horário de atendimento, aceite-o: avance para o passo seguinte do roteiro "
            "(pedir o dado que falta ou resumir a marcação), sem oferecer outro horário.\n"
        )
    busy = "; ".join(f"{_fmt_hour(s)}–{_fmt_hour(e)}" for s, e in slot.conflicts)
    if hours_known:
        if alternative is not None:
            start, who = alternative
            proposal = (
                f"proponha {_fmt_hour(datetime.combine(slot.start.date(), start))} com {who} — o início "
                "livre mais próximo que cabe no horário de atendimento, calculado pelo sistema: proponha "
                "exatamente este"
            )
        else:
            proposal = (
                "nesse dia não há outro início livre que caiba no horário de atendimento: proponha "
                "outro dia"
            )
        return (
            "\nVERIFICAÇÃO DO HORÁRIO PEDIDO (feita pelo sistema — é um facto, não volte a deduzir):\n"
            f"O lead pediu {asked}; {ends}. Esse horário colide com um compromisso já marcado ({busy}).\n"
            f"→ Diga que esse horário já está ocupado e {proposal}.\n"
        )
    return (
        "\nVERIFICAÇÃO DO HORÁRIO PEDIDO (o sistema verificou a agenda):\n"
        f"O lead pediu {asked}; {ends}. Esse horário colide com um compromisso já marcado ({busy}). "
        "Diga que esse horário já está ocupado e proponha o horário livre mais próximo que caiba "
        "no horário de atendimento.\n"
    )
