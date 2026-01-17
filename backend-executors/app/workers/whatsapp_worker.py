import logging
import os
import time
from typing import Optional

from app.clients import crm_client
from app.core.config import settings
from app.core.logging import log_ctx, setup_logging
from app.runners.whatsapp import execute_job


POLL_BACKOFF_SECONDS = [1, 2, 5, 10, 30]
SHORT_SLEEP_SECONDS = 0.5


def _parse_types() -> list[str]:
    raw = os.getenv("WHATSAPP_WORKER_TYPES", "whatsapp.inbound.n8n")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_optional_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def main() -> int:
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    types = _parse_types()
    max_jobs = _parse_optional_int("WHATSAPP_WORKER_MAX_JOBS")
    max_runtime_seconds = _parse_optional_int("WHATSAPP_WORKER_MAX_RUNTIME_SECONDS")
    started_at = time.time()
    completed_jobs = 0
    backoff_index = 0

    logger.info(
        "event=worker_started types=%s max_jobs=%s max_runtime_seconds=%s",
        types,
        max_jobs,
        max_runtime_seconds,
        extra={"phase": "worker"},
    )

    while True:
        if max_runtime_seconds and (time.time() - started_at) >= max_runtime_seconds:
            logger.info("event=worker_stopped reason=max_runtime", extra={"phase": "worker"})
            return 0
        if max_jobs and completed_jobs >= max_jobs:
            logger.info("event=worker_stopped reason=max_jobs", extra={"phase": "worker"})
            return 0

        try:
            job = crm_client.get_next_job(types, limit=1)
        except crm_client.CRMClientError as exc:
            logger.error(
                "event=job_poll_error error=%s",
                exc,
                extra={"phase": "poll"},
            )
            sleep_seconds = POLL_BACKOFF_SECONDS[min(backoff_index, len(POLL_BACKOFF_SECONDS) - 1)]
            backoff_index = min(backoff_index + 1, len(POLL_BACKOFF_SECONDS) - 1)
            time.sleep(sleep_seconds)
            continue

        if not job:
            sleep_seconds = POLL_BACKOFF_SECONDS[min(backoff_index, len(POLL_BACKOFF_SECONDS) - 1)]
            logger.info(
                "event=no_job_available sleep=%ss",
                sleep_seconds,
                extra={"phase": "poll"},
            )
            backoff_index = min(backoff_index + 1, len(POLL_BACKOFF_SECONDS) - 1)
            time.sleep(sleep_seconds)
            continue

        backoff_index = 0
        payload = job.get("payload") or {}
        ctx_logger = log_ctx(
            logger,
            job_id=str(job.get("id")),
            lead_id=payload.get("lead_id"),
            user_id=payload.get("user_id"),
            instance_id=payload.get("instance_id"),
            provider=payload.get("provider"),
            attempt=job.get("attempts"),
        )
        ctx_logger.info("event=job_found", extra={"phase": "poll"})

        execute_job(str(job.get("id")), logger)
        completed_jobs += 1
        time.sleep(SHORT_SLEEP_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
