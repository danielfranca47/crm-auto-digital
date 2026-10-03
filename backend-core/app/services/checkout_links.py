"""
Links de checkout Efí por plano/origem — gerados sob demanda pelo backend-crm em
`/checkout/efi/{offer_key}` (ver docs/architecture/billing-efi.md).

Usado pelos emails de aviso/expiração (`jobs/subscription_jobs.py`) e pelo
`renewal_checkout_url` de `GET /me/entitlements` (`api/subscriptions.py`).
"""
from typing import Optional

from app.config import settings

FALLBACK_CHECKOUT_URL = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/assinatura"

# offer_key por plano — usados para montar o link de checkout Efí sob demanda
_PLAN_OFFER_KEYS: dict[str, str] = {
    "crm_start": "start",
    "crm_growth": "growth",
}


def get_offer_checkout_url(plan_code: str, origin_offer: Optional[str] = None) -> Optional[str]:
    """Link directo para o checkout da oferta, ou None se o plano não tem oferta vendável
    (ou `CRM_PUBLIC_BASE_URL` não está definida)."""
    # Fundador renovando mantém a condição travada (R$197); qualquer outro caso usa o preço
    # normal do plano (ex.: Growth R$297) — ver docs/architecture/billing-efi.md
    if plan_code == "crm_growth" and origin_offer == "growth_fundador":
        offer_key = "growth_founder_renewal"
    else:
        offer_key = _PLAN_OFFER_KEYS.get(plan_code)
    crm_base = (settings.CRM_PUBLIC_BASE_URL or "").rstrip("/")
    if not offer_key or not crm_base:
        return None
    return f"{crm_base}/checkout/efi/{offer_key}"


def get_checkout_url(plan_code: str, origin_offer: Optional[str] = None) -> str:
    """Igual a `get_offer_checkout_url`, mas cai para a página de assinatura do CRM quando
    não há oferta — para emails, onde tem de haver sempre um link clicável."""
    return get_offer_checkout_url(plan_code, origin_offer) or FALLBACK_CHECKOUT_URL
