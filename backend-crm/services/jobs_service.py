"""Serviços de fila de jobs e agentes locais."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


def _sanitize_agent(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
    data = dict(row)
    data.pop("token", None)
    data["capabilities"] = _json_loads(data.get("capabilities"))

    for key in ("last_seen", "last_seen_at", "revoked_at", "created_at", "updated_at"):
        if data.get(key):
            data[key] = str(data[key]).replace(" ", "T")

    data["revoked"] = data.get("revoked_at") is not None
    return data


def _get_agent_by_credentials(agent_id: str, token: str) -> Tuple[Dict[str, Any], sqlite3.Connection]:
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail="Agent not registered")
    if not row["token"] or row["token"] != token:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid agent token")
    if row["revoked_at"] or row["status"] == "disabled":
        conn.close()
        raise HTTPException(status_code=403, detail="Agent revoked")
    data = dict(row)
    if data.get("user_id") is None:
        conn.close()
        raise HTTPException(status_code=403, detail="Agent has no owner assigned")
    return data, conn


def _update_agent_touch(agent_id: str, *, user_id: Optional[int] = None) -> None:
    with get_connection() as conn:
        params: List[Any] = [AGENT_STATUS_ONLINE, agent_id]
        where_clause = "WHERE id=?"
        if user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(user_id)

        conn.execute(
            f"""
            UPDATE agents
               SET last_seen=CURRENT_TIMESTAMP,
                   last_seen_at=CURRENT_TIMESTAMP,
                   status=?,
                   updated_at=CURRENT_TIMESTAMP
             {where_clause}
            """,
            params,
        )
        conn.commit()


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

    _, conn = _get_agent_by_credentials(agent_id, token)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE agents
               SET name=COALESCE(?, name),
                   capabilities=?,
                   version=?,
                   status=?,
                   last_seen=CURRENT_TIMESTAMP,
                   last_seen_at=CURRENT_TIMESTAMP,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=? AND token=?
            """,
            (name, caps_txt, version, AGENT_STATUS_ONLINE, agent_id, token),
        )
        conn.commit()
        row = cur.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    finally:
        conn.close()

    return _sanitize_agent(row)


def provision_agent(*, user_id: int, name: Optional[str] = None) -> Dict[str, Any]:
    import secrets
    from uuid import uuid4

    agent_id = uuid4().hex
    agent_token = secrets.token_urlsafe(32)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agents (id, user_id, name, token, capabilities, version, status, last_seen, last_seen_at, revoked_at)
            VALUES (?, ?, ?, ?, NULL, NULL, ?, NULL, NULL, NULL)
            """,
            (agent_id, user_id, name, agent_token, AGENT_STATUS_OFFLINE),
        )
        conn.commit()

    return {
        "agent_id": agent_id,
        "agent_token": agent_token,
        "name": name,
        "user_id": user_id,
        "status": AGENT_STATUS_OFFLINE,
    }


def list_agents(max_age_seconds: int = 120, *, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    threshold_dt = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    agents: List[Dict[str, Any]] = []
    with get_connection() as conn:
        cur = conn.cursor()
        params: List[Any] = []
        where_clause = ""
        if user_id is not None:
            where_clause = "WHERE user_id = ?"
            params.append(user_id)
        for row in cur.execute(
            f"SELECT * FROM agents {where_clause} ORDER BY name ASC, id ASC",
            params,
        ):
            data = _sanitize_agent(row)
            last_seen = data.get("last_seen_at") or data.get("last_seen")
            if last_seen:
                try:
                    last_seen_dt = datetime.fromisoformat(str(last_seen))
                except ValueError:
                    last_seen_dt = None
                data["online"] = last_seen_dt is not None and last_seen_dt >= threshold_dt
            else:
                data["online"] = False
            if data.get("revoked_at"):
                data["status"] = "disabled"
            agents.append(data)
    return agents


def revoke_agent(*, agent_id: str, user_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT * FROM agents WHERE id=? AND user_id=?",
            (agent_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agente não encontrado")

        cur.execute(
            """
            UPDATE agents
               SET revoked_at=CURRENT_TIMESTAMP,
                   status='disabled',
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=? AND user_id=?
            """,
            (agent_id, user_id),
        )
        conn.commit()
        refreshed = cur.execute(
            "SELECT * FROM agents WHERE id=? AND user_id=?",
            (agent_id, user_id),
        ).fetchone()
    return _sanitize_agent(refreshed)


def reprovision_agent(*, agent_id: str, user_id: int) -> Dict[str, Any]:
    import secrets

    new_token = secrets.token_urlsafe(32)
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT * FROM agents WHERE id=? AND user_id=?",
            (agent_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agente não encontrado")

        cur.execute(
            """
            UPDATE agents
               SET token=?,
                   revoked_at=NULL,
                   status='offline',
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=? AND user_id=?
            """,
            (new_token, agent_id, user_id),
        )
        conn.commit()
        refreshed = cur.execute(
            "SELECT * FROM agents WHERE id=? AND user_id=?",
            (agent_id, user_id),
        ).fetchone()

    agent_data = _sanitize_agent(refreshed)
    agent_data["agent_token"] = new_token
    return agent_data


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
    user_id: Optional[int] = None,
):
    scheduled_value = scheduled_at.isoformat() if scheduled_at else None
    payload_txt = _json_dumps(payload)

    cur.execute(
        """
        INSERT INTO jobs (type, payload, priority, scheduled_at, status, result, error, assigned_agent_id, attempts, created_at, updated_at, user_id)
        VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), 'pending', NULL, NULL, NULL, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """,
        (job_type, payload_txt, priority, scheduled_value, user_id),
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


def get_job(job_id: int, *, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        params: List[Any] = [job_id]
        where_clause = "WHERE id=?"
        if user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(user_id)
        row = cur.execute(f"SELECT * FROM jobs {where_clause}", params).fetchone()
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
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    agent_local_job_types = {"maps_search_fallback", "maps_enrich_fallback"}
    if job_type in agent_local_job_types and user_id is None:
        raise HTTPException(status_code=400, detail="user_id é obrigatório para jobs do agente local")

    with get_connection() as conn:
        cur = conn.cursor()
        job = _insert_job(
            cur,
            job_type=job_type,
            payload=payload,
            priority=priority,
            scheduled_at=scheduled_at,
            user_id=user_id,
        )
        conn.commit()
    return job


def fetch_next_job(
    *,
    agent_id: str,
    token: str,
    accepted_types: Optional[Sequence[str]] = None,
) -> Optional[Dict[str, Any]]:
    agent, conn = _get_agent_by_credentials(agent_id, token)
    user_id = agent.get("user_id")
    conn.close()
    # Escopa jobs ao dono do agente; impede que um agente visualize jobs de outro usuário.
    params: List[Any] = [JOB_STATUS_PENDING]
    params.append(user_id)
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
               AND user_id = ?
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
        refreshed = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.commit()

    _update_agent_touch(agent_id, user_id=user_id)

    job_row = refreshed or row
    job = dict(job_row)
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

    agent, conn = _get_agent_by_credentials(agent_id, token)
    user_id = agent.get("user_id")
    conn.close()

    with get_connection() as conn:
        cur = conn.cursor()
        params: List[Any] = [job_id]
        where_clause = "WHERE id=?"
        where_clause += " AND user_id = ?"
        params.append(user_id)
        row = cur.execute(f"SELECT * FROM jobs {where_clause}", params).fetchone()
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
            _handle_whatsapp_report(conn, payload, status, result, error_txt, user_id=user_id)

        conn.commit()

    _update_agent_touch(agent_id, user_id=user_id)
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
    user_id: Optional[int] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (lead_id, channel, message_id, action, notes, user_id),
    )


def _handle_whatsapp_report(conn, payload, status, result, error_txt, *, user_id: Optional[int] = None):
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
        lead_params: List[Any] = [lead_id]
        user_clause = ""
        if user_id is not None:
            user_clause = " AND user_id = ?"
            lead_params.append(user_id)
        conn.execute(
            f"UPDATE leads SET category='qualification', lastMovement=CURRENT_TIMESTAMP WHERE id=?{user_clause}",
            lead_params,
        )
        _log_prospection(
            conn,
            lead_id=lead_id,
            channel="whatsapp",
            message_id=message_id,
            action="sent",
            notes=notes,
            user_id=user_id,
        )
        _log_prospection(
            conn,
            lead_id=lead_id,
            channel="whatsapp",
            message_id=None,
            action="moved_stage",
            notes="auto:qualification",
            user_id=user_id,
        )
    elif status == JOB_STATUS_FAILED:
        _log_prospection(
            conn,
            lead_id=lead_id,
            channel="whatsapp",
            message_id=message_id,
            action="failed",
            notes=notes or "erro",
            user_id=user_id,
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
    lead_ids: Sequence[int], *, message: Optional[str] = None, lead_messages: Optional[Dict[int, str]] = None, user_id: Optional[int] = None
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
        params_jobs: List[Any] = [JOB_STATUS_PENDING, JOB_STATUS_IN_PROGRESS]
        user_filter = ""
        if user_id is not None:
            user_filter = "AND user_id = ?"
            params_jobs.append(user_id)
        pending_rows = cur.execute(
            f"""
            SELECT id, payload
              FROM jobs
             WHERE type='whatsapp_send'
               AND status IN (?, ?)
               {user_filter}
            """,
            params_jobs,
        ).fetchall()
        existing = []
        for row in pending_rows:
            payload = _json_loads(row["payload"])
            if isinstance(payload, dict):
                existing.append((row["id"], payload.get("lead_id"), payload.get("message_id")))

        for lead_id in lead_ids:
            try:
                lead_params: List[Any] = [lead_id]
                lead_clause = "WHERE id=?"
                if user_id is not None:
                    lead_clause += " AND user_id = ?"
                    lead_params.append(user_id)
                lead = cur.execute(
                    f"SELECT id, phone, customMessage FROM leads {lead_clause}",
                    lead_params,
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
                    user_id=user_id,
                )

                _log_prospection(
                    conn,
                    lead_id=lead_id,
                    channel="whatsapp",
                    message_id=message_id,
                    action="queued",
                    notes=f"phone={phone}",
                    user_id=user_id,
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


def get_whatsapp_queue(limit: int = 5, *, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        params: List[Any] = [JOB_STATUS_PENDING, limit]
        user_filter = ""
        if user_id is not None:
            user_filter = "AND user_id = ?"
            params.insert(1, user_id)
        rows = cur.execute(
            f"""
            SELECT id, payload, created_at, scheduled_at
              FROM jobs
             WHERE type='whatsapp_send' AND status=? {user_filter}
             ORDER BY scheduled_at ASC, created_at ASC, id ASC
             LIMIT ?
            """,
            params,
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


def get_whatsapp_recent(seconds: int = 300, *, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    seconds = max(30, min(int(seconds), 3600))
    with get_connection() as conn:
        cur = conn.cursor()
        params: List[Any] = [JOB_STATUS_COMPLETED, JOB_STATUS_FAILED, f"-{seconds} seconds"]
        user_filter = ""
        if user_id is not None:
            user_filter = "AND user_id = ?"
            params.append(user_id)
        rows = cur.execute(
            f"""
            SELECT id, payload, status, result, error, completed_at
              FROM jobs
             WHERE type='whatsapp_send'
               AND status IN (?, ?)
               AND completed_at IS NOT NULL
               AND completed_at >= datetime('now', ?)
               {user_filter}
             ORDER BY completed_at DESC
             LIMIT 200
            """,
            params,
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


def get_whatsapp_summary(*, user_id: Optional[int] = None) -> Dict[str, Any]:
    with get_connection() as conn:
        cur = conn.cursor()
        params_pending: List[Any] = [JOB_STATUS_PENDING]
        params_completed: List[Any] = [JOB_STATUS_COMPLETED]
        params_failed: List[Any] = [JOB_STATUS_FAILED]
        user_filter = ""
        if user_id is not None:
            user_filter = "AND user_id = ?"
            params_pending.append(user_id)
            params_completed.append(user_id)
            params_failed.append(user_id)
        pending = cur.execute(
            f"SELECT COUNT(*) AS c FROM jobs WHERE type='whatsapp_send' AND status=? {user_filter}",
            params_pending,
        ).fetchone()["c"]
        sent_today = cur.execute(
            f"""
            SELECT COUNT(*) AS c
              FROM jobs
             WHERE type='whatsapp_send'
               AND status=?
               AND date(completed_at) = date('now')
               {user_filter}
            """,
            params_completed,
        ).fetchone()["c"]
        failed_today = cur.execute(
            f"""
            SELECT COUNT(*) AS c
              FROM jobs
             WHERE type='whatsapp_send'
               AND status=?
               AND date(completed_at) = date('now')
               {user_filter}
            """,
            params_failed,
        ).fetchone()["c"]
    return {
        "pending": int(pending or 0),
        "sent_today": int(sent_today or 0),
        "failed_today": int(failed_today or 0),
    }


def get_jobs_overview(seconds: int = 120, *, user_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "agents": list_agents(max_age_seconds=seconds, user_id=user_id),
        "summary": get_whatsapp_summary(user_id=user_id),
    }


__all__ = [
    "provision_agent",
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
