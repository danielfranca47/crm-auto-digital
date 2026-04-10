from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List

from database import get_connection

# Padrões que indicam mídia em mensagens salvas pelo inbound handler
_AUDIO_PATTERNS = [r"\[audio\]", r"\[voz\]", r"data:audio/"]
_IMAGE_PATTERNS = [r"\[imagem\]", r"\[image\]", r"\[foto\]", r"data:image/"]
_VIDEO_PATTERNS = [r"\[video\]", r"\[vídeo\]", r"data:video/"]


def load_real_conversations(
    user_id: int,
    limit_leads: int = 20,
    limit_msgs_per_lead: int = 30,
) -> List[Dict[str, Any]]:
    """
    Retorna até `limit_leads` leads reais do usuário (não sandbox), com até
    `limit_msgs_per_lead` mensagens cada. Exclui leads com menos de 5 mensagens.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        lead_rows = cur.execute(
            """
            SELECT l.id as lead_id
              FROM leads l
             WHERE l.user_id = ?
               AND l.is_playground = 0
             ORDER BY l.createdAt DESC
             LIMIT ?
            """,
            (user_id, limit_leads * 3),  # busca mais para filtrar os que têm poucas msgs
        ).fetchall()

        result: List[Dict[str, Any]] = []
        for lr in lead_rows:
            if len(result) >= limit_leads:
                break

            lead_id = int(lr["lead_id"])
            msgs = cur.execute(
                """
                SELECT body, model, message_type, createdAt
                  FROM messages
                 WHERE lead_id = ?
                 ORDER BY createdAt ASC
                 LIMIT ?
                """,
                (lead_id, limit_msgs_per_lead),
            ).fetchall()

            if len(msgs) < 5:
                continue  # sem dados suficientes

            result.append(
                {
                    "lead_id": lead_id,
                    "messages": [
                        {
                            "body": m["body"],
                            "model": m["model"] or "outbound",
                            "message_type": m["message_type"] or "text",
                            "created_at": m["createdAt"],
                        }
                        for m in msgs
                    ],
                }
            )

        return result
    finally:
        conn.close()


def detect_media_types(conversations: List[Dict[str, Any]]) -> Dict[str, int]:
    """Conta ocorrências de cada tipo de mídia nos corpos das mensagens."""
    counts: Dict[str, int] = {"audio": 0, "image": 0, "video": 0, "text": 0}

    for conv in conversations:
        for msg in conv.get("messages", []):
            body = (msg.get("body") or "").lower()
            msg_type = (msg.get("message_type") or "text").lower()

            if msg_type == "audio" or any(re.search(p, body) for p in _AUDIO_PATTERNS):
                counts["audio"] += 1
            elif msg_type == "image" or any(re.search(p, body) for p in _IMAGE_PATTERNS):
                counts["image"] += 1
            elif msg_type == "video" or any(re.search(p, body) for p in _VIDEO_PATTERNS):
                counts["video"] += 1
            else:
                counts["text"] += 1

    return counts


def format_conversations_for_llm(conversations: List[Dict[str, Any]], max_chars: int = 200) -> str:
    """Formata conversas no estilo [VENDEDOR]/[LEAD] para uso em prompts LLM."""
    lines: List[str] = []
    for i, conv in enumerate(conversations, 1):
        lines.append(f"--- Conversa {i} (lead_id={conv['lead_id']}) ---")
        for msg in conv["messages"]:
            role = "[LEAD]" if msg["model"] == "inbound" else "[VENDEDOR]"
            body = (msg["body"] or "")[:max_chars]
            lines.append(f"{role}: {body}")
        lines.append("")

    return "\n".join(lines)


def get_conversation_sample_stats(user_id: int) -> Dict[str, Any]:
    """Retorna estatísticas de conversas reais para preview antes da análise."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        row = cur.execute(
            """
            SELECT
                COUNT(DISTINCT l.id) as leads_count,
                COUNT(m.id) as messages_count,
                MIN(m.createdAt) as oldest,
                MAX(m.createdAt) as newest
              FROM leads l
              LEFT JOIN messages m ON m.lead_id = l.id
             WHERE l.user_id = ?
               AND l.is_playground = 0
            """,
            (user_id,),
        ).fetchone()

        leads_count = int(row["leads_count"] or 0)
        messages_count = int(row["messages_count"] or 0)

        return {
            "leads_count": leads_count,
            "messages_count": messages_count,
            "date_range": {
                "from": row["oldest"],
                "to": row["newest"],
            },
            "has_enough_data": leads_count >= 3 and messages_count >= 15,
        }
    finally:
        conn.close()
