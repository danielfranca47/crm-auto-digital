# backend/routes/whatsapp_worker.py
"""Endpoints legados do worker remoto (agora desativados)."""

from fastapi import APIRouter

from services import jobs_service

router = APIRouter(prefix="/api/whatsapp/worker", tags=["WhatsApp Worker"])


@router.post("/start")
def start_worker():
    jobs = jobs_service.overview()["jobs"]
    return {
        "ok": False,
        "started": False,
        "running": jobs["in_progress"] > 0,
        "message": "Worker remoto desativado. Utilize o Agente Local.",
    }


@router.post("/stop")
def stop_worker():
    jobs = jobs_service.overview()["jobs"]
    return {
        "ok": False,
        "stopped": True,
        "running": jobs["in_progress"] > 0,
        "message": "Worker remoto desativado. Controle feito pelo Agente Local.",
    }


@router.get("/status")
def status_worker():
    jobs = jobs_service.overview()["jobs"]
    return {
        "running": jobs["in_progress"] > 0,
        "processed_ok": jobs["completed_recent"],
        "processed_fail": jobs["failed_recent"],
        "last_error": None,
        "last_item": None,
        "message": "Worker remoto substituído pelo Agente Local",
    }
