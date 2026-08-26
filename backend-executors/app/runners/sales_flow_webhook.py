import argparse
import logging
import sys
from typing import Any, Dict, Optional

import httpx

from app.clients import crm_client
from app.core.config import settings
from app.core.logging import log_ctx, setup_logging

REQUEST_TIMEOUT_SECONDS = 10


def _is_retryable_status(status_code: Optional[int]) -> bool:
    if status_code is None:
        return True  # erro de rede/timeout sem status — trata como transitório
    if status_code == 429:
        return True
    return 500 <= status_code <= 599


def _call_webhook(*, method: str, url: str, payload: Dict[str, Any]) -> httpx.Response:
    if method == "GET":
        params = {k: v for k, v in payload.items() if v is not None and not isinstance(v, (dict, list))}
        return httpx.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    return httpx.request(method, url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)


def _fail(
    job_id: str,
    logger: logging.LoggerAdapter,
    error: str,
    *,
    retryable: bool,
) -> int:
    logger.error(
        "event=sales_flow_webhook_error error=%s retryable=%s",
        error,
        retryable,
        extra={"phase": "send"},
    )
    try:
        crm_client.fail_job(job_id, error=error, details={"retryable": retryable})
    except crm_client.CRMClientError as exc:
        logger.error("event=job_fail_report_error error=%s", exc, extra={"phase": "fail"})
    return 1


def execute_job(job_id: str, logger: logging.Logger) -> int:
    ctx_logger = log_ctx(logger, job_id=job_id)
    lease_owner = "executors:sales_flow_webhook"
    attempt = None

    try:
        claim_response = crm_client.claim_job(job_id, lease_owner=lease_owner, ttl_seconds=60)
        normalized = claim_response.get("normalized") if isinstance(claim_response, dict) else None
        if isinstance(normalized, dict):
            attempt = normalized.get("attempts")
        ctx_logger = log_ctx(logger, job_id=job_id, attempt=attempt)
        ctx_logger.info("event=job_claimed", extra={"phase": "claim"})
    except crm_client.CRMClientConflictError as exc:
        ctx_logger.error("event=job_claim_conflict error=%s", exc, extra={"phase": "claim"})
        return 1
    except crm_client.CRMClientError as exc:
        ctx_logger.error("event=job_claim_error error=%s", exc, extra={"phase": "claim"})
        return 1

    try:
        job = crm_client.get_job(job_id)
    except crm_client.CRMClientError as exc:
        return _fail(job_id, ctx_logger, f"erro ao buscar job: {exc}", retryable=True)

    payload: Dict[str, Any] = job.get("payload") or {}
    user_id = job.get("user_id")
    lead_id = payload.get("lead_id")
    url = payload.get("url")
    method = (payload.get("method") or "POST").strip().upper()

    ctx_logger = log_ctx(logger, job_id=job_id, lead_id=lead_id, user_id=user_id, attempt=attempt)

    if not url:
        return _fail(job_id, ctx_logger, "payload incompleto (url ausente)", retryable=False)

    ctx_logger.info("event=sales_flow_webhook_dispatch method=%s url=%s", method, url, extra={"phase": "send"})

    try:
        response = _call_webhook(method=method, url=url, payload=payload)
    except httpx.TimeoutException as exc:
        return _fail(job_id, ctx_logger, f"timeout ao chamar webhook: {exc}", retryable=True)
    except httpx.HTTPError as exc:
        return _fail(job_id, ctx_logger, f"erro de rede ao chamar webhook: {exc}", retryable=True)

    if response.status_code >= 400:
        return _fail(
            job_id,
            ctx_logger,
            f"webhook respondeu status {response.status_code}",
            retryable=_is_retryable_status(response.status_code),
        )

    try:
        crm_client.complete_job(
            job_id,
            result={"status": "sent", "lead_id": lead_id, "status_code": response.status_code},
        )
    except crm_client.CRMClientError as exc:
        ctx_logger.error("event=job_complete_report_error error=%s", exc, extra={"phase": "complete"})
        return 1

    ctx_logger.info(
        "event=sales_flow_webhook_sent lead_id=%s status_code=%s",
        lead_id,
        response.status_code,
        extra={"phase": "send"},
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sales flow webhook dispatch executor runner")
    parser.add_argument("--job-id", dest="job_id", help="Job ID to execute")
    args = parser.parse_args()

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    if not args.job_id:
        logger.error("Missing --job-id. Example: python -m app.runners.sales_flow_webhook --job-id 123")
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
