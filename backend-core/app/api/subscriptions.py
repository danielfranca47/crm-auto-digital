import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.services.email_service import (
    render_subscription_cancelled_email,
    render_welcome_email,
    send_email,
)
from .auth import get_current_user, get_password_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["subscriptions"])


class SubscriptionCreate(BaseModel):
    user_id: Optional[int] = None
    product_code: str
    plan_code: str


class SubscriptionOut(BaseModel):
    id: int
    product_code: str
    plan_code: str
    status: str
    current_period_start: datetime
    current_period_end: Optional[datetime]

    class Config:
        orm_mode = True


class UserLimits(BaseModel):
    max_leads: Optional[int]
    max_agents_local: Optional[int]
    max_pesquisa_selenium_daily: Optional[int]
    max_pesquisa_turbo_monthly: Optional[int]
    max_prospec_monthly: Optional[int]
    max_copy_generation_monthly: Optional[int]
    max_ia_conversas_monthly: Optional[int]
    max_whatsapp_send_daily: Optional[int]
    max_email_send_daily: Optional[int]
    max_prospects_daily: Optional[int]
    max_maps_search_daily: Optional[int]
    max_maps_enrich_daily: Optional[int]
    require_agent_local_activation_fee: bool
    ia_memory_advanced: bool
    follow_up_enabled: bool = True
    playground_monthly_limit: Optional[int] = None


class ProductEntitlement(BaseModel):
    product_code: str
    status: str
    plan_code: Optional[str]
    current_period_end: Optional[datetime] = None


class EntitlementsResponse(BaseModel):
    subscription_status: str
    products: List[ProductEntitlement]
    limits: UserLimits


def _calculate_limits(current_user: models.User, db: Session) -> UserLimits:
    active_subscriptions = (
        db.query(models.Subscription)
        .join(models.Plan)
        .filter(models.Subscription.user_id == current_user.id, models.Subscription.status == "active")
        .all()
    )

    plan_ids = [sub.plan_id for sub in active_subscriptions]
    plan_limits_by_plan = {}
    if plan_ids:
        limits = db.query(models.PlanLimits).filter(models.PlanLimits.plan_id.in_(plan_ids)).all()
        plan_limits_by_plan = {limit.plan_id: limit for limit in limits}

    def add_limit(current: Optional[int], value: Optional[int]) -> Optional[int]:
        if current is None or value is None:
            return None
        return current + value

    totals: Dict[str, Optional[int]] = {
        "max_leads": 0,
        "max_agents_local": 0,
        "max_pesquisa_selenium_daily": 0,
        "max_pesquisa_turbo_monthly": 0,
        "max_prospec_monthly": 0,
        "max_copy_generation_monthly": 0,
        "max_ia_conversas_monthly": 0,
        "max_whatsapp_send_daily": 0,
        "max_email_send_daily": 0,
        "max_prospects_daily": 0,
        "max_maps_search_daily": 0,
        "max_maps_enrich_daily": 0,
    }
    require_agent_local_activation_fee = False
    ia_memory_advanced = False
    follow_up_enabled = True  # default True — planos legados não têm o campo
    playground_monthly_limit: Optional[int] = None  # None = ilimitado

    for sub in active_subscriptions:
        plan_limit = plan_limits_by_plan.get(sub.plan_id)
        if not plan_limit:
            continue
        totals = {key: add_limit(totals[key], plan_limit.as_dict()[key]) for key in totals}
        require_agent_local_activation_fee = (
            require_agent_local_activation_fee or plan_limit.require_agent_local_activation_fee
        )
        ia_memory_advanced = ia_memory_advanced or plan_limit.ia_memory_advanced
        # follow_up_enabled: False se qualquer plano activo o desactivar
        if not getattr(plan_limit, "follow_up_enabled", True):
            follow_up_enabled = False
        # playground_monthly_limit: usar o menor limite definido (None = ilimitado)
        plm = getattr(plan_limit, "playground_monthly_limit", None)
        if plm is not None:
            playground_monthly_limit = plm if playground_monthly_limit is None else min(playground_monthly_limit, plm)

    user_addons = db.query(models.UserAddon).filter(models.UserAddon.user_id == current_user.id).all()
    for addon in user_addons:
        if addon.addon_type == "extra_leads":
            totals["max_leads"] = add_limit(totals["max_leads"], addon.quantity)
        elif addon.addon_type == "extra_conversational_ai_conversations":
            totals["max_ia_conversas_monthly"] = add_limit(
                totals["max_ia_conversas_monthly"], addon.quantity
            )

    return UserLimits(
        **totals,
        require_agent_local_activation_fee=require_agent_local_activation_fee,
        ia_memory_advanced=ia_memory_advanced,
        follow_up_enabled=follow_up_enabled,
        playground_monthly_limit=playground_monthly_limit,
    )


@router.get("/subscriptions/me", response_model=List[SubscriptionOut])
async def list_my_subscriptions(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    subscriptions = (
        db.query(models.Subscription)
        .join(models.Product)
        .join(models.Plan)
        .filter(models.Subscription.user_id == current_user.id)
        .all()
    )

    return [
        SubscriptionOut(
            id=sub.id,
            product_code=sub.product.code,
            plan_code=sub.plan.code,
            status=sub.status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
        )
        for sub in subscriptions
    ]


@router.post("/subscriptions", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: SubscriptionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_user_id = payload.user_id or current_user.id
    if payload.user_id and payload.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create subscriptions for other users")

    product = db.query(models.Product).filter(models.Product.code == payload.product_code).first()
    if not product or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    plan = db.query(models.Plan).filter(models.Plan.code == payload.plan_code).first()
    if not plan or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found or inactive")

    if plan.product_id != product.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan does not belong to product")

    subscription = models.Subscription(
        user_id=target_user_id,
        product_id=product.id,
        plan_id=plan.id,
        status="active",
        current_period_start=datetime.utcnow(),
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return SubscriptionOut(
        id=subscription.id,
        product_code=product.code,
        plan_code=plan.code,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
    )


@router.get("/me/limits", response_model=UserLimits)
async def get_my_limits(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _calculate_limits(current_user, db)


def _require_service_token(x_service_token: str = Header(None)) -> str:
    expected = settings.CORE_SERVICE_TOKEN
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    return x_service_token


class PaymentEventRequest(BaseModel):
    email: str
    plan_code: str
    action: Literal["activate", "cancel", "renew"]
    origin_offer: Optional[str] = None
    charge_id: Optional[int] = None


@router.post("/internal/subscriptions/payment-event", status_code=status.HTTP_200_OK)
async def payment_event(
    payload: PaymentEventRequest,
    _: str = Depends(_require_service_token),
    db: Session = Depends(get_db),
) -> dict:
    """Endpoint interno — chamado pelo backend-crm ao receber webhook do gateway de pagamento (Efí)."""
    email = payload.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    new_user_created = False
    if not user:
        if payload.action == "cancel":
            logger.info("payment_event: utilizador '%s' não encontrado — ignorado", email)
            return {"ok": True, "action": "skipped", "reason": "user_not_found"}
        # Novo comprador (activate OU 1ª cobrança reportada como renew): criar conta automaticamente.
        # Alguns gateways não distinguem de forma confiável a 1ª cobrança de renovações seguintes.
        alphabet = string.ascii_letters + string.digits + "!@#$%"
        temp_password = "".join(secrets.choice(alphabet) for _ in range(14))
        user = models.User(
            email=email,
            password_hash=get_password_hash(temp_password),
            name=None,
            status="active",
        )
        db.add(user)
        db.flush()  # obtém user.id sem commit
        new_user_created = True
        logger.info("payment_event: novo utilizador criado email=%s id=%s", email, user.id)
        try:
            login_url = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/login"
            html, text = render_welcome_email(None, temp_password, login_url)
            send_email(
                to=email,
                subject="Bem-vindo à Lara AI — as tuas credenciais de acesso",
                html=html,
                text=text,
            )
            logger.info("payment_event: email de boas-vindas enviado para %s", email)
        except Exception as exc:
            logger.error("payment_event: falha ao enviar email para %s — %s", email, exc)

    plan = db.query(models.Plan).filter(models.Plan.code == payload.plan_code).first()
    if not plan:
        logger.error("payment_event: plano '%s' não encontrado", payload.plan_code)
        return {"ok": True, "action": "skipped", "reason": "plan_not_found"}

    now = datetime.utcnow()

    if payload.action == "cancel":
        db.query(models.Subscription).filter(
            models.Subscription.user_id == user.id,
            models.Subscription.plan_id == plan.id,
            models.Subscription.status == "active",
        ).update({"status": "cancelled"})
        db.commit()
        logger.info("payment_event: subscrição cancelada user=%s plan=%s", user.id, payload.plan_code)
        try:
            html, text = render_subscription_cancelled_email(user.name, plan.name)
            send_email(
                to=user.email,
                subject="Subscrição cancelada — Digital Pro",
                html=html,
                text=text,
            )
            logger.info("payment_event: email de cancelamento enviado para %s", user.email)
        except Exception as exc:
            logger.error("payment_event: falha ao enviar email de cancelamento para %s — %s", user.email, exc)
        return {"ok": True, "action": "cancelled"}

    if payload.action == "renew":
        sub = db.query(models.Subscription).filter(
            models.Subscription.user_id == user.id,
            models.Subscription.plan_id == plan.id,
            models.Subscription.status == "active",
        ).first()
        if sub:
            base = sub.current_period_end if sub.current_period_end and sub.current_period_end > now else now
            sub.current_period_end = base + timedelta(days=30)
            # Reinicia o ciclo de avisos de expiração para o próximo período. Corrige também um
            # bug latente: sem este reset, uma sub que já recebeu um aviso nunca mais recebia outro.
            sub.expiry_warning_stage = None
            if not sub.origin_offer and payload.origin_offer:
                sub.origin_offer = payload.origin_offer
            # Sempre a cobrança mais recente — é essa que seria reembolsada em caso de pedido.
            if payload.charge_id:
                sub.efi_charge_id = payload.charge_id
            db.commit()
            logger.info("payment_event: subscrição renovada user=%s plan=%s", user.id, payload.plan_code)
            return {"ok": True, "action": "renewed"}
        # Se não existe activa, activa nova

    # activate (ou renew sem sub activa)
    db.query(models.Subscription).filter(
        models.Subscription.user_id == user.id,
        models.Subscription.status == "active",
        models.Subscription.product_id == plan.product_id,
    ).update({"status": "cancelled"})
    sub = models.Subscription(
        user_id=user.id,
        product_id=plan.product_id,
        plan_id=plan.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        origin_offer=payload.origin_offer,
        efi_charge_id=payload.charge_id,
    )
    db.add(sub)
    db.commit()
    logger.info("payment_event: subscrição activada user=%s plan=%s", user.id, payload.plan_code)
    return {"ok": True, "action": "created_and_activated" if new_user_created else "activated"}


@router.get("/internal/subscriptions/by-email/{email}")
async def get_subscription_by_email(
    email: str,
    _: str = Depends(_require_service_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Endpoint interno — usado pelo backend-crm para localizar a assinatura activa mais recente
    de um utilizador (por email) e o efi_charge_id necessário para acionar um reembolso."""
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilizador não encontrado")

    sub = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == user.id, models.Subscription.status == "active")
        .order_by(models.Subscription.created_at.desc())
        .first()
    )
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscrição activa não encontrada")

    plan = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
    return {
        "plan_code": plan.code if plan else None,
        "status": sub.status,
        "current_period_end": sub.current_period_end,
        "efi_charge_id": sub.efi_charge_id,
    }


@router.get("/me/entitlements", response_model=EntitlementsResponse)
async def get_entitlements(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    subscriptions = (
        db.query(models.Subscription)
        .join(models.Product)
        .join(models.Plan)
        .filter(models.Subscription.user_id == current_user.id)
        .all()
    )

    product_entries: List[ProductEntitlement] = []
    has_active = False
    has_expired = False
    for sub in subscriptions:
        if not sub.product:
            continue
        status_value = sub.status or "inactive"
        if status_value == "active":
            has_active = True
        elif status_value == "expired":
            has_expired = True
        product_entries.append(
            ProductEntitlement(
                product_code=sub.product.code,
                status=status_value,
                plan_code=sub.plan.code if sub.plan else None,
                current_period_end=sub.current_period_end,
            )
        )

    limits = _calculate_limits(current_user, db)

    if has_active:
        overall_status = "active"
    elif has_expired:
        overall_status = "expired"
    else:
        overall_status = "inactive"

    return EntitlementsResponse(
        subscription_status=overall_status,
        products=product_entries,
        limits=limits,
    )
