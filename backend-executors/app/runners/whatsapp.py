import argparse
import logging
import sys

from app.core.config import settings
from app.core.logging import log_ctx, setup_logging


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
    ctx_logger.info("stub runner ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
