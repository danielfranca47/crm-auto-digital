import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from core_client import fetch_core_ai_profile_resolve
from database import get_connection
from models import AppointmentCreate, AppointmentOut, AppointmentUpdate, AppointmentStatus, AppointmentOutcomeUpdate
from security_core import CurrentUser, require_crm_access
from services.appointment_outcomes import apply_outcome
from services.briefing_service import schedule_briefing_job
from services.google_calendar_service import delete_event as gcal_delete, push_event as gcal_push, update_event as gcal_update
from services.jobs_service import TYPE_WHATSAPP_APPOINTMENT_REMINDER, create_job

logger = logging.getLogger(__name__)

_REMINDER_DEFAULTS_BY_TEMPLATE = {
    "hybrid_scheduler": [-1440, -120],  # Agent 3: -24h, -2h
}
_REMINDER_DEFAULTS_FALLBACK = [-1440, -60]  # Agent 1 default: -24h, -1h

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


def _serialize(row) -> AppointmentOut:
    data = {key: row[key] for key in row.keys()}
    return AppointmentOut(**data)


def _ensure_lead_exists(conn, lead_id: int) -> None:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM leads WHERE id = ?", (lead_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Lead não encontrado")


def _get_appointment(conn, appointment_id: int):
    cur = conn.cursor()
    cur.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    return row


def _validate_interval(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise HTTPException(
            status_code=400, detail="O horário de término deve ser maior que o horário de início."
        )


def _check_conflict(
    conn, lead_id: int, start_at: datetime, end_at: datetime, exclude_id: Optional[int] = None
) -> None:
    cur = conn.cursor()
    params = [lead_id, end_at.isoformat(), start_at.isoformat()]
    query = (
        "SELECT 1 FROM appointments "
        "WHERE lead_id = ? AND start_at < ? AND end_at > ?"
    )
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    cur.execute(query, params)
    if cur.fetchone():
        raise HTTPException(
            status_code=409,
            detail="Já existe um compromisso para este lead que conflita com o horário informado.",
        )


@router.get("", response_model=List[AppointmentOut])
def list_appointments(
    start: Optional[datetime] = Query(None, description="Início do intervalo"),
    end: Optional[datetime] = Query(None, description="Fim do intervalo"),
    lead_id: Optional[int] = Query(None, description="ID do lead"),
    status: Optional[AppointmentStatus] = Query(None, description="Status do compromisso"),
) -> List[AppointmentOut]:
    if start and end:
        _validate_interval(start, end)
    elif not start and not end and lead_id is None:
        raise HTTPException(status_code=400, detail="Informe ao menos start ou end para filtrar o intervalo.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        clauses = []
        params: List[object] = []
        if start:
            clauses.append("end_at >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("start_at <= ?")
            params.append(end.isoformat())
        if lead_id is not None:
            clauses.append("lead_id = ?")
            params.append(lead_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = " AND ".join(clauses)
        query = "SELECT * FROM appointments"
        if where:
            query += f" WHERE {where}"
        query += " ORDER BY start_at ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        return [_serialize(row) for row in rows]
    finally:
        conn.close()


@router.get("/lead/{lead_id}", response_model=List[AppointmentOut])
def list_by_lead(lead_id: int) -> List[AppointmentOut]:
    conn = get_connection()
    try:
        _ensure_lead_exists(conn, lead_id)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM appointments WHERE lead_id = ? ORDER BY start_at ASC",
            (lead_id,),
        )
        rows = cur.fetchall()
        return [_serialize(row) for row in rows]
    finally:
        conn.close()


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment(payload: AppointmentCreate) -> AppointmentOut:
    _validate_interval(payload.start_at, payload.end_at)

    conn = get_connection()
    try:
        _ensure_lead_exists(conn, payload.lead_id)
        _check_conflict(conn, payload.lead_id, payload.start_at, payload.end_at)

        cur = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()  # tz-aware
        cur.execute(
            """
            INSERT INTO appointments (
                lead_id, title, description, type, start_at, end_at, status, location, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.lead_id,
                payload.title,
                payload.description,
                payload.type,
                payload.start_at.isoformat(),
                payload.end_at.isoformat(),
                payload.status,
                payload.location,
                now_iso,
                now_iso,
            ),
        )
        conn.commit()
        appointment_id = cur.lastrowid
        cur.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
        row = cur.fetchone()
        result = _serialize(row)

        # Agendar jobs de lembrete + push Google Calendar
        lead_row = cur.execute(
            "SELECT user_id FROM leads WHERE id = ?", (payload.lead_id,)
        ).fetchone()
        if lead_row:
            user_id = lead_row["user_id"]
            _schedule_reminder_jobs(
                lead_id=payload.lead_id,
                user_id=user_id,
                appointment_id=appointment_id,
                appointment_title=payload.title,
                appointment_start_at=payload.start_at,
            )
            _schedule_briefing_job(
                lead_id=payload.lead_id,
                user_id=user_id,
                appointment_id=appointment_id,
                appointment_start_at=payload.start_at,
            )
            gcal_event_id = gcal_push(
                user_id=user_id,
                appointment={
                    "title": payload.title,
                    "description": payload.description,
                    "start_at": payload.start_at.isoformat(),
                    "end_at": payload.end_at.isoformat(),
                    "location": payload.location,
                },
            )
            if gcal_event_id:
                cur.execute(
                    "UPDATE appointments SET google_event_id = ? WHERE id = ?",
                    (gcal_event_id, appointment_id),
                )
                conn.commit()

        return result
    finally:
        conn.close()


def _schedule_reminder_jobs(
    *,
    lead_id: int,
    user_id: int,
    appointment_id: int,
    appointment_title: str,
    appointment_start_at: datetime,
) -> None:
    try:
        ai_profile = fetch_core_ai_profile_resolve(user_id)
    except Exception:
        ai_profile = None

    template_key = (ai_profile or {}).get("template_key") or ""
    offsets = None
    if ai_profile:
        offsets = ai_profile.get("appointment_reminder_offsets")
    if not offsets:
        offsets = _REMINDER_DEFAULTS_BY_TEMPLATE.get(template_key, _REMINDER_DEFAULTS_FALLBACK)

    now_utc = datetime.now(timezone.utc)
    for offset_minutes in offsets:
        send_at = appointment_start_at + timedelta(minutes=offset_minutes)
        # Garantir timezone-aware para comparação
        if send_at.tzinfo is None:
            send_at = send_at.replace(tzinfo=timezone.utc)
        if send_at <= now_utc:
            continue
        try:
            create_job(
                job_type=TYPE_WHATSAPP_APPOINTMENT_REMINDER,
                payload={
                    "lead_id": lead_id,
                    "user_id": user_id,
                    "appointment_id": appointment_id,
                    "appointment_title": appointment_title,
                    "appointment_start_at": appointment_start_at.isoformat(),
                    "message_text": "appointment_reminder_trigger",
                },
                scheduled_at=send_at,
                user_id=user_id,
            )
            logger.info(
                "reminder_job_scheduled lead_id=%s appointment_id=%s send_at=%s",
                lead_id,
                appointment_id,
                send_at.isoformat(),
            )
        except Exception as exc:
            logger.warning(
                "reminder_job_schedule_failed lead_id=%s appointment_id=%s error=%s",
                lead_id,
                appointment_id,
                exc,
            )


def _schedule_briefing_job(
    *,
    lead_id: int,
    user_id: int,
    appointment_id: int,
    appointment_start_at: datetime,
) -> None:
    try:
        ai_profile = fetch_core_ai_profile_resolve(user_id) or {}
    except Exception:
        ai_profile = {}

    briefing_enabled = ai_profile.get("briefing_enabled")
    if briefing_enabled is False:
        return

    lead_time = ai_profile.get("briefing_lead_time") or 120
    schedule_briefing_job(
        lead_id=lead_id,
        user_id=user_id,
        appointment_id=appointment_id,
        appointment_start_at=appointment_start_at,
        lead_time_minutes=int(lead_time),
    )


@router.put("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: int, payload: AppointmentUpdate) -> AppointmentOut:
    if payload.start_at and payload.end_at:
        _validate_interval(payload.start_at, payload.end_at)

    conn = get_connection()
    try:
        row = _get_appointment(conn, appointment_id)
        current = {key: row[key] for key in row.keys()}

        new_lead_id = payload.lead_id if payload.lead_id is not None else current["lead_id"]
        if payload.lead_id is not None:
            _ensure_lead_exists(conn, payload.lead_id)

        start_at = payload.start_at or datetime.fromisoformat(current["start_at"])
        end_at = payload.end_at or datetime.fromisoformat(current["end_at"])
        _validate_interval(start_at, end_at)

        if new_lead_id is None:
            new_lead_id = current["lead_id"]

        _check_conflict(conn, new_lead_id, start_at, end_at, exclude_id=appointment_id)

        fields = []
        values = []
        mapping = {
            "title": payload.title,
            "description": payload.description,
            "type": payload.type,
            "start_at": start_at.isoformat() if payload.start_at else None,
            "end_at": end_at.isoformat() if payload.end_at else None,
            "status": payload.status,
            "location": payload.location,
            "lead_id": payload.lead_id,
        }
        for column, value in mapping.items():
            if value is not None:
                fields.append(f"{column} = ?")
                values.append(value)

        if not fields:
            return _serialize(row)

        values.append(datetime.now(timezone.utc).isoformat())  # tz-aware
        fields.append("updated_at = ?")

        values.append(appointment_id)
        sql = f"UPDATE appointments SET {', '.join(fields)} WHERE id = ?"
        cur = conn.cursor()
        cur.execute(sql, values)
        conn.commit()
        cur.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
        updated = cur.fetchone()

        # Sync update to Google Calendar (fail-silent)
        google_event_id = current.get("google_event_id")
        if google_event_id:
            lead_row = cur.execute(
                "SELECT user_id FROM leads WHERE id = ?", (current["lead_id"],)
            ).fetchone()
            if lead_row and lead_row["user_id"]:
                updated_data = {key: updated[key] for key in updated.keys()}
                gcal_update(
                    user_id=lead_row["user_id"],
                    google_event_id=google_event_id,
                    appointment=updated_data,
                )

        return _serialize(updated)
    finally:
        conn.close()


@router.delete("/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: int) -> None:
    conn = get_connection()
    try:
        row = _get_appointment(conn, appointment_id)
        appointment = {key: row[key] for key in row.keys()}

        # Delete from Google Calendar before DB delete (fail-silent)
        google_event_id = appointment.get("google_event_id")
        if google_event_id:
            cur = conn.cursor()
            lead_row = cur.execute(
                "SELECT user_id FROM leads WHERE id = ?", (appointment["lead_id"],)
            ).fetchone()
            if lead_row and lead_row["user_id"]:
                gcal_delete(user_id=lead_row["user_id"], google_event_id=google_event_id)

        cur = conn.cursor()
        cur.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
        conn.commit()
    finally:
        conn.close()


def _update_status(appointment_id: int, status: AppointmentStatus) -> AppointmentOut:
    conn = get_connection()
    try:
        _get_appointment(conn, appointment_id)
        cur = conn.cursor()
        cur.execute(
            "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(), appointment_id),  # tz-aware
        )
        conn.commit()
        cur.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
        row = cur.fetchone()
        return _serialize(row)
    finally:
        conn.close()


@router.post("/{appointment_id}/complete", response_model=AppointmentOut)
def mark_completed(appointment_id: int) -> AppointmentOut:
    return _update_status(appointment_id, "completed")


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def mark_canceled(appointment_id: int) -> AppointmentOut:
    return _update_status(appointment_id, "canceled")


@router.post("/{appointment_id}/outcome", response_model=AppointmentOut)
def set_outcome(
    appointment_id: int,
    payload: AppointmentOutcomeUpdate,
    current_user: CurrentUser = Depends(require_crm_access),
) -> AppointmentOut:
    conn = get_connection()
    try:
        updated = apply_outcome(
            conn,
            appointment_id=appointment_id,
            user_id=current_user.id,
            payload=payload,
        )
        conn.commit()
        return _serialize(updated)
    except ValueError as exc:
        if str(exc) == "appointment_not_found":
            raise HTTPException(status_code=404, detail="Compromisso não encontrado")
        if str(exc) == "missing_reschedule_start":
            raise HTTPException(status_code=400, detail="reschedule_start_at é obrigatório para rescheduled")
        if str(exc) == "appointment_conflict":
            raise HTTPException(status_code=409, detail="Já existe um compromisso conflitante para este período.")
        raise HTTPException(status_code=400, detail="Erro ao registrar outcome")
    finally:
        conn.close()
