from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List

from fastapi import HTTPException
from pydantic import BaseModel, Field

from core_client import fetch_core_ai_profile, fetch_core_ai_profile_resolve
from database import get_connection
from security_core import CurrentUser
from services.ai_playbooks import get_playbook
from services.ai_orchestrator.history import get_recent_history
from services.ai_orchestrator.inbound_event import InboundEvent

logger = logging.getLogger(__name__)


class ContextBundle(BaseModel):
    user_id: int
    entitlements: Dict[str, Any] = Field(default_factory=dict)
    ai_profile: Dict[str, Any] | None = None
    playbook: Dict[str, Any]
    lead: Dict[str, Any]
    history: List[Dict[str, Any]]
    next_action: str = "reply"
    metadata: Dict[str, Any]
    conversation_goal: str | None = None


def build_context_bundle(
    current_user: CurrentUser,
    lead_id: int,
    inbound_message_text: str,
    channel: str = "whatsapp",
) -> ContextBundle:
    """Legacy builder for authenticated flows (still used by manual script)."""

    if not current_user.token:
        raise HTTPException(status_code=401, detail="Token ausente para consultar o core")

    entitlements = current_user.entitlements or {}
    ai_profile = fetch_core_ai_profile(current_user.token)
    template_key = ai_profile.get("template_key") if ai_profile else None
    if ai_profile is not None and not ai_profile.get("agent_mode"):
        template_norm = str(template_key or "")
        if template_norm.startswith("closer"):
            ai_profile["agent_mode"] = "direto"
        elif template_norm.startswith("consult"):
            ai_profile["agent_mode"] = "consultivo"
        else:
            ai_profile["agent_mode"] = "agenda"
    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads WHERE id = ? AND user_id = ?", (lead_id, current_user.id))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    lead_data = {key: row[key] for key in row.keys()}

    metadata = {
        "channel": channel,
        "inbound_message_text": inbound_message_text,
        "received_at": datetime.utcnow().isoformat(),
    }

    history: List[Dict[str, Any]] = []

    return ContextBundle(
        user_id=current_user.id,
        entitlements=entitlements,
        ai_profile=ai_profile or {},
        playbook=playbook,
        lead=lead_data,
        history=history,
        next_action=playbook.get("default_next_action", "reply"),
        metadata=metadata,
        conversation_goal="qualify" if not history else "advance",
    )


def _load_lead(user_id: int, lead_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return {key: row[key] for key in row.keys()}


def build_context_bundle_from_inbound(event: InboundEvent) -> ContextBundle:
    ai_profile: Dict[str, Any] | None = None
    ai_profile_status = "ok"
    try:
        ai_profile = fetch_core_ai_profile_resolve(event.user_id)
    except HTTPException as exc:  # fallback
        logger.warning("AI profile resolve failed: %s", exc)
        ai_profile_status = "unavailable"
    else:
        if ai_profile is None:
            ai_profile_status = "not_found"

    template_key = ai_profile.get("template_key") if ai_profile else None
    if ai_profile is not None and not ai_profile.get("agent_mode"):
        template_norm = str(template_key or "")
        if template_norm.startswith("closer"):
            ai_profile["agent_mode"] = "direto"
        elif template_norm.startswith("consult"):
            ai_profile["agent_mode"] = "consultivo"
        else:
            ai_profile["agent_mode"] = "agenda"
    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"

    lead_data = _load_lead(user_id=event.user_id, lead_id=event.lead_id)
    history = get_recent_history(event.lead_id)
    conversation_goal = "qualify" if len(history) <= 1 else "advance"

    metadata = {
        "channel": event.channel,
        "inbound_message_text": event.message_text,
        "received_at": event.received_at or datetime.utcnow().isoformat(),
        "message_id": event.message_id,
        "instance_id": event.instance_id,
        "provider": event.provider,
        "phone": event.phone,
        "ai_profile_status": ai_profile_status if ai_profile is None else "ok",
    }

    return ContextBundle(
        user_id=event.user_id,
        entitlements={},
        ai_profile=ai_profile or {},
        playbook=playbook,
        lead=lead_data,
        history=history,
        next_action=playbook.get("default_next_action", "reply"),
        metadata=metadata,
        conversation_goal=conversation_goal,
    )


def decide_next_action(bundle: ContextBundle) -> Dict[str, Any]:
    text = (bundle.metadata.get("inbound_message_text") or "").strip()
    if not text:
        return {"next_action": "ignore", "reason": "empty_message", "questions": []}

    lowered = text.lower()
    for keyword in ("humano", "atendente", "ligar"):
        if keyword in lowered:
            return {"next_action": "handoff", "reason": f"keyword:{keyword}", "questions": []}

    history = bundle.history or []
    qualification_questions = bundle.playbook.get("qualification_questions") or []
    outbound_present = any((msg.get("model") or "").lower() == "outbound" for msg in history)

    if (len(history) <= 1 or not outbound_present) and qualification_questions:
        return {
            "next_action": "ask_qualification",
            "reason": "qualification_needed",
            "questions": qualification_questions[:2],
        }

    return {"next_action": "reply", "reason": "default_reply", "questions": []}


def log_ai_decision(
    *,
    lead_id: int,
    user_id: int,
    decision: Dict[str, Any],
    template_key: str,
    received_at: str | None,
    message_id: str | None,
) -> None:
    notes = {
        "next_action": decision.get("next_action"),
        "reason": decision.get("reason"),
        "template_key": template_key,
        "questions": decision.get("questions") or [],
        "received_at": received_at,
        "message_id": message_id,
    }

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, 'whatsapp', NULL, 'ai_decided', ?, ?)
            """,
            (lead_id, json.dumps(notes, ensure_ascii=False), user_id),
        )
        conn.commit()
