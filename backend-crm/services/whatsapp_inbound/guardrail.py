from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict

logger = logging.getLogger(__name__)

INBOUND_DEFAULT_CATEGORY = "qualification"


def find_or_create_lead_by_phone(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    phone_norm: str,
    payload: Dict[str, Any],
) -> tuple[int, bool]:
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT id FROM leads WHERE user_id = ? AND phone = ? LIMIT 1",
        (user_id, phone_norm),
    ).fetchone()
    if existing:
        return int(existing["id"]), False

    contact_name = (
        payload.get("contact_name")
        or payload.get("sender_name")
        or payload.get("name")
        or phone_norm
    )
    company = payload.get("company")
    wa_display_name = (payload.get("wa_display_name") or "").strip() or None
    try:
        from services.agent_type import resolve_agent_type_for_user

        agent_type = resolve_agent_type_for_user(user_id=user_id)
    except Exception:
        agent_type = "agent_1"

    try:
        cur.execute(
            """
            INSERT INTO leads (user_id, companyName, contactName, phone, origin, category, agent_type, wa_display_name)
            VALUES (?, ?, ?, ?, 'whatsapp_inbound', ?, ?, ?)
            """,
            (user_id, company, contact_name, phone_norm, INBOUND_DEFAULT_CATEGORY, agent_type, wa_display_name),
        )
    except sqlite3.OperationalError:
        # Compat com schemas antigos usados em testes isolados (sem coluna agent_type).
        cur.execute(
            """
            INSERT INTO leads (user_id, companyName, contactName, phone, origin, category)
            VALUES (?, ?, ?, ?, 'whatsapp_inbound', ?)
            """,
            (user_id, company, contact_name, phone_norm, INBOUND_DEFAULT_CATEGORY),
        )
    lead_id = int(cur.lastrowid)
    logger.info(
        "inbound_guardrail_created lead_id=%s user_id=%s category=%s",
        lead_id,
        user_id,
        INBOUND_DEFAULT_CATEGORY,
    )
    return lead_id, True


def maybe_promote_lead_on_inbound(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    user_id: int,
    reason: str = "inbound_auto",
) -> bool:
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT category
          FROM leads
         WHERE id = ? AND user_id = ?
        """,
        (lead_id, user_id),
    ).fetchone()
    if not row:
        logger.info(
            "inbound_guardrail_skip lead_id=%s user_id=%s reason=lead_not_found",
            lead_id,
            user_id,
        )
        return False

    try:
        category_value = row["category"]
    except (TypeError, KeyError, IndexError):
        category_value = row[0] if row else None
    current_category = (category_value or "").strip().lower()
    if current_category not in {"to-prospect", "in-progress"}:
        logger.info(
            "inbound_guardrail_skip lead_id=%s user_id=%s current_category=%s reason=not_eligible",
            lead_id,
            user_id,
            current_category,
        )
        return False

    updated = cur.execute(
        """
        UPDATE leads
           SET category = ?,
               lastMovement = CURRENT_TIMESTAMP
         WHERE id = ? AND user_id = ?
           AND lower(trim(coalesce(category, ''))) IN ('to-prospect', 'in-progress')
        """,
        (INBOUND_DEFAULT_CATEGORY, lead_id, user_id),
    )
    if updated.rowcount == 0:
        logger.info(
            "inbound_guardrail_skip lead_id=%s user_id=%s current_category=%s reason=update_noop",
            lead_id,
            user_id,
            current_category,
        )
        return False

    notes = f"system:{current_category}->{INBOUND_DEFAULT_CATEGORY}|{reason}"
    cur.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, 'whatsapp', NULL, 'moved_stage', ?, ?)
        """,
        (lead_id, notes, user_id),
    )
    logger.info(
        "inbound_guardrail_promoted lead_id=%s user_id=%s from=%s to=%s reason=%s",
        lead_id,
        user_id,
        current_category,
        INBOUND_DEFAULT_CATEGORY,
        reason,
    )
    return True
