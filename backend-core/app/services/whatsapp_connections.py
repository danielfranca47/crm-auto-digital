from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app import models
from app.utils.crypto import decrypt_secret, encrypt_secret, SecretEncryptionError


def get_connection_for_user(db: Session, user_id: int) -> Optional[models.WhatsappConnection]:
    return db.query(models.WhatsappConnection).filter(models.WhatsappConnection.user_id == user_id).first()


def get_connection_by_instance(db: Session, instance_id: str) -> Optional[models.WhatsappConnection]:
    return (
        db.query(models.WhatsappConnection)
        .filter(models.WhatsappConnection.instance_id == instance_id)
        .first()
    )


def mask_token(encrypted_token: Optional[str]) -> Optional[str]:
    if not encrypted_token:
        return None
    try:
        plain = decrypt_secret(encrypted_token)
        suffix = plain[-4:] if len(plain) > 4 else plain
        return f"****{suffix}"
    except SecretEncryptionError:
        return "****"


def upsert_connection(
    *,
    db: Session,
    user_id: int,
    instance_id: str,
    instance_token: str,
    phone_e164: Optional[str] = None,
    status: Optional[str] = None,
    provider: str = "uazapi",
) -> models.WhatsappConnection:
    existing = get_connection_for_user(db, user_id)
    encrypted_token = encrypt_secret(instance_token)

    if existing:
        existing.instance_id = instance_id
        existing.instance_token_encrypted = encrypted_token
        existing.phone_e164 = phone_e164
        if status:
            existing.status = status
        existing.provider = provider or existing.provider
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    connection = models.WhatsappConnection(
        user_id=user_id,
        provider=provider,
        instance_id=instance_id,
        phone_e164=phone_e164,
        instance_token_encrypted=encrypted_token,
        status=status or "active",
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def upsert_connection_optional_token(
    *,
    db: Session,
    user_id: int,
    instance_id: str,
    instance_token: Optional[str] = None,
    phone_e164: Optional[str] = None,
    status: Optional[str] = None,
    provider: str = "uazapi",
) -> models.WhatsappConnection:
    existing = get_connection_for_user(db, user_id)
    encrypted_token = encrypt_secret(instance_token) if instance_token else None

    if existing:
        existing.instance_id = instance_id
        if encrypted_token:
            existing.instance_token_encrypted = encrypted_token
        existing.phone_e164 = phone_e164
        if status:
            existing.status = status
        existing.provider = provider or existing.provider
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    if not instance_token:
        raise ValueError("instance_token_required")

    connection = models.WhatsappConnection(
        user_id=user_id,
        provider=provider,
        instance_id=instance_id,
        phone_e164=phone_e164,
        instance_token_encrypted=encrypted_token,
        status=status or "active",
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def _add_limit(current: Optional[int], value: Optional[int]) -> Optional[int]:
    if current is None or value is None:
        return None
    return current + value


def _calculate_basic_limits(db: Session, user_id: int) -> Dict[str, Optional[int]]:
    active_subscriptions = (
        db.query(models.Subscription)
        .join(models.Plan)
        .filter(models.Subscription.user_id == user_id, models.Subscription.status == "active")
        .all()
    )

    plan_ids = [sub.plan_id for sub in active_subscriptions]
    plan_limits_by_plan = {}
    if plan_ids:
        limits = db.query(models.PlanLimits).filter(models.PlanLimits.plan_id.in_(plan_ids)).all()
        plan_limits_by_plan = {limit.plan_id: limit for limit in limits}

    totals: Dict[str, Optional[int]] = {
        "max_ia_conversas_monthly": 0,
    }

    for sub in active_subscriptions:
        plan_limit = plan_limits_by_plan.get(sub.plan_id)
        if not plan_limit:
            continue
        totals = {
            key: _add_limit(totals[key], plan_limit.as_dict().get(key))
            for key in totals
        }

    user_addons = db.query(models.UserAddon).filter(models.UserAddon.user_id == user_id).all()
    for addon in user_addons:
        if addon.addon_type == "extra_conversational_ai_conversations":
            totals["max_ia_conversas_monthly"] = _add_limit(
                totals["max_ia_conversas_monthly"], addon.quantity
            )

    return totals


def get_orion_limits(db: Session, user_id: int) -> Dict[str, Optional[int]]:
    limits = _calculate_basic_limits(db, user_id)
    ia_limit = limits.get("max_ia_conversas_monthly")

    def _is_allowed(value: Optional[int]) -> bool:
        return value is None or value > 0

    return {
        "max_ia_conversas_monthly": ia_limit,
        "allow_orion": _is_allowed(ia_limit),
    }


def allow_orion(db: Session, user_id: int) -> bool:
    return get_orion_limits(db, user_id).get("allow_orion", False)
