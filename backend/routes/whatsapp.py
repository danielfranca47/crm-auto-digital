# backend/routes/whatsapp.py
from fastapi import APIRouter
from typing import Optional
import threading, time, urllib.parse

from database import get_connection
from automations.whatsapp.qr_manager import qr_manager

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
    return {
        "ok": False,
        "running": False,
        "message": "Worker desativado. Utilize o Agente Local para processar os envios.",
    }

@router.post("/worker/stop")
def worker_stop():
    return {
        "ok": False,
        "running": False,
        "message": "Worker desativado. Utilize o Agente Local para processar os envios.",
    }

@router.get("/worker/state")
def worker_state():
    return {
        "running": False,
        "last_error": None,
        "processed_ok": 0,
        "processed_fail": 0,
        "last_item": None,
        "message": "Worker desativado. Utilize o Agente Local para processar os envios.",
    }

# Alias opcional para compatibilidade com o front atual
@router.get("/worker/status")
def worker_status():
    return {"running": False, "message": "Worker desativado. Utilize o Agente Local."}
