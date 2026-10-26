"""Guardrail de código: a data da marcação tem de cair no dia que o cliente pediu.

O LLM resolve bem *qual* dia o cliente quer ("sexta", "amanhã"), mas erra com
frequência a conversão para data — mesmo com a tabela_de_dias no prompt (em
teste real: "Dia: 28/10 (sexta-feira)", sendo 28/10 uma quarta). Aqui a
referência do dia (sinal `meeting_day_reference` da Filha, ou o dia da semana
escrito junto da data na mensagem) é convertida em data de forma determinística
e, se não bater com `meeting_datetime_candidate`, corrigimos o candidato e a
data escrita na mensagem — o cliente vê o mesmo dia que fica gravado.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

WEEKDAY_NAMES_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
_WEEKDAY_SHORT_PT = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
_MONTH_NAMES_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

_RELATIVE_OFFSETS = {"hoje": 0, "amanha": 1, "depois de amanha": 2}
_WEEKDAY_BY_KEY = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6,
}

# Dia da semana escrito no texto. "segunda" sozinho também quer dizer "segunda opção" —
# por isso só é aceite como dia quando vem colado a uma data (ver _weekday_near).
_WEEKDAY_RE = re.compile(
    r"\b(segunda|ter[cç]a|quarta|quinta|sexta)(?:[\s-]*feira)?\b|\b(s[aá]bado|domingo)\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_LONG_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + "|".join(_MONTH_NAMES_PT + ("marco",)) + r")\b",
    re.IGNORECASE,
)
_RELATIVE_RE = re.compile(r"\b(depois de amanh[aã]|amanh[aã]|hoje)\b", re.IGNORECASE)
_ISO_PREFIX_RE =re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})")
_NEAR_WINDOW = 25  # caracteres entre data e dia da semana para os considerar o mesmo "dia"


@dataclass
class DateGuardResult:
    candidate: Optional[str]
    message_text: str
    trace: Dict[str, Any] = field(default_factory=dict)


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn"
    )


def _weekday_key(raw: str) -> Optional[int]:
    norm = _strip_accents(raw.lower()).replace("-feira", "").replace(" feira", "").strip()
    return _WEEKDAY_BY_KEY.get(norm)


def local_today(tz_name: Optional[str], now_utc: Optional[datetime] = None) -> date:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        tz = ZoneInfo(str(tz_name)) if tz_name else timezone.utc
    except Exception:
        tz = timezone.utc
    return now.astimezone(tz).date()


def _infer_year(day: int, month: int, today: date) -> Optional[date]:
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if candidate >= today:
            return candidate
    return None


def _next_weekday(today: date, weekday: int) -> date:
    delta = (weekday - today.weekday()) % 7
    return today + timedelta(days=delta or 7)


def _resolve_reference(reference: str, today: date, current: date) -> Optional[date]:
    """Converte a referência do dia em data. Para dia da semana, mantém `current`
    quando já cai nesse dia (respeita "sexta da próxima semana" quando o LLM acerta)."""
    norm = _strip_accents(reference.strip().lower())
    for key in ("depois de amanha", "amanha", "hoje"):
        if re.search(rf"\b{key}\b", norm):
            return today + timedelta(days=_RELATIVE_OFFSETS[key])
    match = _NUMERIC_DATE_RE.search(norm)
    if match:
        return _infer_year(int(match.group(1)), int(match.group(2)), today)
    for token in re.split(r"[\s,]+", norm):
        weekday = _weekday_key(token)
        if weekday is not None:
            if current.weekday() == weekday and current >= today:
                return current
            return _next_weekday(today, weekday)
    return None


def _find_dates(text: str, today: date) -> List[Tuple[int, int, date, str]]:
    """(início, fim, data, tipo) de cada data escrita no texto."""
    found = []
    for m in _NUMERIC_DATE_RE.finditer(text):
        resolved = _infer_year(int(m.group(1)), int(m.group(2)), today)
        if resolved:
            found.append((m.start(), m.end(), resolved, "numeric"))
    for m in _LONG_DATE_RE.finditer(text):
        month_key = _strip_accents(m.group(2).lower())
        month = [_strip_accents(n) for n in _MONTH_NAMES_PT].index(month_key) + 1
        resolved = _infer_year(int(m.group(1)), month, today)
        if resolved:
            found.append((m.start(), m.end(), resolved, "long"))
    return sorted(found)


def _weekday_near(text: str, start: int, end: int) -> Optional[re.Match]:
    best = None
    for m in _WEEKDAY_RE.finditer(text):
        gap = start - m.end() if m.end() <= start else m.start() - end
        if 0 <= gap <= _NEAR_WINDOW and (best is None or gap < best[0]):
            best = (gap, m)
    return best[1] if best else None


def _format_like(original: str, new_date: date, kind: str) -> str:
    if kind == "long":
        return f"{new_date.day} de {_MONTH_NAMES_PT[new_date.month - 1]}"
    day_part, month_part = original.split("/")[:2]
    day = f"{new_date.day:02d}" if len(day_part) == 2 else str(new_date.day)
    month = f"{new_date.month:02d}" if len(month_part) == 2 else str(new_date.month)
    if original.count("/") == 2:
        year_part = original.split("/")[2]
        year = str(new_date.year)[-len(year_part):]
        return f"{day}/{month}/{year}"
    return f"{day}/{month}"


def _weekday_like(original: str, weekday: int) -> str:
    full = "-feira" in original.lower() or " feira" in original.lower()
    name = WEEKDAY_NAMES_PT[weekday] if full or weekday >= 5 else _WEEKDAY_SHORT_PT[weekday]
    return name.capitalize() if original[:1].isupper() else name


def _fix_text(text: str, old: date, new: date, today: date) -> str:
    """Reescreve no texto cada data (e o dia da semana colado a ela) que contradiga `new`:
    a data antiga do candidato, ou um par data+dia da semana em que o dia da semana é o
    certo mas a data não."""
    edits: List[Tuple[int, int, str]] = []
    for start, end, written, kind in _find_dates(text, today):
        weekday_match = _weekday_near(text, start, end)
        weekday_written = _weekday_key(weekday_match.group(0)) if weekday_match else None
        date_is_wrong = written != new and (
            written == old
            or (weekday_written == new.weekday() and abs((written - new).days) <= 7)
        )
        if date_is_wrong:
            edits.append((start, end, _format_like(text[start:end], new, kind)))
        if (date_is_wrong or written == new) and weekday_match and weekday_written != new.weekday():
            edits.append((
                weekday_match.start(), weekday_match.end(),
                _weekday_like(weekday_match.group(0), new.weekday()),
            ))
    for start, end, replacement in sorted(set(edits), reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def _relative_near(text: str, start: int, end: int) -> Optional[str]:
    for m in _RELATIVE_RE.finditer(text):
        gap = start - m.end() if m.end() <= start else m.start() - end
        if 0 <= gap <= _NEAR_WINDOW:
            return m.group(0)
    return None


def _reference_from_text(text: str, current: date, today: date) -> Optional[str]:
    """Sem sinal da Filha: o dia da semana (ou "amanhã"/"hoje") escrito junto da data do
    candidato; senão, o único dia da semana inequívoco no texto. "amanhã" solto não conta
    ("até amanhã!" não diz nada sobre o dia marcado)."""
    for start, end, written, _kind in _find_dates(text, today):
        if written == current:
            match = _weekday_near(text, start, end)
            if match:
                return match.group(0)
            relative = _relative_near(text, start, end)
            if relative:
                return relative
    explicit = {
        _weekday_key(m.group(0))
        for m in _WEEKDAY_RE.finditer(text)
        if m.group(2) or "feira" in m.group(0).lower()
    }
    if len(explicit) == 1:
        return WEEKDAY_NAMES_PT[explicit.pop()]
    return None


def _written_by_lead(reference: str, lead_messages: List[str]) -> bool:
    match = _NUMERIC_DATE_RE.search(reference)
    if not match:
        return True
    wanted = (int(match.group(1)), int(match.group(2)))
    return any(
        (int(m.group(1)), int(m.group(2))) == wanted
        for text in lead_messages
        for m in _NUMERIC_DATE_RE.finditer(text or "")
    )


def _day_mentioned(reference: str, messages: List[str], today: date) -> bool:
    """O dia da referência (dia da semana ou hoje/amanhã) aparece em alguma das mensagens —
    pelo nome, por "amanhã"/"hoje" que caia nesse dia, ou por uma data dd/mm desse dia."""
    target = _resolve_reference(reference, today, today + timedelta(days=-1))
    if target is None:
        return True
    for text in messages:
        text = text or ""
        for m in _WEEKDAY_RE.finditer(text):
            if _weekday_key(m.group(0)) == target.weekday():
                return True
        for m in _RELATIVE_RE.finditer(text):
            if _resolve_reference(m.group(0), today, today) == target:
                return True
        if any(written == target for _s, _e, written, _k in _find_dates(text, today)):
            return True
    return False


def _latest_lead_day_word(lead_messages: List[str]) -> Optional[str]:
    """Última palavra de dia nas mensagens (da mais recente para a mais antiga); dentro de
    uma mensagem, a última ocorrência."""
    for text in lead_messages:
        text = text or ""
        hits = [(m.start(), m.group(0)) for m in _RELATIVE_RE.finditer(text)]
        hits += [
            (m.start(), m.group(0))
            for m in _WEEKDAY_RE.finditer(text)
            if not m.group(0).lower().startswith("segunda") or "feira" in m.group(0).lower()
        ]
        hits += [(m.start(), m.group(0)) for m in _NUMERIC_DATE_RE.finditer(text)]
        if hits:
            return max(hits)[1]
    return None


def reconcile_meeting_date(
    candidate: Optional[str],
    message_text: str,
    *,
    day_reference: Optional[str],
    tz_name: Optional[str],
    now_utc: Optional[datetime] = None,
    lead_messages: Optional[List[str]] = None,
    earlier_messages: Optional[List[str]] = None,
    is_confirmation: bool = False,
) -> DateGuardResult:
    """`lead_messages`: textos do lead, do mais recente para o mais antigo. Quando vem, um
    `dd/mm` em `day_reference` só vale se o lead o escreveu — senão é a data que o LLM
    calculou (a que queremos conferir), e vale a última palavra de dia dita pelo lead.

    `earlier_messages` + `is_confirmation`: no turno em que o lead confirma, o dia tem de já
    ter sido falado na conversa (lead ou agente, antes desta resposta). Em teste real o LLM
    confirmou "quarta-feira" depois de propor só horários de terça; nesse caso vale o último
    dia falado."""
    text = message_text or ""
    if not candidate or not isinstance(candidate, str):
        return DateGuardResult(candidate, text)
    iso = _ISO_PREFIX_RE.match(candidate)
    if not iso:
        return DateGuardResult(candidate, text)
    try:
        current = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    except ValueError:
        return DateGuardResult(candidate, text)

    today = local_today(tz_name, now_utc)
    source = "signal"
    reference = str(day_reference).strip() if isinstance(day_reference, str) and day_reference.strip() else None
    if reference and lead_messages is not None and not _written_by_lead(reference, lead_messages):
        source = "lead_messages"
        reference = _latest_lead_day_word(lead_messages)
    if (
        reference
        and is_confirmation
        and earlier_messages
        and not _NUMERIC_DATE_RE.search(reference)
        and not _day_mentioned(reference, earlier_messages, today)
    ):
        fallback = _latest_lead_day_word(earlier_messages)
        if fallback:
            source = "earlier_messages"
            reference = fallback
    resolved =_resolve_reference(reference, today, current) if reference else None
    if resolved is None:
        source = "message_text"
        reference = _reference_from_text(text, current, today)
        resolved = _resolve_reference(reference, today, current) if reference else None
    if resolved is None:
        return DateGuardResult(candidate, text, {"applied": False, "reason": "no_reference"})

    new_candidate = candidate
    if resolved != current:
        new_candidate = candidate[: iso.start(1)] + resolved.isoformat() + candidate[iso.end(3):]
    new_text = _fix_text(text, current, resolved, today)
    trace = {
        "applied": resolved != current or new_text != text,
        "reference": reference,
        "reference_source": source,
        "candidate_from": candidate,
        "candidate_to": new_candidate,
        "text_changed": new_text != text,
    }
    return DateGuardResult(new_candidate, new_text, trace)
