from __future__ import annotations

import sqlite3
from typing import Dict, List

from database import get_connection


def get_recent_history(lead_id: int, limit: int = 20) -> List[Dict[str, str]]:
    """Retorna histórico recente de mensagens de um lead em ordem cronológica."""

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, channel, body, model, createdAt
            FROM messages
            WHERE lead_id = ?
            ORDER BY createdAt DESC
            LIMIT ?
            """,
            (lead_id, limit),
        ).fetchall()

    # inverter para ordem cronológica
    return [dict(row) for row in reversed(rows)]
