"""
Envia mensagem via WhatsApp Web (Selenium).
Wrapper fino sobre WhatsAppRunner que não requer AgentConfig completo.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class _WAConfig:
    """Config mínima para WhatsAppRunner — sem credenciais de agente."""
    user_data_dir: Path = Path.home() / ".agent-local" / "chrome-profile"
    chrome_binary: Optional[str] = os.getenv("CHROME_BINARY") or None
    headless: bool = False


def send_message(
    phone: str,
    message: str,
    *,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """
    Envia mensagem via WhatsApp Web.
    Retorna {'status': 'sent'|'failed', 'reason': str}.

    O Chrome usa o perfil persistido em ~/.agent-local/chrome-profile,
    por isso o utilizador só precisa de fazer o scan do QR uma vez.
    """
    def _emit(msg: str) -> None:
        logger.info(msg)
        if on_progress:
            on_progress(msg)

    runner = None
    try:
        from agent.whatsapp_runner import WhatsAppRunner
        runner = WhatsAppRunner(_WAConfig())

        _emit("A abrir o Chrome com WhatsApp Web…")
        result = runner.send_whatsapp(phone=phone, message=message)
        _emit("A fechar o Chrome…")

        if result.get("status") == "sent":
            return {"status": "sent", "reason": result.get("notes", "ok")}

        reason = result.get("notes", "Erro desconhecido")
        if reason == "not_logged":
            reason = "WhatsApp Web não está autenticado. Faz o scan do QR no Chrome."
        elif reason == "invalid_number":
            reason = "Número inválido ou sem conta WhatsApp."
        return {"status": "failed", "reason": reason}

    except Exception as exc:
        logger.exception("Falha ao enviar via WhatsApp Web")
        return {"status": "failed", "reason": str(exc)}

    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception:
                pass
