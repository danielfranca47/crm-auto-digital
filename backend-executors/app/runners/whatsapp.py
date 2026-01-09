import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

from app.clients import crm_client
from app.core.config import settings
from app.core.logging import log_ctx, setup_logging
from app.services import decision_engine


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


def main() -> int:
    parser = argparse.ArgumentParser(description="WhatsApp executor runner (stub)")
    parser.add_argument("--job-id", dest="job_id", help="Job ID to execute")
    args = parser.parse_args()

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    if not args.job_id:
        logger.error("Missing --job-id. Example: python -m app.runners.whatsapp --job-id 123")
        return 2

    ctx_logger = log_ctx(logger, job_id=args.job_id)
    lease_owner = "executors:local"

    try:
        crm_client.claim_job(args.job_id, lease_owner=lease_owner, ttl_seconds=300)
    except crm_client.CRMClientConflictError as exc:
        ctx_logger.error("job already locked: %s", exc)
        return 1
    except crm_client.CRMClientError as exc:
        ctx_logger.error(str(exc))
        return 1

    try:
        job = crm_client.get_job(args.job_id)
        context = crm_client.get_whatsapp_execution_context(args.job_id)

        lead = context.get("lead") or {}
        history = context.get("history") or []
        ai_profile = context.get("ai_profile") or {}
        playbook = context.get("playbook") or {}
        metadata = context.get("metadata") or {}

        lead_id = _safe_get(lead, "id")
        lead_name = _safe_get(lead, "contactName", "companyName", "name")
        lead_phone = _safe_get(lead, "phone", "phone_e164")

        ctx_logger.info("job loaded type=%s status=%s", job.get("type"), job.get("status"))
        ctx_logger.info("lead id=%s name=%s phone=%s", lead_id, lead_name, lead_phone)
        ctx_logger.info("history total=%s last=%s", len(history), _format_history(history))
        ctx_logger.info(
            "ai_profile id=%s name=%s template_key=%s",
            _safe_get(ai_profile, "id"),
            _safe_get(ai_profile, "name"),
            _safe_get(ai_profile, "template_key"),
        )
        ctx_logger.info(
            "playbook template_key=%s",
            _safe_get(playbook, "template_key", "name"),
        )
        ctx_logger.info(
            "metadata provider=%s instance_id=%s message_id=%s received_at=%s phone=%s",
            metadata.get("provider"),
            metadata.get("instance_id"),
            metadata.get("message_id"),
            metadata.get("received_at"),
            metadata.get("phone"),
        )
        decision = decision_engine.decide(context, logger=ctx_logger)
        ctx_logger.info(
            "decision recorded next_action=%s reason=%s",
            decision.next_action,
            decision.reason,
        )
        crm_client.complete_job(
            args.job_id,
            result={"context_fetched": True, "decision": decision.model_dump()},
        )
        return 0
    except Exception as exc:
        ctx_logger.error("whatsapp runner error: %s", exc)
        try:
            crm_client.fail_job(args.job_id, error=str(exc))
        except crm_client.CRMClientError:
            ctx_logger.error("failed to mark job as failed in CRM")
        return 1


if __name__ == "__main__":
    sys.exit(main())
