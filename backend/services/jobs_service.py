"""Serviço de gerenciamento de jobs para o Agente Local."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from database import get_connection


JobStatus = str

PENDING: JobStatus = "pending"
IN_PROGRESS: JobStatus = "in_progress"
COMPLETED: JobStatus = "completed"
FAILED: JobStatus = "failed"


class AgentAuthError(Exception):
    """Erro levantado quando um agente não está autorizado."""


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def register_agent(agent_id: str, name: str, token: str) -> Dict[str, Any]:
    """Cria ou atualiza um agente local."""
    if not agent_id or not token:
        raise ValueError("agent_id e token são obrigatórios")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agents (id, name, token, status, last_seen, updated_at)
            VALUES (?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                token = excluded.token,
                status = 'active',
                last_seen = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (agent_id, name, token),
        )
        conn.commit()

        row = cur.execute(
            "SELECT id, name, status, last_seen, created_at, updated_at FROM agents WHERE id=?",
            (agent_id,),
        ).fetchone()

    return dict(row) if row else {"id": agent_id, "name": name, "status": "active"}


def authenticate_agent(agent_id: str, token: str) -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, token, status, last_seen FROM agents WHERE id=?",
            (agent_id,),
        ).fetchone()

    if not row or row["token"] != token:
        raise AgentAuthError("Agente não autorizado")

    return dict(row)


def touch_agent(agent_id: str, status: str = "active") -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE agents
               SET status = ?,
                   last_seen = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (status, agent_id),
        )
        conn.commit()


def enqueue_job(job_type: str, payload: Dict[str, Any], priority: int = 0) -> int:
    payload_str = json.dumps(payload or {})
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO jobs (type, payload, priority, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (job_type, payload_str, priority),
        )
        job_id = cur.lastrowid
        conn.commit()
    return int(job_id)


def _serialize_job_row(row: Any) -> Dict[str, Any]:
    payload = json.loads(row["payload"] or "{}")
    result = json.loads(row["result"]) if row["result"] else None
    return {
        "id": row["id"],
        "type": row["type"],
        "payload": payload,
        "status": row["status"],
        "priority": row["priority"],
        "result": result,
        "error": row["error"],
        "agent_id": row["agent_id"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def assign_next_job(agent_id: str, accepted_types: Optional[Sequence[str]] = None) -> Optional[Dict[str, Any]]:
    placeholders = ""
    if accepted_types:
        placeholders = ",".join(["?"] * len(accepted_types))
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        if accepted_types:
            row = cur.execute(
                f"""
                SELECT * FROM jobs
                 WHERE status = 'pending'
                   AND type IN ({placeholders})
                 ORDER BY priority DESC, created_at ASC
                 LIMIT 1
                """,
                tuple(accepted_types),
            ).fetchone()
        else:
            row = cur.execute(
                """
                SELECT * FROM jobs
                 WHERE status = 'pending'
                 ORDER BY priority DESC, created_at ASC
                 LIMIT 1
                """,
            ).fetchone()

        if not row:
            conn.commit()
            touch_agent(agent_id, status="inactive")
            return None

        cur.execute(
            """
            UPDATE jobs
               SET status = 'in_progress',
                   agent_id = ?,
                   started_at = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (agent_id, row["id"]),
        )
        conn.commit()

    touch_agent(agent_id, status="active")
    return _serialize_job_row(row)


def report_job_result(
    agent_id: str,
    job_id: int,
    status: JobStatus,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    if status not in {COMPLETED, FAILED}:
        raise ValueError("Status de término inválido para report")

    result_json = json.dumps(result or {}) if result else None

    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError("Job não encontrado")
        if row["agent_id"] and row["agent_id"] != agent_id:
            raise AgentAuthError("Job pertence a outro agente")

        cur.execute(
            """
            UPDATE jobs
               SET status = ?,
                   result = ?,
                   error = ?,
                   agent_id = ?,
                   finished_at = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (status, result_json, error, agent_id, job_id),
        )
        conn.commit()

    touch_agent(agent_id, status="active")
    job_dict = _serialize_job_row(row)
    job_dict.update({"status": status, "result": result or job_dict.get("result"), "error": error})
    _apply_post_job_hooks(job_dict, status, result or {}, error)
    return job_dict


def _apply_post_job_hooks(job: Dict[str, Any], status: JobStatus, result: Dict[str, Any], error: Optional[str]) -> None:
    job_type = job.get("type")
    payload = job.get("payload") or {}
    if job_type == "whatsapp_send":
        _handle_whatsapp_job(job, status, payload, result, error)


def _handle_whatsapp_job(
    job: Dict[str, Any],
    status: JobStatus,
    payload: Dict[str, Any],
    result: Dict[str, Any],
    error: Optional[str],
) -> None:
    queue_id = payload.get("queue_id")
    lead_id = payload.get("lead_id")
    message_id = payload.get("message_id")
    notes = result.get("notes") if isinstance(result, dict) else None
    error_text = error or (result.get("error") if isinstance(result, dict) else None)

    with get_connection() as conn:
        cur = conn.cursor()
        if queue_id:
            cur.execute(
                """
                UPDATE prospection_whatsapp_queue
                   SET status = ?,
                       processedAt = CURRENT_TIMESTAMP,
                       attempts = attempts + 1,
                       lastError = ?
                 WHERE id = ?
                """,
                (
                    "sent" if status == COMPLETED else "failed",
                    notes or error_text,
                    queue_id,
                ),
            )
        if lead_id and message_id:
            cur.execute(
                """
                INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
                VALUES (?, 'whatsapp', ?, ?, ?)
                """,
                (
                    lead_id,
                    message_id,
                    "sent" if status == COMPLETED else "failed",
                    notes or error_text,
                ),
            )
        conn.commit()


def overview(hours: int = 24) -> Dict[str, Any]:
    """Retorna dados de status da fila de jobs e agentes."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    with get_connection() as conn:
        cur = conn.cursor()
        pending = cur.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status = 'pending'",
        ).fetchone()["c"]
        in_progress = cur.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status = 'in_progress'",
        ).fetchone()["c"]
        completed_recent = cur.execute(
            """
            SELECT COUNT(*) AS c
              FROM jobs
             WHERE status = 'completed'
               AND finished_at IS NOT NULL
               AND finished_at >= ?
            """,
            (cutoff_iso,),
        ).fetchone()["c"]
        failed_recent = cur.execute(
            """
            SELECT COUNT(*) AS c
              FROM jobs
             WHERE status = 'failed'
               AND finished_at IS NOT NULL
               AND finished_at >= ?
            """,
            (cutoff_iso,),
        ).fetchone()["c"]

        agents = [
            dict(row)
            for row in cur.execute(
                """
                SELECT id, name, status, last_seen, updated_at
                  FROM agents
                 ORDER BY updated_at DESC
                """
            ).fetchall()
        ]

    return {
        "jobs": {
            "pending": int(pending),
            "in_progress": int(in_progress),
            "completed_recent": int(completed_recent),
            "failed_recent": int(failed_recent),
        },
        "agents": agents,
        "generated_at": _now_iso(),
    }


def list_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
             ORDER BY created_at DESC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_serialize_job_row(r) for r in rows]
