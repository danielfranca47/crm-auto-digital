"""Funções auxiliares para lidar com webhooks WhatsApp inbound (ETAPA 3)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core_client import fetch_core_whatsapp_connection_resolve
from database import get_connection
from services.jobs_service import TYPE_WHATSAPP_INBOUND_N8N, create_job
from services.whatsapp_inbound.phone import normalize_phone


class InboundWebhookPayload(BaseModel):
    instance_id: str
    sender: str = Field(..., alias="from")
    message_text: Optional[str] = Field(None, alias="message_text")
    message: Optional[str] = Field(None, alias="message")
    body: Optional[str] = Field(None, alias="body")
    text: Optional[str] = Field(None, alias="text")
    message_id: Optional[str] = Field(None, alias="message_id")
    event_id: Optional[str] = Field(None, alias="event_id")
    timestamp: Optional[Any] = Field(None, alias="timestamp")
    provider: Optional[str] = None

    model_config = ConfigDict(extra="allow")

    def resolved_message_text(self) -> str:
        for candidate in (self.message_text, self.message, self.body, self.text):
            if candidate:
                return str(candidate)
        return ""

    def resolved_event_id(self) -> str:
        return str(self.message_id or self.event_id or "").strip()


def _mask_duplicate_error(exc: sqlite3.IntegrityError) -> bool:
    return "UNIQUE" in str(exc).upper()


def insert_inbound_event(
    conn: sqlite3.Connection,
    *,
    provider: str,
    instance_id: str,
    external_event_id: str,
    user_id: int,
) -> bool:
    """
    Tenta registrar o evento inbound. Retorna True se inseriu, False se já existia.
    """

    try:
        conn.execute(
            """
            INSERT INTO inbound_events (provider, instance_id, external_event_id, user_id)
            VALUES (?, ?, ?, ?)
            """,
            (provider, instance_id, external_event_id, user_id),
        )
        return True
    except sqlite3.IntegrityError as exc:  # idempotência
        if _mask_duplicate_error(exc):
            conn.rollback()
            return False
        raise


def find_or_create_lead_by_phone(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    phone_norm: str,
    payload: Dict[str, Any],
) -> int:
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT id FROM leads WHERE user_id = ? AND phone = ? LIMIT 1",
        (user_id, phone_norm),
    ).fetchone()
    if existing:
        return int(existing["id"])

    contact_name = payload.get("contact_name") or payload.get("sender_name") or payload.get("name")
    company = payload.get("company") or "WhatsApp inbound"
    cur.execute(
        """
        INSERT INTO leads (user_id, companyName, contactName, phone, origin, category)
        VALUES (?, ?, ?, ?, 'whatsapp_inbound', 'to-prospect')
        """,
        (user_id, company, contact_name, phone_norm),
    )
    return int(cur.lastrowid)


def save_inbound_message(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    body: str,
    user_id: int,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (lead_id, channel, subject, body, model)
        VALUES (?, 'whatsapp', NULL, ?, 'inbound')
        """,
        (lead_id, body),
    )
    message_id = int(cur.lastrowid)
    cur.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, 'whatsapp', ?, 'inbound_received', NULL, ?)
        """,
        (lead_id, message_id, user_id),
    )
    return message_id


def build_job_payload(
    *,
    lead_id: int,
    user_id: int,
    instance_id: str,
    provider: str,
    phone: str,
    message_text: str,
    external_event_id: str,
    received_at: str,
) -> Dict[str, Any]:
    return {
        "lead_id": lead_id,
        "user_id": user_id,
        "instance_id": instance_id,
        "provider": provider,
        "phone": phone,
        "message_text": message_text,
        "message_id": external_event_id,
        "received_at": received_at,
    }


def handle_inbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    parsed = InboundWebhookPayload(**payload)
    message_text = parsed.resolved_message_text()
    if not message_text:
        raise HTTPException(status_code=400, detail="message_text obrigatório")

    external_event_id = parsed.resolved_event_id()
    if not external_event_id:
        raise HTTPException(status_code=400, detail="message_id/event_id obrigatório")

    phone_norm = normalize_phone(parsed.sender)
    if not phone_norm:
        raise HTTPException(status_code=400, detail="Telefone inválido")

    connection = fetch_core_whatsapp_connection_resolve(parsed.instance_id)
    status = (connection.get("connection_status") or "").lower()
    if status and status != "active":
        raise HTTPException(status_code=403, detail="Conexão inativa")

    if connection.get("allow_orion") is False:
        raise HTTPException(status_code=403, detail="Plano não habilitado para Orion")

    provider = connection.get("provider") or parsed.provider or "uazapi"
    user_id = int(connection["user_id"])

    received_at = parsed.timestamp or datetime.utcnow().isoformat()
    received_iso = str(received_at).replace(" ", "T")

    with get_connection() as conn:
        inserted = insert_inbound_event(
            conn,
            provider=provider,
            instance_id=parsed.instance_id,
            external_event_id=external_event_id,
            user_id=user_id,
        )
        if not inserted:
            return {"status": "duplicate", "lead_id": None, "job_id": None}

        lead_id = find_or_create_lead_by_phone(
            conn,
            user_id=user_id,
            phone_norm=phone_norm,
            payload=payload,
        )
        save_inbound_message(conn, lead_id=lead_id, body=message_text, user_id=user_id)
        conn.commit()

    job_payload = build_job_payload(
        lead_id=lead_id,
        user_id=user_id,
        instance_id=parsed.instance_id,
        provider=provider,
        phone=phone_norm,
        message_text=message_text,
        external_event_id=external_event_id,
        received_at=received_iso,
    )
    job = create_job(job_type=TYPE_WHATSAPP_INBOUND_N8N, payload=job_payload, user_id=user_id)
    return {"status": "accepted", "lead_id": lead_id, "job_id": job.get("id")}
