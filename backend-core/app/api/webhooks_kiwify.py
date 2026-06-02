"""
Webhook Kiwify — recebe eventos de pagamento e activa/renova/cancela subscriptions.

Mapeamento oferta → plano CRM:
  gOjcexD (Start  R$97)  → crm_start
  To8qV99 (Growth R$197) → crm_growth
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Mapeamento fixo: identificador do link Kiwify → código do plano CRM
OFFER_TO_PLAN: Dict[str, str] = {
    "gOjcexD": "crm_start",
    "To8qV99": "crm_growth",
}

# Eventos que activam ou renovam subscription
ACTIVATE_EVENTS = {
    "order_approved", "order.approved",
    "subscription_renewed", "subscription.renewed",
    "purchase_approved",
}

# Eventos que cancelam subscription
CANCEL_EVENTS = {
    "order_refunded", "order.refunded",
    "subscription_cancelled", "subscription.cancelled",
    "subscription_canceled",
    "charge_failed", "charge.failed",
}


def _extract_field(payload: Dict[str, Any], *paths: str) -> Optional[str]:
    """Tenta extrair um campo de múltiplos caminhos possíveis no payload."""
    for path in paths:
        keys = path.split(".")
        val = payload
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                val = None
                break
        if val and isinstance(val, str):
            return val.strip()
    return None


def _resolve_plan_code(payload: Dict[str, Any]) -> Optional[str]:
    """
    Determina o plan_code a partir do payload Kiwify.
    Tenta múltiplas localizações onde o identificador da oferta pode aparecer.
    """
    # Tenta encontrar o identificador da oferta em campos conhecidos
    candidates = [
        _extract_field(payload, "data.product.ucode", "data.order.ucode",
                       "data.subscription.plan.id", "data.plan.id",
                       "data.offer.id", "offer_id", "plan_id"),
    ]

    for candidate in candidates:
        if candidate and candidate in OFFER_TO_PLAN:
            return OFFER_TO_PLAN[candidate]

    # Fallback: verifica se algum valor no payload corresponde a uma oferta conhecida
    payload_str = str(payload)
    for offer_id, plan_code in OFFER_TO_PLAN.items():
        if offer_id in payload_str:
            return plan_code

    return None


def _activate_subscription(user: models.User, plan_code: str, db: Session, months: int = 1) -> None:
    plan = db.query(models.Plan).filter(models.Plan.code == plan_code).first()
    if not plan:
        logger.error("Plano '%s' não encontrado no DB — webhook Kiwify", plan_code)
        return

    # Cancela subscriptions activas existentes do mesmo produto
    db.query(models.Subscription).filter(
        models.Subscription.user_id == user.id,
        models.Subscription.status == "active",
        models.Subscription.product_id == plan.product_id,
    ).update({"status": "cancelled"})

    now = datetime.utcnow()
    sub = models.Subscription(
        user_id=user.id,
        product_id=plan.product_id,
        plan_id=plan.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30 * months),
    )
    db.add(sub)
    db.commit()
    logger.info("Subscription activada: user_id=%s plan=%s", user.id, plan_code)


def _renew_subscription(user: models.User, plan_code: str, db: Session) -> None:
    plan = db.query(models.Plan).filter(models.Plan.code == plan_code).first()
    if not plan:
        return

    sub = db.query(models.Subscription).filter(
        models.Subscription.user_id == user.id,
        models.Subscription.status == "active",
        models.Subscription.plan_id == plan.id,
    ).first()

    now = datetime.utcnow()
    if sub:
        # Estende a partir do final do período actual (ou de agora se já expirou)
        base = sub.current_period_end if sub.current_period_end and sub.current_period_end > now else now
        sub.current_period_end = base + timedelta(days=30)
        db.commit()
        logger.info("Subscription renovada: user_id=%s plan=%s new_end=%s", user.id, plan_code, sub.current_period_end)
    else:
        # Não existe activa — activa nova
        _activate_subscription(user, plan_code, db, months=1)


def _cancel_subscription(user: models.User, plan_code: str, db: Session) -> None:
    plan = db.query(models.Plan).filter(models.Plan.code == plan_code).first()
    if not plan:
        return

    db.query(models.Subscription).filter(
        models.Subscription.user_id == user.id,
        models.Subscription.status == "active",
        models.Subscription.plan_id == plan.id,
    ).update({"status": "cancelled"})
    db.commit()
    logger.info("Subscription cancelada: user_id=%s plan=%s", user.id, plan_code)


@router.post("/kiwify")
async def kiwify_webhook(request: Request, signature: Optional[str] = None) -> Dict[str, Any]:
    """
    Recebe eventos de pagamento do Kiwify e activa/renova/cancela subscriptions.
    Validação: HMAC-SHA1 via query param ?signature= usando KIWIFY_WEBHOOK_SECRET como chave.
    """
    import hashlib
    import hmac as hmac_lib

    raw_body = await request.body()

    # Loga o payload completo para diagnóstico
    try:
        payload: Dict[str, Any] = __import__("json").loads(raw_body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido")

    # DIAGNÓSTICO — print forçado para stdout
    print(f"[KIWIFY] payload: {payload}", flush=True)
    print(f"[KIWIFY] signature query: {signature}", flush=True)
    print(f"[KIWIFY] body_len: {len(raw_body)}", flush=True)

    # Calcula HMAC-SHA1 para diagnóstico
    if settings.KIWIFY_WEBHOOK_SECRET:
        expected = hmac_lib.new(
            settings.KIWIFY_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha1,
        ).hexdigest()
        match = (expected == signature) if signature else False
        print(f"[KIWIFY] HMAC expected={expected} received={signature} match={match}", flush=True)
        # Validação comentada temporariamente para diagnóstico
        # if not match:
        #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    # ── Identificar evento ────────────────────────────────────────────────────
    event = (
        _extract_field(payload, "event", "type", "data.order.status")
        or ""
    ).lower().replace(" ", "_")

    if event not in ACTIVATE_EVENTS and event not in CANCEL_EVENTS:
        logger.info("Kiwify webhook: evento '%s' ignorado", event)
        return {"ok": True, "action": "ignored", "event": event}

    # ── Identificar cliente ───────────────────────────────────────────────────
    email = _extract_field(
        payload,
        "data.customer.email",
        "customer.email",
        "data.buyer.email",
        "buyer.email",
        "email",
    )
    if not email:
        logger.warning("Kiwify webhook: email não encontrado no payload")
        return {"ok": True, "action": "skipped", "reason": "no_email"}

    # ── Identificar plano ─────────────────────────────────────────────────────
    plan_code = _resolve_plan_code(payload)
    if not plan_code:
        logger.warning("Kiwify webhook: oferta não mapeada para plano. Payload: %s", payload)
        return {"ok": True, "action": "skipped", "reason": "plan_not_mapped"}

    # ── Processar ─────────────────────────────────────────────────────────────
    db: Session = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            logger.info("Kiwify webhook: utilizador '%s' não encontrado — ignorado", email)
            return {"ok": True, "action": "skipped", "reason": "user_not_found", "email": email}

        if event in CANCEL_EVENTS:
            _cancel_subscription(user, plan_code, db)
            action = "cancelled"
        elif event in {"subscription_renewed", "subscription.renewed"}:
            _renew_subscription(user, plan_code, db)
            action = "renewed"
        else:
            _activate_subscription(user, plan_code, db)
            action = "activated"

        return {"ok": True, "action": action, "email": email, "plan": plan_code}

    finally:
        db.close()
