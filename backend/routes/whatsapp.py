# backend/routes/whatsapp.py
from fastapi import APIRouter
from typing import Optional
import threading, time, urllib.parse

from database import get_connection
from automations.whatsapp.qr_manager import qr_manager
from automations.whatsapp.whatsapp_worker import worker  # usa o singleton real do worker

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
    started = worker.start()  # False se já estava rodando
    return {
        "ok": True,
        "started": bool(started),
        "running": worker.is_running(),
    }

@router.post("/worker/stop")
def worker_stop():
    worker.stop()
    return {
        "ok": True,
        "running": worker.is_running(),
    }

@router.get("/worker/state")
def worker_state():
    s = worker.state
    return {
        "running": worker.is_running(),
        "last_error": s.last_error,
        "processed_ok": s.processed_ok,
        "processed_fail": s.processed_fail,
        "last_item": s.last_item,
    }

# Alias opcional para compatibilidade com o front atual
@router.get("/worker/status")
def worker_status():
    return {"running": worker.is_running()}
