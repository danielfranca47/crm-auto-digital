"""
monitor_inbound_handler.py — Processa mensagens recebidas numa instância de
monitoramento de colaborador.

Completamente isolado do pipeline de IA do CRM:
- NUNCA chama guardrail.py / orchestrator.py / LLM
- NUNCA enfileira job whatsapp.send.local ou whatsapp.inbound.n8n
- Cria/atualiza um lead REAL no Kanban (categoria "monitoring"), diferente do
  Agente Espião (services/spy_agent/spy_inbound_handler.py), que só grava em
  spy_agent_messages e nunca cria leads.

Um mesmo telefone falando com dois colaboradores monitorados diferentes vira
dois leads distintos — a chave de deduplicação inclui o instance_id, não só
(user_id, phone).
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, Optional

from database import get_connection

logger = logging.getLogger(__name__)

MONITORING_CATEGORY = "monitoring"


def is_monitor_instance(instance_id: str) -> bool:
    """Verifica se instance_id está cadastrado como instância de monitoramento de colaborador."""
    if not instance_id:
        return False
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM collab_monitor_instances WHERE instance_id = ? LIMIT 1",
            (instance_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_monitor_info(instance_id: str) -> Optional[Dict[str, Any]]:
    """Retorna {user_id, collaborator_name} da instância monitor, ou None se não cadastrada."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, collaborator_name FROM collab_monitor_instances WHERE instance_id = ? LIMIT 1",
            (instance_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def find_or_create_monitor_lead(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    instance_id: str,
    phone_norm: str,
    payload: Dict[str, Any],
) -> int:
    """Chave de deduplicação (user_id, phone, instance_id) — nunca reaproveita o lead
    de outro colaborador monitorado, mesmo que seja o mesmo telefone."""
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT id FROM leads WHERE user_id = ? AND phone = ? AND collab_monitor_instance_id = ? LIMIT 1",
        (user_id, phone_norm, instance_id),
    ).fetchone()
    if existing:
        return int(existing["id"])

    wa_display_name = (payload.get("wa_display_name") or "").strip() or None
    contact_name = wa_display_name or phone_norm

    cur.execute(
        """
        INSERT INTO leads
            (user_id, companyName, contactName, phone, origin, category,
             wa_display_name, collab_monitor_instance_id, bot_disabled, bot_disabled_reason)
        VALUES (?, NULL, ?, ?, 'whatsapp_inbound', ?, ?, ?, 1, 'collab_monitor')
        """,
        (user_id, contact_name, phone_norm, MONITORING_CATEGORY, wa_display_name, instance_id),
    )
    lead_id = int(cur.lastrowid)
    conn.commit()
    logger.info(
        "[collab_monitor] lead criado lead_id=%s user_id=%s instance=%s phone=%s",
        lead_id,
        user_id,
        instance_id,
        phone_norm,
    )
    return lead_id


def _save_message(conn: sqlite3.Connection, *, lead_id: int, body: str, model: str) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (lead_id, channel, subject, body, model)
        VALUES (?, 'whatsapp', NULL, ?, ?)
        """,
        (lead_id, body, model),
    )
    return int(cur.lastrowid)


def handle_monitor_inbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recebe um payload normalizado (mesmo formato usado pelo spy handler) e:
      1. resolve a conta/colaborador dono da instância
      2. cria/atualiza o lead real (categoria "monitoring")
      3. grava a mensagem no histórico real do lead (`messages`)
    Nunca aciona guardrail, orchestrator, LLM ou fila de envio.

    Campos esperados no payload:
      instance_id, from (sender_phone e164), message_text, message_id,
      message_type, media_url (opcional), from_me
    """
    instance_id: str = payload.get("instance_id") or ""
    phone_norm: str = payload.get("from") or ""
    message_text: str = payload.get("message_text") or ""
    from_me: bool = bool(payload.get("from_me", False))

    monitor_info = get_monitor_info(instance_id)
    if monitor_info is None:
        logger.warning("[collab_monitor] instância não cadastrada: %s", instance_id)
        return {"status": "ignored", "reason": "monitor_instance_not_found"}

    if not phone_norm:
        logger.warning("[collab_monitor] sender ausente instance=%s", instance_id)
        return {"status": "ignored", "reason": "missing_sender"}

    if not message_text:
        # Mensagens de mídia sem texto (imagem/áudio/etc.) ainda não têm tratamento
        # dedicado nesta base — ficam para uma iteração futura (ver "Ajustes Possíveis").
        return {"status": "ignored", "reason": "missing_text"}

    user_id = int(monitor_info["user_id"])
    conn = get_connection()
    try:
        lead_id = find_or_create_monitor_lead(
            conn,
            user_id=user_id,
            instance_id=instance_id,
            phone_norm=phone_norm,
            payload=payload,
        )
        model = "human_agent" if from_me else "inbound"
        message_id = _save_message(conn, lead_id=lead_id, body=message_text, model=model)
        conn.commit()
    finally:
        conn.close()

    return {"status": "ok", "lead_id": lead_id, "message_id": message_id}
