import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import sqlite3
from fastapi import APIRouter, Depends

from database import get_connection
from security_core import CurrentUser, require_crm_access
from services import jobs_service, rate_limit_service

router = APIRouter(prefix="/api/usage", tags=["Usage"])


LimitDict = Dict[str, Any]


def _get_limit_value(limits: LimitDict, key: str) -> Optional[int]:
    value = limits.get(key)
    return value if isinstance(value, int) or value is None else None


def _calculate_remaining(limit_value: Optional[int], used: int) -> Optional[int]:
    if limit_value is None:
        return None
    return max(0, limit_value - used)


def build_usage_payload(
    *, conn: sqlite3.Connection, entitlements: Dict[str, Any], user_id: int
) -> Dict[str, Any]:
    limits: LimitDict = entitlements.get("limits") if isinstance(entitlements, dict) else {}

    lead_limit = _get_limit_value(limits, "max_leads")
    leads_row = conn.execute(
        "SELECT COUNT(*) AS total FROM leads WHERE user_id = ?", (user_id,)
    ).fetchone()
    leads_total = int(leads_row["total"]) if leads_row else 0

    agents_limit = _get_limit_value(limits, "max_agents_local")
    agents_total_active = rate_limit_service._count_active_agents(conn, user_id, "")

    copy_limit = _get_limit_value(limits, "max_copy_generation_monthly")
    rate_limit_service._ensure_usage_monthly_table(conn)
    copy_used = rate_limit_service._get_monthly_usage(
        conn=conn, user_id=user_id, limit_key="max_copy_generation_monthly"
    )
    copy_remaining = rate_limit_service.get_monthly_remaining(
        limit_key="max_copy_generation_monthly",
        user_id=user_id,
        entitlements=entitlements,
        conn=conn,
    )

    rate_limit_service._ensure_usage_table(conn)

    daily_keys = [
        "max_prospects_daily",
        "max_whatsapp_send_daily",
        "max_email_send_daily",
        "max_maps_search_daily",
        "max_maps_enrich_daily",
    ]

    daily_usage: Dict[str, Dict[str, Optional[int]]] = {}
    for key in daily_keys:
        limit_value = _get_limit_value(limits, key)
        used = rate_limit_service._get_daily_usage(conn=conn, user_id=user_id, limit_key=key)
        daily_usage[key] = {
            "used": used,
            "limit": limit_value,
            "remaining": _calculate_remaining(limit_value, used),
        }

    # Conversas IA mensais
    ia_limit = _get_limit_value(limits, "max_ia_conversas_monthly")
    ia_used = rate_limit_service._get_monthly_usage(
        conn=conn, user_id=user_id, limit_key="max_ia_conversas_monthly"
    )
    ia_remaining = _calculate_remaining(ia_limit, ia_used)
    ia_pct = round((ia_used / ia_limit) * 100) if ia_limit else None

    # Playground mensal
    playground_limit = limits.get("playground_monthly_limit")
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS playground_usage_monthly (
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, month)
        )
        """
    )
    playground_row = conn.execute(
        "SELECT count FROM playground_usage_monthly WHERE user_id = ? AND month = ?",
        (user_id, month_key),
    ).fetchone()
    playground_used = int(playground_row["count"]) if playground_row else 0
    playground_remaining = _calculate_remaining(
        int(playground_limit) if playground_limit is not None else None, playground_used
    )

    # Ingestão de conhecimento semanal — conta direto na tabela jobs (mesma fonte do gate em
    # routes/knowledge_ingest.py), não em limit_usage (ver nota em docs/architecture/plans-limits.md)
    knowledge_ingest_limit = _get_limit_value(limits, "knowledge_ingest_weekly_limit")
    knowledge_ingest_used = rate_limit_service.get_weekly_job_usage(
        job_type=jobs_service.TYPE_KNOWLEDGE_INGEST, user_id=user_id, conn=conn
    )
    knowledge_ingest_remaining = _calculate_remaining(knowledge_ingest_limit, knowledge_ingest_used)

    # Links de checkout (Efí) para CTAs de upgrade — gerados sob demanda em /checkout/efi/{offer}
    _crm_base = os.environ.get("CRM_PUBLIC_BASE_URL", "").rstrip("/")
    checkout_links = {
        "crm_start": f"{_crm_base}/checkout/efi/start",
        "crm_growth": f"{_crm_base}/checkout/efi/growth",
    }

    return {
        "leads": {
            "total": leads_total,
            "limit": lead_limit,
            "remaining": _calculate_remaining(lead_limit, leads_total),
        },
        "agents": {
            "active": agents_total_active,
            "limit": agents_limit,
            "remaining": _calculate_remaining(agents_limit, agents_total_active),
        },
        "copy_monthly": {
            "limit": copy_limit,
            "used": copy_used,
            "remaining": copy_remaining,
        },
        "daily": daily_usage,
        "ia_monthly": {
            "used": ia_used,
            "limit": ia_limit,
            "remaining": ia_remaining,
            "pct": ia_pct,
        },
        "playground_monthly": {
            "used": playground_used,
            "limit": playground_limit,
            "remaining": playground_remaining,
        },
        "knowledge_ingest_weekly": {
            "used": knowledge_ingest_used,
            "limit": knowledge_ingest_limit,
            "remaining": knowledge_ingest_remaining,
        },
        "checkout_links": checkout_links,
    }


@router.get("")
def get_usage(current_user: CurrentUser = Depends(require_crm_access)) -> Dict[str, Any]:
    entitlements = current_user.entitlements or {}
    with get_connection() as conn:
        usage_payload = build_usage_payload(
            conn=conn, entitlements=entitlements, user_id=current_user.id
        )

    return {"entitlements": entitlements, "usage": usage_payload}
