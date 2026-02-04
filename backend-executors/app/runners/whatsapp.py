import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

from app.clients import core_client, crm_client
from app.core.config import settings
from app.core.logging import log_ctx, setup_logging
from app.services import decision_engine

JOB_MAX_ATTEMPTS = 3


class ExecutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        phase: str,
        service: str,
        http_status: Optional[int] = None,
        retryable: Optional[bool] = None,
        error_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.service = service
        self.http_status = http_status
        self.retryable = retryable
        self.error_type = error_type
        self.details = details or {}


def _truncate(text: str, limit: int = 120) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _safe_get(data: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def _format_history(history: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    if not history:
        return []
    last_messages = history[-limit:]
    formatted = []
    for item in last_messages:
        model = item.get("model") or "unknown"
        body = item.get("body") or ""
        formatted.append(f"{model}: {_truncate(str(body))}")
    return formatted


def _mask_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    suffix = phone[-4:] if len(phone) > 4 else phone
    return f"***{suffix}"


def _resolve_user_id(context: Dict[str, Any], job: Dict[str, Any]) -> Optional[int]:
    lead = context.get("lead") or {}
    job_ctx = context.get("job") or {}
    payload = job_ctx.get("payload") or {}
    return (
        lead.get("user_id")
        or job.get("user_id")
        or job_ctx.get("user_id")
        or payload.get("user_id")
    )


def _build_outbound_body(decision: decision_engine.DecisionOutput) -> Optional[str]:
    if decision.next_action in {"reply", "ask_qualification"}:
        return decision.message_text or ""
    if decision.next_action == "handoff":
        return decision.message_text or ""
    return None


def _format_questions(questions: List[str]) -> str:
    normalized = [str(item).strip() for item in questions if str(item).strip()]
    if not normalized:
        return ""
    return "Perfeito — só pra eu te ajudar melhor:\n" + "\n".join(
        f"- {question}" for question in normalized
    )


def _build_result_payload(
    decision: decision_engine.DecisionOutput,
    *,
    lead_id: Optional[int],
    user_id: Optional[int],
    phone: Optional[str],
    source_job_id: Optional[int],
) -> Dict[str, Any]:
    return {
        "context_fetched": True,
        "decision": decision.model_dump(),
        "lead_id": lead_id,
        "user_id": user_id,
        "phone": phone,
        "suggested_category": decision.suggested_category,
        "category_reason": decision.category_reason,
        "outcome": decision.outcome,
        "kanban_highlight": decision.kanban_highlight,
        "signals": decision.signals,
        "confidence": decision.confidence,
        "source_job_id": source_job_id,
    }


def _is_retryable_status(status_code: Optional[int]) -> bool:
    if status_code is None:
        return False
    if status_code == 429:
        return True
    return 500 <= status_code <= 599


def _is_retryable_error(status_code: Optional[int], error_type: Optional[str]) -> bool:
    if error_type in {"network", "timeout"}:
        return True
    return _is_retryable_status(status_code)


def _build_failure_details(exc: ExecutionError) -> Dict[str, Any]:
    details = {
        "phase": exc.phase,
        "service": exc.service,
        "http_status": exc.http_status,
        "retryable": exc.retryable if exc.retryable is not None else _is_retryable_status(exc.http_status),
    }
    if exc.error_type:
        details["error_type"] = exc.error_type
    details.update(exc.details)
    return details


def _fail_job(job_id: str, logger: logging.LoggerAdapter, exc: ExecutionError, attempt: Optional[int]) -> int:
    details = _build_failure_details(exc)
    retryable = bool(details.get("retryable"))
    error_event_map = {
        "claim": "job_claim_error",
        "context": "job_context_error",
        "reserve": "outbound_reserve_error",
        "attach_provider": "outbound_attach_provider_error",
        "core_send": "core_send_error",
        "mark_sent": "mark_sent_error",
        "complete": "job_complete_error",
    }
    error_event = error_event_map.get(exc.phase, "job_error")
    logger.error(
        "event=%s error=%s",
        error_event,
        exc,
        extra={"phase": exc.phase},
    )
    try:
        crm_client.fail_job(job_id, error=str(exc), details=details)
    except crm_client.CRMClientError as crm_exc:
        logger.error("event=job_fail_report_error error=%s", crm_exc, extra={"phase": "fail"})
        return 1

    if retryable and attempt is not None and attempt < JOB_MAX_ATTEMPTS:
        logger.info(
            "event=job_retry_scheduled retryable=%s",
            retryable,
            extra={"phase": exc.phase},
        )
        return 1

    logger.error(
        "event=job_failed_final retryable=%s",
        retryable,
        extra={"phase": exc.phase},
    )
    return 1


def execute_job(job_id: str, logger: logging.Logger) -> int:
    ctx_logger = log_ctx(logger, job_id=job_id)
    lease_owner = "executors:local"
    attempt = None

    try:
        claim_response = crm_client.claim_job(job_id, lease_owner=lease_owner, ttl_seconds=300)
        claim_job = claim_response.get("job") if isinstance(claim_response, dict) else None
        normalized = claim_response.get("normalized") if isinstance(claim_response, dict) else None
        if isinstance(normalized, dict):
            attempt = normalized.get("attempts")
        if attempt is None and isinstance(claim_job, dict):
            attempt = claim_job.get("attempts")

        ctx_logger = log_ctx(logger, job_id=job_id, attempt=attempt)
        ctx_logger.info("event=job_claimed", extra={"phase": "claim"})
    except crm_client.CRMClientConflictError as exc:
        ctx_logger.error("event=job_claim_conflict error=%s", exc, extra={"phase": "claim"})
        return 1
    except crm_client.CRMClientError as exc:
        exec_error = ExecutionError(
            str(exc),
            phase="claim",
            service="crm",
            http_status=exc.status_code,
            retryable=_is_retryable_error(exc.status_code, exc.error_type),
            error_type=exc.error_type,
        )
        return _fail_job(job_id, ctx_logger, exec_error, attempt)

    try:
        job = crm_client.get_job(job_id)
        context = crm_client.get_whatsapp_execution_context(job_id)
    except crm_client.CRMClientError as exc:
        exec_error = ExecutionError(
            str(exc),
            phase="context",
            service="crm",
            http_status=exc.status_code,
            retryable=_is_retryable_error(exc.status_code, exc.error_type),
            error_type=exc.error_type,
        )
        return _fail_job(job_id, ctx_logger, exec_error, attempt)

    lead = context.get("lead") or {}
    history = context.get("history") or []
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}

    lead_id = _safe_get(lead, "id")
    lead_name = _safe_get(lead, "contactName", "companyName", "name")
    lead_phone = _safe_get(lead, "phone", "phone_e164")
    user_id = _resolve_user_id(context, job)
    in_reply_to_message_id = metadata.get("message_id")
    if not in_reply_to_message_id:
        exec_error = ExecutionError(
            "missing in_reply_to_message_id in execution context",
            phase="context",
            service="executor",
            retryable=False,
        )
        return _fail_job(job_id, ctx_logger, exec_error, attempt)

    instance_id = metadata.get("instance_id")
    provider = metadata.get("provider") or "uazapi"
    phone = metadata.get("phone") or lead_phone

    ctx_logger = log_ctx(
        logger,
        job_id=job_id,
        lead_id=lead_id,
        user_id=user_id,
        instance_id=instance_id,
        provider=provider,
        attempt=attempt,
    )
    ctx_logger.info(
        "event=job_loaded type=%s status=%s",
        job.get("type"),
        job.get("status"),
        extra={"phase": "context"},
    )
    ctx_logger.info(
        "event=lead_loaded name=%s phone=%s",
        lead_name,
        _mask_phone(str(phone) if phone else None),
        extra={"phase": "context"},
    )
    ctx_logger.info(
        "event=history_loaded total=%s last=%s",
        len(history),
        _format_history(history),
        extra={"phase": "context"},
    )
    ctx_logger.info(
        "event=ai_profile_loaded id=%s name=%s template_key=%s",
        _safe_get(ai_profile, "id"),
        _safe_get(ai_profile, "name"),
        _safe_get(ai_profile, "template_key"),
        extra={"phase": "context"},
    )
    ctx_logger.info(
        "event=playbook_loaded template_key=%s",
        _safe_get(playbook, "template_key", "name"),
        extra={"phase": "context"},
    )
    ctx_logger.info(
        "event=metadata_loaded provider=%s instance_id=%s message_id=%s received_at=%s phone=%s",
        metadata.get("provider"),
        metadata.get("instance_id"),
        metadata.get("message_id"),
        metadata.get("received_at"),
        metadata.get("phone"),
        extra={"phase": "context"},
    )

    decision = decision_engine.decide(context, logger=ctx_logger)
    ctx_logger.info(
        "event=decision_made next_action=%s reason=%s",
        decision.next_action,
        decision.reason,
        extra={"phase": "decision"},
    )
    outbound_body = _build_outbound_body(decision)
    if decision.next_action == "ask_qualification" and not outbound_body:
        fallback_text = _format_questions(decision.questions or [])
        if fallback_text:
            outbound_body = fallback_text
    result_payload = _build_result_payload(
        decision,
        lead_id=lead_id,
        user_id=user_id,
        phone=phone,
        source_job_id=int(job_id),
    )

    if decision.next_action == "ignore":
        result_payload["outbound_status"] = "skipped_ignore"
        try:
            crm_client.complete_job(job_id, result=result_payload)
        except crm_client.CRMClientError as exc:
            exec_error = ExecutionError(
                str(exc),
                phase="complete",
                service="crm",
                http_status=exc.status_code,
                retryable=_is_retryable_error(exc.status_code, exc.error_type),
                error_type=exc.error_type,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)
        ctx_logger.info("event=job_completed status=skipped_ignore", extra={"phase": "complete"})
        return 0

    if outbound_body is None or outbound_body == "":
        if decision.next_action == "handoff":
            result_payload["outbound_status"] = "skipped_handoff_empty"
        else:
            result_payload["outbound_status"] = "skipped_empty_body"
        try:
            crm_client.complete_job(job_id, result=result_payload)
        except crm_client.CRMClientError as exc:
            exec_error = ExecutionError(
                str(exc),
                phase="complete",
                service="crm",
                http_status=exc.status_code,
                retryable=_is_retryable_error(exc.status_code, exc.error_type),
                error_type=exc.error_type,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)
        ctx_logger.info("event=job_completed status=%s", result_payload["outbound_status"], extra={"phase": "complete"})
        return 0

    outbound_payload = {
        "job_id": int(job_id),
        "lead_id": lead_id,
        "user_id": user_id,
        "phone": phone,
        "body": outbound_body,
        "provider": provider,
        "in_reply_to_message_id": in_reply_to_message_id,
    }
    ctx_logger.info("event=outbound_request url=/api/whatsapp/outbound", extra={"phase": "reserve"})
    try:
        outbound_response = crm_client.register_whatsapp_outbound(outbound_payload)
    except crm_client.CRMClientError as exc:
        exec_error = ExecutionError(
            str(exc),
            phase="reserve",
            service="crm",
            http_status=exc.status_code,
            retryable=_is_retryable_error(exc.status_code, exc.error_type),
            error_type=exc.error_type,
        )
        return _fail_job(job_id, ctx_logger, exec_error, attempt)

    outbound_status = outbound_response.get("status")
    outbound_event_status = outbound_response.get("outbound_event_status")
    provider_message_id = outbound_response.get("provider_message_id")
    result_payload["outbound_status"] = outbound_status
    result_payload["outbound_event_id"] = outbound_response.get("outbound_event_id")
    result_payload["outbound_message_id"] = outbound_response.get("message_id")

    if outbound_status == "already_sent":
        ctx_logger.info("event=outbound_already_sent", extra={"phase": "reserve"})
        try:
            crm_client.complete_job(job_id, result=result_payload)
        except crm_client.CRMClientError as exc:
            exec_error = ExecutionError(
                str(exc),
                phase="complete",
                service="crm",
                http_status=exc.status_code,
                retryable=_is_retryable_error(exc.status_code, exc.error_type),
                error_type=exc.error_type,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)
        ctx_logger.info("event=job_completed status=already_sent", extra={"phase": "complete"})
        return 0

    if outbound_status in {"reserved", "reserved_exists"}:
        outbound_event_id = outbound_response.get("outbound_event_id")
        if not outbound_event_id:
            exec_error = ExecutionError(
                "missing outbound_event_id for reserved outbound",
                phase="reserve",
                service="executor",
                retryable=False,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)
        ctx_logger.info(
            "event=outbound_%s outbound_event_status=%s",
            outbound_status,
            outbound_event_status,
            extra={"phase": "reserve"},
        )

        if outbound_event_status == "sent":
            result_payload["outbound_status"] = "already_sent"
            result_payload["provider_message_id"] = provider_message_id
            try:
                crm_client.complete_job(job_id, result=result_payload)
            except crm_client.CRMClientError as exc:
                exec_error = ExecutionError(
                    str(exc),
                    phase="complete",
                    service="crm",
                    http_status=exc.status_code,
                    retryable=_is_retryable_error(exc.status_code, exc.error_type),
                    error_type=exc.error_type,
                )
                return _fail_job(job_id, ctx_logger, exec_error, attempt)
            ctx_logger.info("event=job_completed status=already_sent", extra={"phase": "complete"})
            return 0

        if provider_message_id:
            ctx_logger.info("event=mark_sent_request url=mark-sent", extra={"phase": "mark_sent"})
            try:
                mark_sent_response = crm_client.mark_whatsapp_outbound_sent(
                    int(outbound_event_id),
                    {"provider_message_id": provider_message_id, "provider": provider},
                )
            except crm_client.CRMClientError as exc:
                exec_error = ExecutionError(
                    str(exc),
                    phase="mark_sent",
                    service="crm",
                    http_status=exc.status_code,
                    retryable=_is_retryable_error(exc.status_code, exc.error_type),
                    error_type=exc.error_type,
                )
                return _fail_job(job_id, ctx_logger, exec_error, attempt)
            final_status = mark_sent_response.get("status")
            result_payload["outbound_mark_sent_status"] = final_status
            result_payload["outbound_status"] = final_status
            try:
                crm_client.complete_job(job_id, result=result_payload)
            except crm_client.CRMClientError as exc:
                exec_error = ExecutionError(
                    str(exc),
                    phase="complete",
                    service="crm",
                    http_status=exc.status_code,
                    retryable=_is_retryable_error(exc.status_code, exc.error_type),
                    error_type=exc.error_type,
                )
                return _fail_job(job_id, ctx_logger, exec_error, attempt)
            ctx_logger.info("event=mark_sent_success status=%s", final_status, extra={"phase": "mark_sent"})
            ctx_logger.info("event=job_completed status=%s", final_status, extra={"phase": "complete"})
            return 0

        ctx_logger.info("event=core_send_request url=/whatsapp/send", extra={"phase": "core_send"})
        try:
            core_response = core_client.send_whatsapp_message(
                {
                    "provider": provider,
                    "instance_id": instance_id,
                    "number": phone,
                    "text": outbound_body,
                }
            )
        except core_client.CoreClientError as exc:
            detail = exc.response_body or ""
            ctx_logger.info(
                "event=core_send_error status=%s detail=%s",
                exc.status_code,
                detail,
                extra={"phase": "core_send"},
            )
            message = str(exc)
            retryable = _is_retryable_error(exc.status_code, exc.error_type)
            if exc.status_code == 401:
                message = "Core service token inválido ou ausente"
                retryable = False
            elif exc.status_code == 403:
                if "connection inactive" in detail.lower():
                    message = "WhatsApp connection inactive (instância não está ativa)"
                else:
                    message = "Acesso negado pelo Core"
                retryable = False
            exec_error = ExecutionError(
                message,
                phase="core_send",
                service="core",
                http_status=exc.status_code,
                retryable=retryable,
                error_type=exc.error_type,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)

        provider_message_id = core_response.get("provider_message_id")
        result_payload["provider_message_id"] = provider_message_id
        ctx_logger.info("event=core_send_success", extra={"phase": "core_send"})

        ctx_logger.info("event=attach_provider_request url=attach-provider", extra={"phase": "attach_provider"})
        try:
            attach_response = crm_client.attach_whatsapp_outbound_provider(
                int(outbound_event_id),
                {"provider_message_id": provider_message_id, "provider": provider},
            )
        except crm_client.CRMClientError as exc:
            exec_error = ExecutionError(
                str(exc),
                phase="attach_provider",
                service="crm",
                http_status=exc.status_code,
                retryable=_is_retryable_error(exc.status_code, exc.error_type),
                error_type=exc.error_type,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)
        provider_message_id = attach_response.get("provider_message_id") or provider_message_id
        ctx_logger.info("event=attach_provider_success", extra={"phase": "attach_provider"})

        ctx_logger.info("event=mark_sent_request url=mark-sent", extra={"phase": "mark_sent"})
        try:
            mark_sent_response = crm_client.mark_whatsapp_outbound_sent(
                int(outbound_event_id),
                {"provider_message_id": provider_message_id, "provider": provider},
            )
        except crm_client.CRMClientError as exc:
            exec_error = ExecutionError(
                str(exc),
                phase="mark_sent",
                service="crm",
                http_status=exc.status_code,
                retryable=_is_retryable_error(exc.status_code, exc.error_type),
                error_type=exc.error_type,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)

        final_status = mark_sent_response.get("status")
        if final_status not in {"sent", "already_sent"}:
            exec_error = ExecutionError(
                f"unexpected outbound final status: {final_status}",
                phase="mark_sent",
                service="crm",
                retryable=False,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)

        result_payload["outbound_mark_sent_status"] = final_status
        result_payload["outbound_status"] = final_status
        ctx_logger.info("event=mark_sent_success status=%s", final_status, extra={"phase": "mark_sent"})

        try:
            crm_client.complete_job(job_id, result=result_payload)
        except crm_client.CRMClientError as exc:
            exec_error = ExecutionError(
                str(exc),
                phase="complete",
                service="crm",
                http_status=exc.status_code,
                retryable=_is_retryable_error(exc.status_code, exc.error_type),
                error_type=exc.error_type,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)
        ctx_logger.info("event=job_completed status=%s", final_status, extra={"phase": "complete"})
        return 0

    result_payload["outbound_status"] = outbound_status or "unknown"
    try:
        crm_client.complete_job(job_id, result=result_payload)
    except crm_client.CRMClientError as exc:
        exec_error = ExecutionError(
            str(exc),
            phase="complete",
            service="crm",
            http_status=exc.status_code,
            retryable=_is_retryable_error(exc.status_code, exc.error_type),
            error_type=exc.error_type,
        )
        return _fail_job(job_id, ctx_logger, exec_error, attempt)
    ctx_logger.info("event=job_completed status=%s", result_payload["outbound_status"], extra={"phase": "complete"})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WhatsApp executor runner (stub)")
    parser.add_argument("--job-id", dest="job_id", help="Job ID to execute")
    args = parser.parse_args()

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    if not args.job_id:
        logger.error("Missing --job-id. Example: python -m app.runners.whatsapp --job-id 123")
        return 2

    try:
        return execute_job(str(args.job_id), logger)
    except Exception as exc:
        ctx_logger = log_ctx(logger, job_id=args.job_id)
        ctx_logger.error("event=job_execution_error error=%s", exc, extra={"phase": "unknown"})
        try:
            crm_client.fail_job(args.job_id, error=str(exc))
        except crm_client.CRMClientError:
            ctx_logger.error("event=job_fail_report_error error=failed_to_mark_job_failed", extra={"phase": "fail"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
