from fastapi import FastAPI

from app.api import health
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings.log_level)

app = FastAPI(title="Executors API", version="0.1.0")

app.include_router(health.router)
