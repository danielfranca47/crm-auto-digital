from __future__ import annotations

import json
import sqlite3
from typing import Optional


def apply_closing_bot_disable_side_effect(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    user_id: Optional[int],
    old_category: Optional[str],
    new_category: Optional[str],
    agent_mode_normalized: Optional[str] = None,
    presentation_variant: Optional[str] = None,
    meeting_scheduled: Optional[bool] = None,
    outcome: Optional[str] = None,
) -> bool:
    """Aplica side-effect de negócio: ao entrar em closing, desabilita bot.

    Idempotente: só atualiza/loga quando há transição para closing E bot ainda ativo.
    """
    old_norm = (old_category or "").strip().lower()
    new_norm = (new_category or "").strip().lower()
    if new_norm != "closing" or old_norm == "closing":
        return False

    mode_norm = (agent_mode_normalized or "").strip().lower()
    variant_norm = (presentation_variant or "").strip().lower()
    outcome_norm = (outcome or "").strip().lower()
    has_runtime_context = any(
        value is not None
        for value in (agent_mode_normalized, presentation_variant, meeting_scheduled, outcome)
    )

    # Backward compatibility: sem contexto adicional, mantém regra histórica
    # (entrar em closing desativa bot).
    should_disable = True
    if has_runtime_context:
        should_disable = bool(meeting_scheduled) or mode_norm == "agenda" or outcome_norm == "won"
        if not should_disable and (variant_norm == "sales" or mode_norm == "direto"):
            return False
        if not should_disable:
            return False

    cur = conn.cursor()
    row = cur.execute("SELECT bot_disabled FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        return False
    if int(row["bot_disabled"] or 0) == 1:
        return False

    cur.execute(
        """
        UPDATE leads
           SET bot_disabled = 1,
               bot_disabled_reason = 'category_closing',
               lastMovement = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (lead_id,),
    )
    notes = {"disabled": True, "reason": "category_closing"}
    cur.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'bot_disabled_changed', ?, ?)
        """,
        (lead_id, json.dumps(notes, ensure_ascii=False), user_id),
    )
    return True


def apply_disqualified_bot_disable_side_effect(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    user_id: Optional[int],
    old_category: Optional[str],
    new_category: Optional[str],
) -> bool:
    """Aplica side-effect de negócio: ao entrar em disqualified, desabilita bot.

    Idempotente: só atualiza/loga quando há transição para disqualified E bot ainda ativo.
    Reativação continua manual (mesmo comportamento unidirecional de closing).
    """
    old_norm = (old_category or "").strip().lower()
    new_norm = (new_category or "").strip().lower()
    if new_norm != "disqualified" or old_norm == "disqualified":
        return False

    cur = conn.cursor()
    row = cur.execute("SELECT bot_disabled FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        return False
    if int(row["bot_disabled"] or 0) == 1:
        return False

    cur.execute(
        """
        UPDATE leads
           SET bot_disabled = 1,
               bot_disabled_reason = 'category_disqualified',
               lastMovement = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (lead_id,),
    )
    notes = {"disabled": True, "reason": "category_disqualified"}
    cur.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'bot_disabled_changed', ?, ?)
        """,
        (lead_id, json.dumps(notes, ensure_ascii=False), user_id),
    )
    return True
