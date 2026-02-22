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

MEETING_WINDOW_DAYS = 7
MEETING_TYPES = {"meeting", "presentation"}
MEETING_STATUSES = {"pending", "scheduled"}


@dataclass(frozen=True)
class MeetingSignal:
    lead_id: Optional[int]
    user_id: Optional[int]
    job_id: Optional[int]
    agent_mode: Optional[str]
    meeting_scheduled: bool
    start_at: Optional[datetime]




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

    start_at = extract_start_at(
        metadata,
        context.get("history") or [],
        tz_name=ai_profile.get("timezone"),
    )
    return MeetingSignal(
        lead_id=int(lead_id) if lead_id is not None else None,
        user_id=int(user_id) if user_id is not None else None,
        job_id=int(job_id) if job_id is not None else None,
        agent_mode=agent_mode,
        meeting_scheduled=meeting_scheduled,
        start_at=start_at,
    )


def _resolve_timezone(tz_name: Optional[str]) -> timezone | ZoneInfo:
    if not tz_name:
        return timezone.utc
    try:
        return ZoneInfo(str(tz_name))
    except Exception:
        return timezone.utc


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


def handle_meeting_scheduled(
    context: Dict[str, Any],
    decision: DecisionOutput,
    *,
    logger: Optional[logging.Logger] = None,
    client: Any = None,
    now_utc: Optional[datetime] = None,
) -> None:
    if client is None:
        from app.clients import crm_client

        client = crm_client
    now_utc = _ensure_aware(now_utc or datetime.now(timezone.utc), "UTC")
    signal = _extract_meeting_signal(context, decision)
    if signal.agent_mode != "agenda" or not signal.meeting_scheduled:
        return
    if signal.lead_id is None:
        return

    if not signal.start_at:
        client.log_meeting_scheduled(
            lead_id=signal.lead_id,
            user_id=signal.user_id,
            job_id=signal.job_id,
            reason="missing_start_at",
        )
        return

    if logger:
        logger.info(
            "event=meeting_scheduled_ready lead_id=%s user_id=%s job_id=%s",
            signal.lead_id,
            signal.user_id,
            signal.job_id,
        )

    start = now_utc.isoformat()
    end = (now_utc + timedelta(days=MEETING_WINDOW_DAYS)).isoformat()
    try:
        appointments = client.list_appointments(
            start=start,
            end=end,
            lead_id=signal.lead_id,
        )
    except Exception:
        appointments = []

    if has_future_meeting(appointments, now=now_utc, window_days=MEETING_WINDOW_DAYS):
        client.set_lead_bot_disabled(signal.lead_id, True, reason="meeting_scheduled")
        return

    start_iso = signal.start_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_dt = signal.start_at + timedelta(minutes=30)
    end_iso = end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    client.create_lead_appointment(
        lead_id=signal.lead_id,
        title="Reunião agendada",
        description="Reunião confirmada pelo SDR Scheduler.",
        appointment_type="meeting",
        start_at=start_iso,
        end_at=end_iso,
    )
    client.set_lead_bot_disabled(signal.lead_id, True, reason="meeting_scheduled")
