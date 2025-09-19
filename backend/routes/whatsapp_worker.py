# backend/routes/whatsapp_worker.py
from fastapi import APIRouter
from automations.whatsapp.whatsapp_worker import worker

router = APIRouter(prefix="/api/whatsapp/worker", tags=["WhatsApp Worker"])

@router.post("/start")
def start_worker():
    started = worker.start()
    return {"ok": True, "started": started}

@router.post("/stop")
def stop_worker():
    worker.stop()
    return {"ok": True, "stopped": True}

@router.get("/status")
def status_worker():
    st = worker.state
    return {
        "running": worker.is_running(),
        "processed_ok": st.processed_ok,
        "processed_fail": st.processed_fail,
        "last_error": st.last_error,
        "last_item": st.last_item,
    }
