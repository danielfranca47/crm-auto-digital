from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import get_connection

logger = logging.getLogger(__name__)

TYPE_FOLLOWUP_TICK = "whatsapp.followup.tick"
_RECONCILE_GUARD_STATUS_ENQUEUED = "enqueued"


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _now_iso_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def reconcile_due_followups(*, limit: int = 100, dry_run: bool = False) -> Dict[str, Any]:
    """
    Detecta follow-ups vencidos elegíveis e enfileira jobs canônicos idempotentes.

    Elegibilidade atual:
      - followup_status = 'active'
      - next_followup_at <= now
      - bot_disabled = 0
      - category = 'follow-up'
    """

    scanned = 0
    eligible = 0
    enqueued = 0
    skipped_duplicate = 0
    skipped_dry_run = 0
    items: List[Dict[str, Any]] = []

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")

        rows = cur.execute(
            """
            SELECT id, user_id, category, followup_status, next_followup_at, followup_contract
              FROM leads
             WHERE followup_status = 'active'
               AND COALESCE(bot_disabled, 0) = 0
               AND category = 'follow-up'
               AND next_followup_at IS NOT NULL
               AND datetime(next_followup_at) <= CURRENT_TIMESTAMP
             ORDER BY datetime(next_followup_at) ASC, id ASC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()

        scanned = len(rows)
        for row in rows:
            lead_id = int(row["id"])
            user_id = row["user_id"]
            due_at = str(row["next_followup_at"])
            eligible += 1

            logger.info(
                "followup.reconcile_due_detected lead_id=%s user_id=%s due_at=%s",
                lead_id,
                user_id,
                due_at,
            )

            existing_guard = cur.execute(
                """
                SELECT g.id AS guard_id, g.job_id, j.status AS job_status
                  FROM followup_reconcile_guard g
             LEFT JOIN jobs j ON j.id = g.job_id
                 WHERE g.lead_id = ?
                   AND g.due_at = ?
                 LIMIT 1
                """,
                (lead_id, due_at),
            ).fetchone()

            # Se o job anterior deste vencimento falhou, liberamos nova tentativa.
            if existing_guard and str(existing_guard["job_status"] or "").lower() == "failed":
                cur.execute("DELETE FROM followup_reconcile_guard WHERE id = ?", (existing_guard["guard_id"],))
                logger.info(
                    "followup.reconcile_release_failed_guard lead_id=%s user_id=%s due_at=%s failed_job_id=%s",
                    lead_id,
                    user_id,
                    due_at,
                    existing_guard["job_id"],
                )

            guard_insert = cur.execute(
                """
                INSERT OR IGNORE INTO followup_reconcile_guard (
                    lead_id,
                    due_at,
                    status,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (lead_id, due_at, _RECONCILE_GUARD_STATUS_ENQUEUED),
            )
            if guard_insert.rowcount == 0:
                skipped_duplicate += 1
                logger.info(
                    "followup.reconcile_skip_duplicate lead_id=%s user_id=%s due_at=%s",
                    lead_id,
                    user_id,
                    due_at,
                )
                cur.execute(
                    """
                    INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
                    VALUES (?, NULL, NULL, 'followup_reconcile_skipped_duplicate', ?, ?)
                    """,
                    (
                        lead_id,
                        _json_dumps({"due_at": due_at, "reason": "guard_exists"}),
                        user_id,
                    ),
                )
                continue

            if dry_run:
                skipped_dry_run += 1
                cur.execute(
                    "DELETE FROM followup_reconcile_guard WHERE lead_id = ? AND due_at = ?",
                    (lead_id, due_at),
                )
                continue

            payload: Dict[str, Any] = {
                "lead_id": lead_id,
                "user_id": user_id,
                "due_at": due_at,
                "source": "followup_reconciler",
                "enqueued_at": _now_iso_utc(),
            }
            payload_txt = _json_dumps(payload)

            cur.execute(
                """
                INSERT INTO jobs (
                    user_id,
                    type,
                    payload,
                    status,
                    priority,
                    attempts,
                    assigned_agent_id,
                    created_at,
                    updated_at,
                    scheduled_at,
                    started_at,
                    completed_at,
                    result,
                    error
                ) VALUES (?, ?, ?, 'pending', 0, 0, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL, NULL, NULL)
                """,
                (user_id, TYPE_FOLLOWUP_TICK, payload_txt),
            )
            job_id = int(cur.lastrowid)
            enqueued += 1

            cur.execute(
                """
                UPDATE followup_reconcile_guard
                   SET job_id = ?,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE lead_id = ? AND due_at = ?
                """,
                (job_id, lead_id, due_at),
            )

            cur.execute(
                """
                INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
                VALUES (?, NULL, NULL, 'followup_job_enqueued', ?, ?)
                """,
                (
                    lead_id,
                    _json_dumps({"job_id": job_id, "job_type": TYPE_FOLLOWUP_TICK, "due_at": due_at}),
                    user_id,
                ),
            )

            logger.info(
                "followup.reconcile_job_enqueued lead_id=%s user_id=%s due_at=%s job_id=%s",
                lead_id,
                user_id,
                due_at,
                job_id,
            )
            items.append({"lead_id": lead_id, "job_id": job_id, "due_at": due_at})

        conn.commit()

    return {
        "scanned": scanned,
        "eligible": eligible,
        "enqueued": enqueued,
        "skipped_duplicate": skipped_duplicate,
        "skipped_dry_run": skipped_dry_run,
        "job_type": TYPE_FOLLOWUP_TICK,
        "items": items,
    }
