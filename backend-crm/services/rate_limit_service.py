"""Rate limit helpers based on entitlements returned by backend-core."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import sqlite3

from fastapi import HTTPException

from database import get_connection
from services import jobs_service

LIMIT_KEYS_BY_TYPE: Dict[str, str] = {
    jobs_service.TYPE_WHATSAPP_SEND: "max_whatsapp_send_daily",
    jobs_service.TYPE_MAPS_SEARCH: "max_maps_search_daily",
    jobs_service.TYPE_MAPS_ENRICH: "max_maps_enrich_daily",
}

USAGE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS limit_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    limit_key TEXT NOT NULL,
    day_utc TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, limit_key, day_utc)
);
"""


@dataclass
class RateLimitState:
    job_type: str
    limit_key: Optional[str]
    limit_value: Optional[int]
    usage: int
    _conn: Optional[sqlite3.Connection]
    _owns_conn: bool

    def ensure_can_consume(self, amount: int = 1) -> None:
        """Raises HTTPException if consuming the requested amount would exceed the limit."""

        if self.limit_value is None:
            return

        if self.usage + amount > self.limit_value:
            canonical = jobs_service.normalize_job_type(self.job_type)
            raise HTTPException(
                status_code=429,
                detail=f"Limite diário atingido para {canonical}. Atualize seu plano.",
            )

        self.usage += amount

    def close(self) -> None:
        if self._owns_conn and self._conn:
            self._conn.close()


def _extract_limit_value(entitlements: Optional[Dict[str, Any]], limit_key: Optional[str]) -> Optional[int]:
    if not entitlements or not limit_key:
        return None

    limits = entitlements.get("limits") if isinstance(entitlements, dict) else None
    if not isinstance(limits, dict):
        return None

    value = limits.get(limit_key)
    return value if isinstance(value, int) or value is None else None


def _ensure_usage_table(conn: sqlite3.Connection) -> None:
    conn.executescript(USAGE_TABLE_SQL)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_limit_usage_user_day ON limit_usage(user_id, limit_key, day_utc)"
    )


def _get_daily_usage(*, conn: sqlite3.Connection, user_id: int, limit_key: str) -> int:
    row = conn.execute(
        """
        SELECT used FROM limit_usage
         WHERE user_id = ? AND limit_key = ? AND day_utc = DATE('now', 'utc')
        """,
        (user_id, limit_key),
    ).fetchone()
    return int(row["used"]) if row else 0


def _increment_daily_usage(*, conn: sqlite3.Connection, user_id: int, limit_key: str, amount: int) -> None:
    conn.execute(
        """
        INSERT INTO limit_usage (user_id, limit_key, day_utc, used)
        VALUES (?, ?, DATE('now','utc'), ?)
        ON CONFLICT(user_id, limit_key, day_utc)
        DO UPDATE SET used = limit_usage.used + excluded.used, updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, limit_key, amount),
    )
    conn.commit()


def _count_jobs_for_today(
    *, conn: sqlite3.Connection, user_id: int, job_types: Sequence[str]
) -> int:
    if not job_types:
        return 0

    placeholders = ",".join(["?"] * len(job_types))
    params: List[Any] = [user_id, *job_types]
    row = conn.execute(
        f"""
        SELECT COUNT(*) as total
          FROM jobs
         WHERE user_id = ?
           AND type IN ({placeholders})
           AND DATE(created_at, 'utc') = DATE('now', 'utc')
        """,
        params,
    ).fetchone()
    return int(row["total"]) if row else 0


def build_rate_limit_state(
    *, job_type: str, user_id: Optional[int], entitlements: Optional[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None
) -> RateLimitState:
    """
    Returns a RateLimitState with current usage for the given job type.

    If there is no applicable limit (missing user_id, missing entitlement key or value is None)
    the returned state will have limit_value=None and ensure_can_consume will no-op.
    """

    canonical = jobs_service.normalize_job_type(job_type)
    limit_key = LIMIT_KEYS_BY_TYPE.get(canonical)
    limit_value = _extract_limit_value(entitlements, limit_key)

    if user_id is None or limit_value is None:
        return RateLimitState(
            job_type=canonical,
            limit_key=limit_key,
            limit_value=limit_value,
            usage=0,
            _conn=None,
            _owns_conn=False,
        )

    owns_conn = False
    db_conn = conn
    if db_conn is None:
        db_conn = get_connection()
        owns_conn = True

    variants = jobs_service.expand_type_variants(canonical)
    usage = _count_jobs_for_today(conn=db_conn, user_id=user_id, job_types=variants)

    return RateLimitState(
        job_type=canonical,
        limit_key=limit_key,
        limit_value=limit_value,
        usage=usage,
        _conn=db_conn,
        _owns_conn=owns_conn,
    )


def ensure_daily_limit(
    *, job_type: str, user_id: Optional[int], entitlements: Optional[Dict[str, Any]]
) -> None:
    """Convenience wrapper for single-job flows."""

    state = build_rate_limit_state(job_type=job_type, user_id=user_id, entitlements=entitlements)
    try:
        state.ensure_can_consume()
    finally:
        state.close()


def consume_daily_units(
    *,
    limit_key: str,
    amount: int,
    user_id: Optional[int],
    entitlements: Optional[Dict[str, Any]],
    label: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Consumes a daily limit measured in arbitrary units (e.g., prospects)."""

    if amount <= 0:
        return

    limit_value = _extract_limit_value(entitlements, limit_key)
    if user_id is None or limit_value is None:
        return

    owns_conn = False
    db_conn = conn
    if db_conn is None:
        db_conn = get_connection()
        owns_conn = True

    try:
        _ensure_usage_table(db_conn)
        usage = _get_daily_usage(conn=db_conn, user_id=user_id, limit_key=limit_key)
        if usage + amount > limit_value:
            detail_label = label or limit_key
            raise HTTPException(
                status_code=429,
                detail=f"Limite diário atingido para {detail_label}. Atualize seu plano.",
            )

        _increment_daily_usage(conn=db_conn, user_id=user_id, limit_key=limit_key, amount=amount)
    finally:
        if owns_conn and db_conn:
            db_conn.close()

