import argparse
import logging
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from app.clients import core_client, crm_client
from app.core.config import settings
from app.core.logging import log_ctx, setup_logging

JOB_MAX_ATTEMPTS = 3


def _is_retryable_status(status_code: Optional[int]) -> bool:
    if status_code is None:
        return False
    if status_code == 429:
        return True
    return 500 <= status_code <= 599


def _send_email(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    from_name: Optional[str],
    to_email: str,
    subject: Optional[str],
    body: str,
) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{username}>" if from_name else username
    msg["To"] = to_email
    msg["Subject"] = subject or "(sem assunto)"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        server.starttls()
    try:
        server.login(username, password)
        server.sendmail(username, [to_email], msg.as_string())
    finally:
        server.quit()


def _fail(
    job_id: str,
    logger: logging.LoggerAdapter,
    error: str,
    *,
    retryable: bool,
) -> int:
    logger.error(
        "event=email_send_error error=%s retryable=%s",
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
    lease_owner = "executors:email"
    attempt = None

    try:
        claim_response = crm_client.claim_job(job_id, lease_owner=lease_owner, ttl_seconds=120)
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
    to_email = payload.get("email")
    subject = payload.get("subject")
    body = payload.get("body")

    ctx_logger = log_ctx(logger, job_id=job_id, lead_id=lead_id, user_id=user_id, attempt=attempt)

    if not user_id or not to_email or not body:
        return _fail(
            job_id,
            ctx_logger,
            "payload incompleto (user_id/email/body ausente)",
            retryable=False,
        )

    try:
        creds = core_client.get_smtp_credentials(int(user_id))
    except core_client.CoreClientError as exc:
        if exc.status_code == 404:
            return _fail(job_id, ctx_logger, "usuário sem conta de email SMTP conectada", retryable=False)
        return _fail(
            job_id,
            ctx_logger,
            f"erro ao buscar credencial SMTP: {exc}",
            retryable=_is_retryable_status(exc.status_code),
        )

    ctx_logger.info("event=smtp_credentials_loaded host=%s", creds.get("host"), extra={"phase": "send"})

    try:
        _send_email(
            host=creds["host"],
            port=int(creds["port"]),
            username=creds["username"],
            password=creds["password"],
            from_name=creds.get("from_name"),
            to_email=to_email,
            subject=subject,
            body=body,
        )
    except smtplib.SMTPAuthenticationError as exc:
        return _fail(job_id, ctx_logger, f"autenticação SMTP recusada: {exc}", retryable=False)
    except (smtplib.SMTPException, OSError) as exc:
        return _fail(job_id, ctx_logger, f"erro ao enviar via SMTP: {exc}", retryable=True)

    try:
        crm_client.complete_job(job_id, result={"status": "sent", "lead_id": lead_id, "email": to_email})
    except crm_client.CRMClientError as exc:
        ctx_logger.error("event=job_complete_report_error error=%s", exc, extra={"phase": "complete"})
        return 1

    ctx_logger.info("event=email_sent lead_id=%s", lead_id, extra={"phase": "send"})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Email cold outreach executor runner")
    parser.add_argument("--job-id", dest="job_id", help="Job ID to execute")
    args = parser.parse_args()

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    if not args.job_id:
        logger.error("Missing --job-id. Example: python -m app.runners.email --job-id 123")
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
