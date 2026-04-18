from fastapi import FastAPI

from app.api import health, meta_prompter, playground_internal
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings.log_level)

app = FastAPI(title="Executors API", version="0.1.0")

app.include_router(health.router)
app.include_router(meta_prompter.router)
app.include_router(playground_internal.router)
