from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from core_client import fetch_core_ai_profile, fetch_core_ai_profile_resolve
from database import get_connection
from security_core import CurrentUser
from services.ai_playbooks import get_playbook
from services.ai_orchestrator.history import get_recent_history
from services.ai_orchestrator.inbound_event import InboundEvent
from services.qualification_state import get_qualification_state

logger = logging.getLogger(__name__)


def _resolve_presentation_contract(
    *,
    ai_profile: Dict[str, Any] | None,
    agent_mode_normalized: str,
) -> Dict[str, Any]:
    profile = ai_profile or {}
    raw_variant = str(profile.get("presentation_variant") or "").strip().lower()
    raw_hybrid = str(profile.get("hybrid_flow_style") or "").strip().lower()

    valid_variants = {"sales", "scheduler"}
    valid_hybrid_styles = {"offer_then_schedule", "schedule_then_offer"}

    if raw_variant in valid_variants:
        variant = raw_variant
        source = "ai_profile"
    elif agent_mode_normalized == "direto":
        variant = "sales"
        source = "agent_mode_default"
    elif agent_mode_normalized in {"agenda", "consultivo"}:
        variant = "scheduler"
        source = "agent_mode_default"
    else:
        variant = "scheduler"
        source = "fallback"

    hybrid_style = raw_hybrid if raw_hybrid in valid_hybrid_styles else None
    if hybrid_style and source != "ai_profile":
        source = f"{source}+hybrid"

    offer_pack = profile.get("offer_pack")
    if isinstance(offer_pack, str):
        try:
            parsed = json.loads(offer_pack)
            offer_pack = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            offer_pack = None
    elif not isinstance(offer_pack, dict):
        offer_pack = None

    return {
        "presentation_variant": variant,
        "presentation_variant_source": source,
        "hybrid_flow_style": hybrid_style,
        "offer_pack": offer_pack,
    }

def _normalize_agent_mode_for_bundle(ai_profile: Dict[str, Any] | None, template_key: str | None) -> str:
    profile = ai_profile or {}
    mode = str(profile.get("agent_mode") or "").strip().lower()
    if mode in {"consultivo", "agenda", "direto"}:
        return mode
    if mode == "closer":
        return "direto"
    if mode in {"sdr_scheduler", "sdr"}:
        return "agenda"
    template_norm = str(template_key or "")
    if template_norm.startswith("hybrid_scheduler"):
        return "agenda"
    if template_norm.startswith("closer"):
        return "direto"
    if template_norm.startswith("consult"):
        return "consultivo"
    return "agenda"


def apply_mode_overrides(
    playbook: Dict[str, Any],
    agent_mode_normalized: str,
    ai_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    merged = dict(playbook or {})
    if agent_mode_normalized == "consultivo":
        merged.update({
            "max_chars": 700,
            "qualification_depth": "high",
            "max_questions_per_turn": 1,
            "must_handoff_on_high_intent": True,
        })
    elif agent_mode_normalized == "agenda":
        merged.update({
            "max_chars": 350,
            "qualification_depth": "medium",
        })
        # Só injeta must_collect se o AI Profile definiu campos explicitamente
        profile_fields = (ai_profile or {}).get("qualification_required_fields")
        if isinstance(profile_fields, list) and len(profile_fields) > 0:
            merged.update({"must_collect": profile_fields})
        # profile_fields == None → não configurado, sem override automático
        # profile_fields == [] → lista vazia explícita = modo passivo, sem must_collect
    elif agent_mode_normalized == "direto":
        merged.update({
            "max_chars": 300,
            "qualification_depth": "low",
            "cta_every_turn": True,
        })
    return merged


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
    qualification_state: Optional[Dict[str, Any]] = None
    knowledge_items: Optional[Dict[str, str]] = None


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
    normalized_mode = _normalize_agent_mode_for_bundle(ai_profile, template_key)
    if ai_profile is not None:
        ai_profile["agent_mode"] = normalized_mode
    presentation_contract = _resolve_presentation_contract(ai_profile=ai_profile, agent_mode_normalized=normalized_mode)
    if ai_profile is not None:
        ai_profile["presentation_variant"] = presentation_contract["presentation_variant"]
        ai_profile["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
        ai_profile["offer_pack"] = presentation_contract["offer_pack"]
    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"
    playbook = apply_mode_overrides(playbook, normalized_mode, ai_profile=ai_profile)
    playbook["presentation_variant"] = presentation_contract["presentation_variant"]
    playbook["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    playbook["offer_pack"] = presentation_contract["offer_pack"]

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads WHERE id = ? AND user_id = ?", (lead_id, current_user.id))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    lead_data = {key: row[key] for key in row.keys()}

    _lead_origin_raw = lead_data.get("origin") or ""
    _is_outbound = _lead_origin_raw.lower() not in ("whatsapp", "inbound", "manual", "planilha", "")
    metadata = {
        "channel": channel,
        "inbound_message_text": inbound_message_text,
        "received_at": datetime.utcnow().isoformat(),
        "presentation_variant": presentation_contract["presentation_variant"],
        "presentation_variant_source": presentation_contract["presentation_variant_source"],
        "hybrid_flow_style": presentation_contract["hybrid_flow_style"],
        "lead_origin": "outbound" if _is_outbound else "inbound",
        "lead_origin_label": (
            "OUTBOUND (lead foi abordado — não te conhecia)"
            if _is_outbound
            else "INBOUND (lead veio te procurar)"
        ),
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
    normalized_mode = _normalize_agent_mode_for_bundle(ai_profile, template_key)
    if ai_profile is not None:
        ai_profile["agent_mode"] = normalized_mode
    presentation_contract = _resolve_presentation_contract(ai_profile=ai_profile, agent_mode_normalized=normalized_mode)
    if ai_profile is not None:
        ai_profile["presentation_variant"] = presentation_contract["presentation_variant"]
        ai_profile["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
        ai_profile["offer_pack"] = presentation_contract["offer_pack"]
    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"
    playbook = apply_mode_overrides(playbook, normalized_mode, ai_profile=ai_profile)
    playbook["presentation_variant"] = presentation_contract["presentation_variant"]
    playbook["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    playbook["offer_pack"] = presentation_contract["offer_pack"]

    lead_data = _load_lead(user_id=event.user_id, lead_id=event.lead_id)
    history = get_recent_history(event.lead_id)
    conversation_goal = "qualify" if len(history) <= 1 else "advance"

    _lead_origin_raw = lead_data.get("origin") or ""
    _is_outbound = _lead_origin_raw.lower() not in ("whatsapp", "inbound", "manual", "planilha", "")
    metadata = {
        "channel": event.channel,
        "inbound_message_text": event.message_text,
        "received_at": event.received_at or datetime.utcnow().isoformat(),
        "message_id": event.message_id,
        "instance_id": event.instance_id,
        "provider": event.provider,
        "phone": event.phone,
        "ai_profile_status": ai_profile_status if ai_profile is None else "ok",
        "presentation_variant": presentation_contract["presentation_variant"],
        "presentation_variant_source": presentation_contract["presentation_variant_source"],
        "hybrid_flow_style": presentation_contract["hybrid_flow_style"],
        "lead_origin": "outbound" if _is_outbound else "inbound",
        "lead_origin_label": (
            "OUTBOUND (lead foi abordado — não te conhecia)"
            if _is_outbound
            else "INBOUND (lead veio te procurar)"
        ),
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


def _load_knowledge_items(user_id: int) -> Dict[str, str]:
    """Carrega knowledge items do utilizador agrupados por categoria (primeira entrada por categoria)."""
    knowledge_by_category: Dict[str, str] = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT category, content_text FROM knowledge_items WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        for row in cur.fetchall():
            cat = row["category"] or "uncategorized"
            if cat not in knowledge_by_category:
                knowledge_by_category[cat] = row["content_text"]
    return knowledge_by_category


def build_context_bundle_for_playground(
    user_id: int,
    ai_profile: Dict[str, Any],
    lead_id: int,
    message_text: str,
) -> ContextBundle:
    """
    Constrói um ContextBundle para o playground, sem InboundEvent nem WhatsApp.
    Reutiliza toda a lógica de normalização de agent_mode, playbook e histórico.
    """
    template_key = ai_profile.get("template_key") or None
    normalized_mode = _normalize_agent_mode_for_bundle(ai_profile, template_key)

    ai_profile = dict(ai_profile)
    ai_profile["agent_mode"] = normalized_mode

    presentation_contract = _resolve_presentation_contract(
        ai_profile=ai_profile,
        agent_mode_normalized=normalized_mode,
    )
    ai_profile["presentation_variant"] = presentation_contract["presentation_variant"]
    ai_profile["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    ai_profile["offer_pack"] = presentation_contract["offer_pack"]

    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"
    playbook = apply_mode_overrides(playbook, normalized_mode, ai_profile=ai_profile)
    playbook["presentation_variant"] = presentation_contract["presentation_variant"]
    playbook["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    playbook["offer_pack"] = presentation_contract["offer_pack"]

    lead = _load_lead(user_id, lead_id)
    history = get_recent_history(lead_id)
    conversation_goal = "qualify" if len(history) <= 1 else "advance"

    qualification_state = get_qualification_state(lead_id)
    knowledge_items = _load_knowledge_items(user_id)

    metadata = {
        "channel": "playground",
        "inbound_message_text": message_text,
        "received_at": datetime.utcnow().isoformat(),
        "presentation_variant": presentation_contract["presentation_variant"],
        "presentation_variant_source": presentation_contract["presentation_variant_source"],
        "hybrid_flow_style": presentation_contract["hybrid_flow_style"],
        "lead_origin": "playground",
        "lead_origin_label": "PLAYGROUND (simulação sem WhatsApp)",
    }

    return ContextBundle(
        user_id=user_id,
        entitlements={},
        ai_profile=ai_profile,
        playbook=playbook,
        lead=lead,
        history=history,
        next_action=playbook.get("default_next_action", "reply"),
        metadata=metadata,
        conversation_goal=conversation_goal,
        qualification_state=qualification_state,
        knowledge_items=knowledge_items,
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
