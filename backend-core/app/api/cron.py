"""
Endpoint de trigger manual do job diário (admin-only).
Útil para testes sem ter de esperar pelo schedule automático.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.api.admin import require_admin

router = APIRouter(prefix="/admin/cron", tags=["cron"])


@router.post("/daily")
async def trigger_daily_job(_: dict = Depends(require_admin)) -> Dict[str, Any]:
    """Executa manualmente o job diário de expiração de subscriptions."""
    from app.jobs.subscription_jobs import run_daily_subscription_jobs

    result = run_daily_subscription_jobs()
    return {"ok": True, **result}


@router.post("/whatsapp-connection-check")
async def trigger_whatsapp_connection_check(_: dict = Depends(require_admin)) -> Dict[str, Any]:
    """Executa manualmente a verificação de saúde das conexões WhatsApp
    (normalmente agendada a cada 6h) — útil para validar sem esperar o
    schedule automático. Usa a versão async diretamente (não
    `run_whatsapp_connection_check`) porque esta rota já roda dentro do event
    loop do FastAPI."""
    from app.jobs.whatsapp_connection_check_jobs import run_whatsapp_connection_check_async

    result = await run_whatsapp_connection_check_async()
    return {"ok": True, **result}


@router.post("/uazapi-cleanup")
async def trigger_uazapi_cleanup(_: dict = Depends(require_admin)) -> Dict[str, Any]:
    """Executa manualmente a limpeza de instâncias órfãs na UazAPI
    (normalmente diária, 03:00 UTC). Usa a versão async — esta rota já corre
    dentro do event loop do FastAPI."""
    from app.jobs.uazapi_cleanup_jobs import run_uazapi_cleanup_async

    result = await run_uazapi_cleanup_async()
    return {"ok": True, **result}
