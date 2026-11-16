import os

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "executors",
        "env": settings.env,
        "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA") or None,
    }
