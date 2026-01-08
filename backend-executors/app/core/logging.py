import logging
from typing import Any, Dict, Optional


class JobIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_id"):
            record.job_id = "-"
        return True


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s job_id=%(job_id)s %(message)s"
        )
    )
    handler.addFilter(JobIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def log_ctx(
    logger: logging.Logger,
    job_id: Optional[str] = None,
    **fields: Any,
) -> logging.LoggerAdapter:
    context: Dict[str, Any] = {"job_id": job_id, **fields}
    return logging.LoggerAdapter(logger, context)
