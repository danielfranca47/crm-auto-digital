from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import sqlite3


def _check_conflict(
    conn: sqlite3.Connection,
    lead_id: int,
    start_at: datetime,
    end_at: datetime,
    *,
    exclude_id: Optional[int] = None,
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
        raise ValueError("appointment_conflict")


def apply_outcome(
    conn: sqlite3.Connection,
    *,
    appointment_id: int,
    user_id: int,
    payload: Any,
) -> Dict[str, Any]:
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT a.*, l.user_id
          FROM appointments a
          JOIN leads l ON l.id = a.lead_id
         WHERE a.id = ? AND l.user_id = ?
        """,
        (appointment_id, user_id),
    ).fetchone()
    if not row:
        raise ValueError("appointment_not_found")

    lead_id = row["lead_id"]
    outcome = payload.outcome
    if outcome == "rescheduled" and not payload.reschedule_start_at:
        raise ValueError("missing_reschedule_start")

    status = "completed" if outcome in {"completed", "no_show"} else "pending"
    start_at = row["start_at"]
    end_at = row["end_at"]
    if outcome == "rescheduled":
        new_start = payload.reschedule_start_at
        new_end = payload.reschedule_end_at or payload.reschedule_start_at
        _check_conflict(conn, lead_id, new_start, new_end, exclude_id=appointment_id)
        start_at = new_start.isoformat()
        end_at = new_end.isoformat()

    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        UPDATE appointments
           SET outcome = ?,
               outcome_note = ?,
               outcome_at = ?,
               status = ?,
               start_at = ?,
               end_at = ?,
               updated_at = ?
         WHERE id = ?
        """,
        (
            outcome,
            payload.note,
            now_iso,
            status,
            start_at,
            end_at,
            now_iso,
            appointment_id,
        ),
    )

    if payload.reactivate_bot:
        cur.execute(
            """
            UPDATE leads
               SET bot_disabled = 0,
                   bot_disabled_reason = NULL,
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (lead_id,),
        )
        notes = {"disabled": False, "reason": "post_meeting_outcome"}
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'bot_disabled_changed', ?, ?)
            """,
            (lead_id, json.dumps(notes, ensure_ascii=False), user_id),
        )

    if payload.move_lead_to:
        cur.execute(
            """
            UPDATE leads
               SET category = ?,
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (payload.move_lead_to, lead_id),
        )
        notes = f"manual_post_meeting:{outcome}|{payload.move_lead_to}"
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'moved_stage', ?, ?)
            """,
            (lead_id, notes, user_id),
        )

    outcome_notes = {
        "appointment_id": appointment_id,
        "outcome": outcome,
        "note": payload.note,
    }
    cur.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'appointment_outcome', ?, ?)
        """,
        (lead_id, json.dumps(outcome_notes, ensure_ascii=False), user_id),
    )
    return dict(cur.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone())
