import logging
from typing import Any, Dict, Optional


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field in (
            "job_id",
            "lead_id",
            "user_id",
            "instance_id",
            "provider",
            "attempt",
            "phase",
        ):
            if not hasattr(record, field):
                setattr(record, field, "-")
        return True


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "job_id=%(job_id)s lead_id=%(lead_id)s user_id=%(user_id)s "
            "instance_id=%(instance_id)s provider=%(provider)s "
            "attempt=%(attempt)s phase=%(phase)s %(message)s"
        )
    )
    handler.addFilter(ContextFilter())
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
