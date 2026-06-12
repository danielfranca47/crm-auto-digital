"""
Job diário de expiração de subscriptions.

Executado pelo APScheduler às 09:00 UTC:
  1. Subscriptions expiradas (current_period_end < now, status=active) → status="expired" + email
  2. Subscriptions a expirar em ≤3 dias (expiry_warning_sent=False) → email de aviso + flag sent=True
"""
import logging
from datetime import datetime, timedelta

from app.db import SessionLocal
from app import models
from app.config import settings

logger = logging.getLogger(__name__)

# Checkout links por plano (para incluir no email de aviso/expiração)
PLAN_CHECKOUT_LINKS: dict[str, str] = {
    "crm_start": "https://pay.kiwify.com.br/gOjcexD",
    "crm_growth": "https://pay.kiwify.com.br/To8qV99",
}
FALLBACK_CHECKOUT_URL = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/assinatura"


def _get_checkout_url(plan_code: str) -> str:
    return PLAN_CHECKOUT_LINKS.get(plan_code, FALLBACK_CHECKOUT_URL)


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
        warning_window = now + timedelta(days=3)

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
                    checkout_url = _get_checkout_url(plan.code)
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

        # ── 2. Aviso antecipado (≤3 dias, não enviado ainda) ─────────────────
        expiring_subs = (
            db.query(models.Subscription)
            .filter(
                models.Subscription.status == "active",
                models.Subscription.current_period_end.isnot(None),
                models.Subscription.current_period_end > now,
                models.Subscription.current_period_end <= warning_window,
                models.Subscription.expiry_warning_sent == False,  # noqa: E712
            )
            .all()
        )

        for sub in expiring_subs:
            sub.expiry_warning_sent = True
            warning_count += 1

            try:
                user = db.query(models.User).filter(models.User.id == sub.user_id).first()
                plan = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
                if user and plan:
                    checkout_url = _get_checkout_url(plan.code)
                    html, text = render_subscription_expiring_email(
                        user.name, plan.name, sub.current_period_end, checkout_url
                    )
                    send_email(
                        to=user.email,
                        subject="O teu plano expira em breve — Digital Pro",
                        html=html,
                        text=text,
                    )
                    logger.info("Aviso de expiração enviado: user_id=%s", sub.user_id)
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
