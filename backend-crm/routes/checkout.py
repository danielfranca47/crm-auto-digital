"""Geração de links de checkout Efí sob demanda (não há link estático reaproveitável)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from services import efi_client

router = APIRouter(prefix="/checkout", tags=["Checkout"])
logger = logging.getLogger(__name__)


def _offers() -> Dict[str, Dict[str, Any]]:
    """Ofertas comerciais disponíveis. plan_id lido do ambiente — difere entre sandbox/produção."""
    return {
        "start": {
            "plan_id": os.environ.get("EFI_PLAN_ID_START"),
            "item_name": "Plano Start - Lara AI",
            "value_cents": 9700,
            "plan_code": "crm_start",
        },
        "growth": {
            "plan_id": os.environ.get("EFI_PLAN_ID_GROWTH"),
            "item_name": "Plano Growth - Lara AI",
            "value_cents": 19700,
            "plan_code": "crm_growth",
        },
        "growth_fundador": {
            "plan_id": os.environ.get("EFI_PLAN_ID_GROWTH_FUNDADOR"),
            "item_name": "Plano Growth Fundador - Lara AI",
            "value_cents": 14700,
            "plan_code": "crm_growth",
        },
    }


@router.get("/efi/{offer_key}")
async def checkout_efi(offer_key: str) -> RedirectResponse:
    """Gera um link de checkout Efí para a oferta e redireciona o visitante até lá."""
    offer = _offers().get(offer_key)
    if not offer or not offer["plan_id"]:
        logger.warning("checkout_efi: oferta '%s' desconhecida ou sem plan_id configurado", offer_key)
        raise HTTPException(status_code=404, detail="Oferta indisponível")

    base_url = os.environ.get("CRM_PUBLIC_BASE_URL", "").rstrip("/")
    notification_url = f"{base_url}/webhooks/efi"

    try:
        # custom_id carrega plan_code + offer_key (separados por ":") para o webhook conseguir
        # distinguir a origem da assinatura (ex.: campanha "growth_fundador" vs "growth" normal)
        # — ver docs/architecture/billing-efi.md
        payment_url = await efi_client.create_subscription_link(
            plan_id=int(offer["plan_id"]),
            item_name=offer["item_name"],
            value_cents=offer["value_cents"],
            notification_url=notification_url,
            custom_id=f'{offer["plan_code"]}:{offer_key}',
        )
    except Exception as exc:
        logger.error("checkout_efi: erro ao gerar link para oferta '%s': %s", offer_key, exc)
        raise HTTPException(status_code=502, detail="Erro ao gerar checkout")

    logger.info("checkout_efi: link gerado oferta=%s -> %s", offer_key, payment_url)
    return RedirectResponse(url=payment_url, status_code=307)
