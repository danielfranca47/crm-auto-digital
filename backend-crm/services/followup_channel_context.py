from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import HTTPException

from services.jobs_service import TYPE_WHATSAPP_INBOUND_N8N, expand_type_variants


def _parse_payload(raw_payload: Any) -> Dict[str, Any]:
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str) and raw_payload.strip():
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def resolve_followup_tick_channel_context(conn, *, lead_id: int, user_id: int) -> Dict[str, Any]:
    cur = conn.cursor()
    inbound_type_variants = expand_type_variants(TYPE_WHATSAPP_INBOUND_N8N)
    placeholders = ",".join(["?"] * len(inbound_type_variants))
    rows = cur.execute(
        f"""
        SELECT payload
          FROM jobs
         WHERE user_id = ?
           AND type IN ({placeholders})
         ORDER BY id DESC
         LIMIT 50
        """,
        (user_id, *inbound_type_variants),
    ).fetchall()

    for candidate in rows:
        payload = _parse_payload(candidate["payload"])
        if int(payload.get("lead_id") or 0) != int(lead_id):
            continue
        instance_id = payload.get("instance_id")
        provider = payload.get("provider")
        if not instance_id or not provider:
            break
        return {
            "instance_id": instance_id,
            "provider": provider,
            "phone": payload.get("phone"),
        }

    raise HTTPException(
        status_code=400,
        detail="Contexto de canal indisponível para follow-up (inbound prévio com instância ativa não encontrado)",
    )
