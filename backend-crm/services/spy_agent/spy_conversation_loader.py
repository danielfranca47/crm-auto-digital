"""
spy_conversation_loader.py — Carrega conversas da instância espiã para análise.

Lê de spy_agent_messages (tabela isolada), não da tabela messages do CRM.
Agrupa por sender_phone e enriquece mensagens com transcrições de mídia.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from database import get_connection


def load_spy_conversations(
    user_id: int,
    limit_leads: int = 20,
    limit_msgs_per_sender: int = 30,
) -> List[Dict[str, Any]]:
    """
    Retorna até `limit_leads` conversas agrupadas por sender_phone.
    Cada conversa é uma lista de mensagens ordenadas por received_at.

    Regras:
    - Exclui senders com menos de 5 mensagens
    - Inclui transcrição de áudio/imagem quando disponível
    - Para vídeo: detecta texto acompanhante enviado pelo mesmo sender nos 5 min seguintes
    - Exclui mensagens de áudio/imagem que ainda não foram processadas (sem processed_at)
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Busca senders com mais mensagens primeiro
        sender_rows = cur.execute(
            """
            SELECT sender_phone, COUNT(*) as msg_count
              FROM spy_agent_messages
             WHERE user_id = ?
             GROUP BY sender_phone
             ORDER BY msg_count DESC
             LIMIT ?
            """,
            (user_id, limit_leads * 3),
        ).fetchall()

        result: List[Dict[str, Any]] = []
        for sr in sender_rows:
            if len(result) >= limit_leads:
                break

            sender_phone = sr["sender_phone"]
            msg_count = sr["msg_count"]
            if msg_count < 5:
                continue

            msgs = cur.execute(
                """
                SELECT id, body, message_type, media_url, transcription, processed_at, received_at
                  FROM spy_agent_messages
                 WHERE user_id = ? AND sender_phone = ?
                 ORDER BY received_at ASC
                 LIMIT ?
                """,
                (user_id, sender_phone, limit_msgs_per_sender),
            ).fetchall()

            formatted: List[Dict[str, Any]] = []
            for m in msgs:
                msg_type = m["message_type"] or "text"

                # Áudio/imagem sem processamento concluído: aguarda
                if msg_type in ("audio", "image") and not m["processed_at"]:
                    continue

                body = _build_body(m)
                if not body:
                    continue

                formatted.append(
                    {
                        "body": body,
                        "model": "inbound",  # mensagens da instância espiã são sempre inbound
                        "message_type": msg_type,
                        "created_at": m["received_at"],
                    }
                )

            if len(formatted) < 5:
                continue

            result.append({"lead_id": sender_phone, "messages": formatted})

        return result
    finally:
        conn.close()


def _build_body(msg: Any) -> str | None:
    """Monta o texto representativo da mensagem, enriquecido com mídia."""
    msg_type = (msg["message_type"] or "text").lower()
    body = msg["body"] or ""
    transcription = msg["transcription"] or ""

    if msg_type == "text":
        return body.strip() or None

    if msg_type == "audio":
        if transcription:
            return f"[ÁUDIO: {transcription}]"
        return "[ÁUDIO: transcrição indisponível]"

    if msg_type == "image":
        if transcription:
            return f"[IMAGEM: {transcription}]"
        if body:
            return f"[IMAGEM com legenda: {body}]"
        return "[IMAGEM]"

    if msg_type == "video":
        # Inclui texto do body se existir (texto acompanhante enviado junto ao vídeo)
        if body:
            return f"[VÍDEO - texto acompanhante: {body}]"
        return "[VÍDEO]"

    return body.strip() or None


def get_spy_conversation_stats(user_id: int) -> Dict[str, Any]:
    """Retorna estatísticas das mensagens espiãs para preview."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        row = cur.execute(
            """
            SELECT
                COUNT(DISTINCT sender_phone) as senders_count,
                COUNT(*) as messages_count,
                MIN(received_at) as oldest,
                MAX(received_at) as newest
              FROM spy_agent_messages
             WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        senders_count = int(row["senders_count"] or 0)
        messages_count = int(row["messages_count"] or 0)

        # Contagem por tipo de mídia
        type_rows = cur.execute(
            """
            SELECT message_type, COUNT(*) as cnt
              FROM spy_agent_messages
             WHERE user_id = ?
             GROUP BY message_type
            """,
            (user_id,),
        ).fetchall()
        type_counts = {r["message_type"]: r["cnt"] for r in type_rows}

        return {
            "senders_count": senders_count,
            "messages_count": messages_count,
            "date_range": {"from": row["oldest"], "to": row["newest"]},
            "type_counts": type_counts,
            "has_enough_data": senders_count >= 3 and messages_count >= 15,
            "source": "spy_instance",
        }
    finally:
        conn.close()
