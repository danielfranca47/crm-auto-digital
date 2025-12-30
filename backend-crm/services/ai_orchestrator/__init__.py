"""Context bundle builder for AI orchestrator (ETAPA 1 MVP)."""
from datetime import datetime
from typing import Any, Dict, List

from fastapi import HTTPException
from pydantic import BaseModel, Field

from core_client import fetch_core_ai_profile
from database import get_connection
from security_core import CurrentUser
from services.ai_playbooks import get_playbook


class ContextBundle(BaseModel):
    user_id: int
    entitlements: Dict[str, Any]
    ai_profile: Dict[str, Any] | None = None
    playbook: Dict[str, Any]
    lead: Dict[str, Any]
    history: List[Dict[str, Any]] = Field(default_factory=list)
    next_action: str = "reply"
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _fetch_lead(lead_id: int, user_id: int) -> Dict[str, Any]:
    """Load a lead owned by the current user or raise HTTP 404."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    return {key: row[key] for key in row.keys()}


def build_context_bundle(
    current_user: CurrentUser,
    lead_id: int,
    inbound_message_text: str,
    channel: str = "whatsapp",
) -> ContextBundle:
    """
    Monta um ContextBundle interno para orquestração de IA sem expor endpoint público.
    """

    if not current_user.token:
        raise HTTPException(status_code=401, detail="Token ausente para consultar o core")

    entitlements = current_user.entitlements or {}
    ai_profile = fetch_core_ai_profile(current_user.token)
    template_key = ai_profile.get("template_key") if ai_profile else None
    playbook = get_playbook(template_key)

    lead_data = _fetch_lead(lead_id=lead_id, user_id=current_user.id)

    metadata = {
        "channel": channel,
        "inbound_message_text": inbound_message_text,
        "received_at": datetime.utcnow().isoformat(),
    }

    return ContextBundle(
        user_id=current_user.id,
        entitlements=entitlements,
        ai_profile=ai_profile or {},
        playbook=playbook,
        lead=lead_data,
        history=[],
        next_action=playbook.get("default_next_action", "reply"),
        metadata=metadata,
    )
