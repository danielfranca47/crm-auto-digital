from __future__ import annotations

import json
import os
import sqlite3
import json
import os
import sqlite3
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from database import get_connection
from services.ai_orchestrator import (
    InboundEvent,
    build_context_bundle_from_inbound,
)
from services.jobs_service import get_job

router = APIRouter(prefix="/api", tags=["WhatsApp Executor"])


def _require_service_token(x_service_token: str | None = Header(None, alias="X-Service-Token")) -> str:
    expected = os.getenv("CRM_SERVICE_TOKEN") or os.getenv("CORE_SERVICE_TOKEN")
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return x_service_token


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
