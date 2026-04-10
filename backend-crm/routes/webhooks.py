"""Routers de webhooks externos (WhatsApp inbound + pagamento)."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from core_client import fetch_core_ai_profile_by_webhook_secret
from database import get_connection
from services.followup_state import stop_followup_for_lead_category
from services.jobs_service import TYPE_WHATSAPP_SEND, create_job
from services.phone_normalizer import PhoneNormalizationError, normalize_to_e164
from services.spy_agent.spy_inbound_handler import handle_spy_inbound, is_spy_instance
from services.whatsapp_inbound.inbound_handler import InboundWebhookPayload, handle_inbound

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)


_GROUP_JID_SUFFIX = "@g.us"


def _is_group_marker(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().endswith(_GROUP_JID_SUFFIX)


def _has_group_jid(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_norm = str(key).strip().lower()
            if key_norm in {"remotejid", "chatid", "id"} and _is_group_marker(value):
                return True
            if _has_group_jid(value):
                return True
    elif isinstance(payload, list):
        for item in payload:
            if _has_group_jid(item):
                return True
    elif _is_group_marker(payload):
        return True
    return False


def is_group_message_payload(payload: Dict[str, Any]) -> bool:
    chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}

    if chat.get("isGroup") is True:
        return True
    if data.get("isGroup") is True or bool(data.get("groupId")):
        return True
    if message.get("isGroup") is True or bool(message.get("groupId")):
        return True

    if _has_group_jid(payload):
        return True

    if chat and message and chat.get("type") == "group":
        return True

    return False


@router.post("/whatsapp/inbound")
def whatsapp_inbound_webhook(
    payload: InboundWebhookPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    expected_secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="CRM_WEBHOOK_SECRET não configurado")
    if not x_webhook_secret or x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    return handle_inbound(payload.model_dump(by_alias=True))


@router.post("/whatsapp/uazapi")
def whatsapp_uazapi_webhook(
    payload: Dict[str, Any],
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    secret: str | None = Query(default=None),
):
    expected_secret = os.getenv("CRM_WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="CRM_WEBHOOK_SECRET não configurado")
    if (x_webhook_secret != expected_secret) and (secret != expected_secret):
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    def _normalize_e164(value: str | None) -> str:
        if not value:
            return ""
        try:
            return normalize_to_e164(value)
        except PhoneNormalizationError:
            digits = re.sub(r"\D+", "", str(value))
            if not digits:
                return ""
            try:
                return normalize_to_e164(f"+{digits}")
            except PhoneNormalizationError:
                return ""

    event = payload.get("event") or payload.get("EventType") or payload.get("type")
    instance_id = payload.get("instance") or payload.get("instanceName")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}

    def _resolve_sender_e164() -> str:
        chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
        chat_phone = chat.get("phone")
        sender_phone = data.get("sender") or message.get("sender_pn")
        return _normalize_e164(chat_phone) or _normalize_e164(sender_phone)

    sender = _resolve_sender_e164()
    message_id = data.get("messageId") or data.get("id") or message.get("messageid") or message.get("id")
    message_type = data.get("messageType") or message.get("type") or message.get("messageType")
    message_text = data.get("text") or message.get("text") or message.get("content")
    from_me = data.get("fromMe") is True or message.get("fromMe") is True

    logger.info(
        "uazapi webhook event=%s instance=%s sender=%s message_id=%s",
        event,
        instance_id,
        sender,
        message_id,
    )

    if event not in {"messages", "message"}:
        return {"status": "ignored", "reason": "event_not_messages"}

    # ── Roteamento: instância espiã → spy handler (aceita mídia e fromMe) ─────
    # Deve vir ANTES do filtro from_me: o spy precisa capturar mensagens do
    # vendedor (fromMe=True) para aprender o estilo de comunicação.
    if instance_id and is_spy_instance(instance_id):
        is_group = is_group_message_payload(payload)
        if not is_group:
            media_url = (
                data.get("mediaUrl")
                or data.get("media_url")
                or message.get("mediaUrl")
                or message.get("media_url")
            )
            # sender já vem de _resolve_sender_e164() que usa chat.phone (lead) como prioridade,
            # então tanto inbound quanto fromMe ficam agrupados pelo phone do lead.
            spy_payload = {
                "instance_id": instance_id,
                "from": sender,
                "message_text": message_text,
                "message_id": message_id,
                "message_type": message_type or "text",
                "media_url": media_url,
                "from_me": from_me,
            }
            return handle_spy_inbound(spy_payload)
    # ─────────────────────────────────────────────────────────────────────────

    if from_me:
        return {"status": "ignored", "reason": "from_me"}

    is_group = is_group_message_payload(payload)
    if is_group:
        logger.info(
            "uazapi webhook ignored group_message instance=%s sender=%s message_id=%s",
            instance_id,
            sender,
            message_id,
        )
        return {"status": "ignored", "reason": "group_message"}

    if message_type and message_type != "text":
        return {"status": "ignored", "reason": "not_text"}
    if not message_text:
        return {"status": "ignored", "reason": "missing_text"}
    if not instance_id or not sender or not message_id:
        detail = "Payload Uazapi incompleto"
        if not sender:
            detail = "Payload Uazapi incompleto (sender inválido)"
        raise HTTPException(status_code=400, detail=detail)

    inbound_payload = {
        "instance_id": instance_id,
        "from": sender,
        "message_text": message_text,
        "message_id": message_id,
        "timestamp": message.get("messageTimestamp") or data.get("messageTimestamp"),
        "provider": "uazapi",
        "is_group": False,
    }

    return handle_inbound(inbound_payload)


# ---------------------------------------------------------------------------
# Normalização de payloads de pagamento por gateway
# ---------------------------------------------------------------------------

def _normalize_payment_payload(gateway: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai campos canônicos de pagamento conforme o gateway."""
    g = gateway.lower()

    if g == "hotmart":
        data = raw.get("data") or {}
        buyer = data.get("buyer") or {}
        purchase = data.get("purchase") or {}
        return {
            "checkout_token": purchase.get("src") or raw.get("src"),
            "email": buyer.get("email"),
            "phone": buyer.get("phone"),
            "document": buyer.get("document"),
            "status": (purchase.get("status") or "").upper(),
        }

    if g == "kiwify":
        customer = raw.get("Customer") or {}
        return {
            "checkout_token": raw.get("tracking_source"),
            "email": customer.get("email"),
            "phone": customer.get("mobile"),
            "document": None,
            "status": (raw.get("order_status") or raw.get("status") or "").upper(),
        }

    if g == "stripe":
        obj = raw.get("data", {}).get("object") or raw
        metadata = obj.get("metadata") or {}
        return {
            "checkout_token": metadata.get("lead_id"),
            "email": obj.get("customer_email") or obj.get("receipt_email"),
            "phone": None,
            "document": None,
            "status": (raw.get("type") or "").replace("payment_intent.", "").upper(),
        }

    # Genérico
    return {
        "checkout_token": raw.get("src") or raw.get("ref"),
        "email": raw.get("email"),
        "phone": raw.get("phone"),
        "document": raw.get("document"),
        "status": (raw.get("status") or "").upper(),
    }


def _is_payment_confirmed(status: str) -> bool:
    confirmed = {"APPROVED", "COMPLETE", "COMPLETED", "SUCCEEDED", "PAID", "CONFIRMED"}
    return any(status.startswith(s) or s in status for s in confirmed)


# ---------------------------------------------------------------------------
# Busca do lead por camadas
# ---------------------------------------------------------------------------

def _find_lead_by_checkout_token(conn, token: str, user_id: int) -> Optional[Dict]:
    if not token:
        return None
    row = conn.execute(
        "SELECT * FROM leads WHERE checkout_token = ? AND user_id = ? LIMIT 1",
        (str(token), user_id),
    ).fetchone()
    return dict(row) if row else None


def _find_lead_by_phone(conn, phone: str, user_id: int) -> Optional[Dict]:
    if not phone:
        return None
    try:
        normalized = normalize_to_e164(phone)
    except PhoneNormalizationError:
        digits = re.sub(r"\D+", "", phone)
        if not digits:
            return None
        try:
            normalized = normalize_to_e164(f"+{digits}")
        except PhoneNormalizationError:
            return None
    row = conn.execute(
        "SELECT * FROM leads WHERE phone = ? AND user_id = ? LIMIT 1",
        (normalized, user_id),
    ).fetchone()
    return dict(row) if row else None


def _find_lead_by_email(conn, email: str, user_id: int) -> Optional[Dict]:
    if not email:
        return None
    row = conn.execute(
        "SELECT * FROM leads WHERE lower(email) = lower(?) AND user_id = ? LIMIT 1",
        (email, user_id),
    ).fetchone()
    return dict(row) if row else None


def _find_lead_by_document(conn, document: str, user_id: int) -> Optional[Dict]:
    if not document:
        return None
    row = conn.execute(
        "SELECT * FROM leads WHERE observations LIKE ? AND user_id = ? LIMIT 1",
        (f"%{document}%", user_id),
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Ações pós-pagamento
# ---------------------------------------------------------------------------

def _move_lead_to_client_list(conn, lead_id: int, user_id: int) -> None:
    conn.execute(
        "UPDATE leads SET category = 'client-list', lastMovement = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    )
    stop_followup_for_lead_category(conn, lead_id=lead_id, user_id=user_id, new_category="client-list")


def _create_notification(conn, user_id: int, lead_id: Optional[int], ntype: str, body: str) -> None:
    try:
        conn.execute(
            "INSERT INTO notifications (user_id, lead_id, type, body) VALUES (?, ?, ?, ?)",
            (user_id, lead_id, ntype, body),
        )
    except Exception:
        pass


def _save_unmatched_event(conn, gateway: str, raw: Dict, normalized: Dict) -> None:
    conn.execute(
        """INSERT INTO unmatched_payment_events
           (gateway, raw_payload, buyer_email, buyer_phone, buyer_document, checkout_token)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            gateway,
            json.dumps(raw, ensure_ascii=False),
            normalized.get("email"),
            normalized.get("phone"),
            normalized.get("document"),
            str(normalized.get("checkout_token") or ""),
        ),
    )


def _schedule_post_purchase_jobs(lead_id: int, user_id: int) -> None:
    """Cria job de onboarding (imediato), upsell (+30min) e NPS (+7 dias)."""
    now = datetime.utcnow()

    create_job(
        job_type="whatsapp.onboarding",
        payload={"lead_id": lead_id, "user_id": user_id, "trigger": "payment_confirmed"},
        user_id=user_id,
    )
    create_job(
        job_type="whatsapp.upsell",
        payload={"lead_id": lead_id, "user_id": user_id},
        user_id=user_id,
        scheduled_at=now + timedelta(minutes=30),
    )
    create_job(
        job_type="whatsapp.nps",
        payload={"lead_id": lead_id, "user_id": user_id},
        user_id=user_id,
        scheduled_at=now + timedelta(days=7),
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/payment/{gateway}")
def payment_webhook(
    gateway: str,
    raw_payload: Dict[str, Any],
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
    token: Optional[str] = Query(default=None),
):
    """
    Webhook de confirmação de pagamento.
    Autenticado pelo payment_webhook_secret do AI Profile (via header X-Webhook-Secret ou query ?token=).
    """
    secret = x_webhook_secret or token
    if not secret:
        raise HTTPException(status_code=401, detail="Webhook secret ausente")

    ai_profile = fetch_core_ai_profile_by_webhook_secret(secret)
    if not ai_profile:
        raise HTTPException(status_code=401, detail="Webhook secret inválido")

    user_id: int = int(ai_profile["user_id"])
    normalized = _normalize_payment_payload(gateway, raw_payload)

    logger.info(
        "payment_webhook gateway=%s user_id=%s status=%s checkout_token=%s email=%s",
        gateway,
        user_id,
        normalized.get("status"),
        normalized.get("checkout_token"),
        normalized.get("email"),
    )

    if not _is_payment_confirmed(normalized.get("status") or ""):
        return {"status": "ignored", "reason": "payment_not_confirmed", "payment_status": normalized.get("status")}

    with get_connection() as conn:
        # 1. Token do link (mais confiável)
        lead = _find_lead_by_checkout_token(conn, normalized.get("checkout_token") or "", user_id)
        # 2. Telefone normalizado
        if not lead:
            lead = _find_lead_by_phone(conn, normalized.get("phone") or "", user_id)
        # 3. E-mail
        if not lead:
            lead = _find_lead_by_email(conn, normalized.get("email") or "", user_id)
        # 4. Documento (CPF / CNPJ)
        if not lead:
            lead = _find_lead_by_document(conn, normalized.get("document") or "", user_id)

        if not lead:
            _save_unmatched_event(conn, gateway, raw_payload, normalized)
            _create_notification(
                conn,
                user_id=user_id,
                lead_id=None,
                ntype="payment_unmatched",
                body=(
                    f"Pagamento confirmado sem lead vinculado — revisão necessária. "
                    f"Gateway: {gateway} | Email: {normalized.get('email')} | "
                    f"Telefone: {normalized.get('phone')}"
                ),
            )
            conn.commit()
            logger.warning(
                "payment_webhook unmatched gateway=%s email=%s phone=%s",
                gateway,
                normalized.get("email"),
                normalized.get("phone"),
            )
            # Sempre 200 — gateway não deve retentar
            return {"status": "unmatched", "message": "Pagamento registrado para revisão manual"}

        lead_id = int(lead["id"])
        _move_lead_to_client_list(conn, lead_id=lead_id, user_id=user_id)
        _create_notification(
            conn,
            user_id=user_id,
            lead_id=lead_id,
            ntype="payment_confirmed",
            body=f"Pagamento confirmado — lead movido para client-list. Gateway: {gateway}",
        )
        conn.commit()

    _schedule_post_purchase_jobs(lead_id=lead_id, user_id=user_id)

    logger.info("payment_webhook matched lead_id=%s user_id=%s gateway=%s", lead_id, user_id, gateway)
    return {"status": "ok", "lead_id": lead_id}
