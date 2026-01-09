from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_connection
from services.ai_orchestrator import (
    InboundEvent,
    build_context_bundle_from_inbound,
)
from services.jobs_service import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_PENDING,
    get_job,
)

router = APIRouter(prefix="/api", tags=["WhatsApp Executor"])


def _require_service_token(x_service_token: str | None = Header(None, alias="X-Service-Token")) -> str:
    expected = os.getenv("CRM_SERVICE_TOKEN") or os.getenv("CORE_SERVICE_TOKEN")
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return x_service_token


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _json_loads(data: Optional[str]) -> Any:
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


def _normalize_job(
    job: Dict[str, Any],
    *,
    status_override: Optional[str] = None,
    lease_owner_override: Optional[str] = None,
) -> Dict[str, Any]:
    status_map = {
        JOB_STATUS_PENDING: "queued",
        JOB_STATUS_IN_PROGRESS: "running",
        JOB_STATUS_COMPLETED: "succeeded",
        JOB_STATUS_FAILED: "failed",
    }
    raw_status = status_override or job.get("status")
    return {
        "status": status_map.get(raw_status, raw_status),
        "attempts": job.get("attempts"),
        "locked_at": job.get("started_at"),
        "lease_owner": lease_owner_override or job.get("assigned_agent_id"),
        "last_error": job.get("error"),
    }


def _parse_db_datetime(value: Optional[Any]) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace(" ", "T")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@router.get("/jobs/{job_id}")
def get_job_by_id(job_id: int, _: str = Depends(_require_service_token)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return {"job": job}


def _fetch_latest_ai_decision(lead_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT notes FROM prospection_logs
             WHERE lead_id = ? AND action = 'ai_decided'
             ORDER BY id DESC
             LIMIT 1
            """,
            (lead_id,),
        ).fetchone()
    if not row:
        return None
    notes = row["notes"]
    if not notes:
        return None
    try:
        return json.loads(notes)
    except json.JSONDecodeError:
        return {"raw_notes": notes}


@router.get("/whatsapp/execution-context")
def whatsapp_execution_context(
    job_id: int = Query(..., description="ID do job inbound"),
    _: str = Depends(_require_service_token),
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    payload = job.get("payload") or {}
    lead_id = payload.get("lead_id")
    user_id = payload.get("user_id")
    message_text = payload.get("message_text")
    if not lead_id or not user_id:
        raise HTTPException(status_code=400, detail="Payload do job incompleto para montar contexto")

    event = InboundEvent(
        user_id=int(user_id),
        lead_id=int(lead_id),
        channel="whatsapp",
        message_text=str(message_text or ""),
        received_at=str(payload.get("received_at") or ""),
        phone=payload.get("phone"),
        message_id=payload.get("message_id"),
        instance_id=payload.get("instance_id"),
        provider=payload.get("provider"),
    )

    bundle = build_context_bundle_from_inbound(event)
    decision = _fetch_latest_ai_decision(lead_id=event.lead_id)

    if bundle.lead.get("bot_disabled"):
        bundle.metadata["bot_disabled"] = True

    return {
        "job": job,
        "lead": bundle.lead,
        "history": bundle.history,
        "ai_profile": bundle.ai_profile,
        "playbook": bundle.playbook,
        "decision": decision,
        "metadata": bundle.metadata,
    }


class OutboundMessage(BaseModel):
    job_id: int
    lead_id: int
    user_id: int
    phone: str
    body: str
    provider_message_id: str | None = None
    in_reply_to_message_id: str | None = None


class ClaimJobRequest(BaseModel):
    lease_owner: str = Field(..., description="Identificador do executor/worker")
    lease_ttl_seconds: int = Field(300, ge=1, description="Tempo de lease em segundos")


class CompleteJobRequest(BaseModel):
    result: Dict[str, Any] = Field(default_factory=dict)


class FailJobRequest(BaseModel):
    error: str = Field(..., description="Mensagem de erro")
    details: Optional[Dict[str, Any]] = Field(default=None)


class BotDisabledRequest(BaseModel):
    disabled: bool
    reason: Optional[str] = None


class HandoffRequestedLog(BaseModel):
    user_id: int
    lead_id: int
    job_id: int
    message_id: Optional[str] = None
    reason: Optional[str] = None
    policy: str
    identity_mode: str


@router.post("/internal/jobs/{job_id}/claim")
def claim_job_internal(
    job_id: int,
    payload: ClaimJobRequest,
    _: str = Depends(_require_service_token),
):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Job não encontrado")

        current_status = row["status"]
        if current_status in {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED}:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Job já finalizado")

        if current_status == JOB_STATUS_IN_PROGRESS:
            started_at = _parse_db_datetime(row["started_at"])
            if started_at:
                now = datetime.utcnow()
                if (now - started_at).total_seconds() < payload.lease_ttl_seconds:
                    conn.rollback()
                    raise HTTPException(status_code=409, detail="Job já está em execução")

        threshold_delta = f"-{payload.lease_ttl_seconds} seconds"
        updated = cur.execute(
            """
            UPDATE jobs
               SET status=?,
                   started_at=CURRENT_TIMESTAMP,
                   attempts=attempts + 1,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=?
               AND status IN (?, ?)
               AND (
                    status != ?
                    OR started_at IS NULL
                    OR started_at < datetime('now', ?)
               )
            """,
            (
                JOB_STATUS_IN_PROGRESS,
                job_id,
                JOB_STATUS_PENDING,
                JOB_STATUS_IN_PROGRESS,
                JOB_STATUS_IN_PROGRESS,
                threshold_delta,
            ),
        )
        if updated.rowcount == 0:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Job já está em execução")

        refreshed = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.commit()

    job = dict(refreshed)
    job["payload"] = _json_loads(job.get("payload"))
    job["result"] = _json_loads(job.get("result"))
    return {
        "job": job,
        "normalized": _normalize_job(
            job,
            status_override=JOB_STATUS_IN_PROGRESS,
            lease_owner_override=payload.lease_owner,
        ),
    }


@router.post("/internal/jobs/{job_id}/complete")
def complete_job_internal(
    job_id: int,
    payload: CompleteJobRequest,
    _: str = Depends(_require_service_token),
):
    result_txt = _json_dumps(payload.result)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Job não encontrado")
        if row["status"] in {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED}:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Job já finalizado")

        cur.execute(
            """
            UPDATE jobs
               SET status=?,
                   completed_at=CURRENT_TIMESTAMP,
                   result=?,
                   error=NULL,
                   started_at=NULL,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=?
            """,
            (JOB_STATUS_COMPLETED, result_txt, job_id),
        )
        refreshed = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.commit()

    job = dict(refreshed)
    job["payload"] = _json_loads(job.get("payload"))
    job["result"] = _json_loads(job.get("result"))
    return {"job": job, "normalized": _normalize_job(job, status_override=JOB_STATUS_COMPLETED)}


@router.post("/internal/jobs/{job_id}/fail")
def fail_job_internal(
    job_id: int,
    payload: FailJobRequest,
    _: str = Depends(_require_service_token),
):
    if payload.details is not None:
        error_txt = _json_dumps({"error": payload.error, "details": payload.details})
    else:
        error_txt = str(payload.error)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Job não encontrado")
        if row["status"] in {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED}:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Job já finalizado")

        cur.execute(
            """
            UPDATE jobs
               SET status=?,
                   completed_at=CURRENT_TIMESTAMP,
                   error=?,
                   result=NULL,
                   started_at=NULL,
                   updated_at=CURRENT_TIMESTAMP
             WHERE id=?
            """,
            (JOB_STATUS_FAILED, error_txt, job_id),
        )
        refreshed = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.commit()

    job = dict(refreshed)
    job["payload"] = _json_loads(job.get("payload"))
    job["result"] = _json_loads(job.get("result"))
    return {"job": job, "normalized": _normalize_job(job, status_override=JOB_STATUS_FAILED)}


@router.post("/internal/leads/{lead_id}/bot-disabled")
def set_lead_bot_disabled(
    lead_id: int,
    payload: BotDisabledRequest,
    _: str = Depends(_require_service_token),
):
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT id, user_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        cur.execute(
            """
            UPDATE leads
               SET bot_disabled = ?,
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (1 if payload.disabled else 0, lead_id),
        )

        notes = {"disabled": payload.disabled}
        if payload.reason:
            notes["reason"] = payload.reason
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'bot_disabled_changed', ?, ?)
            """,
            (lead_id, _json_dumps(notes), row["user_id"]),
        )
        conn.commit()
        return {"status": "ok", "lead_id": lead_id, "bot_disabled": payload.disabled}


@router.post("/internal/logs/handoff-requested")
def log_handoff_requested(
    payload: HandoffRequestedLog,
    _: str = Depends(_require_service_token),
):
    with get_connection() as conn:
        cur = conn.cursor()
        notes = payload.dict()
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'handoff_requested', ?, ?)
            """,
            (payload.lead_id, _json_dumps(notes), payload.user_id),
        )
        conn.commit()
        return {"status": "ok"}


@router.post("/whatsapp/outbound")
def register_outbound(
    payload: OutboundMessage,
    _: str = Depends(_require_service_token),
):
    job = get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job.get("user_id") and int(job["user_id"]) != payload.user_id:
        raise HTTPException(status_code=400, detail="user_id não corresponde ao job")

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO outbound_events (job_id, lead_id, user_id, phone, provider_message_id, in_reply_to_message_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.job_id,
                    payload.lead_id,
                    payload.user_id,
                    payload.phone,
                    payload.provider_message_id,
                    payload.in_reply_to_message_id,
                ),
            )
            outbound_event_id = int(cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper():
                conn.rollback()
                existing = cur.execute(
                    """
                    SELECT id, provider_message_id, in_reply_to_message_id
                      FROM outbound_events
                     WHERE job_id = ? OR (in_reply_to_message_id IS NOT NULL AND in_reply_to_message_id = ?)
                     LIMIT 1
                    """,
                    (payload.job_id, payload.in_reply_to_message_id),
                ).fetchone()
                return {
                    "status": "already_sent",
                    "outbound_event_id": existing["id"] if existing else None,
                    "provider_message_id": existing["provider_message_id"] if existing else None,
                    "in_reply_to_message_id": existing["in_reply_to_message_id"] if existing else None,
                }
            raise

        cur.execute(
            """
            INSERT INTO messages (lead_id, channel, subject, body, model)
            VALUES (?, 'whatsapp', NULL, ?, 'outbound')
            """,
            (payload.lead_id, payload.body),
        )
        message_id = int(cur.lastrowid)

        notes = {
            "job_id": payload.job_id,
            "provider_message_id": payload.provider_message_id,
            "in_reply_to_message_id": payload.in_reply_to_message_id,
        }
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, 'whatsapp', ?, 'outbound_sent', ?, ?)
            """,
            (
                payload.lead_id,
                message_id,
                json.dumps(notes, ensure_ascii=False),
                payload.user_id,
            ),
        )
        conn.commit()

    return {"status": "sent", "message_id": message_id, "outbound_event_id": outbound_event_id}
