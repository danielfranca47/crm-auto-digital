from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import HTTPException

from services.jobs_service import TYPE_WHATSAPP_INBOUND, expand_type_variants


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
    from core_client import fetch_core_whatsapp_connection_by_user

    try:
        connection = fetch_core_whatsapp_connection_by_user(int(user_id))
    except HTTPException as exc:
        if exc.status_code not in {404, 400}:
            # Falha operacional ao contatar o core/token inválido: falhar cedo.
            raise
    else:
        connection_status = str(connection.get("connection_status") or "").strip().lower()
        if connection_status != "active":
            raise HTTPException(
                status_code=400,
                detail="Conexão WhatsApp atual do usuário está inativa para follow-up automático",
            )

        instance_id = connection.get("instance_id")
        provider = connection.get("provider")
        if not instance_id or not provider:
            raise HTTPException(
                status_code=400,
                detail="Conexão WhatsApp atual do usuário está incompleta (instance_id/provider)",
            )

        return {
            "instance_id": instance_id,
            "provider": provider,
            "phone": connection.get("phone_e164"),
        }

    # Fallback auxiliar: histórico inbound por lead em cenários legados onde o core ainda
    # não disponibiliza/retorna a conexão atual por user_id.
    cur = conn.cursor()
    inbound_type_variants = expand_type_variants(TYPE_WHATSAPP_INBOUND)
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
