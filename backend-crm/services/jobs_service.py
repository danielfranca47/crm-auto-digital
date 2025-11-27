"""Serviços de fila de jobs e agentes locais."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException

from database import get_connection

logger = logging.getLogger(__name__)

JOB_STATUS_PENDING = "pending"
JOB_STATUS_IN_PROGRESS = "in_progress"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

AGENT_STATUS_ONLINE = "online"
AGENT_STATUS_OFFLINE = "offline"

_VALID_JOB_STATUSES = {
    JOB_STATUS_PENDING,
    JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _json_loads(data: Optional[str]) -> Any:
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


def _capabilities_to_text(capabilities: Optional[Sequence[str]]) -> Optional[str]:
    if not capabilities:
        return None
    return _json_dumps(list(capabilities))


def _update_agent_touch(agent_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE agents
               SET last_seen=CURRENT_TIMESTAMP,
                   status=?,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=?
            """,
            (AGENT_STATUS_ONLINE, agent_id),
        )
        conn.commit()


def _ensure_agent(agent_id: str, token: str) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Agent not registered")
        if row["token"] and row["token"] != token:
            raise HTTPException(status_code=401, detail="Invalid agent token")
        cur.execute(
            """
            UPDATE agents
               SET last_seen=CURRENT_TIMESTAMP,
                   status=?,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=?
            """,
            (AGENT_STATUS_ONLINE, agent_id),
        )
        conn.commit()
        return dict(row)


# ---------------------------------------------------------------------------
# Agent management
# ---------------------------------------------------------------------------

def register_agent(
    *,
    agent_id: str,
    name: Optional[str],
    token: str,
    capabilities: Optional[Sequence[str]] = None,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    if not agent_id or not token:
        raise HTTPException(status_code=400, detail="agent_id e token são obrigatórios")

    caps_txt = _capabilities_to_text(capabilities)

    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT token FROM agents WHERE id=?", (agent_id,)).fetchone()
        if row:
            existing_token = row["token"]
            if existing_token and existing_token != token:
                raise HTTPException(status_code=401, detail="Token inválido para o agente")
            cur.execute(
                """
                UPDATE agents
                   SET name=?,
                       token=?,
                       capabilities=?,
                       version=?,
                       status=?,
                       last_seen=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE id=?
                """,
                (name, token, caps_txt, version, AGENT_STATUS_ONLINE, agent_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO agents (id, name, token, capabilities, version, status, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (agent_id, name, token, caps_txt, version, AGENT_STATUS_ONLINE),
            )
        conn.commit()
        row = cur.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()

    data = dict(row)
    data["capabilities"] = _json_loads(data.get("capabilities"))
    data["last_seen"] = (
        str(data.get("last_seen")).replace(" ", "T") if data.get("last_seen") else None
    )
    return data


def list_agents(max_age_seconds: int = 120) -> List[Dict[str, Any]]:
    threshold_dt = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    agents: List[Dict[str, Any]] = []
    with get_connection() as conn:
        cur = conn.cursor()
        for row in cur.execute("SELECT * FROM agents ORDER BY name ASC, id ASC"):
            data = dict(row)
            data["capabilities"] = _json_loads(data.get("capabilities"))
            last_seen = data.get("last_seen")
            if last_seen:
                last_seen_iso = str(last_seen).replace(" ", "T")
                data["last_seen"] = last_seen_iso
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen_iso)
                except ValueError:
                    last_seen_dt = None
                data["online"] = last_seen_dt is not None and last_seen_dt >= threshold_dt
            else:
                data["online"] = False
            agents.append(data)
    return agents


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def _insert_job(
    cur,
    *,
    job_type: str,
    payload: Dict[str, Any],
    priority: int = 0,
    scheduled_at: Optional[datetime] = None,
):
    scheduled_value = scheduled_at.isoformat() if scheduled_at else None
    payload_txt = _json_dumps(payload)

    cur.execute(
        """
        INSERT INTO jobs (type, payload, priority, scheduled_at, status, result, error, assigned_agent_id, attempts, created_at, updated_at)
        VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), 'pending', NULL, NULL, NULL, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (job_type, payload_txt, priority, scheduled_value),
    )
    job_id = cur.lastrowid
    row = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    job = dict(row)
    job["payload"] = payload
    job["result"] = _json_loads(job.get("result"))
    logger.info(
        "create_job id=%s type=%s lead_id=%s message_id=%s",
        job_id,
        job_type,
        payload.get("lead_id"),
        payload.get("message_id"),
    )
    return job


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None

    job = dict(row)
    job["payload"] = _json_loads(job.get("payload"))
    job["result"] = _json_loads(job.get("result"))
    return job


def create_job(
    *,
    job_type: str,
    payload: Dict[str, Any],
    priority: int = 0,
    scheduled_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        job = _insert_job(
            cur,
            job_type=job_type,
            payload=payload,
            priority=priority,
            scheduled_at=scheduled_at,
        )
        conn.commit()
    return job


def fetch_next_job(
    *,
    agent_id: str,
    token: str,
    accepted_types: Optional[Sequence[str]] = None,
) -> Optional[Dict[str, Any]]:
    _ensure_agent(agent_id, token)
    params: List[Any] = [JOB_STATUS_PENDING]
    type_filter = ""
    if accepted_types:
        placeholders = ",".join(["?"] * len(accepted_types))
        type_filter = f"AND type IN ({placeholders})"
        params.extend(accepted_types)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute(
            f"""
            SELECT * FROM jobs
             WHERE status=?
               {type_filter}
             ORDER BY priority DESC, scheduled_at ASC, created_at ASC, id ASC
             LIMIT 1
            """,
            params,
        ).fetchone()
        if not row:
            conn.commit()
            return None

        job_id = row["id"]
        updated = cur.execute(
            """
            UPDATE jobs
               SET status=?,
                   assigned_agent_id=?,
                   attempts = attempts + 1,
                   started_at=CURRENT_TIMESTAMP,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=? AND status=?
            """,
            (JOB_STATUS_IN_PROGRESS, agent_id, job_id, JOB_STATUS_PENDING),
        )
        if updated.rowcount == 0:
            conn.rollback()
            return None
        conn.commit()

    _update_agent_touch(agent_id)

    job = dict(row)
    job["payload"] = _json_loads(job.get("payload"))
    job["result"] = _json_loads(job.get("result"))
    return job


def report_job(
    *,
    agent_id: str,
    token: str,
    job_id: int,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    if status not in _VALID_JOB_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")

    _ensure_agent(agent_id, token)

    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job não encontrado")
        if row["assigned_agent_id"] and row["assigned_agent_id"] != agent_id:
            raise HTTPException(status_code=403, detail="Job atribuído a outro agente")

        result_txt = _json_dumps(result) if result is not None else None
        error_txt = str(error) if error else None
        completed_at_expr = "CURRENT_TIMESTAMP" if status in {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED} else "completed_at"

        cur.execute(
            f"""
            UPDATE jobs
               SET status=?,
                   result=?,
                   error=?,
                   updated_at=CURRENT_TIMESTAMP,
                   completed_at={completed_at_expr}
             WHERE id=?
            """,
            (status, result_txt, error_txt, job_id),
        )

        job_type = row["type"]
        payload = _json_loads(row["payload"])
        if job_type == "whatsapp_send":
            _handle_whatsapp_report(conn, payload, status, result, error_txt)

        conn.commit()

    _update_agent_touch(agent_id)
    return {"ok": True, "status": status}


# ---------------------------------------------------------------------------
# WhatsApp helpers
# ---------------------------------------------------------------------------

def _sanitize_phone(phone: Optional[str]) -> str:
    return re.sub(r"\D+", "", phone or "")


def _log_prospection(
    conn,
    *,
    lead_id: int,
    action: str,
    channel: str = "whatsapp",
    message_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (lead_id, channel, message_id, action, notes),
    )


def _handle_whatsapp_report(conn, payload, status, result, error_txt):
    lead_id = (payload or {}).get("lead_id")
    message_id = (payload or {}).get("message_id")
    if not lead_id:
        return

    notes = None
    if isinstance(result, dict):
        notes = result.get("notes") or result.get("detail")
    if not notes and error_txt:
        notes = error_txt

    if status == JOB_STATUS_COMPLETED:
        conn.execute(
            "UPDATE leads SET category='qualification', lastMovement=CURRENT_TIMESTAMP WHERE id=?",
            (lead_id,),
        )
        conn.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
            VALUES (?, 'whatsapp', ?, 'sent', ?)
            """,
            (lead_id, message_id, notes),
        )
        conn.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
            VALUES (?, 'whatsapp', NULL, 'moved_stage', 'auto:qualification')
            """,
            (lead_id,),
        )
    elif status == JOB_STATUS_FAILED:
        conn.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
            VALUES (?, 'whatsapp', ?, 'failed', ?)
            """,
            (lead_id, message_id, notes or "erro"),
        )


def _persist_whatsapp_message(cur, lead_id: int, body: str) -> Dict[str, Any]:
    body_txt = (body or "").strip()
    if not body_txt:
        raise ValueError("mensagem vazia")

    cur.execute(
        """
        INSERT INTO messages (lead_id, channel, subject, body, model)
        VALUES (?, 'whatsapp', NULL, ?, 'manual')
        """,
        (lead_id, body_txt),
    )
    message_id = int(cur.lastrowid)
    cur.execute(
        """
        INSERT INTO message_selections (lead_id, channel, message_id)
        VALUES (?, 'whatsapp', ?)
        ON CONFLICT(lead_id, channel)
        DO UPDATE SET message_id=excluded.message_id, selectedAt=CURRENT_TIMESTAMP
        """,
        (lead_id, message_id),
    )
    return {"id": message_id, "body": body_txt}


def enqueue_whatsapp_jobs(
    lead_ids: Sequence[int], *, message: Optional[str] = None, lead_messages: Optional[Dict[int, str]] = None
) -> Dict[str, Any]:
    if not lead_ids:
        return {"queued": [], "skipped": []}

    queued: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    logger.info(
        "enqueue_whatsapp_jobs lead_ids=%s message_present=%s overrides=%s",
        list(lead_ids),
        bool((message or "").strip()),
        list((lead_messages or {}).keys()),
    )

    with get_connection() as conn:
        cur = conn.cursor()
        pending_rows = cur.execute(
            """
            SELECT id, payload
              FROM jobs
             WHERE type='whatsapp_send'
               AND status IN (?, ?)
            """,
            (JOB_STATUS_PENDING, JOB_STATUS_IN_PROGRESS),
        ).fetchall()
        existing = []
        for row in pending_rows:
            payload = _json_loads(row["payload"])
            if isinstance(payload, dict):
                existing.append((row["id"], payload.get("lead_id"), payload.get("message_id")))

        for lead_id in lead_ids:
            try:
                lead = cur.execute(
                    "SELECT id, phone, customMessage FROM leads WHERE id=?",
                    (lead_id,),
                ).fetchone()
                if not lead:
                    reason = "lead_nao_encontrado"
                    skipped.append({"lead_id": lead_id, "reason": reason})
                    logger.info("enqueue_whatsapp_jobs skip lead_id=%s reason=%s", lead_id, reason)
                    continue

                phone = _sanitize_phone(lead["phone"])
                if not phone:
                    reason = "telefone_invalido"
                    skipped.append({"lead_id": lead_id, "reason": reason})
                    logger.info("enqueue_whatsapp_jobs skip lead_id=%s reason=%s", lead_id, reason)
                    continue

                override_msg = None
                if lead_messages and lead_id in lead_messages:
                    override_msg = (lead_messages[lead_id] or "").strip() or None
                if not override_msg and message:
                    override_msg = message

                msg_row = None
                if override_msg:
                    msg_row = _persist_whatsapp_message(cur, lead_id, override_msg)
                    logger.info(
                        "enqueue_whatsapp_jobs persisted override message lead_id=%s message_id=%s",
                        lead_id,
                        msg_row["id"],
                    )
                else:
                    msg_row = cur.execute(
                        """
                        SELECT m.id, m.body
                          FROM message_selections s
                          JOIN messages m ON m.id = s.message_id
                         WHERE s.lead_id=? AND s.channel='whatsapp'
                         ORDER BY s.selectedAt DESC
                         LIMIT 1
                        """,
                        (lead_id,),
                    ).fetchone()
                    if not msg_row:
                        msg_row = cur.execute(
                            """
                            SELECT id, body
                              FROM messages
                             WHERE lead_id=? AND channel='whatsapp'
                             ORDER BY createdAt DESC
                             LIMIT 1
                            """,
                            (lead_id,),
                        ).fetchone()
                    if not msg_row:
                        custom_msg = (lead["customMessage"] or "").strip()
                        if custom_msg:
                            msg_row = _persist_whatsapp_message(cur, lead_id, custom_msg)
                            logger.info(
                                "enqueue_whatsapp_jobs created message from customMessage lead_id=%s message_id=%s",
                                lead_id,
                                msg_row["id"],
                            )
                        else:
                            reason = "sem_mensagem"
                            skipped.append({"lead_id": lead_id, "reason": reason})
                            logger.info("enqueue_whatsapp_jobs skip lead_id=%s reason=%s", lead_id, reason)
                            continue

                message_id = int(msg_row["id"])
                body = msg_row["body"]

                already = next(
                    (row_id for row_id, lid, mid in existing if lid == lead_id and mid == message_id), None
                )
                if already:
                    reason = "ja_pendente"
                    skipped.append({"lead_id": lead_id, "reason": reason, "job_id": already})
                    logger.info(
                        "enqueue_whatsapp_jobs skip lead_id=%s reason=%s job_id=%s",
                        lead_id,
                        reason,
                        already,
                    )
                    continue

                job = _insert_job(
                    cur,
                    job_type="whatsapp_send",
                    payload={
                        "lead_id": lead_id,
                        "message_id": message_id,
                        "phone": phone,
                        "body": body,
                    },
                )

                _log_prospection(
                    conn,
                    lead_id=lead_id,
                    channel="whatsapp",
                    message_id=message_id,
                    action="queued",
                    notes=f"phone={phone}",
                )

                queued.append({"lead_id": lead_id, "message_id": message_id, "job_id": job["id"]})
                logger.info(
                    "enqueue_whatsapp_jobs queued lead_id=%s message_id=%s job_id=%s",
                    lead_id,
                    message_id,
                    job["id"],
                )
            except Exception:
                logger.exception("enqueue_whatsapp_jobs unexpected error lead_id=%s", lead_id)
                skipped.append({"lead_id": lead_id, "reason": "erro_interno"})
                continue

        conn.commit()

    return {"queued": queued, "skipped": skipped}


def get_whatsapp_queue(limit: int = 5) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, payload, created_at, scheduled_at
              FROM jobs
             WHERE type='whatsapp_send' AND status=?
             ORDER BY scheduled_at ASC, created_at ASC, id ASC
             LIMIT ?
            """,
            (JOB_STATUS_PENDING, limit),
        ).fetchall()
    queue: List[Dict[str, Any]] = []
    for row in rows:
        payload = _json_loads(row["payload"])
        queue.append(
            {
                "id": row["id"],
                "payload": payload,
                "lead_id": (payload or {}).get("lead_id"),
                "message_id": (payload or {}).get("message_id"),
                "created_at": str(row["created_at"]).replace(" ", "T") if row["created_at"] else None,
                "scheduled_at": str(row["scheduled_at"]).replace(" ", "T") if row["scheduled_at"] else None,
            }
        )
    return queue


def get_whatsapp_recent(seconds: int = 300) -> List[Dict[str, Any]]:
    seconds = max(30, min(int(seconds), 3600))
    with get_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, payload, status, result, error, completed_at
              FROM jobs
             WHERE type='whatsapp_send'
               AND status IN (?, ?)
               AND completed_at IS NOT NULL
               AND completed_at >= datetime('now', ?)
             ORDER BY completed_at DESC
             LIMIT 200
            """,
            (JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, f"-{seconds} seconds"),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        payload = _json_loads(row["payload"])
        result = _json_loads(row["result"])
        items.append(
            {
                "id": row["id"],
                "lead_id": (payload or {}).get("lead_id"),
                "message_id": (payload or {}).get("message_id"),
                "status": row["status"],
                "notes": (result or {}).get("notes") if isinstance(result, dict) else None,
                "error": row["error"],
                "completed_at": str(row["completed_at"]).replace(" ", "T") if row["completed_at"] else None,
            }
        )
    return items


def get_whatsapp_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        pending = cur.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE type='whatsapp_send' AND status=?",
            (JOB_STATUS_PENDING,),
        ).fetchone()["c"]
        sent_today = cur.execute(
            """
            SELECT COUNT(*) AS c
              FROM jobs
             WHERE type='whatsapp_send'
               AND status=?
               AND date(completed_at) = date('now')
            """,
            (JOB_STATUS_COMPLETED,),
        ).fetchone()["c"]
        failed_today = cur.execute(
            """
            SELECT COUNT(*) AS c
              FROM jobs
             WHERE type='whatsapp_send'
               AND status=?
               AND date(completed_at) = date('now')
            """,
            (JOB_STATUS_FAILED,),
        ).fetchone()["c"]
    return {
        "pending": int(pending or 0),
        "sent_today": int(sent_today or 0),
        "failed_today": int(failed_today or 0),
    }


def get_jobs_overview(seconds: int = 120) -> Dict[str, Any]:
    return {
        "agents": list_agents(max_age_seconds=seconds),
        "summary": get_whatsapp_summary(),
    }


__all__ = [
    "register_agent",
    "fetch_next_job",
    "report_job",
    "get_job",
    "create_job",
    "enqueue_whatsapp_jobs",
    "get_whatsapp_queue",
    "get_whatsapp_recent",
    "get_whatsapp_summary",
    "get_jobs_overview",
    "list_agents",
]
