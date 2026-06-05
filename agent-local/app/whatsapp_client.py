"""
Envia mensagem via WhatsApp Web (Selenium).

Mantém um runner singleton enquanto o app estiver aberto — o Chrome não é
fechado entre envios, poupando o tempo de arranque e permitindo reutilizar
a sessão do WhatsApp Web já autenticada.

Uso:
    from app.whatsapp_client import send_message, close_runner

    result = send_message(phone, msg, on_progress=callback)
    # no quit do app:
    close_runner()
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ---------- config mínima (sem credenciais de agente) -----------------------

class _WAConfig:
    user_data_dir: Path = Path.home() / ".agent-local" / "chrome-profile"
    chrome_binary: Optional[str] = os.getenv("CHROME_BINARY") or None
    headless: bool = False


# ---------- singleton --------------------------------------------------------

_runner = None  # WhatsAppRunner | None


def _get_runner():
    """Retorna (e cria se necessário) o runner singleton."""
    global _runner
    if _runner is None:
        from agent.whatsapp_runner import WhatsAppRunner
        _runner = WhatsAppRunner(_WAConfig())
        logger.info("WhatsAppRunner criado (singleton)")
    return _runner


def open_for_login() -> None:
    """
    Abre o Chrome e navega directamente para WhatsApp Web.
    Se o QR code aparecer, o utilizador faz o scan — o Chrome fica aberto
    (singleton) para ser reutilizado nos envios seguintes.
    """
    runner = _get_runner()
    driver = runner._ensure_driver()   # cria/recupera o Chrome
    # Navegar explicitamente — _ensure_whatsapp_tab só redirige se
    # ainda não houver janelas abertas; com janelas existentes fica na página actual.
    current = driver.current_url or ""
    if "web.whatsapp.com" not in current:
        driver.get("https://web.whatsapp.com")
    logger.info("WhatsApp Web aberto para login (url=%s)", driver.current_url)


def close_runner() -> None:
    """Fecha o Chrome e liberta o runner. Chamar no quit do app."""
    global _runner
    if _runner is not None:
        try:
            _runner.close()
            logger.info("WhatsAppRunner fechado")
        except Exception:
            pass
        _runner = None


# ---------- API pública ------------------------------------------------------

def send_message(
    phone: str,
    message: str,
    *,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """
    Envia mensagem via WhatsApp Web usando o runner singleton.

    Retorna {'status': 'sent'|'failed', 'reason': str}.

    O Chrome fica aberto após o envio para reutilização imediata.
    Se o WhatsApp Web precisar de QR scan, o runner aguarda até 120s.
    """
    def _emit(msg: str) -> None:
        logger.info(msg)
        if on_progress:
            on_progress(msg)

    try:
        runner = _get_runner()
        _emit("A abrir chat no WhatsApp Web…")
        result = runner.send_whatsapp(phone=phone, message=message)

        if result.get("status") == "sent":
            _emit("Mensagem enviada com sucesso.")
            return {"status": "sent", "reason": result.get("notes", "ok")}

        reason = result.get("notes", "Erro desconhecido")
        if reason == "not_logged":
            reason = "WhatsApp Web não autenticado após aguardar scan do QR."
        elif reason == "invalid_number":
            reason = "Número inválido ou sem conta WhatsApp."
        elif reason == "open_timeout":
            reason = "Tempo esgotado ao abrir o chat. Verifica a ligação à internet."
        return {"status": "failed", "reason": reason}

    except Exception as exc:
        logger.exception("Falha ao enviar via WhatsApp Web")
        # Runner pode estar num estado inválido — descartá-lo para o próximo envio
        close_runner()
        return {"status": "failed", "reason": str(exc)}
