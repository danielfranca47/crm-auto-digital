import argparse
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional

from app.clients import core_client, crm_client
from app.core.config import settings
from app.core.logging import log_ctx, setup_logging
from app.services import decision_engine
from app.services import meeting_scheduler

JOB_MAX_ATTEMPTS = 3
TYPE_WHATSAPP_FOLLOWUP_TICK = "whatsapp.followup.tick"
TYPE_WHATSAPP_FOLLOWUP_PREGENERATE = "whatsapp.followup.pregenerate"
TYPE_WHATSAPP_APPOINTMENT_REMINDER = "whatsapp.appointment.reminder"


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


def _parse_followup_contract(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _inject_followup_contract_context(context: Dict[str, Any], job: Dict[str, Any]) -> None:
    if not _is_followup_tick_job(job):
        return

    lead = context.get("lead") or {}
    metadata = context.get("metadata") or {}
    contract = _parse_followup_contract(lead.get("followup_contract"))
    if not contract:
        context["metadata"] = metadata
        return

    followup_signals = {
        "followup_goal": contract.get("followup_goal"),
        "followup_outcome": contract.get("outcome"),
        "followup_variant": contract.get("followup_variant"),
        "followup_attempts": contract.get("attempts"),
        "followup_max_attempts": contract.get("max_attempts"),
        "followup_meeting_happened": contract.get("meeting_happened"),
        "followup_meeting_or_session_happened": contract.get("meeting_or_session_happened"),
        "followup_proposal_sent": contract.get("proposal_sent"),
        "followup_operator_note": contract.get("operator_note"),
        "followup_status": contract.get("status"),
        "followup_next_followup_at": contract.get("next_followup_at"),
    }

    # entrada sintética para orientar geração proativa quando não há inbound real
    if not metadata.get("inbound_message_text"):
        metadata["inbound_message_text"] = "followup_tick_auto_trigger"

    metadata["followup_context"] = followup_signals
    context["metadata"] = metadata


def _is_followup_tick_job(job: Dict[str, Any]) -> bool:
    return str(job.get("type") or "").strip().lower() == TYPE_WHATSAPP_FOLLOWUP_TICK


def _is_pregenerate_job(job: Dict[str, Any]) -> bool:
    return str(job.get("type") or "").strip().lower() == TYPE_WHATSAPP_FOLLOWUP_PREGENERATE


def _is_appointment_reminder_job(job: Dict[str, Any]) -> bool:
    return str(job.get("type") or "").strip().lower() == TYPE_WHATSAPP_APPOINTMENT_REMINDER


def _resolve_in_reply_to_message_id(*, job_id: str, job: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
    explicit = metadata.get("message_id")
    if explicit:
        return str(explicit)

    if _is_followup_tick_job(job):
        payload = job.get("payload") or {}
        due_at = str(payload.get("due_at") or "na").replace(" ", "T")
        return f"followup:{job_id}:{due_at}"

    return None


def _build_followup_fallback_outbound_body(context: Dict[str, Any]) -> str:
    lead = context.get("lead") or {}
    contact_name = str(lead.get("contactName") or "").strip()
    greeting = f"Olá, {contact_name}." if contact_name else "Olá!"
    return (
        f"{greeting} Passando para dar continuidade ao seu follow-up. "
        "Se fizer sentido, posso te ajudar com os próximos passos por aqui."
    )


def _build_outbound_body(decision: decision_engine.DecisionOutput) -> Optional[str]:
    if decision.next_action in {"reply", "ask_qualification"}:
        return decision.message_text or ""
    if decision.next_action == "handoff":
        return decision.message_text or ""
    return None


_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_LINK_PLACEHOLDER_RE = re.compile(r"\[[^\]]*link[^\]]*\]", re.IGNORECASE)


def _extract_checkout_link_from_offer_pack(context: Dict[str, Any]) -> tuple[Optional[str], str]:
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    source = "none"
    offer_pack = ai_profile.get("offer_pack")
    if isinstance(offer_pack, str):
        try:
            parsed = json.loads(offer_pack)
            offer_pack = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            offer_pack = None
    if not isinstance(offer_pack, dict):
        source = "playbook"
        offer_pack = playbook.get("offer_pack") if isinstance(playbook.get("offer_pack"), dict) else None
    else:
        source = "ai_profile"
    if not isinstance(offer_pack, dict):
        return None, "none"
    items = offer_pack.get("items") if isinstance(offer_pack.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        link = str(item.get("checkout_link") or "").strip()
        if link:
            return link, source
    return None, source


def _enforce_checkout_link_guardrail(
    *,
    decision: decision_engine.DecisionOutput,
    context: Dict[str, Any],
) -> None:
    if not isinstance(decision.decision_trace, dict):
        decision.decision_trace = {}
    trace = decision.decision_trace
    template_key = str(((context.get("ai_profile") or {}).get("template_key") or "")).strip().lower()
    if template_key == "hybrid_scheduler":
        trace["checkout_link_present"] = False
        trace["checkout_link_source"] = "disabled_for_hybrid_scheduler"
        trace["checkout_guardrail_applied"] = False
        trace["checkout_guardrail_reason"] = "hybrid_scheduler_no_checkout"
        return

    checkout_link, checkout_link_source = _extract_checkout_link_from_offer_pack(context)
    trace["checkout_link_present"] = bool(checkout_link)
    trace["checkout_link_source"] = checkout_link_source
    trace["checkout_guardrail_applied"] = False

    if not checkout_link:
        return

    presentation_variant = str(
        trace.get("presentation_variant")
        or (context.get("metadata") or {}).get("presentation_variant")
        or ""
    ).strip().lower()
    suggested_category = str(decision.suggested_category or "").strip().lower()
    outcome = str(decision.outcome or "").strip().lower()
    child_structured = trace.get("child_signals_structured") if isinstance(trace.get("child_signals_structured"), dict) else {}
    checkout_sent = child_structured.get("checkout_sent") is True

    message_text = str(decision.message_text or "")
    has_placeholder_link = bool(_LINK_PLACEHOLDER_RE.search(message_text))
    has_any_url = bool(_URL_RE.search(message_text))
    is_closing_context = suggested_category == "closing"
    is_won_context = outcome == "won"

    if not (checkout_sent or is_closing_context or is_won_context):
        trace["checkout_guardrail_reason"] = "not_checkout_sent_or_closing_or_won"
        return
    if checkout_link in message_text:
        trace["checkout_guardrail_reason"] = "already_contains_real_checkout_link"
        return

    if has_any_url and not has_placeholder_link:
        trace["checkout_guardrail_reason"] = "already_has_url"
        return

    if has_placeholder_link:
        decision.message_text = _LINK_PLACEHOLDER_RE.sub(checkout_link, message_text)
        trace["checkout_guardrail_applied"] = True
        trace["checkout_guardrail_reason"] = "replaced_placeholder"
        return

    if has_any_url:
        trace["checkout_guardrail_reason"] = "already_has_url"
        return

    separator = "\n\n" if message_text.strip() else ""
    decision.message_text = f"{message_text}{separator}{checkout_link}"
    trace["checkout_guardrail_applied"] = True
    trace["checkout_guardrail_reason"] = "appended_missing_link"


def _enforce_checkout_link_guardrail_legacy(
    *,
    decision: decision_engine.DecisionOutput,
    context: Dict[str, Any],
) -> None:
    """Compat shim: preserve old behavior when checkout_sent=true even sem intenção textual."""
    template_key = str(((context.get("ai_profile") or {}).get("template_key") or "")).strip().lower()
    if template_key == "hybrid_scheduler":
        return
    trace = decision.decision_trace if isinstance(decision.decision_trace, dict) else {}
    child_structured = trace.get("child_signals_structured") if isinstance(trace.get("child_signals_structured"), dict) else None
    if not isinstance(child_structured, dict):
        return
    if child_structured.get("checkout_sent") is not True:
        return

    checkout_link, _ = _extract_checkout_link_from_offer_pack(context)
    if not checkout_link:
        return

    message_text = str(decision.message_text or "")
    if checkout_link in message_text:
        return
    if _URL_RE.search(message_text):
        return

    separator = "\n\n" if message_text.strip() else ""
    decision.message_text = f"{message_text}{separator}{checkout_link}"


def _split_message_by_punctuation(text: str, min_chars: int = 15) -> list[str]:
    """Divide texto em partes por marcadores de sentença (. ! ? …).

    Parágrafos duplos (\\n\\n) sempre criam quebra independente de tamanho.
    Frases curtas (< min_chars) são fundidas com a próxima para evitar bolhas triviais.
    Retorna lista com 1+ strings; o caller envia a primeira rastreada e as demais com delay.
    """
    import re as _re

    if not text or not text.strip():
        return []
    normalized = text.strip().replace("...", "…")
    paras = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    if len(paras) > 1:
        return paras
    raw = _re.split(r"(?<=[.!?…])\s+", normalized)
    parts: list[str] = []
    buffer = ""
    for i, frag in enumerate(raw):
        candidate = (buffer + " " + frag).strip() if buffer else frag.strip()
        if len(candidate) < min_chars and i < len(raw) - 1:
            buffer = candidate
        else:
            parts.append(candidate)
            buffer = ""
    if buffer:
        parts.append(buffer)
    return [p for p in parts if p] or [text]


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
        "decision_trace": decision.decision_trace,
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


def _execute_appointment_reminder_pipeline(
    job_id: str,
    job: Dict[str, Any],
    context: Dict[str, Any],
    ctx_logger: logging.Logger,
    attempt: Optional[int],
) -> int:
    """Envia lembrete de appointment via WhatsApp usando template fixo, sem LLM."""
    try:
        lead = context.get("lead") or {}
        metadata = context.get("metadata") or {}
        payload = job.get("payload") or {}

        lead_id = lead.get("id") or payload.get("lead_id")
        user_id = lead.get("user_id") or payload.get("user_id")
        phone = metadata.get("phone") or lead.get("phone") or payload.get("phone")
        instance_id = metadata.get("instance_id") or payload.get("instance_id")
        provider = metadata.get("provider") or payload.get("provider") or "uazapi"
        appointment_id = payload.get("appointment_id")
        title = payload.get("appointment_title") or "reunião"
        start_at_iso = payload.get("appointment_start_at") or ""

        if not phone:
            exec_error = ExecutionError(
                "phone ausente no contexto do lembrete",
                phase="context",
                service="executor",
                retryable=False,
            )
            return _fail_job(job_id, ctx_logger, exec_error, attempt)

        lead_name = str(lead.get("contactName") or lead.get("name") or "").strip()
        greeting = f"Olá{', ' + lead_name if lead_name else ''}!"

        try:
            from datetime import datetime as _dt
            start_dt = _dt.fromisoformat(start_at_iso)
            time_str = start_dt.strftime("%d/%m às %H:%M")
        except Exception:
            time_str = "em breve"

        reminder_text = (
            f"{greeting} Lembrando da sua {title} agendada para {time_str}. "
            "Qualquer dúvida, estou por aqui. Até lá! 😊"
        )

        in_reply_to_message_id = f"reminder:{job_id}:{appointment_id}"
        outbound_payload: Dict[str, Any] = {
            "job_id": int(job_id),
            "lead_id": lead_id,
            "user_id": user_id,
            "phone": phone,
            "body": reminder_text,
            "provider": provider,
            "in_reply_to_message_id": in_reply_to_message_id,
        }
        if instance_id:
            outbound_payload["instance_id"] = instance_id

        ctx_logger.info(
            "event=appointment_reminder_send lead_id=%s appointment_id=%s",
            lead_id,
            appointment_id,
            extra={"phase": "reminder"},
        )
        crm_client.register_whatsapp_outbound(outbound_payload)
        crm_client.complete_job(job_id, {"status": "sent", "lead_id": lead_id, "appointment_id": appointment_id})
        ctx_logger.info("event=appointment_reminder_done lead_id=%s", lead_id, extra={"phase": "reminder"})
        return 0
    except Exception as exc:
        ctx_logger.exception("event=appointment_reminder_error error=%s", exc, extra={"phase": "reminder"})
        exec_error = ExecutionError(str(exc), phase="reminder", service="executor", retryable=True)
        return _fail_job(job_id, ctx_logger, exec_error, attempt)


def _execute_pregenerate_pipeline(
    job_id: str,
    job: Dict[str, Any],
    context: Dict[str, Any],
    ctx_logger: logging.Logger,
    attempt: Optional[int],
) -> int:
    """Roda pipeline LLM para pré-gerar mensagem de follow-up sem enviar."""
    try:
        decision = decision_engine.decide(context, logger=ctx_logger)
        _enforce_checkout_link_guardrail(decision=decision, context=context)
        _enforce_checkout_link_guardrail_legacy(decision=decision, context=context)

        message_text = decision.message_text or _build_followup_fallback_outbound_body(context)
        if not message_text:
            crm_client.complete_job(job_id, {"status": "skipped", "reason": "empty_message"})
            ctx_logger.info("event=pregenerate_skipped reason=empty_message", extra={"phase": "pregenerate"})
            return 0

        payload = job.get("payload") or {}
        lead_id = payload.get("lead_id")
        user_id = payload.get("user_id")

        crm_client.save_pregenerated_message(lead_id=lead_id, user_id=user_id, content=message_text)
        crm_client.complete_job(job_id, {"status": "pregenerated", "lead_id": lead_id})
        ctx_logger.info(
            "event=pregenerate_done lead_id=%s chars=%s",
            lead_id,
            len(message_text),
            extra={"phase": "pregenerate"},
        )
        return 0
    except Exception as exc:
        ctx_logger.exception("event=pregenerate_error error=%s", exc, extra={"phase": "pregenerate"})
        exec_error = ExecutionError(str(exc), phase="pregenerate", service="executor", retryable=True)
        return _fail_job(job_id, ctx_logger, exec_error, attempt)


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

    _inject_followup_contract_context(context, job)
    metadata = context.get("metadata") or {}

    if _is_pregenerate_job(job):
        return _execute_pregenerate_pipeline(job_id, job, context, ctx_logger, attempt)

    if _is_appointment_reminder_job(job):
        return _execute_appointment_reminder_pipeline(job_id, job, context, ctx_logger, attempt)

    lead_id = _safe_get(lead, "id")
    lead_name = _safe_get(lead, "contactName", "companyName", "name")
    lead_phone = _safe_get(lead, "phone", "phone_e164")
    user_id = _resolve_user_id(context, job)
    in_reply_to_message_id = _resolve_in_reply_to_message_id(job_id=job_id, job=job, metadata=metadata)
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
    followup_ctx = metadata.get("followup_context") if isinstance(metadata.get("followup_context"), dict) else {}
    ctx_logger.info(
        "event=metadata_loaded provider=%s instance_id=%s message_id=%s received_at=%s phone=%s followup_variant=%s followup_goal=%s followup_meeting_or_session=%s",
        metadata.get("provider"),
        metadata.get("instance_id"),
        metadata.get("message_id"),
        metadata.get("received_at"),
        metadata.get("phone"),
        followup_ctx.get("followup_variant"),
        followup_ctx.get("followup_goal"),
        followup_ctx.get("followup_meeting_or_session_happened"),
        extra={"phase": "context"},
    )

    decision = decision_engine.decide(context, logger=ctx_logger)
    ctx_logger.info(
        "event=decision_made next_action=%s reason=%s",
        decision.next_action,
        decision.reason,
        extra={"phase": "decision"},
    )
    meeting_scheduler.handle_meeting_scheduled(context, decision, logger=ctx_logger)
    _enforce_checkout_link_guardrail(decision=decision, context=context)
    _enforce_checkout_link_guardrail_legacy(decision=decision, context=context)
    outbound_body = _build_outbound_body(decision)
    if decision.next_action == "ask_qualification" and not outbound_body:
        fallback_text = _format_questions(decision.questions or [])
        if fallback_text:
            outbound_body = fallback_text
    if _is_followup_tick_job(job):
        contract = _parse_followup_contract((context.get("lead") or {}).get("followup_contract"))
        saved_content = (contract.get("scheduled_message") or {}).get("content")
        if saved_content:
            outbound_body = saved_content
        elif not outbound_body:
            outbound_body = _build_followup_fallback_outbound_body(context)

    # Dividir mensagem em partes por pontuação (comportamento multi-mensagem humanizado).
    # A primeira parte é rastreada normalmente; as demais são enviadas com delay progressivo.
    _body_parts = _split_message_by_punctuation(outbound_body or "") if outbound_body else []
    if len(_body_parts) > 1:
        outbound_body = _body_parts[0]
        _extra_body_parts: list[str] = _body_parts[1:]
    else:
        _extra_body_parts = []

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
        _delay_ms = min(max(len(outbound_body) * 40, 1000), 8000)
        try:
            core_response = core_client.send_whatsapp_message(
                {
                    "provider": provider,
                    "instance_id": instance_id,
                    "number": phone,
                    "text": outbound_body,
                    "delay_ms": _delay_ms,
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

        # Mídia rica — envia cada mídia APÓS o texto em sequência (texto aparece primeiro no chat).
        # Falha de mídia individual não aborta o job; é fire-and-forget sem tracking de outbound_event.
        if decision.pre_send_media:
            _media_list = decision.pre_send_media
            if isinstance(_media_list, dict):
                _media_list = [_media_list]
            for _media_item in _media_list:
                _media_url = _media_item.get("media_url")
                _media_type = _media_item.get("media_type", "image")
                if not _media_url:
                    continue
                ctx_logger.info(
                    "event=post_send_media_request media_type=%s order=%s",
                    _media_type,
                    _media_item.get("send_order", 0),
                    extra={"phase": "core_send"},
                )
                try:
                    core_client.send_whatsapp_media(
                        {
                            "provider": provider,
                            "instance_id": instance_id,
                            "number": phone,
                            "media_url": _media_url,
                            "media_type": _media_type,
                        }
                    )
                    ctx_logger.info("event=post_send_media_success media_type=%s", _media_type, extra={"phase": "core_send"})
                except core_client.CoreClientError as media_exc:
                    ctx_logger.warning(
                        "event=post_send_media_error error=%s — continuando",
                        media_exc,
                        extra={"phase": "core_send"},
                    )

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

        # Partes extras por pontuação — enviadas com delay progressivo após o texto principal.
        for _extra_part in _extra_body_parts:
            try:
                _extra_delay_ms = min(max(len(_extra_part) * 40, 1000), 8000)
                import time as _time
                _time.sleep(_extra_delay_ms / 1000)
                core_client.send_whatsapp_message(
                    {
                        "provider": provider,
                        "instance_id": instance_id,
                        "number": phone,
                        "text": _extra_part,
                        "delay_ms": _extra_delay_ms,
                    }
                )
            except core_client.CoreClientError as _extra_exc:
                ctx_logger.warning(
                    "event=extra_body_part_error error=%s — continuando",
                    _extra_exc,
                    extra={"phase": "core_send"},
                )

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
