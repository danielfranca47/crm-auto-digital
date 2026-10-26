"""Horário de atendimento de cada profissional, lido do texto do perfil, para o código decidir
se uma sessão cabe nele.

O horário de atendimento só existe em texto livre (`custom_instructions` e, depois de
fix-disponibilidade-campo-duplo-sentido, `professional_availability`). Pedir à Filha que
conferisse "cabe no horário" no meio da conversa não funcionou (teste real: recusou 11h de
sábado com a Val a atender das 11h às 17h, e aceitou 17h para 1h). Converter o texto numa tabela
é uma tarefa simples para a IA; fazemo-lo uma vez por texto (cache em memória) e a conta de
"cabe ou não" passa a ser do código.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

from app.services import llm_service

# nome do profissional → dia da semana (0 = segunda) → intervalos [início, fim) em minutos
Hours = Dict[str, Dict[int, List[Tuple[int, int]]]]

_DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_HHMM_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*$")
_CACHE: Dict[str, Optional[Hours]] = {}

_EXTRACTION_PROMPT = (
    "Leia o texto de configuração de um negócio e extraia SÓ os horários em que cada profissional "
    "faz sessões/atendimentos com clientes. Ignore o horário em que o assistente responde "
    "mensagens e qualquer grelha que o texto diga para ignorar.\n"
    "Para cada profissional e cada dia da semana em que atende, dê os intervalos [início, fim] em "
    "HH:MM, em que o fim é a hora a que as sessões têm de ACABAR. Dias: mon, tue, wed, thu, fri, "
    "sat, sun. Dia sem atendimento: não o inclua. Se o texto não disser o nome do profissional, "
    "use \"Profissional\".\n"
    "Se o texto não tiver horários de atendimento claros, devolva {\"professionals\": []}.\n"
    "Responda SOMENTE JSON, neste formato:\n"
    "{\"professionals\": [{\"name\": \"Ana\", \"days\": {\"mon\": [[\"09:00\", \"13:00\"], "
    "[\"14:00\", \"18:00\"]], \"sat\": [[\"10:00\", \"14:00\"]]}}]}\n\n"
    "TEXTO:\n"
)


@dataclass
class HoursVerdict:
    fits: bool
    fitting: List[str] = field(default_factory=list)  # profissionais em que a sessão cabe
    checked: Dict[str, List[Tuple[int, int]]] = field(default_factory=dict)  # intervalos desse dia
    suggestion: Optional[time] = None  # início que cabe, quando não cabe
    suggestion_for: Optional[str] = None


def source_text(ai_profile: Dict[str, Any]) -> str:
    parts = [
        str(ai_profile.get("professional_availability") or "").strip(),
        str(ai_profile.get("custom_instructions") or "").strip(),
    ]
    return "\n\n".join(p for p in parts if p)


def _minutes(value: Any) -> Optional[int]:
    m = _HHMM_RE.match(str(value or ""))
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if hour > 24 or minute > 59 or (hour == 24 and minute):
        return None
    return hour * 60 + minute


def parse_hours(payload: Any) -> Optional[Hours]:
    """Valida a resposta da IA. None quando não há nenhum horário utilizável."""
    if not isinstance(payload, dict) or not isinstance(payload.get("professionals"), list):
        return None
    hours: Hours = {}
    for prof in payload["professionals"]:
        if not isinstance(prof, dict) or not isinstance(prof.get("days"), dict):
            continue
        name = str(prof.get("name") or "Profissional").strip() or "Profissional"
        days: Dict[int, List[Tuple[int, int]]] = {}
        for key, ranges in prof["days"].items():
            if key not in _DAY_KEYS or not isinstance(ranges, list):
                continue
            for item in ranges:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    continue
                start, end = _minutes(item[0]), _minutes(item[1])
                if start is not None and end is not None and start < end:
                    days.setdefault(_DAY_KEYS.index(key), []).append((start, end))
        if days:
            hours[name] = days
    return hours or None


def get_hours(ai_profile: Dict[str, Any], logger: Optional[logging.Logger] = None) -> Optional[Hours]:
    """Tabela de horários do perfil; uma chamada à IA por texto diferente. None quando o texto
    não tem horários ou a leitura falha — quem chama mantém o comportamento sem tabela."""
    text = source_text(ai_profile)
    if not text:
        return None
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if key in _CACHE:
        return _CACHE[key]
    log = logger or logging.getLogger(__name__)
    hours: Optional[Hours] = None
    try:
        raw = llm_service.generate_professional_hours(_EXTRACTION_PROMPT + text, ai_profile=ai_profile)
        start, end = raw.find("{"), raw.rfind("}")
        hours = parse_hours(json.loads(raw[start:end + 1])) if start != -1 and end > start else None
    except Exception as exc:  # leitura falhou: fica sem tabela, como antes
        log.warning("event=professional_hours_extract_failed exc_type=%s exc=%s", type(exc).__name__, exc)
    log.info(
        "event=professional_hours_extracted hash=%s hours=%s",
        key[:12],
        json.dumps({n: {_DAY_KEYS[d]: r for d, r in days.items()} for n, days in (hours or {}).items()}),
    )
    _CACHE[key] = hours
    return hours


def mentioned_professional(hours: Hours, messages: List[str]) -> Optional[str]:
    """Profissional nomeado pelo lead (mensagem mais recente que nomeie algum)."""
    for text in messages:
        for name in hours:
            if name != "Profissional" and re.search(rf"\b{re.escape(name)}\b", text or "", re.IGNORECASE):
                return name
    return None


def check(hours: Hours, start: datetime, end: datetime, professional: Optional[str] = None) -> HoursVerdict:
    """A sessão [start, end) cabe no horário de atendimento? Com `professional`, só nesse."""
    weekday = start.weekday()
    s = start.hour * 60 + start.minute
    e = s + int((end - start).total_seconds() // 60)
    names = [professional] if professional in hours else list(hours)
    verdict = HoursVerdict(fits=False)
    duration = e - s
    for name in names:
        ranges = sorted(hours[name].get(weekday, []))
        verdict.checked[name] = ranges
        if any(a <= s and e <= b for a, b in ranges):
            verdict.fitting.append(name)
    verdict.fits = bool(verdict.fitting)
    if not verdict.fits:
        # início válido mais próximo do pedido, entre os profissionais considerados
        best: Optional[Tuple[int, int, str]] = None
        for name, ranges in verdict.checked.items():
            for a, b in ranges:
                if b - a < duration:
                    continue
                candidate = min(max(s, a), b - duration)
                distance = abs(candidate - s)
                if best is None or distance < best[0]:
                    best = (distance, candidate, name)
        if best:
            verdict.suggestion = time(best[1] // 60, best[1] % 60)
            verdict.suggestion_for = best[2]
    return verdict
