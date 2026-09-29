"""
Limpeza diária de instâncias órfãs na UazAPI.

Executado pelo APScheduler uma vez por dia: apaga instâncias que existem na
UazAPI mas não no nosso banco (órfãs), desconectadas e com mais de 10 min de
vida, e loga a ocupação (total antes/depois). Instâncias de clientes nunca
são apagadas aqui — só por demanda, quando o teto é atingido no
`/whatsapp-instances/init` (ver `app/services/uazapi_capacity.py` e
docs/architecture/whatsapp-connection.md, seção "Capacidade de instâncias na
UazAPI").
"""
import asyncio
import logging

from app.db import SessionLocal
from app.services import uazapi_capacity

logger = logging.getLogger(__name__)


async def run_uazapi_cleanup_async() -> dict:
    """Versão async — para quem já está dentro de um event loop (ex.: o
    trigger manual em `app/api/cron.py`)."""
    db = SessionLocal()
    try:
        return await uazapi_capacity.cleanup_orphans(db)
    finally:
        db.close()


def run_uazapi_cleanup() -> dict:
    """Entrypoint síncrono para o APScheduler (thread própria, sem event loop
    ativo) — mesmo padrão de `run_whatsapp_connection_check`."""
    try:
        return asyncio.run(run_uazapi_cleanup_async())
    except Exception as exc:
        logger.warning("uazapi_cleanup falhou: %s", exc)
        return {"error": str(exc)}
