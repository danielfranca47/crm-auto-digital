"""Última proposta de horário feita ao cliente, e qual delas ele aceitou — lidas do histórico.

No turno em que o cliente confirma ("Pode ser sim, marca aí!"), quem escolhia o horário a gravar
era a Filha, sozinha — e em teste real gravou a 1.ª proposta (recusada) em vez da 2.ª (aceite).
Nada guardava "o que foi proposto": o candidato de cada turno só existe no rasto desse turno.
Aqui o código lê, das mensagens já trocadas, o último horário posto em cima da mesa (as opções do
agente na última mensagem que tinha horas, ou a hora que o próprio cliente disse) e decide qual
foi aceite. O decision_engine dá isso à Filha como facto e confere o candidato dela depois.

Também serve a remarcação: lá a pergunta é "o candidato é uma contraproposta que o cliente ainda
não aceitou?" — as mesmas `last_proposal` + `accepted_slot`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from app.services import meeting_date_guard as mdg
from app.services import requested_slot

# Uma opção acaba no "ou", no fim da frase ou na quebra de linha.
_SEGMENT_SPLIT_RE = re.compile(r"\s+ou\s+|[.?!;]\s+|\n+", re.IGNORECASE)
# Frase que fala de um horário que NÃO é proposta ("às 21h não temos", "está ocupado").
_NEGATIVE_RE = re.compile(
    r"\bn[aã]o\b|\bfora\b|ocupad|indispon|infelizmente|fechad|j[aá] passou", re.IGNORECASE
)
# "das 11h às 17h": as duas horas são um intervalo de atendimento, não uma proposta.
_RANGE_RE = re.compile(r"\bd[ao]s?\s+\d{1,2}(?:\s*h\s*\d{0,2}|:\d{2})\s*(?:[àa]s?|at[eé])\s*$", re.IGNORECASE)
_RANGE_START_RE = re.compile(r"^\s*(?:[àa]s?|at[eé])\s+(?:[àa]s\s+)?\d{1,2}(?:\s*h|:\d{2})", re.IGNORECASE)
_RANGE_LEAD_RE = re.compile(r"\bd[ao]s?\s*$", re.IGNORECASE)
_NOT_A_DAY_AFTER = re.compile(r"^\s*(op[cç][aã]o|vez|alternativa)", re.IGNORECASE)


@dataclass
class ProposedOption:
    start: datetime  # no fuso do perfil
    professional: Optional[str] = None
    text: str = ""


@dataclass
class Proposal:
    options: List[ProposedOption] = field(default_factory=list)
    source: str = "none"  # "agent" | "lead" | "none"
    text: str = ""


@dataclass
class AcceptedSlot:
    option: Optional[ProposedOption]
    source: str  # lead_stated | matched_option | single_option | ambiguous | none
    options: List[ProposedOption] = field(default_factory=list)
    proposal_text: str = ""

    @property
    def start(self) -> Optional[datetime]:
        return self.option.start if self.option else None


def _tz(tz_name: Optional[str]):
    try:
        return ZoneInfo(str(tz_name)) if tz_name else timezone.utc
    except Exception:
        return timezone.utc


def _times(text: str) -> List[Tuple[int, int, time]]:
    """(início, fim, hora) de cada hora que pode ser uma proposta."""
    found = []
    for m in requested_slot._TIME_RE.finditer(text or ""):
        before = text[max(0, m.start() - 20):m.start()]
        if requested_slot._NOT_A_SLOT_BEFORE.search(before[-14:]) or _RANGE_LEAD_RE.search(before):
            continue
        if _RANGE_RE.search(before) or _RANGE_START_RE.match(text[m.end():]):
            continue  # "das 11h às 17h" — uma das pontas de um intervalo
        hour, minute = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
        if not (requested_slot._EARLIEST_HOUR <= hour <= requested_slot._LATEST_HOUR) or minute > 59:
            continue
        found.append((m.start(), m.end(), time(hour, minute)))
    return found


def _days(text: str, today: date) -> List[Tuple[int, date]]:
    """(posição, data) de cada dia escrito. Uma data dd/mm com o dia da semana colado que não
    bate com ela vale pelo dia da semana (é a data que o LLM costuma errar)."""
    found: List[Tuple[int, date]] = []
    for m in mdg._RELATIVE_RE.finditer(text):
        resolved = mdg.resolve_day_reference(m.group(0), today)
        if resolved:
            found.append((m.start(), resolved))
    numeric_spans = []
    for start, end, written, _kind in mdg._find_dates(text, today):
        weekday = mdg._weekday_near(text, start, end)
        if weekday and mdg._weekday_key(weekday.group(0)) != written.weekday():
            written = mdg.resolve_day_reference(weekday.group(0), today) or written
        numeric_spans.append((start, end))
        found.append((start, written))
    for m in mdg._WEEKDAY_RE.finditer(text):
        word = m.group(0)
        if word.lower().startswith("segunda") and "feira" not in word.lower() and _NOT_A_DAY_AFTER.match(
            text[m.end():]
        ):
            continue
        if any(abs(m.start() - s) <= mdg._NEAR_WINDOW or abs(m.end() - e) <= mdg._NEAR_WINDOW for s, e in numeric_spans):
            continue  # já contado pela data colada a ele
        resolved = mdg.resolve_day_reference(word, today)
        if resolved:
            found.append((m.start(), resolved))
    return sorted(found)


def _professional_in(text: str, professionals: Sequence[str]) -> Optional[str]:
    hits = [
        (m.start(), name)
        for name in professionals
        if name and name != "Profissional"
        for m in re.finditer(rf"\b{re.escape(name)}\b", text or "", re.IGNORECASE)
    ]
    return min(hits)[1] if hits else None


def options_in_text(
    text: str,
    *,
    tz_name: Optional[str],
    today: date,
    fallback_day: Optional[date] = None,
    professionals: Sequence[str] = (),
) -> List[ProposedOption]:
    """Opções de horário (dia + hora) escritas num texto. A hora leva o dia mais próximo antes
    dela; sem dia antes, o primeiro dia depois dela na mesma opção; senão o último dia do texto,
    senão `fallback_day`. Horas em frases negativas ("às 21h não dá") não são propostas."""
    text = text or ""
    tz = _tz(tz_name)
    days = _days(text, today)
    segments = []
    pos = 0
    for m in _SEGMENT_SPLIT_RE.finditer(text):
        segments.append((pos, m.start()))
        pos = m.end()
    segments.append((pos, len(text)))
    options: List[ProposedOption] = []
    seen = set()
    for seg_start, seg_end in segments:
        segment = text[seg_start:seg_end]
        if _NEGATIVE_RE.search(segment):
            continue
        for t_start, _t_end, wanted in _times(segment):
            abs_pos = seg_start + t_start
            before = [d for p, d in days if p < abs_pos]
            after = [d for p, d in days if abs_pos < p < seg_end]
            day = before[-1] if before else (after[0] if after else (days[-1][1] if days else fallback_day))
            if day is None:
                continue
            start = datetime.combine(day, wanted, tzinfo=tz)
            professional = _professional_in(segment, professionals)
            if start in seen:
                continue
            seen.add(start)
            options.append(ProposedOption(start=start, professional=professional, text=segment.strip()))
    if len(options) > 1 and not any(o.professional for o in options[1:]):
        # "às 11h ou às 15h com a Val": o terapeuta dito uma vez vale para todas as opções
        shared = _professional_in(text, professionals)
        for o in options:
            o.professional = o.professional or shared
    return options


def _body(item: Dict[str, Any]) -> str:
    return str(item.get("body") or item.get("text") or "")


def _is_inbound(item: Dict[str, Any]) -> bool:
    return str(item.get("model") or "").lower() == "inbound"


def last_proposal(
    history: List[Dict[str, Any]],
    inbound_now: str,
    *,
    tz_name: Optional[str],
    now_utc: Optional[datetime] = None,
    professionals: Sequence[str] = (),
) -> Proposal:
    """O último horário posto em cima da mesa antes da mensagem atual: as opções da mensagem
    (ou mensagens seguidas) mais recente do agente que tenha horas, ou a hora que o próprio
    cliente disse, o que for mais recente. `history` em ordem cronológica."""
    now = now_utc or datetime.now(timezone.utc)
    today = mdg.local_today(tz_name, now)
    items = list(history or [])
    if items and _is_inbound(items[-1]) and _body(items[-1]).strip() == (inbound_now or "").strip():
        items = items[:-1]  # o histórico pode já trazer a mensagem atual
    # blocos de mensagens seguidas do mesmo lado, do mais recente para o mais antigo
    blocks: List[Tuple[bool, str]] = []
    for item in reversed(items):
        inbound = _is_inbound(item)
        if blocks and blocks[-1][0] == inbound:
            blocks[-1] = (inbound, _body(item) + "\n" + blocks[-1][1])
        else:
            blocks.append((inbound, _body(item)))
    all_texts = [text for _inbound, text in blocks]
    for index, (inbound, text) in enumerate(blocks):
        fallback_word = mdg.latest_day_word(all_texts[index + 1:])
        fallback_day = mdg.resolve_day_reference(fallback_word, today) if fallback_word else None
        if inbound:
            wanted = requested_slot.requested_time(text)
            if wanted is None:
                continue
            word = mdg.latest_day_word([text])
            day = (mdg.resolve_day_reference(word, today) if word else None) or fallback_day
            if day is None:
                continue
            start = datetime.combine(day, wanted, tzinfo=_tz(tz_name))
            if start <= now:
                continue
            option = ProposedOption(start=start, professional=_professional_in(text, professionals), text=text)
            return Proposal(options=[option], source="lead", text=text)
        options = [
            o
            for o in options_in_text(
                text, tz_name=tz_name, today=today, fallback_day=fallback_day, professionals=professionals
            )
            if o.start > now
        ]
        if options:
            return Proposal(options=options, source="agent", text=text)
    return Proposal()


def accepted_slot(
    inbound_now: str,
    proposal: Proposal,
    *,
    tz_name: Optional[str],
    now_utc: Optional[datetime] = None,
    professionals: Sequence[str] = (),
) -> AcceptedSlot:
    """Qual opção da última proposta o cliente aceitou com a mensagem atual.

    - `lead_stated`: a mensagem traz uma hora que não é nenhuma das opções — é um pedido novo,
      não uma aceitação (quem decide é o resto do fluxo, não esta leitura).
    - `matched_option`: a mensagem nomeia a hora, o dia ou o terapeuta de uma só opção.
    - `single_option`: a proposta só tinha uma opção ("Pode ser sim, marca aí!").
    - `ambiguous`: várias opções e a mensagem não escolhe nenhuma.
    - `none`: não havia horário proposto."""
    options = list(proposal.options)
    text = inbound_now or ""
    today = mdg.local_today(tz_name, now_utc)
    wanted = requested_slot.requested_time(text)
    word = mdg.latest_day_word([text])
    day = mdg.resolve_day_reference(word, today) if word else None
    named = _professional_in(text, professionals)

    narrowed = options
    if wanted is not None:
        narrowed = [o for o in narrowed if o.start.time() == wanted]
        if not narrowed:
            return AcceptedSlot(None, "lead_stated", options, proposal.text)
    if day is not None:
        narrowed = [o for o in narrowed if o.start.date() == day] or narrowed
    if named:
        narrowed = [o for o in narrowed if o.professional == named] or narrowed
    if not options:
        return AcceptedSlot(None, "none", options, proposal.text)
    if len(narrowed) == 1:
        source = "single_option" if len(options) == 1 else "matched_option"
        return AcceptedSlot(narrowed[0], source, options, proposal.text)
    return AcceptedSlot(None, "ambiguous", options, proposal.text)


def offered_durations(pricing_table: str) -> List[int]:
    """Durações (minutos) diferentes que aparecem na tabela de serviços ("60 min", "90 min")."""
    found = {int(m.group(1)) for m in requested_slot._DURATION_MIN_RE.finditer(pricing_table or "")}
    return sorted(d for d in found if 10 <= d <= 240)


def missing_duration(lead_texts: List[str], proposal_text: str, pricing_table: str) -> Optional[List[int]]:
    """Durações por onde o lead ainda tem de escolher — None quando a duração já se sabe: dita pelo
    lead, escrita na proposta que ele aceitou, ou a tabela só tem uma (ou nenhuma tabela).

    Em teste real o lead aceitou "11h na segunda" sem dizer serviço nem duração, e a IA inventou
    "Massagem Relaxante - 60 min" no recibo."""
    durations = offered_durations(pricing_table)
    if len(durations) <= 1:
        return None
    if requested_slot.requested_duration(list(lead_texts) + [proposal_text or ""]) is not None:
        return None
    return durations


def describe(option: ProposedOption) -> str:
    """"sexta-feira, 30/10, às 11h com a Val" — a forma como o facto é dito à Filha."""
    start = option.start
    hour = f"{start.hour}h" + (f"{start.minute:02d}" if start.minute else "")
    text = f"{mdg.WEEKDAY_NAMES_PT[start.weekday()]}, {start.strftime('%d/%m')}, às {hour}"
    return f"{text} com {option.professional}" if option.professional else text


def candidate_iso(option: ProposedOption) -> str:
    return option.start.strftime("%Y-%m-%dT%H:%M:%S")


def ask_which_text(options: List[ProposedOption]) -> str:
    return "Só para confirmar: prefere " + " ou ".join(describe(o) for o in options) + "?"


def durations_text(durations: List[int]) -> str:
    """[20, 60, 90] → "20, 60 ou 90 min"."""
    values = [str(d) for d in durations]
    joined = values[0] if len(values) == 1 else ", ".join(values[:-1]) + " ou " + values[-1]
    return f"{joined} min"


def ask_duration_text(option: ProposedOption, durations: List[int]) -> str:
    return (
        f"Para fechar a marcação de {describe(option)}: que serviço e que duração prefere "
        f"({durations_text(durations)})?"
    )


# Texto que anuncia a marcação como feita ("Experiência Agendada", "fica marcado", "reservada").
_BOOKED_TEXT_RE = re.compile(r"agendad|marcad[ao]|reservad|confirmad", re.IGNORECASE)


@dataclass
class ConfirmationCheck:
    candidate: Optional[str]
    message_text: str
    blocked: bool = False
    trace: Dict[str, Any] = field(default_factory=dict)


def _local(candidate: Optional[str], tz_name: Optional[str]) -> Optional[datetime]:
    if not candidate or not isinstance(candidate, str):
        return None
    raw = candidate.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    tz = _tz(tz_name)
    return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)


def _hour_like(original: str, new: time) -> str:
    if ":" in original:
        return f"{new.hour:02d}:{new.minute:02d}" if len(original.split(":")[0]) == 2 else f"{new.hour}:{new.minute:02d}"
    return f"{new.hour}h" + (f"{new.minute:02d}" if new.minute else "")


def _fix_hour(text: str, old: time, new: time) -> str:
    def swap(m: re.Match) -> str:
        hour, minute = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
        return _hour_like(m.group(0), new) if time(hour, minute) == old else m.group(0)

    return requested_slot._TIME_RE.sub(swap, text)


def reconcile_confirmation(
    candidate: Optional[str],
    message_text: str,
    accepted: AcceptedSlot,
    *,
    tz_name: Optional[str],
    now_utc: Optional[datetime] = None,
    professionals: Sequence[str] = (),
    missing_durations: Optional[List[int]] = None,
) -> ConfirmationCheck:
    """Confere o candidato da Filha, no turno da confirmação, com o horário aceite.

    - aceite único mas duração por saber (`missing_durations`, de missing_duration) → `blocked`:
      não se grava; se a Filha confirmou mesmo assim, o texto passa a ser a pergunta do serviço
      e da duração (se ela já perguntou, o texto dela fica);
    - aceite único e candidato diferente (ou em falta) → candidato passa a ser o aceite; dia,
      hora e terapeuta errados no texto são reescritos (o cliente lê o que fica gravado);
    - várias opções e candidato que não é nenhuma delas → `blocked`: não se grava e o texto passa
      a ser a pergunta "qual prefere?";
    - pedido novo do cliente, ou nenhuma proposta → sem alteração (decide o resto do fluxo)."""
    text = message_text or ""
    current = _local(candidate, tz_name)
    trace: Dict[str, Any] = {
        "accepted_source": accepted.source,
        "accepted": candidate_iso(accepted.option) if accepted.option else None,
        "options": [candidate_iso(o) for o in accepted.options],
        "candidate_from": candidate,
    }
    naive = current.replace(tzinfo=None) if current else None

    if accepted.option is not None and missing_durations:
        confirmed = naive is not None or bool(_BOOKED_TEXT_RE.search(text))
        new_text = ask_duration_text(accepted.option, missing_durations) if confirmed else text
        return ConfirmationCheck(
            None,
            new_text,
            blocked=True,
            trace={**trace, "action": "blocked_duration", "durations": missing_durations, "text_changed": new_text != text},
        )

    if accepted.option is not None:
        target = accepted.option.start.replace(tzinfo=None)
        if naive == target:
            return ConfirmationCheck(candidate, text, trace={**trace, "action": "ok"})
        new_text = text
        if naive is not None:
            today = mdg.local_today(tz_name, now_utc)
            if naive.date() != target.date():
                new_text = mdg._fix_text(new_text, naive.date(), target.date(), today)
            if naive.time() != target.time():
                new_text = _fix_hour(new_text, naive.time(), target.time())
        wanted = accepted.option.professional
        written = {p for p in professionals if p != "Profissional" and re.search(rf"\b{re.escape(p)}\b", new_text)}
        if wanted and len(written) == 1 and wanted not in written:
            new_text = re.sub(rf"\b{re.escape(written.pop())}\b", wanted, new_text)
        new_candidate = candidate_iso(accepted.option)
        return ConfirmationCheck(
            new_candidate,
            new_text,
            trace={
                **trace,
                "action": "filled" if naive is None else "corrected",
                "candidate_to": new_candidate,
                "text_changed": new_text != text,
            },
        )

    if accepted.source == "ambiguous":
        if naive is not None and any(o.start.replace(tzinfo=None) == naive for o in accepted.options):
            return ConfirmationCheck(candidate, text, trace={**trace, "action": "ok"})
        return ConfirmationCheck(None, ask_which_text(accepted.options), blocked=True, trace={**trace, "action": "blocked"})

    return ConfirmationCheck(candidate, text, trace={**trace, "action": "skip"})
