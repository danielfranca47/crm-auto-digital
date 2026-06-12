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
