from __future__ import annotations

import json
import sqlite3
from typing import Literal, Optional

from services.lead_category_policy import BOT_STRUCTURALLY_INACTIVE_CATEGORIES

GLOBAL_PAUSE_REASON = "global_pause"

_EXCLUDED_CATEGORIES_PLACEHOLDERS = ", ".join("?" for _ in BOT_STRUCTURALLY_INACTIVE_CATEGORIES)


def get_status(conn: sqlite3.Connection, *, user_id: int) -> dict:
    row = conn.execute(
        "SELECT is_paused, paused_at FROM bot_global_pause_state WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return {"is_paused": False, "paused_at": None}
    return {"is_paused": bool(row["is_paused"]), "paused_at": row["paused_at"]}


def _log_bot_disabled_changed(
    cur: sqlite3.Cursor, *, lead_id: int, user_id: int, disabled: bool, reason: Optional[str]
) -> None:
    notes = {"disabled": disabled}
    if reason:
        notes["reason"] = reason
    cur.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'bot_disabled_changed', ?, ?)
        """,
        (lead_id, json.dumps(notes, ensure_ascii=False), user_id),
    )


def _upsert_pause_state(cur: sqlite3.Cursor, *, user_id: int, is_paused: bool) -> None:
    if is_paused:
        cur.execute(
            """
            INSERT INTO bot_global_pause_state (user_id, is_paused, paused_at, updated_at)
            VALUES (?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                is_paused = 1,
                paused_at = CASE
                    WHEN bot_global_pause_state.is_paused = 1 THEN bot_global_pause_state.paused_at
                    ELSE CURRENT_TIMESTAMP
                END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id,),
        )
    else:
        cur.execute(
            """
            INSERT INTO bot_global_pause_state (user_id, is_paused, paused_at, updated_at)
            VALUES (?, 0, NULL, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                is_paused = 0,
                paused_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id,),
        )


def pause_all(conn: sqlite3.Connection, *, user_id: int) -> dict:
    """Pausa o bot para todos os leads ativos do usuário, exceto categorias
    estruturalmente inativas. Idempotente: leads já pausados (manual ou por
    regra de negócio) não são tocados nem têm o motivo sobrescrito."""
    cur = conn.cursor()
    rows = cur.execute(
        f"""
        SELECT id FROM leads
         WHERE user_id = ? AND bot_disabled = 0
           AND lower(trim(coalesce(category, ''))) NOT IN ({_EXCLUDED_CATEGORIES_PLACEHOLDERS})
        """,
        (user_id, *BOT_STRUCTURALLY_INACTIVE_CATEGORIES),
    ).fetchall()
    lead_ids = [int(r["id"]) for r in rows]

    if lead_ids:
        cur.executemany(
            """
            UPDATE leads
               SET bot_disabled = 1,
                   bot_disabled_reason = ?,
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            [(GLOBAL_PAUSE_REASON, lead_id) for lead_id in lead_ids],
        )
        for lead_id in lead_ids:
            _log_bot_disabled_changed(
                cur, lead_id=lead_id, user_id=user_id, disabled=True, reason=GLOBAL_PAUSE_REASON
            )

    _upsert_pause_state(cur, user_id=user_id, is_paused=True)
    return {"paused_count": len(lead_ids)}


def resume_all(
    conn: sqlite3.Connection, *, user_id: int, mode: Literal["previously_paused", "all"]
) -> dict:
    """Reativa o bot conforme o modo escolhido no popup de retomada:
    - previously_paused: só os leads desativados pela própria pausa geral.
    - all: todos os leads desativados (manual ou por regra de negócio),
      exceto categorias estruturalmente inativas.
    """
    cur = conn.cursor()

    if mode == "previously_paused":
        rows = cur.execute(
            """
            SELECT id FROM leads
             WHERE user_id = ? AND bot_disabled = 1 AND bot_disabled_reason = ?
            """,
            (user_id, GLOBAL_PAUSE_REASON),
        ).fetchall()
    else:
        rows = cur.execute(
            f"""
            SELECT id FROM leads
             WHERE user_id = ? AND bot_disabled = 1
               AND lower(trim(coalesce(category, ''))) NOT IN ({_EXCLUDED_CATEGORIES_PLACEHOLDERS})
            """,
            (user_id, *BOT_STRUCTURALLY_INACTIVE_CATEGORIES),
        ).fetchall()

    lead_ids = [int(r["id"]) for r in rows]
    if lead_ids:
        cur.executemany(
            """
            UPDATE leads
               SET bot_disabled = 0,
                   bot_disabled_reason = NULL,
                   lastMovement = CURRENT_TIMESTAMP
             WHERE id = ?
            """,
            [(lead_id,) for lead_id in lead_ids],
        )
        for lead_id in lead_ids:
            _log_bot_disabled_changed(cur, lead_id=lead_id, user_id=user_id, disabled=False, reason=None)

    _upsert_pause_state(cur, user_id=user_id, is_paused=False)
    return {"resumed_count": len(lead_ids)}
