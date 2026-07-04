"""Admin endpoints — reembolso de assinaturas (MVP, reembolso total via 1 clique).

Ver docs/architecture/billing-efi.md, secção "Reembolso", para o fluxo completo e as
restrições da API da Efí.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core_client import require_crm_admin
from services import efi_client

router = APIRouter(prefix="/admin/billing", tags=["admin-billing"])
logger = logging.getLogger(__name__)


class RefundRequest(BaseModel):
    email: str


def _core_base() -> str:
    return os.environ.get("CORE_API_BASE", "http://localhost:8001").rstrip("/")


def _core_headers() -> Dict[str, str]:
    return {"x-service-token": os.environ.get("CORE_SERVICE_TOKEN", "")}


@router.post("/refund")
async def refund_user(
    body: RefundRequest,
    _: dict = Depends(require_crm_admin),
) -> Dict[str, Any]:
    """Reembolsa 100% da última cobrança do utilizador e cancela o acesso imediatamente."""
    email = body.email.strip().lower()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_core_base()}/internal/subscriptions/by-email/{email}",
            headers=_core_headers(),
        )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Utilizador ou subscrição activa não encontrada")
        resp.raise_for_status()
        sub_data = resp.json()

    charge_id = sub_data.get("efi_charge_id")
    plan_code = sub_data.get("plan_code")
    if not charge_id:
        raise HTTPException(
            status_code=422,
            detail="Sem charge_id registado para esta assinatura — reembolsar manualmente no painel da Efí.",
        )

    try:
        await efi_client.refund_charge(charge_id)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        logger.error("refund_user: Efí recusou o reembolso email=%s charge_id=%s detail=%s", email, charge_id, detail)
        raise HTTPException(status_code=502, detail=f"Efí recusou o reembolso: {detail}")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_core_base()}/internal/subscriptions/payment-event",
            json={"email": email, "plan_code": plan_code, "action": "cancel"},
            headers=_core_headers(),
        )
        resp.raise_for_status()

    logger.info("refund_user: reembolsado e cancelado email=%s charge_id=%s plan=%s", email, charge_id, plan_code)
    return {"ok": True, "refunded": True, "plan_code": plan_code}
