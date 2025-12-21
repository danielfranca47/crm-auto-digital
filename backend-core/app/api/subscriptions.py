from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from .auth import get_current_user

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
    max_maps_search_daily: Optional[int]
    max_maps_enrich_daily: Optional[int]
    require_agent_local_activation_fee: bool
    ia_memory_advanced: bool


class ProductEntitlement(BaseModel):
    product_code: str
    status: str
    plan_code: Optional[str]


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
        "max_maps_search_daily": 0,
        "max_maps_enrich_daily": 0,
    }
    require_agent_local_activation_fee = False
    ia_memory_advanced = False

    for sub in active_subscriptions:
        plan_limit = plan_limits_by_plan.get(sub.plan_id)
        if not plan_limit:
            continue
        totals = {key: add_limit(totals[key], plan_limit.as_dict()[key]) for key in totals}
        require_agent_local_activation_fee = (
            require_agent_local_activation_fee or plan_limit.require_agent_local_activation_fee
        )
        ia_memory_advanced = ia_memory_advanced or plan_limit.ia_memory_advanced

    user_addons = db.query(models.UserAddon).filter(models.UserAddon.user_id == current_user.id).all()
    for addon in user_addons:
        if addon.addon_type == "extra_leads":
            totals["max_leads"] = add_limit(totals["max_leads"], addon.quantity)
        elif addon.addon_type == "extra_ia_conversations":
            totals["max_ia_conversas_monthly"] = add_limit(
                totals["max_ia_conversas_monthly"], addon.quantity
            )

    return UserLimits(
        **totals,
        require_agent_local_activation_fee=require_agent_local_activation_fee,
        ia_memory_advanced=ia_memory_advanced,
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
    for sub in subscriptions:
        if not sub.product:
            continue
        status_value = sub.status or "inactive"
        if status_value == "active":
            has_active = True
        product_entries.append(
            ProductEntitlement(
                product_code=sub.product.code,
                status=status_value,
                plan_code=sub.plan.code if sub.plan else None,
            )
        )

    limits = _calculate_limits(current_user, db)

    return EntitlementsResponse(
        subscription_status="active" if has_active else "inactive",
        products=product_entries,
        limits=limits,
    )
