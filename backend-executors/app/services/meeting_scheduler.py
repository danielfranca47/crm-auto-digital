from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

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
    agent_mode = ai_profile.get("agent_mode")

    meeting_scheduled = False
    decision_trace = decision.decision_trace or {}
    if decision_trace.get("meeting_scheduled") is True:
        meeting_scheduled = True
    elif "meeting_scheduled" in (decision.reason or ""):
        meeting_scheduled = True

    start_at = extract_start_at(metadata, context.get("history") or [])
    return MeetingSignal(
        lead_id=int(lead_id) if lead_id is not None else None,
        user_id=int(user_id) if user_id is not None else None,
        job_id=int(job_id) if job_id is not None else None,
        agent_mode=agent_mode,
        meeting_scheduled=meeting_scheduled,
        start_at=start_at,
    )


def extract_start_at(metadata: Dict[str, Any], history: Iterable[Dict[str, Any]]) -> Optional[datetime]:
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
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def has_future_meeting(appointments: Iterable[Dict[str, Any]], *, now: datetime, window_days: int) -> bool:
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
) -> None:
    if client is None:
        from app.clients import crm_client

        client = crm_client
    signal = _extract_meeting_signal(context, decision)
    if signal.agent_mode != "sdr_scheduler" or not signal.meeting_scheduled:
        return
    if signal.lead_id is None:
        return

    if logger:
        logger.info(
            "event=meeting_scheduled_disable_bot lead_id=%s user_id=%s job_id=%s",
            signal.lead_id,
            signal.user_id,
            signal.job_id,
        )

    client.set_lead_bot_disabled(signal.lead_id, True, reason="meeting_scheduled")

    if not signal.start_at:
        client.log_meeting_scheduled(
            lead_id=signal.lead_id,
            user_id=signal.user_id,
            job_id=signal.job_id,
            reason="missing_start_at",
        )
        return

    now = datetime.utcnow()
    start = now.isoformat()
    end = (now + timedelta(days=MEETING_WINDOW_DAYS)).isoformat()
    try:
        appointments = client.list_appointments(
            start=start,
            end=end,
            lead_id=signal.lead_id,
        )
    except Exception:
        appointments = []

    if has_future_meeting(appointments, now=now, window_days=MEETING_WINDOW_DAYS):
        return

    client.create_lead_appointment(
        lead_id=signal.lead_id,
        title="Reunião agendada",
        description="Reunião confirmada pelo SDR Scheduler.",
        appointment_type="meeting",
        start_at=signal.start_at.isoformat(),
    )
