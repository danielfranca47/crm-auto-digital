# backend/routes/whatsapp_worker.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/whatsapp/worker", tags=["WhatsApp Worker"])

@router.post("/start")
def start_worker():
    return {
        "ok": False,
        "started": False,
        "message": "Worker desativado. Utilize o Agente Local para processar os envios.",
    }

@router.post("/stop")
def stop_worker():
    return {
        "ok": False,
        "stopped": False,
        "message": "Worker desativado. Utilize o Agente Local para processar os envios.",
    }

@router.get("/status")
def status_worker():
    return {
        "running": False,
        "processed_ok": 0,
        "processed_fail": 0,
        "last_error": None,
        "last_item": None,
        "message": "Worker desativado. Utilize o Agente Local para processar os envios.",
    }
