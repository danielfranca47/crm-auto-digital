"""Routers de webhooks externos (WhatsApp inbound)."""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException

from services.whatsapp_inbound.inbound_handler import handle_inbound

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/whatsapp/inbound")
def whatsapp_inbound_webhook(
    payload: Dict[str, Any],
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    expected_secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="CRM_WEBHOOK_SECRET não configurado")
    if not x_webhook_secret or x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    return handle_inbound(payload)
