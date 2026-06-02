from typing import Any, Dict, Optional

import sqlite3
from fastapi import APIRouter, Depends

from database import get_connection
from security_core import CurrentUser, require_crm_access
from services import rate_limit_service

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

    # Links de checkout Kiwify para CTAs de upgrade
    checkout_links = {
        "crm_start": "https://pay.kiwify.com.br/gOjcexD",
        "crm_growth": "https://pay.kiwify.com.br/To8qV99",
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
