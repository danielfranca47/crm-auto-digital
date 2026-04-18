"""
spy_inbound_handler.py — Processa mensagens recebidas na instância espiã.

Completamente isolado do pipeline do CRM:
- Não cria leads no Kanban
- Não dispara guardrails nem orquestrador de IA
- Armazena em spy_agent_messages
- Cria job spy.media.process para áudio e imagem
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from database import get_connection
from services.jobs_service import create_job

logger = logging.getLogger(__name__)

TYPE_SPY_MEDIA_PROCESS = "spy.media.process"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_spy_instance(instance_id: str) -> bool:
    """Verifica se instance_id está cadastrado como instância espiã de algum usuário."""
    if not instance_id:
        return False
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id FROM spy_agent_config WHERE spy_instance_id = ? LIMIT 1",
            (instance_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_spy_user_id(instance_id: str) -> int | None:
    """Retorna o user_id dono da instância espiã, ou None se não cadastrada."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id FROM spy_agent_config WHERE spy_instance_id = ? LIMIT 1",
            (instance_id,),
        ).fetchone()
        return int(row["user_id"]) if row else None
    finally:
        conn.close()


def handle_spy_inbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recebe um payload normalizado e persiste a mensagem em spy_agent_messages.

    Campos esperados no payload (mesmos do uazapi_webhook):
      instance_id, from (sender_phone), message_text, message_id,
      message_type (text|audio|image|video), media_url (opcional)
    """
    instance_id: str = payload.get("instance_id") or ""
    sender_phone: str = payload.get("from") or payload.get("sender") or ""
    message_text: str | None = payload.get("message_text") or payload.get("body")
    message_id: str | None = payload.get("message_id")
    message_type: str = (payload.get("message_type") or "text").lower()
    media_url: str | None = payload.get("media_url")
    from_me: bool = bool(payload.get("from_me", False))

    user_id = get_spy_user_id(instance_id)
    if user_id is None:
        logger.warning("[spy_inbound] instância não cadastrada: %s", instance_id)
        return {"ok": False, "reason": "spy_instance_not_found"}

    if not sender_phone:
        logger.warning("[spy_inbound] sender_phone ausente instance=%s", instance_id)
        return {"ok": False, "reason": "missing_sender"}

    received_at = _now_utc_iso()
    conn = get_connection()
    try:
        # Idempotência: ignora duplicata se external_message_id já existe
        existing = None
        if message_id:
            existing = conn.execute(
                "SELECT id FROM spy_agent_messages WHERE user_id = ? AND external_message_id = ?",
                (user_id, message_id),
            ).fetchone()

        if existing:
            logger.debug("[spy_inbound] duplicata ignorada message_id=%s", message_id)
            return {"ok": True, "duplicate": True}

        cur = conn.execute(
            """
            INSERT INTO spy_agent_messages
                (user_id, sender_phone, body, message_type, media_url, external_message_id, received_at, from_me)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                sender_phone,
                message_text,
                message_type,
                media_url,
                message_id,
                received_at,
                1 if from_me else 0,
            ),
        )
        conn.commit()
        spy_msg_id = cur.lastrowid

        logger.info(
            "[spy_inbound] mensagem salva id=%s user=%s sender=%s type=%s",
            spy_msg_id,
            user_id,
            sender_phone,
            message_type,
        )
    finally:
        conn.close()

    # Cria job assíncrono para processar mídia (áudio → Whisper, imagem → visão)
    if message_type in ("audio", "image") and media_url:
        try:
            create_job(
                job_type=TYPE_SPY_MEDIA_PROCESS,
                payload={
                    "spy_msg_id": spy_msg_id,
                    "user_id": user_id,
                    "message_type": message_type,
                    "media_url": media_url,
                },
                user_id=user_id,
            )
            logger.info("[spy_inbound] job mídia criado spy_msg_id=%s type=%s", spy_msg_id, message_type)
        except Exception as exc:
            logger.error("[spy_inbound] falha ao criar job mídia spy_msg_id=%s: %s", spy_msg_id, exc)

    return {"ok": True, "spy_msg_id": spy_msg_id, "message_type": message_type}
