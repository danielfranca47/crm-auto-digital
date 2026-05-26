from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from database import get_connection
from services.ai_orchestrator import (
    InboundEvent,
    build_context_bundle_from_inbound,
    enrich_context_bundle,
)
from services.ai_orchestrator.orchestrator import _load_training_examples
from services.qualification_state import (
    get_qualification_state,
    increment_attempt,
    upsert_qualification_state,
)
from services.jobs_service import (
    JOB_BACKOFF_SECONDS,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_IN_PROGRESS,
    JOB_STATUS_PENDING,
    JOB_MAX_ATTEMPTS,
    LEAD_CATEGORIES,
    TYPE_WHATSAPP_FOLLOWUP_TICK,
    TYPE_WHATSAPP_FOLLOWUP_PREGENERATE,
    TYPE_WHATSAPP_APPOINTMENT_REMINDER,
    TYPE_WHATSAPP_APPOINTMENT_BRIEFING,
    TYPE_WHATSAPP_PREAGENDAMENTO_CHECKIN,
    TYPE_WHATSAPP_INBOUND,
    apply_outcome_highlight,
    apply_suggested_category,
    extract_outcome_payload,
    extract_suggested_category,
    expand_type_variants,
    get_job,
    normalize_job_type,
)
from services.briefing_service import generate_and_send_briefing
from services.followup_reconciler import reconcile_due_followups
from services.followup_channel_context import resolve_followup_tick_channel_context
from services.followup_state import (
    progress_followup_after_auto_send,
    stop_followup_on_handoff,
    start_cart_recovery_followup,
)
from core_client import fetch_core_ai_profile_resolve

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


def _compute_backoff_seconds(attempts: int) -> int:
    return JOB_BACKOFF_SECONDS.get(attempts, 0)


def _is_retryable(details: Optional[Dict[str, Any]]) -> bool:
    if not details:
        return False
    if "retryable" in details:
        return bool(details.get("retryable"))
    http_status = details.get("http_status")
    if isinstance(http_status, int):
        if http_status == 429:
            return True
        if 500 <= http_status <= 599:
            return True
    error_type = details.get("error_type")
    if isinstance(error_type, str) and error_type in {"timeout", "network"}:
        return True
    return False


@router.get("/jobs/{job_id}")
def get_job_by_id(job_id: int, _: str = Depends(_require_service_token)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return {"job": job}


@router.get("/internal/jobs/next")
def get_next_job_internal(
    types: Optional[str] = Query(None, description="Comma-separated job types"),
    limit: int = Query(1, ge=1, le=10),
    _: str = Depends(_require_service_token),
):
    requested_types = []
    if types:
        for raw in types.split(","):
            cleaned = raw.strip()
            if cleaned:
                requested_types.append(normalize_job_type(cleaned))
    if not requested_types:
        raise HTTPException(status_code=400, detail="types é obrigatório")

    expanded_types: list[str] = []
    for job_type in requested_types:
        expanded_types.extend(expand_type_variants(job_type))
    if not expanded_types:
        raise HTTPException(status_code=400, detail="types inválido")

    placeholders = ",".join(["?"] * len(expanded_types))
    params: list[Any] = [
        JOB_STATUS_PENDING,
        *expanded_types,
        JOB_MAX_ATTEMPTS,
        limit,
    ]
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            f"""
            SELECT * FROM jobs
             WHERE status=?
               AND type IN ({placeholders})
               AND COALESCE(scheduled_at, CURRENT_TIMESTAMP) <= CURRENT_TIMESTAMP
               AND attempts < ?
             ORDER BY priority DESC, scheduled_at ASC, created_at ASC, id ASC
             LIMIT ?
            """,
            params,
        ).fetchone()
    if not row:
        return Response(status_code=204)
    job = dict(row)
    job["payload"] = _json_loads(job.get("payload"))
    job["result"] = _json_loads(job.get("result"))
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


def _extract_preagendamento_checkin_iso(result_obj: Dict[str, Any]) -> Optional[str]:
    """Extrai checkin_at_iso do sinal emitido pelo child de pré-agendamento."""
    trace = result_obj.get("decision_trace") or {}
    child_sigs = trace.get("child_signals_structured") or {}
    val = child_sigs.get("checkin_at_iso")
    return str(val).strip() if val else None


def _dispatch_sales_flow_media(
    lead_id: int,
    user_id: int,
    phone: str,
    pre_send_media: list,
) -> None:
    from services.jobs_service import TYPE_WHATSAPP_SEND, create_job
    for item in sorted(pre_send_media, key=lambda m: m.get("send_order", 0)):
        media_url = item.get("media_url")
        if not media_url:
            continue
        create_job(
            job_type=TYPE_WHATSAPP_SEND,
            payload={
                "lead_id": lead_id,
                "user_id": user_id,
                "phone": phone,
                "body": "",
                "media_url": media_url,
                "media_type": item.get("media_type", "image"),
                "source": "sales_flow_media",
            },
            user_id=user_id,
        )


_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}


def _dispatch_system_actions(
    lead_id: int,
    user_id: int,
    phone: str,
    system_actions: list,
    conn,
) -> None:
    from services.jobs_service import TYPE_WHATSAPP_SEND, create_job
    for action in system_actions:
        atype = action.get("type")

        if atype == "send_message":
            body = action.get("content", "")
            if not body:
                continue
            create_job(
                job_type=TYPE_WHATSAPP_SEND,
                payload={
                    "lead_id": lead_id,
                    "user_id": user_id,
                    "phone": phone,
                    "body": body,
                    "source": "sales_flow_message",
                },
                user_id=user_id,
            )

        elif atype == "send_media":
            media_url = action.get("media_url", "")
            if not media_url:
                continue
            create_job(
                job_type=TYPE_WHATSAPP_SEND,
                payload={
                    "lead_id": lead_id,
                    "user_id": user_id,
                    "phone": phone,
                    "body": "",
                    "media_url": media_url,
                    "media_type": action.get("media_type", "image"),
                    "source": "sales_flow_media",
                },
                user_id=user_id,
            )

        elif atype == "advance_phase":
            target = action.get("target_phase")
            category = _PHASE_ID_TO_CATEGORY.get(target) if target else None
            if category:
                apply_suggested_category(
                    conn,
                    lead_id=lead_id,
                    user_id=user_id,
                    suggested_category=category,
                    reason="sales_flow_advance_phase",
                )

        elif atype == "mark_phase_triggered":
            phase_id = action.get("phase_id", "")
            if phase_id:
                import json
                row = conn.execute(
                    "SELECT phases_triggered FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id)
                ).fetchone()
                if row:
                    try:
                        existing: list = json.loads(row["phases_triggered"] or "[]")
                    except (ValueError, TypeError):
                        existing = []
                    if phase_id not in existing:
                        existing.append(phase_id)
                        conn.execute(
                            "UPDATE leads SET phases_triggered = ? WHERE id = ? AND user_id = ?",
                            (json.dumps(existing), lead_id, user_id),
                        )
                        conn.commit()


def _schedule_preagendamento_checkin(
    lead_id: int,
    user_id: int,
    checkin_at_iso: str,
) -> None:
    from services.jobs_service import create_job
    try:
        checkin_dt = datetime.fromisoformat(checkin_at_iso)
        if checkin_dt.tzinfo is None:
            checkin_dt = checkin_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return
    if checkin_dt <= datetime.now(timezone.utc):
        return
    create_job(
        job_type=TYPE_WHATSAPP_PREAGENDAMENTO_CHECKIN,
        payload={"lead_id": lead_id, "user_id": user_id, "checkin_at_iso": checkin_at_iso},
        scheduled_at=checkin_dt,
        user_id=user_id,
    )


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

    job_type = normalize_job_type(job.get("type") or "")
    if job_type in (TYPE_WHATSAPP_FOLLOWUP_TICK, TYPE_WHATSAPP_FOLLOWUP_PREGENERATE):
        with get_connection() as conn:
            channel_ctx = resolve_followup_tick_channel_context(conn, lead_id=int(lead_id), user_id=int(user_id))
        payload = {
            **payload,
            "message_text": str(message_text or "followup_tick_auto_trigger"),
            "instance_id": channel_ctx.get("instance_id"),
            "provider": channel_ctx.get("provider"),
            "phone": channel_ctx.get("phone") or payload.get("phone"),
        }
    elif job_type == TYPE_WHATSAPP_APPOINTMENT_REMINDER:
        with get_connection() as conn:
            channel_ctx = resolve_followup_tick_channel_context(conn, lead_id=int(lead_id), user_id=int(user_id))
        payload = {
            **payload,
            "message_text": str(message_text or "appointment_reminder_trigger"),
            "instance_id": channel_ctx.get("instance_id"),
            "provider": channel_ctx.get("provider"),
            "phone": channel_ctx.get("phone") or payload.get("phone"),
        }
    elif job_type == TYPE_WHATSAPP_PREAGENDAMENTO_CHECKIN:
        with get_connection() as conn:
            channel_ctx = resolve_followup_tick_channel_context(conn, lead_id=int(lead_id), user_id=int(user_id))
        payload = {
            **payload,
            "message_text": "preagendamento_checkin_trigger",
            "instance_id": channel_ctx.get("instance_id"),
            "provider": channel_ctx.get("provider"),
            "phone": channel_ctx.get("phone") or payload.get("phone"),
        }

    event = InboundEvent(
        user_id=int(user_id),
        lead_id=int(lead_id),
        channel="whatsapp",
        message_text=str(payload.get("message_text") or ""),
        received_at=str(payload.get("received_at") or ""),
        phone=payload.get("phone"),
        message_id=payload.get("message_id"),
        instance_id=payload.get("instance_id"),
        provider=payload.get("provider"),
    )

    bundle = build_context_bundle_from_inbound(event)
    bundle = enrich_context_bundle(bundle, event.user_id)
    decision = _fetch_latest_ai_decision(lead_id=event.lead_id)
    qualification_state = get_qualification_state(event.lead_id)

    if bundle.lead.get("bot_disabled"):
        bundle.metadata["bot_disabled"] = True

    bundle.metadata["allowed_lead_categories"] = LEAD_CATEGORIES

    # training_examples carregado separadamente pois requer ai_profile_id resolvido
    _ai_profile = bundle.ai_profile or {}
    training_examples = _load_training_examples(
        user_id=event.user_id,
        ai_profile_id=_ai_profile.get("id", 0),
        agent_mode=_ai_profile.get("agent_mode"),
    )

    return {
        "job": job,
        "lead": bundle.lead,
        "history": bundle.history,
        "ai_profile": bundle.ai_profile,
        "playbook": bundle.playbook,
        "decision": decision,
        "qualification_state": qualification_state,
        "metadata": bundle.metadata,
        "knowledge_items": bundle.knowledge_items or {},
        "knowledge_media": bundle.knowledge_media or {},
        "lead_detected_language": bundle.lead_detected_language or "all",
        "generated_prompt_parts": bundle.generated_prompt_parts or {},
        "training_examples": training_examples,
    }


class PregenerateResultPayload(BaseModel):
    lead_id: int
    user_id: int
    content: str


@router.put("/whatsapp/followup/scheduled-message")
def save_pregenerated_message(
    payload: PregenerateResultPayload,
    _: str = Depends(_require_service_token),
):
    """Salva mensagem pré-gerada pelo executor em followup_contract.scheduled_message."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT followup_contract FROM leads WHERE id = ? AND user_id = ?",
            (payload.lead_id, payload.user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        raw = row["followup_contract"]
        if isinstance(raw, str) and raw.strip():
            try:
                contract = json.loads(raw)
            except json.JSONDecodeError:
                contract = {}
        elif isinstance(raw, dict):
            contract = raw
        else:
            contract = {}

        existing = contract.get("scheduled_message") or {}
        if existing.get("edited_by_user"):
            return {"status": "skipped", "reason": "user_already_edited"}

        contract["scheduled_message"] = {
            "content": payload.content,
            "media_url": None,
            "media_type": None,
            "edited_by_user": False,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.execute(
            "UPDATE leads SET followup_contract = ?, lastMovement = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (json.dumps(contract, ensure_ascii=False), payload.lead_id, payload.user_id),
        )
        conn.commit()
    return {"status": "ok"}


class QualificationStateUpsertRequest(BaseModel):
    user_id: int
    patch: Dict[str, Any] = Field(default_factory=dict)


class QualificationStateAttemptRequest(BaseModel):
    user_id: int
    field: str


class FollowupReconcileRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    dry_run: bool = False


class ExecuteBriefingRequest(BaseModel):
    job_id: int
    lead_id: int
    user_id: int
    appointment_id: Optional[int] = None


@router.post("/internal/appointments/briefing/execute")
def execute_appointment_briefing(
    payload: ExecuteBriefingRequest,
    _: str = Depends(_require_service_token),
):
    """Executa o job de briefing pré-reunião: gera e envia o dossiê para o operador."""
    job = get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job_type = normalize_job_type(job.get("type") or "")
    if job_type != TYPE_WHATSAPP_APPOINTMENT_BRIEFING:
        raise HTTPException(status_code=400, detail="Tipo de job inválido para briefing")

    try:
        generate_and_send_briefing(
            lead_id=payload.lead_id,
            user_id=payload.user_id,
            appointment_id=payload.appointment_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar briefing: {exc}")

    return {"status": "ok", "job_id": payload.job_id}


@router.post("/internal/followup/reconcile")
def reconcile_followup_internal(
    payload: FollowupReconcileRequest,
    _: str = Depends(_require_service_token),
):
    result = reconcile_due_followups(limit=payload.limit, dry_run=payload.dry_run)
    return {"status": "ok", **result}


@router.get("/internal/leads/{lead_id}/qualification-state")
def get_lead_qualification_state(
    lead_id: int,
    _: str = Depends(_require_service_token),
):
    return {"qualification_state": get_qualification_state(lead_id)}


@router.post("/internal/leads/{lead_id}/qualification-state")
def upsert_lead_qualification_state(
    lead_id: int,
    payload: QualificationStateUpsertRequest,
    _: str = Depends(_require_service_token),
):
    state = upsert_qualification_state(lead_id=lead_id, user_id=payload.user_id, patch=payload.patch or {})
    return {"qualification_state": state}


@router.post("/internal/leads/{lead_id}/qualification-state/increment-attempt")
def increment_lead_qualification_attempt(
    lead_id: int,
    payload: QualificationStateAttemptRequest,
    _: str = Depends(_require_service_token),
):
    state = increment_attempt(lead_id=lead_id, user_id=payload.user_id, field=payload.field)
    return {"qualification_state": state}


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


class MeetingScheduledLog(BaseModel):
    lead_id: int
    user_id: Optional[int] = None
    job_id: Optional[int] = None
    reason: str


class MarkOutboundSentRequest(BaseModel):
    provider_message_id: str
    provider: Optional[str] = None


class AttachProviderRequest(BaseModel):
    provider_message_id: str
    provider: Optional[str] = None


@router.get("/internal/outbound-events/{outbound_event_id}")
def get_outbound_event_internal(
    outbound_event_id: int,
    _: str = Depends(_require_service_token),
):
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT * FROM outbound_events WHERE id = ?",
            (outbound_event_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Outbound event não encontrado")
    event = dict(row)
    return {"outbound_event": event}


@router.post("/internal/jobs/{job_id}/claim")
def claim_job_internal(
    job_id: int,
    payload: ClaimJobRequest,
    _: str = Depends(_require_service_token),
):
    final_status = JOB_STATUS_FAILED
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

        job_payload = _json_loads(row["payload"]) or {}
        job_type = normalize_job_type(row["type"])

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

        if job_type == TYPE_WHATSAPP_INBOUND:
            lead_id = job_payload.get("lead_id")
            if lead_id is not None:
                result_obj = payload.result if isinstance(payload.result, dict) else {}
                decision_trace = result_obj.get("decision_trace") if isinstance(result_obj.get("decision_trace"), dict) else None
                outcome = result_obj.get("outcome")
                suggested_category, category_reason = extract_suggested_category(payload.result)
                apply_suggested_category(
                    conn,
                    lead_id=int(lead_id),
                    user_id=row["user_id"],
                    suggested_category=suggested_category,
                    reason=category_reason,
                    inbound_message_text=job_payload.get("message_text"),
                    decision_trace=decision_trace,
                    outcome=outcome,
                )
                # outcome / kanban_highlight MUST be persisted only for inbound jobs.
                # Never persist these signals for outbound (whatsapp.send.local).
                outcome, highlight, outcome_reason, source_job_id = extract_outcome_payload(payload.result)
                apply_outcome_highlight(
                    conn,
                    lead_id=int(lead_id),
                    user_id=row["user_id"],
                    outcome=outcome,
                    highlight=highlight,
                    reason=outcome_reason,
                    source_job_id=source_job_id,
                )
                checkin_iso = _extract_preagendamento_checkin_iso(result_obj)
                if checkin_iso:
                    _schedule_preagendamento_checkin(
                        lead_id=int(lead_id),
                        user_id=row["user_id"],
                        checkin_at_iso=checkin_iso,
                    )
                _pre_send_media = result_obj.get("pre_send_media") or []
                if isinstance(_pre_send_media, dict):
                    _pre_send_media = [_pre_send_media]
                _lead_phone = job_payload.get("phone")
                if _lead_phone and _pre_send_media:
                    _dispatch_sales_flow_media(
                        lead_id=int(lead_id),
                        user_id=row["user_id"],
                        phone=_lead_phone,
                        pre_send_media=_pre_send_media,
                    )
                _system_actions = result_obj.get("system_actions") or []
                if _lead_phone and _system_actions:
                    _dispatch_system_actions(
                        lead_id=int(lead_id),
                        user_id=row["user_id"],
                        phone=_lead_phone,
                        system_actions=_system_actions,
                        conn=conn,
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
    details = payload.details or {}
    if payload.details is not None:
        error_txt = _json_dumps({"error": payload.error, "details": payload.details})
    else:
        error_txt = str(payload.error)

    final_status = JOB_STATUS_FAILED
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

        attempts = int(row["attempts"] or 0)
        retryable = _is_retryable(details)
        update_stmt = None
        update_params: list[Any] = []
        if retryable and attempts < JOB_MAX_ATTEMPTS:
            final_status = JOB_STATUS_PENDING
            backoff_seconds = _compute_backoff_seconds(attempts)
            schedule_expr = "CURRENT_TIMESTAMP"
            schedule_params: list[Any] = []
            if backoff_seconds > 0:
                schedule_expr = "datetime('now', ?)"
                schedule_params.append(f"+{backoff_seconds} seconds")
            update_stmt = f"""
                UPDATE jobs
                   SET status=?,
                       error=?,
                       result=NULL,
                       started_at=NULL,
                       assigned_agent_id=NULL,
                       scheduled_at={schedule_expr},
                       completed_at=NULL,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE id=?
            """
            update_params = [JOB_STATUS_PENDING, error_txt, *schedule_params, job_id]
        else:
            update_stmt = """
                UPDATE jobs
                   SET status=?,
                       completed_at=CURRENT_TIMESTAMP,
                       error=?,
                       result=NULL,
                       started_at=NULL,
                       assigned_agent_id=NULL,
                       updated_at=CURRENT_TIMESTAMP
                 WHERE id=?
            """
            update_params = [JOB_STATUS_FAILED, error_txt, job_id]
        cur.execute(update_stmt, update_params)
        refreshed = cur.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.commit()

    job = dict(refreshed)
    job["payload"] = _json_loads(job.get("payload"))
    job["result"] = _json_loads(job.get("result"))
    return {"job": job, "normalized": _normalize_job(job, status_override=final_status)}


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
                   bot_disabled_reason = ?,
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            (
                1 if payload.disabled else 0,
                (payload.reason or None) if payload.disabled else None,
                lead_id,
            ),
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
        if payload.disabled:
            stop_followup_on_handoff(
                conn,
                lead_id=lead_id,
                user_id=int(row["user_id"]),
                reason=payload.reason,
            )
        conn.commit()
        return {"status": "ok", "lead_id": lead_id, "bot_disabled": payload.disabled}


@router.post("/internal/leads/{lead_id}/buying-signal")
def create_buying_signal_notification(
    lead_id: int,
    _: str = Depends(_require_service_token),
):
    """Cria notificação buying_signal_detected para o operador."""
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT id, user_id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        user_id = row["user_id"]
        cur.execute(
            """
            INSERT INTO notifications (user_id, lead_id, type, read, created_at)
            VALUES (?, ?, 'buying_signal_detected', 0, CURRENT_TIMESTAMP)
            """,
            (user_id, lead_id),
        )
        conn.commit()
    return {"status": "ok", "lead_id": lead_id}


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


@router.post("/internal/logs/meeting-scheduled")
def log_meeting_scheduled(
    payload: MeetingScheduledLog,
    _: str = Depends(_require_service_token),
):
    with get_connection() as conn:
        cur = conn.cursor()
        notes = payload.dict()
        user_id = payload.user_id
        if user_id is None:
            row = cur.execute("SELECT user_id FROM leads WHERE id = ?", (payload.lead_id,)).fetchone()
            if row:
                user_id = row["user_id"]
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'meeting_scheduled', ?, ?)
            """,
            (payload.lead_id, _json_dumps(notes), user_id),
        )
        conn.commit()
        return {"status": "ok"}


@router.post("/whatsapp/outbound")
def register_outbound(
    payload: OutboundMessage,
    _: str = Depends(_require_service_token),
):
    if not payload.in_reply_to_message_id:
        raise HTTPException(
            status_code=400,
            detail="in_reply_to_message_id é obrigatório para outbound WhatsApp",
        )

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
                INSERT INTO outbound_events (
                    job_id, lead_id, user_id, phone, provider_message_id, in_reply_to_message_id, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'reserved')
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
                    SELECT id, provider_message_id, in_reply_to_message_id, status, message_id
                      FROM outbound_events
                     WHERE job_id = ? AND in_reply_to_message_id = ?
                     LIMIT 1
                    """,
                    (payload.job_id, payload.in_reply_to_message_id),
                ).fetchone()

                if not existing:
                    raise HTTPException(
                        status_code=500,
                        detail="IntegrityError sem registro existente encontrado (inconsistência de idempotência)",
                    )

                if existing["status"] == "sent":
                    return {
                        "status": "already_sent",
                        "outbound_event_id": existing["id"],
                        "provider_message_id": existing["provider_message_id"],
                        "in_reply_to_message_id": existing["in_reply_to_message_id"],
                        "message_id": existing["message_id"],
                        "outbound_event_status": existing["status"],
                    }

                return {
                    "status": "reserved_exists",
                    "outbound_event_id": existing["id"],
                    "provider_message_id": existing["provider_message_id"],
                    "in_reply_to_message_id": existing["in_reply_to_message_id"],
                    "message_id": existing["message_id"],
                    "outbound_event_status": existing["status"],
                }
            raise

        # Create message and link
        cur.execute(
            """
            INSERT INTO messages (lead_id, channel, subject, body, model)
            VALUES (?, 'whatsapp', NULL, ?, 'outbound')
            """,
            (payload.lead_id, payload.body),
        )
        message_id = int(cur.lastrowid)

        cur.execute(
            """
            UPDATE outbound_events
               SET message_id = ?
             WHERE id = ?
            """,
            (message_id, outbound_event_id),
        )

        notes = {
            "job_id": payload.job_id,
            "provider_message_id": payload.provider_message_id,
            "in_reply_to_message_id": payload.in_reply_to_message_id,
        }
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, 'whatsapp', ?, 'outbound_reserved', ?, ?)
            """,
            (
                payload.lead_id,
                message_id,
                json.dumps(notes, ensure_ascii=False),
                payload.user_id,
            ),
        )

        conn.commit()

    return {
        "status": "reserved",
        "message_id": message_id,
        "outbound_event_id": outbound_event_id,
    }



@router.post("/whatsapp/outbound/{outbound_event_id}/mark-sent")
def mark_outbound_sent(
    outbound_event_id: int,
    payload: MarkOutboundSentRequest,
    _: str = Depends(_require_service_token),
):
    # Pré-leitura do user_id fora do lock exclusivo, para buscar AI Profile
    _ai_profile: Optional[Dict[str, Any]] = None
    with get_connection() as _pre_conn:
        _pre_row = _pre_conn.execute(
            "SELECT user_id FROM outbound_events WHERE id = ?",
            (outbound_event_id,),
        ).fetchone()
    if _pre_row:
        try:
            _ai_profile = fetch_core_ai_profile_resolve(int(_pre_row["user_id"])) or {}
        except Exception:
            pass

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute(
            "SELECT * FROM outbound_events WHERE id = ?",
            (outbound_event_id,),
        ).fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Outbound event não encontrado")

        if row["status"] == "sent":
            conn.rollback()
            return {
                "status": "already_sent",
                "outbound_event_id": outbound_event_id,
                "provider_message_id": row["provider_message_id"],
            }

        cur.execute(
            """
            UPDATE outbound_events
               SET status = 'sent',
                   provider_message_id = COALESCE(?, provider_message_id)
             WHERE id = ?
            """,
            (payload.provider_message_id, outbound_event_id),
        )

        message_id = row["message_id"]
        existing_log = None
        if message_id:
            existing_log = cur.execute(
                """
                SELECT id FROM prospection_logs
                 WHERE lead_id = ? AND action = 'outbound_sent' AND message_id = ?
                 LIMIT 1
                """,
                (row["lead_id"], message_id),
            ).fetchone()

        if not existing_log:
            notes = {
                "job_id": row["job_id"],
                "provider_message_id": payload.provider_message_id,
                "in_reply_to_message_id": row["in_reply_to_message_id"],
                "provider": payload.provider,
            }
            cur.execute(
                """
                INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
                VALUES (?, 'whatsapp', ?, 'outbound_sent', ?, ?)
                """,
                (
                    row["lead_id"],
                    message_id,
                    json.dumps(notes, ensure_ascii=False),
                    row["user_id"],
                ),
            )

        job_row = cur.execute(
            "SELECT id, type FROM jobs WHERE id = ?",
            (row["job_id"],),
        ).fetchone()
        job_type = normalize_job_type(job_row["type"]) if job_row else None
        if job_type == "whatsapp.followup.tick":
            progress_followup_after_auto_send(
                conn,
                lead_id=int(row["lead_id"]),
                user_id=int(row["user_id"]),
                source_job_id=int(row["job_id"]),
                ai_profile=_ai_profile,
            )
        else:
            # Cart recovery: detecta envio de link de pagamento pelo bot para agent_2
            if message_id:
                msg_row = cur.execute(
                    "SELECT body FROM messages WHERE id = ?",
                    (message_id,),
                ).fetchone()
                message_body = (msg_row["body"] if msg_row else "") or ""
                if "http" in message_body.lower():
                    lead_row = cur.execute(
                        "SELECT agent_type, followup_status FROM leads WHERE id = ?",
                        (row["lead_id"],),
                    ).fetchone()
                    if (
                        lead_row
                        and lead_row["agent_type"] == "agent_2"
                        and str(lead_row["followup_status"] or "").lower() != "active"
                    ):
                        start_cart_recovery_followup(
                            conn,
                            lead_id=int(row["lead_id"]),
                            user_id=int(row["user_id"]),
                        )

        conn.commit()

    return {
        "status": "sent",
        "outbound_event_id": outbound_event_id,
        "provider_message_id": payload.provider_message_id,
    }


@router.post("/whatsapp/outbound/{outbound_event_id}/attach-provider")
def attach_outbound_provider(
    outbound_event_id: int,
    payload: AttachProviderRequest,
    _: str = Depends(_require_service_token),
):
    if not payload.provider_message_id:
        raise HTTPException(status_code=400, detail="provider_message_id é obrigatório")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute(
            "SELECT id, provider_message_id, status FROM outbound_events WHERE id = ?",
            (outbound_event_id,),
        ).fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Outbound event não encontrado")

        existing = row["provider_message_id"]
        if existing:
            if existing != payload.provider_message_id:
                conn.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="provider_message_id já definido com valor diferente",
                )
            conn.rollback()
            return {
                "status": "ok",
                "outbound_event_id": outbound_event_id,
                "provider_message_id": existing,
                "outbound_event_status": row["status"],
            }

        if row["status"] == "sent":
            if not existing:
                cur.execute(
                    """
                    UPDATE outbound_events
                       SET provider_message_id = ?
                     WHERE id = ?
                    """,
                    (payload.provider_message_id, outbound_event_id),
                )
                conn.commit()
                return {
                    "status": "ok",
                    "outbound_event_id": outbound_event_id,
                    "provider_message_id": payload.provider_message_id,
                    "outbound_event_status": row["status"],
                }
            conn.rollback()
            return {
                "status": "ok",
                "outbound_event_id": outbound_event_id,
                "provider_message_id": existing,
                "outbound_event_status": row["status"],
            }

        cur.execute(
            """
            UPDATE outbound_events
               SET provider_message_id = ?
             WHERE id = ?
            """,
            (payload.provider_message_id, outbound_event_id),
        )
        conn.commit()

    return {
        "status": "ok",
        "outbound_event_id": outbound_event_id,
        "provider_message_id": payload.provider_message_id,
        "outbound_event_status": row["status"],
    }
