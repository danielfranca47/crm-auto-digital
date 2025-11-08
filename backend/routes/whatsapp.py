# backend/routes/whatsapp.py
from fastapi import APIRouter

from automations.whatsapp.qr_manager import qr_manager
from services import jobs_service

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])

# ---------- ENDPOINTS: QR / LOGIN ----------
@router.post("/iniciar-qr")
def iniciar_qr():
    # Abre (ou reutiliza) o Chrome, vai para web.whatsapp.com e retorna QR (se necessário)
    return qr_manager.iniciar_e_capturar_qr()

@router.get("/verificar-login")
def verificar_login(passive: bool = False):
    # Garante navegar até web.whatsapp.com e só então checa DOM (#side vs [data-ref]) passiva
    return qr_manager.verificar_login(passive=passive)

@router.get("/novo-qr")
def novo_qr():
    return qr_manager.novo_qr()

@router.post("/stop")
def stop():
    # Encerra apenas a sessão do Chrome (driver). Não mexe no worker.
    return qr_manager.stop()

# ---------- ENDPOINTS: WORKER ----------
@router.post("/worker/start")
def worker_start():
    """Mantido para compatibilidade — o processamento agora ocorre via Agente Local."""
    overview = jobs_service.overview()
    return {
        "ok": False,
        "running": overview["jobs"]["in_progress"] > 0,
        "message": "Worker remoto desativado. Inicie o Agente Local para processar a fila.",
    }


@router.post("/worker/stop")
def worker_stop():
    overview = jobs_service.overview()
    return {
        "ok": False,
        "running": overview["jobs"]["in_progress"] > 0,
        "message": "Worker remoto desativado. Finalize o Agente Local localmente se necessário.",
    }


@router.get("/worker/state")
def worker_state():
    overview = jobs_service.overview()
    jobs = overview["jobs"]
    return {
        "running": jobs["in_progress"] > 0,
        "processed_ok": jobs["completed_recent"],
        "processed_fail": jobs["failed_recent"],
        "last_error": None,
        "last_item": None,
        "message": "Worker remoto substituído pelo Agente Local",
    }


# Alias opcional para compatibilidade com o front atual
@router.get("/worker/status")
def worker_status():
    jobs = jobs_service.overview()["jobs"]
    return {
        "running": jobs["in_progress"] > 0,
        "message": "Worker remoto desativado; utilize o Agente Local",
    }
