import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.email_service import (
    render_whatsapp_disconnected_email,
    render_whatsapp_reconnected_email,
    send_email,
)
from app.utils.crypto import decrypt_secret, encrypt_secret, SecretEncryptionError

logger = logging.getLogger(__name__)

_DISCONNECT_EMAIL_COOLDOWN = timedelta(minutes=30)


def normalize_connection_status_for_crm(status: Optional[str]) -> str:
    if not status:
        return "inactive"
    normalized = status.strip().lower()
    if normalized in {"connected", "active", "loggedin", "logged_in"}:
        return "active"
    return "inactive"


def apply_connection_status_change(db: Session, connection: models.WhatsappConnection, new_status: str) -> None:
    """Atualiza o status real de uma conexão e dispara os emails de
    desconexão/reconexão quando há mudança de estado ativo↔inativo, com
    cooldown de 30min para evitar spam em caso de flapping. Chamada tanto
    pelo webhook `connection` da UazAPI (`whatsapp_instances.py::connection_event`)
    quanto pela verificação periódica de saúde (`jobs/whatsapp_connection_check_jobs.py`)
    — ver docs/architecture/whatsapp-connection.md, seção "Deteção de queda de sessão"."""
    was_active = normalize_connection_status_for_crm(connection.status) == "active"
    is_active = normalize_connection_status_for_crm(new_status) == "active"

    connection.status = new_status
    db.add(connection)
    db.commit()
    db.refresh(connection)

    if was_active and not is_active:
        now = datetime.utcnow()
        last_email_at = connection.last_disconnect_email_at
        cooldown_expired = last_email_at is None or (now - last_email_at) >= _DISCONNECT_EMAIL_COOLDOWN

        if cooldown_expired:
            try:
                user = db.query(models.User).filter(models.User.id == connection.user_id).first()
                if user and user.email:
                    login_url = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/ai-profile"
                    html, text = render_whatsapp_disconnected_email(user.name, login_url)
                    send_email(
                        to=user.email,
                        subject="A tua Lara desconectou do WhatsApp — reconecta agora",
                        html=html,
                        text=text,
                    )
                connection.last_disconnect_email_at = now
            except Exception as exc:
                logger.warning(
                    "apply_connection_status_change: falha ao enviar email de desconexão user_id=%s error=%s",
                    connection.user_id,
                    exc,
                )
        else:
            logger.info(
                "apply_connection_status_change: cooldown ativo, email de desconexão suprimido instance_id=%s last_email_at=%s",
                connection.instance_id,
                last_email_at,
            )

        connection.disconnect_alert_sent_at = now
        db.add(connection)
        db.commit()

    if not was_active and is_active and connection.disconnect_alert_sent_at:
        disconnect_email_was_sent = (
            connection.last_disconnect_email_at is not None
            and connection.last_disconnect_email_at >= connection.disconnect_alert_sent_at
        )
        if disconnect_email_was_sent:
            try:
                user = db.query(models.User).filter(models.User.id == connection.user_id).first()
                if user and user.email:
                    login_url = (settings.CRM_FRONTEND_URL or "https://crmapp.danielfranca.pt").rstrip("/") + "/ai-profile"
                    html, text = render_whatsapp_reconnected_email(user.name, login_url)
                    send_email(
                        to=user.email,
                        subject="A tua Lara reconectou ao WhatsApp",
                        html=html,
                        text=text,
                    )
            except Exception as exc:
                logger.warning(
                    "apply_connection_status_change: falha ao enviar email de reconexão user_id=%s error=%s",
                    connection.user_id,
                    exc,
                )
        else:
            logger.info(
                "apply_connection_status_change: email de reconexão suprimido (desconexão correspondente também foi suprimida) instance_id=%s",
                connection.instance_id,
            )
        connection.disconnect_alert_sent_at = None
        db.add(connection)
        db.commit()


def get_connection_for_user(db: Session, user_id: int) -> Optional[models.WhatsappConnection]:
    """Resolve a conexão de AGENTE da conta (role='agent') — usada por quem precisa
    saber "qual instância envia mensagens por este usuário" (ex.: resolve-by-user,
    consumido pelo executor real). Nunca deve devolver uma instância role='monitor'."""
    return (
        db.query(models.WhatsappConnection)
        .filter(models.WhatsappConnection.user_id == user_id, models.WhatsappConnection.role == "agent")
        .order_by(models.WhatsappConnection.id.desc())
        .first()
    )


def get_connection_by_instance(db: Session, instance_id: str) -> Optional[models.WhatsappConnection]:
    return (
        db.query(models.WhatsappConnection)
        .filter(models.WhatsappConnection.instance_id == instance_id)
        .first()
    )


def delete_connection_by_instance(db: Session, instance_id: str) -> bool:
    connection = get_connection_by_instance(db, instance_id)
    if not connection:
        return False
    db.delete(connection)
    db.commit()
    return True


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
    role: str = "agent",
) -> models.WhatsappConnection:
    """Resolve a linha existente por instance_id (nunca por user_id) — uma conta pode
    ter várias instâncias (ex.: agente + monitor de colaborador); resolver por user_id
    faria uma segunda instância sobrescrever a primeira em vez de criar uma linha nova."""
    existing = get_connection_by_instance(db, instance_id)
    encrypted_token = encrypt_secret(instance_token)

    if existing and existing.user_id == user_id:
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
        role=role,
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
    role: str = "agent",
) -> models.WhatsappConnection:
    """Ver docstring de upsert_connection — mesma regra: resolve por instance_id."""
    existing = get_connection_by_instance(db, instance_id)
    encrypted_token = encrypt_secret(instance_token) if instance_token else None

    if existing and existing.user_id == user_id:
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
        role=role,
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
