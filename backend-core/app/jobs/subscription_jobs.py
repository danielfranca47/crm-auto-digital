"""
Job diário de expiração de subscriptions.

Executado pelo APScheduler às 09:00 UTC:
  1. Subscriptions expiradas (current_period_end < now, status=active) → status="expired" + email
  2. Avisos antecipados em vários pontos antes de expirar — 30/15/7/3/2/1/0 dias
     (`expiry_warning_stage` guarda o estágio mais urgente já enviado; reposto a None a cada
     renovação em `payment_event`, ver docs/architecture/billing-efi.md)
"""
import logging
from datetime import datetime, timedelta

from app.db import SessionLocal
from app import models
from app.config import settings

logger = logging.getLogger(__name__)

FALLBACK_CHECKOUT_URL = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/assinatura"

# Dias-antes-de-expirar em que um aviso é disparado, do menos ao mais urgente.
_WARNING_THRESHOLDS = [0, 1, 2, 3, 7, 15, 30]

# offer_key por plano — usados para montar o link de checkout Efí sob demanda (ver
# docs/architecture/billing-efi.md)
_PLAN_OFFER_KEYS: dict[str, str] = {
    "crm_start": "start",
    "crm_growth": "growth",
}


def _get_checkout_url(plan_code: str, origin_offer: str | None = None) -> str:
    # Fundador renovando mantém a condição travada (R$197); qualquer outro caso usa o preço
    # normal do plano (ex.: Growth R$297) — ver docs/architecture/billing-efi.md
    if plan_code == "crm_growth" and origin_offer == "growth_fundador":
        offer_key = "growth_founder_renewal"
    else:
        offer_key = _PLAN_OFFER_KEYS.get(plan_code)
    crm_base = (settings.CRM_PUBLIC_BASE_URL or "").rstrip("/")
    if not offer_key or not crm_base:
        return FALLBACK_CHECKOUT_URL
    return f"{crm_base}/checkout/efi/{offer_key}"


def run_daily_subscription_jobs() -> dict:
    """
    Processa expiração de subscriptions e envia avisos antecipados.
    Retorna sumário das acções tomadas (útil para o endpoint de trigger manual).
    """
    from app.services.email_service import (
        render_subscription_expired_email,
        render_subscription_expiring_email,
        send_email,
    )

    db = SessionLocal()
    expired_count = 0
    warning_count = 0
    errors: list[str] = []

    try:
        now = datetime.utcnow()
        warning_window = now + timedelta(days=_WARNING_THRESHOLDS[-1])

        # ── 1. Cancelar subscriptions expiradas ──────────────────────────────
        expired_subs = (
            db.query(models.Subscription)
            .filter(
                models.Subscription.status == "active",
                models.Subscription.current_period_end.isnot(None),
                models.Subscription.current_period_end < now,
            )
            .all()
        )

        for sub in expired_subs:
            sub.status = "expired"
            expired_count += 1
            logger.info("Subscription expirada: id=%s user_id=%s", sub.id, sub.user_id)

            try:
                user = db.query(models.User).filter(models.User.id == sub.user_id).first()
                plan = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
                if user and plan:
                    checkout_url = _get_checkout_url(plan.code, sub.origin_offer)
                    html, text = render_subscription_expired_email(user.name, plan.name, checkout_url)
                    send_email(
                        to=user.email,
                        subject="O teu plano expirou — Digital Pro",
                        html=html,
                        text=text,
                    )
            except Exception as exc:
                msg = f"Email expiração user_id={sub.user_id}: {exc}"
                logger.warning(msg)
                errors.append(msg)

        # ── 2. Avisos antecipados em múltiplos estágios (30/15/7/3/2/1/0 dias) ──
        expiring_subs = (
            db.query(models.Subscription)
            .filter(
                models.Subscription.status == "active",
                models.Subscription.current_period_end.isnot(None),
                models.Subscription.current_period_end > now,
                models.Subscription.current_period_end <= warning_window,
            )
            .all()
        )

        for sub in expiring_subs:
            days_remaining = (sub.current_period_end.date() - now.date()).days
            if days_remaining < 0:
                continue  # já expirado — tratado na Parte 1

            applicable = next((t for t in _WARNING_THRESHOLDS if days_remaining <= t), None)
            if applicable is None:
                continue
            if sub.expiry_warning_stage is not None and applicable >= sub.expiry_warning_stage:
                continue  # já enviámos um aviso igual ou mais urgente para este período

            sub.expiry_warning_stage = applicable
            warning_count += 1

            try:
                user = db.query(models.User).filter(models.User.id == sub.user_id).first()
                plan = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
                if user and plan:
                    checkout_url = _get_checkout_url(plan.code, sub.origin_offer)
                    html, text = render_subscription_expiring_email(
                        user.name,
                        plan.name,
                        sub.current_period_end,
                        checkout_url,
                        days_remaining=days_remaining,
                        is_founder_transition=(sub.origin_offer == "growth_fundador"),
                    )
                    send_email(
                        to=user.email,
                        subject="O teu plano expira em breve — Digital Pro",
                        html=html,
                        text=text,
                    )
                    logger.info(
                        "Aviso de expiração enviado: user_id=%s stage=%s dias=%s",
                        sub.user_id, applicable, days_remaining,
                    )
            except Exception as exc:
                msg = f"Email aviso user_id={sub.user_id}: {exc}"
                logger.warning(msg)
                errors.append(msg)

        db.commit()

    except Exception as exc:
        logger.error("Erro no job diário de subscriptions: %s", exc)
        db.rollback()
        errors.append(str(exc))
    finally:
        db.close()

    summary = {
        "expired": expired_count,
        "warnings_sent": warning_count,
        "errors": errors,
        "ran_at": datetime.utcnow().isoformat(),
    }
    logger.info("Job diário concluído: %s", summary)
    return summary
