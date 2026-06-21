from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional
from zoneinfo import ZoneInfo

try:
    from dateparser.search import search_dates
except Exception:  # dependency opcional em ambientes sem acesso a pacote
    search_dates = None

from app.schemas.decision import DecisionOutput
from app.services import llm_service

MEETING_WINDOW_DAYS = 7  # janela p/ checar se O MESMO lead já tem reunião futura
CALENDAR_CONFLICT_WINDOW_DAYS = 30  # janela coberta por context["calendar_busy_slots"] (ver orchestrator.py)
MEETING_TYPES = {"meeting", "presentation"}
MEETING_STATUSES = {"pending", "scheduled"}

MEETING_CONFLICT_MESSAGE = (
    "Peço desculpa, esse horário acabou de ficar indisponível. "
    "Pode escolher outro horário, por favor?"
)


@dataclass(frozen=True)
class MeetingSignal:
    lead_id: Optional[int]
    user_id: Optional[int]
    job_id: Optional[int]
    agent_mode: Optional[str]
    meeting_scheduled: bool
    start_at: Optional[datetime]
    is_phase_entry: bool




def _normalize_agent_mode(raw_mode: Optional[str]) -> str:
    normalized = str(raw_mode or "").strip().lower().replace("_", "-")
    if normalized in {"consultivo", "agenda", "direto"}:
        return normalized
    if normalized == "closer":
        return "direto"
    if normalized in {"sdr-scheduler", "sdr"}:
        return "agenda"
    return "agenda"

def _safe_get(data: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def _extract_meeting_signal(context: Dict[str, Any], decision: DecisionOutput) -> MeetingSignal:
    lead = context.get("lead") or {}
    job = context.get("job") or {}
    payload = job.get("payload") or {}
    ai_profile = context.get("ai_profile") or {}
    metadata = context.get("metadata") or {}

    lead_id = _safe_get(lead, "id") or _safe_get(payload, "lead_id")
    user_id = _safe_get(lead, "user_id") or _safe_get(payload, "user_id")
    job_id = _safe_get(job, "id") or _safe_get(payload, "job_id")
    agent_mode = _normalize_agent_mode(ai_profile.get("agent_mode"))

    meeting_scheduled = False
    decision_trace = decision.decision_trace or {}
    if decision_trace.get("meeting_scheduled") is True:
        meeting_scheduled = True
    elif "meeting_scheduled" in (decision.reason or ""):
        meeting_scheduled = True
    is_phase_entry = bool(decision_trace.get("is_phase_entry", False))

    now_utc = _ensure_aware(datetime.now(timezone.utc), "UTC")
    tz_name = ai_profile.get("timezone")
    structured_signals = decision_trace.get("child_signals_structured") or {}
    candidate_str = structured_signals.get("meeting_datetime_candidate")
    start_at = parse_meeting_candidate(candidate_str, tz_name=tz_name, now_utc=now_utc)
    if start_at is not None:
        logging.getLogger(__name__).info(
            "event=meeting_datetime_source source=structured_candidate tz_used=%s",
            _resolve_timezone_name(tz_name),
        )
    else:
        if candidate_str:
            logging.getLogger(__name__).warning(
                "event=meeting_datetime_candidate_invalid reason=parse_or_past tz_used=%s",
                _resolve_timezone_name(tz_name),
            )
        logging.getLogger(__name__).info("event=meeting_datetime_source source=fallback_extract_start_at")
        start_at = extract_start_at(
            metadata,
            context.get("history") or [],
            tz_name=tz_name,
            now_utc=now_utc,
        )
    return MeetingSignal(
        lead_id=int(lead_id) if lead_id is not None else None,
        user_id=int(user_id) if user_id is not None else None,
        job_id=int(job_id) if job_id is not None else None,
        agent_mode=agent_mode,
        meeting_scheduled=meeting_scheduled,
        start_at=start_at,
        is_phase_entry=is_phase_entry,
    )


@dataclass(frozen=True)
class CancelRescheduleSignal:
    lead_id: Optional[int]
    user_id: Optional[int]
    job_id: Optional[int]
    cancel_requested: bool
    reschedule_requested: bool
    new_start_at: Optional[datetime]


def _extract_cancel_reschedule_signal(
    context: Dict[str, Any], decision: DecisionOutput
) -> CancelRescheduleSignal:
    """Lê os sinais de cancelamento/reagendamento produzidos por _decide_post_meeting_management.

    Paralelo a _extract_meeting_signal, mas para o caminho dedicado de gestão pós-confirmação
    (decision_trace.effective_route_to == "meeting_management") em vez da pipeline Mãe/Filha.
    """
    lead = context.get("lead") or {}
    job = context.get("job") or {}
    payload = job.get("payload") or {}
    ai_profile = context.get("ai_profile") or {}

    lead_id = _safe_get(lead, "id") or _safe_get(payload, "lead_id")
    user_id = _safe_get(lead, "user_id") or _safe_get(payload, "user_id")
    job_id = _safe_get(job, "id") or _safe_get(payload, "job_id")

    decision_trace = decision.decision_trace or {}
    structured_signals = decision_trace.get("child_signals_structured") or {}
    cancel_requested = bool(structured_signals.get("meeting_cancel_requested"))
    reschedule_requested = bool(structured_signals.get("meeting_reschedule_requested"))

    new_start_at: Optional[datetime] = None
    if reschedule_requested:
        now_utc = _ensure_aware(datetime.now(timezone.utc), "UTC")
        tz_name = ai_profile.get("timezone")
        candidate_str = structured_signals.get("meeting_datetime_candidate")
        new_start_at = parse_meeting_candidate(candidate_str, tz_name=tz_name, now_utc=now_utc)

    return CancelRescheduleSignal(
        lead_id=int(lead_id) if lead_id is not None else None,
        user_id=int(user_id) if user_id is not None else None,
        job_id=int(job_id) if job_id is not None else None,
        cancel_requested=cancel_requested,
        reschedule_requested=reschedule_requested,
        new_start_at=new_start_at,
    )


def _resolve_timezone(tz_name: Optional[str]) -> timezone | ZoneInfo:
    if not tz_name:
        return timezone.utc
    try:
        return ZoneInfo(str(tz_name))
    except Exception:
        return timezone.utc


def _resolve_timezone_name(tz_name: Optional[str]) -> str:
    resolved = _resolve_timezone(tz_name)
    if isinstance(resolved, ZoneInfo):
        return str(resolved)
    if tz_name:
        logging.getLogger(__name__).warning(
            "event=meeting_datetime_candidate_invalid reason=invalid_timezone tz_requested=%s tz_fallback=UTC",
            tz_name,
        )
    return "UTC"


def parse_meeting_candidate(
    candidate_str: Optional[str],
    *,
    tz_name: Optional[str],
    now_utc: datetime,
) -> Optional[datetime]:
    if not candidate_str:
        return None

    normalized = str(candidate_str).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_resolve_timezone(tz_name))

    parsed_utc = parsed.astimezone(timezone.utc)
    if parsed_utc <= _ensure_aware(now_utc, "UTC").astimezone(timezone.utc):
        return None
    return parsed_utc


def _has_explicit_time_hint(text: str) -> bool:
    lowered = (text or "").lower()
    if "às" in lowered:
        return True
    if ":" in lowered:
        return bool(re.search(r"\b\d{1,2}:\d{2}\b", lowered))
    return bool(re.search(r"\b\d{1,2}\s*h(?:\s*\d{2})?\b", lowered))


def _ensure_aware(dt: datetime, tz_name: Optional[str]) -> datetime:
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=_resolve_timezone(tz_name))


def parse_human_datetime(
    text: str,
    *,
    tz_name: str | None,
    now_utc: datetime,
) -> Optional[datetime]:
    if not text or not _has_explicit_time_hint(text):
        return None

    tz_obj = _resolve_timezone(tz_name)
    base_local = _ensure_aware(now_utc, "UTC").astimezone(tz_obj)
    if search_dates is not None:
        settings = {
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": base_local,
            "TIMEZONE": str(tz_obj),
            "RETURN_AS_TIMEZONE_AWARE": True,
            "DATE_ORDER": "DMY",
        }

        candidates = search_dates(text, languages=["pt"], settings=settings) or []
        for matched_text, parsed in candidates:
            if not _has_explicit_time_hint(matched_text):
                continue
            parsed_utc = _ensure_aware(parsed, tz_name).astimezone(timezone.utc)
            if parsed_utc <= now_utc.astimezone(timezone.utc):
                continue
            return parsed_utc

    fallback = _fallback_parse_human_datetime(text=text, tz_name=tz_name, now_utc=now_utc)
    if fallback:
        return fallback
    return None


def _extract_hour_minute(text: str) -> Optional[tuple[int, int]]:
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\b(\d{1,2})\s*h\s*(\d{2})?\b", text)
    if m:
        return int(m.group(1)), int(m.group(2) or 0)
    m = re.search(r"\bàs\s*(\d{1,2})\b", text)
    if m:
        return int(m.group(1)), 0
    return None


def _fallback_parse_human_datetime(text: str, *, tz_name: Optional[str], now_utc: datetime) -> Optional[datetime]:
    lowered = (text or "").lower()
    hm = _extract_hour_minute(lowered)
    if not hm:
        return None
    hour, minute = hm
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    tz_obj = _resolve_timezone(tz_name)
    base_local = _ensure_aware(now_utc, "UTC").astimezone(tz_obj)

    if "hoje" in lowered:
        local_dt = base_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if local_dt <= base_local:
            return None
        return local_dt.astimezone(timezone.utc)

    if "amanhã" in lowered or "amanha" in lowered:
        local_dt = (base_local + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        return local_dt.astimezone(timezone.utc)

    day_match = re.search(r"\bdia\s*(\d{1,2})/(\d{1,2})\b", lowered)
    if day_match:
        day = int(day_match.group(1))
        month = int(day_match.group(2))
        year = base_local.year
        try:
            local_dt = datetime(year, month, day, hour, minute, tzinfo=tz_obj)
        except ValueError:
            return None
        if local_dt <= base_local:
            try:
                local_dt = datetime(year + 1, month, day, hour, minute, tzinfo=tz_obj)
            except ValueError:
                return None
        return local_dt.astimezone(timezone.utc)

    week_days = {
        "segunda": 0,
        "terça": 1,
        "terca": 1,
        "quarta": 2,
        "quinta": 3,
        "sexta": 4,
        "sábado": 5,
        "sabado": 5,
        "domingo": 6,
    }
    for label, weekday in week_days.items():
        if label in lowered:
            delta = (weekday - base_local.weekday()) % 7
            if delta == 0:
                delta = 7
            target = (base_local + timedelta(days=delta)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
            return target.astimezone(timezone.utc)

    return None


def extract_start_at(
    metadata: Dict[str, Any],
    history: Iterable[Dict[str, Any]],
    *,
    tz_name: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> Optional[datetime]:
    now_utc = _ensure_aware(now_utc or datetime.now(timezone.utc), "UTC")
    text_candidates = [
        str(metadata.get("inbound_message_text") or ""),
    ]
    for item in history:
        text = item.get("body") or item.get("message") or item.get("text")
        if text:
            text_candidates.append(str(text))

    iso_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(:\d{2})?")
    for text in text_candidates:
        match = iso_pattern.search(text)
        if not match:
            continue
        candidate = f"{match.group(1)}T{match.group(2)}"
        try:
            parsed = datetime.fromisoformat(candidate)
            parsed_utc = _ensure_aware(parsed, tz_name).astimezone(timezone.utc)
            if parsed_utc > now_utc:
                return parsed_utc
        except ValueError:
            continue

    for text in text_candidates:
        parsed_human = parse_human_datetime(text, tz_name=tz_name, now_utc=now_utc)
        if parsed_human:
            return parsed_human
    return None


def has_future_meeting(appointments: Iterable[Dict[str, Any]], *, now: datetime, window_days: int) -> bool:
    now = _ensure_aware(now, "UTC").astimezone(timezone.utc)
    end = now + timedelta(days=window_days)
    for appointment in appointments:
        status = str(appointment.get("status") or "").lower()
        if status and status not in MEETING_STATUSES:
            continue
        appt_type = str(appointment.get("type") or "").lower()
        if appt_type and appt_type not in MEETING_TYPES:
            continue
        start_raw = appointment.get("start_at") or appointment.get("startAt") or appointment.get("startTime")
        if not start_raw:
            continue
        try:
            if isinstance(start_raw, datetime):
                start_at = start_raw
            else:
                candidate = str(start_raw).replace(" ", "T")
                start_at = datetime.fromisoformat(candidate)
            start_at = _ensure_aware(start_at, "UTC").astimezone(timezone.utc)
        except ValueError:
            continue
        if now <= start_at <= end:
            return True
    return False


def _has_conflict(
    busy_slots: Iterable[Dict[str, Any]],
    start_at: datetime,
    end_at: datetime,
    *,
    exclude_lead_id: Optional[int] = None,
) -> bool:
    """Verifica sobreposição entre [start_at, end_at) e os busy_slots do profissional."""
    start_at = _ensure_aware(start_at, "UTC").astimezone(timezone.utc)
    end_at = _ensure_aware(end_at, "UTC").astimezone(timezone.utc)
    for slot in busy_slots:
        if exclude_lead_id is not None and slot.get("lead_id") == exclude_lead_id:
            continue
        try:
            slot_start = datetime.fromisoformat(str(slot.get("start_at")))
            slot_end = datetime.fromisoformat(str(slot.get("end_at")))
        except (ValueError, TypeError):
            continue
        slot_start = _ensure_aware(slot_start, "UTC").astimezone(timezone.utc)
        slot_end = _ensure_aware(slot_end, "UTC").astimezone(timezone.utc)
        if slot_start < end_at and slot_end > start_at:
            return True
    return False


def _generate_conflict_message(
    ai_profile: Dict[str, Any],
    *,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """Tenta gerar a mensagem de conflito no tom do agente via LLM.

    Nunca propaga excepção — qualquer falha (sem API key, erro de rede, timeout,
    resposta vazia/inválida) devolve None, e o caller cai no fallback fixo.
    """
    tone_of_voice = str(ai_profile.get("tone_of_voice") or "profissional").strip()
    brand_name = str(ai_profile.get("brand_name") or "").strip()
    identity_mode = str(ai_profile.get("identity_mode") or "").strip()

    if identity_mode == "user_clone" and brand_name:
        persona_line = f"Fale na primeira pessoa, como se fosse {brand_name}."
    elif brand_name:
        persona_line = f"Fale na terceira pessoa, como assistente do/a {brand_name}."
    else:
        persona_line = "Fale na terceira pessoa, como assistente do negócio."

    prompt = (
        "Escreva uma única mensagem curta de WhatsApp em português, avisando o lead que "
        "o horário que ele acabou de confirmar ficou indisponível (outra pessoa ocupou o "
        "mesmo horário) e pedindo para ele escolher outro horário.\n"
        f"Tom de voz: {tone_of_voice}.\n"
        f"{persona_line}\n"
        "Regras: no máximo 2 frases curtas. Sem markdown. Peça desculpa de forma natural, "
        "sem som robótico. Termine convidando o lead a sugerir um novo horário.\n"
        "Responda apenas com o texto da mensagem, sem aspas, sem explicações."
    )

    try:
        generated = llm_service.generate_conflict_message(prompt)
    except Exception as exc:
        if logger:
            logger.warning(
                "event=conflict_message_generation_failed exc_type=%s exc=%s",
                type(exc).__name__, exc,
            )
        return None

    generated = (generated or "").strip()
    return generated or None


def handle_meeting_scheduled(
    context: Dict[str, Any],
    decision: DecisionOutput,
    *,
    logger: Optional[logging.Logger] = None,
    client: Any = None,
    now_utc: Optional[datetime] = None,
    is_playground: bool = False,
) -> Optional[str]:
    """Cria o appointment quando a IA confirma um horário.

    Retorna uma mensagem de correção (para o caller enviar ao lead) quando o
    horário colide com outro compromisso do profissional — nesse caso o
    appointment NÃO é criado e o bot não é desabilitado. Retorna None em
    qualquer outro caso (incluindo o caminho feliz de criação normal).
    """
    if client is None:
        from app.clients import crm_client

        client = crm_client
    now_utc = _ensure_aware(now_utc or datetime.now(timezone.utc), "UTC")
    signal = _extract_meeting_signal(context, decision)
    if signal.agent_mode != "agenda" or not signal.meeting_scheduled:
        return None
    if signal.lead_id is None:
        return None

    if signal.is_phase_entry:
        # M3: o lead está a tocar esta fase pela primeira vez nesta mensagem — a Mãe pode ter
        # interpretado um pedido/negociação inicial como confirmação. Não cria appointment nem
        # desativa o bot agora; a resposta natural da filha (proposta/negociação) segue ao lead
        # e a confirmação real só passa a poder criar o appointment num turno em que o lead já
        # estava antes nesta fase.
        if logger:
            logger.info(
                "event=meeting_scheduled_deferred_phase_entry lead_id=%s user_id=%s job_id=%s",
                signal.lead_id,
                signal.user_id,
                signal.job_id,
            )
        return None

    if not signal.start_at:
        client.log_meeting_scheduled(
            lead_id=signal.lead_id,
            user_id=signal.user_id,
            job_id=signal.job_id,
            reason="missing_start_at",
        )
        return None

    if logger:
        logger.info(
            "event=meeting_scheduled_ready lead_id=%s user_id=%s job_id=%s",
            signal.lead_id,
            signal.user_id,
            signal.job_id,
        )

    # calendar_busy_slots vem do ContextBundle (orchestrator.py::_load_calendar_busy_slots),
    # já escopado ao profissional (user_id) — substitui o antigo client.list_appointments(...)
    # (que exigia JWT de usuário e sempre falhava com 401 a partir daqui).
    busy_slots = context.get("calendar_busy_slots") or []

    same_lead_slots = [slot for slot in busy_slots if slot.get("lead_id") == signal.lead_id]
    if has_future_meeting(same_lead_slots, now=now_utc, window_days=MEETING_WINDOW_DAYS):
        client.set_lead_bot_disabled(signal.lead_id, True, reason="meeting_scheduled")
        return None

    end_dt = signal.start_at + timedelta(minutes=30)
    window_end = now_utc + timedelta(days=CALENDAR_CONFLICT_WINDOW_DAYS)
    if signal.start_at > window_end:
        if logger:
            logger.info(
                "event=meeting_conflict_check_skipped reason=outside_window lead_id=%s start_at=%s",
                signal.lead_id,
                signal.start_at.isoformat(),
            )
    elif _has_conflict(busy_slots, signal.start_at, end_dt, exclude_lead_id=signal.lead_id):
        if logger:
            logger.warning(
                "event=meeting_conflict_detected lead_id=%s user_id=%s job_id=%s start_at=%s",
                signal.lead_id,
                signal.user_id,
                signal.job_id,
                signal.start_at.isoformat(),
            )
        client.log_meeting_scheduled(
            lead_id=signal.lead_id,
            user_id=signal.user_id,
            job_id=signal.job_id,
            reason="conflict_detected",
        )
        ai_profile = context.get("ai_profile") or {}
        return _generate_conflict_message(ai_profile, logger=logger) or MEETING_CONFLICT_MESSAGE

    start_iso = signal.start_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_iso = end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    title = "[Playground] Reunião agendada" if is_playground else "Reunião agendada"
    description = (
        "Reunião simulada no Playground."
        if is_playground
        else "Reunião confirmada pelo SDR Scheduler."
    )
    client.create_lead_appointment(
        lead_id=signal.lead_id,
        title=title,
        description=description,
        appointment_type="meeting",
        start_at=start_iso,
        end_at=end_iso,
        source="playground" if is_playground else None,
    )
    client.set_lead_bot_disabled(signal.lead_id, True, reason="meeting_scheduled")
    return None


def handle_meeting_cancel_or_reschedule(
    context: Dict[str, Any],
    decision: DecisionOutput,
    *,
    logger: Optional[logging.Logger] = None,
    client: Any = None,
    now_utc: Optional[datetime] = None,
) -> Optional[str]:
    """Aplica de verdade o cancelamento/reagendamento detectado por _decide_post_meeting_management.

    Mesmo contrato de retorno de handle_meeting_scheduled: devolve uma mensagem de correção
    (para o caller enviar ao lead) quando o reagendamento colide com outro compromisso do
    profissional — nesse caso o appointment original NÃO é alterado. Retorna None em
    qualquer outro caso, incluindo o caminho feliz.
    """
    if client is None:
        from app.clients import crm_client

        client = crm_client
    signal = _extract_cancel_reschedule_signal(context, decision)
    if signal.lead_id is None:
        return None
    if not signal.cancel_requested and not signal.reschedule_requested:
        return None

    busy_slots = context.get("calendar_busy_slots") or []
    same_lead_slots = [
        slot
        for slot in busy_slots
        if slot.get("lead_id") == signal.lead_id and slot.get("id") is not None
    ]
    if not same_lead_slots:
        if logger:
            logger.info(
                "event=meeting_cancel_reschedule_appointment_not_found lead_id=%s",
                signal.lead_id,
            )
        return None

    same_lead_slots.sort(key=lambda slot: str(slot.get("start_at") or ""))
    appointment_id = same_lead_slots[0]["id"]

    if signal.cancel_requested:
        try:
            client.cancel_appointment(appointment_id)
        except Exception as exc:
            if logger:
                logger.warning(
                    "event=meeting_cancel_failed appointment_id=%s exc_type=%s exc=%s",
                    appointment_id,
                    type(exc).__name__,
                    exc,
                )
            return None
        client.set_lead_bot_disabled(signal.lead_id, False, reason="meeting_canceled")
        if logger:
            logger.info(
                "event=meeting_canceled appointment_id=%s lead_id=%s",
                appointment_id,
                signal.lead_id,
            )
        return None

    # signal.reschedule_requested == True a partir daqui
    if not signal.new_start_at:
        if logger:
            logger.info(
                "event=meeting_reschedule_missing_candidate lead_id=%s",
                signal.lead_id,
            )
        return None

    end_dt = signal.new_start_at + timedelta(minutes=30)
    start_iso = signal.new_start_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_iso = end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        client.reschedule_appointment(appointment_id, start_at=start_iso, end_at=end_iso)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 409:
            if logger:
                logger.warning(
                    "event=meeting_reschedule_conflict appointment_id=%s lead_id=%s start_at=%s",
                    appointment_id,
                    signal.lead_id,
                    signal.new_start_at.isoformat(),
                )
            ai_profile = context.get("ai_profile") or {}
            return _generate_conflict_message(ai_profile, logger=logger) or MEETING_CONFLICT_MESSAGE
        if logger:
            logger.warning(
                "event=meeting_reschedule_failed appointment_id=%s exc_type=%s exc=%s",
                appointment_id,
                type(exc).__name__,
                exc,
            )
        return None

    if logger:
        logger.info(
            "event=meeting_rescheduled appointment_id=%s lead_id=%s start_at=%s",
            appointment_id,
            signal.lead_id,
            signal.new_start_at.isoformat(),
        )
    return None
