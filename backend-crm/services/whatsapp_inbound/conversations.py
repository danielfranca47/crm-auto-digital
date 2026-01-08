"""Helpers para controle de conversas Orion por telefone/mês."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional


def get_month_key(iso_or_any_timestamp: Optional[str]) -> str:
    """Retorna chave YYYY-MM usando o timestamp fornecido ou utcnow."""
    if iso_or_any_timestamp:
        try:
            dt = datetime.fromisoformat(str(iso_or_any_timestamp).replace(" ", "T"))
        except ValueError:
            dt = datetime.utcnow()
    else:
        dt = datetime.utcnow()
    return dt.strftime("%Y-%m")


def try_register_conversation(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    phone_e164: str,
    month_key: str,
    lead_id: Optional[int] = None,
) -> bool:
    """Insere conversa se não existir; retorna True se consumiu, False se já havia."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO orion_conversations (user_id, phone_e164, month_key, lead_id)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, phone_e164, month_key, lead_id),
        )
        return True
    except sqlite3.IntegrityError:
        cur.execute(
            """
            UPDATE orion_conversations
            SET last_seen_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND phone_e164 = ? AND month_key = ?
            """,
            (user_id, phone_e164, month_key),
        )
        return False


def get_conversations_count_for_month(
    conn: sqlite3.Connection, *, user_id: int, month_key: str
) -> int:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT COUNT(*) as total FROM orion_conversations WHERE user_id = ? AND month_key = ?",
        (user_id, month_key),
    ).fetchone()
    return int(row["total"]) if row else 0
