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
    jobs_service.TYPE_EMAIL_SEND_COLD: "max_email_send_daily",
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

USAGE_MONTHLY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS limit_usage_monthly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    limit_key TEXT NOT NULL,
    month_utc TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, limit_key, month_utc)
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


def _ensure_usage_monthly_table(conn: sqlite3.Connection) -> None:
    conn.executescript(USAGE_MONTHLY_TABLE_SQL)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_limit_usage_monthly_user_month ON limit_usage_monthly(user_id, limit_key, month_utc)"
    )


def _extract_count_limit(entitlements: Optional[Dict[str, Any]], *, limit_key: str) -> Optional[int]:
    return _extract_limit_value(entitlements, limit_key)


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


def _adjust_daily_usage(
    *, conn: sqlite3.Connection, user_id: int, limit_key: str, delta: int
) -> None:
    """Adjusts the daily usage by ``delta`` (can be negative). Ensures non-negative usage."""

    conn.execute(
        """
        INSERT INTO limit_usage (user_id, limit_key, day_utc, used)
        VALUES (?, ?, DATE('now','utc'), ?)
        ON CONFLICT(user_id, limit_key, day_utc)
        DO UPDATE SET used = max(0, limit_usage.used + excluded.used), updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, limit_key, delta),
    )
    conn.commit()


def _get_monthly_usage(*, conn: sqlite3.Connection, user_id: int, limit_key: str) -> int:
    row = conn.execute(
        """
        SELECT used FROM limit_usage_monthly
         WHERE user_id = ? AND limit_key = ? AND month_utc = strftime('%Y-%m','now','utc')
        """,
        (user_id, limit_key),
    ).fetchone()
    return int(row["used"]) if row else 0


def _adjust_monthly_usage(*, conn: sqlite3.Connection, user_id: int, limit_key: str, delta: int) -> None:
    """Adjusts the monthly usage by ``delta`` (can be negative). Ensures non-negative usage."""

    conn.execute(
        """
        INSERT INTO limit_usage_monthly (user_id, limit_key, month_utc, used)
        VALUES (?, ?, strftime('%Y-%m','now','utc'), ?)
        ON CONFLICT(user_id, limit_key, month_utc)
        DO UPDATE SET used = max(0, limit_usage_monthly.used + excluded.used), updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, limit_key, delta),
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


def ensure_daily_units_available(
    *,
    limit_key: str,
    amount: int,
    user_id: Optional[int],
    entitlements: Optional[Dict[str, Any]],
    label: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    Validates that ``amount`` units can be consumed today without exceeding the limit.

    Returns the remaining available units after this request (or 0 if unlimited/no user).
    Raises HTTPException 429 if the limit would be exceeded.
    """

    if amount <= 0:
        return 0

    limit_value = _extract_limit_value(entitlements, limit_key)
    if user_id is None or limit_value is None:
        return 0

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
        return max(0, limit_value - usage - amount)
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def reserve_daily_units(
    *,
    limit_key: str,
    amount: int,
    user_id: Optional[int],
    entitlements: Optional[Dict[str, Any]],
    label: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    Pre-emptively consumes ``amount`` units to block heavy work if quota is insufficient.

    Returns the amount reserved (0 if no reservation was needed). Raises HTTPException 429
    if the reservation would exceed the daily limit.
    """

    if amount <= 0:
        return 0

    limit_value = _extract_limit_value(entitlements, limit_key)
    if user_id is None or limit_value is None:
        return 0

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

        _adjust_daily_usage(conn=db_conn, user_id=user_id, limit_key=limit_key, delta=amount)
        return amount
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def refund_daily_units(
    *,
    limit_key: str,
    amount: int,
    user_id: Optional[int],
    entitlements: Optional[Dict[str, Any]],
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Refunds previously reserved units (amount must be positive)."""

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
        _adjust_daily_usage(conn=db_conn, user_id=user_id, limit_key=limit_key, delta=-amount)
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def get_monthly_remaining(
    *,
    limit_key: str,
    user_id: Optional[int],
    entitlements: Optional[Dict[str, Any]],
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[int]:
    """
    Returns remaining units for the current UTC month (or None if unlimited/no user).
    """

    limit_value = _extract_limit_value(entitlements, limit_key)
    if user_id is None or limit_value is None:
        return None

    owns_conn = False
    db_conn = conn
    if db_conn is None:
        db_conn = get_connection()
        owns_conn = True

    try:
        _ensure_usage_monthly_table(db_conn)
        usage = _get_monthly_usage(conn=db_conn, user_id=user_id, limit_key=limit_key)
        return max(0, limit_value - usage)
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def consume_monthly_units(
    *,
    limit_key: str,
    amount: int,
    user_id: Optional[int],
    entitlements: Optional[Dict[str, Any]],
    label: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Consumes monthly units after validating the entitlement."""

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
        _ensure_usage_monthly_table(db_conn)
        usage = _get_monthly_usage(conn=db_conn, user_id=user_id, limit_key=limit_key)
        if usage + amount > limit_value:
            detail_label = label or limit_key
            raise HTTPException(
                status_code=429,
                detail=f"Limite mensal atingido para {detail_label}. Atualize seu plano.",
            )

        _adjust_monthly_usage(conn=db_conn, user_id=user_id, limit_key=limit_key, delta=amount)
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def get_total_leads(*, user_id: Optional[int], conn: Optional[sqlite3.Connection] = None) -> int:
    if user_id is None:
        return 0

    owns_conn = False
    db_conn = conn
    if db_conn is None:
        db_conn = get_connection()
        owns_conn = True

    try:
        row = db_conn.execute("SELECT COUNT(*) AS total FROM leads WHERE user_id = ?", (user_id,)).fetchone()
        return int(row["total"]) if row else 0
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def get_total_agents(*, user_id: Optional[int], conn: Optional[sqlite3.Connection] = None) -> int:
    if user_id is None:
        return 0

    owns_conn = False
    db_conn = conn
    if db_conn is None:
        db_conn = get_connection()
        owns_conn = True

    try:
        row = db_conn.execute("SELECT COUNT(*) AS total FROM agents WHERE user_id = ?", (user_id,)).fetchone()
        return int(row["total"]) if row else 0
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def get_remaining_lead_slots(
    *, user_id: Optional[int], entitlements: Optional[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None
) -> Optional[int]:
    """
    Returns remaining lead capacity for the current user or ``None`` if unlimited/not applicable.
    """

    limit_value = _extract_count_limit(entitlements, limit_key="max_leads")
    if user_id is None or limit_value is None:
        return None

    owns_conn = False
    db_conn = conn
    if db_conn is None:
        db_conn = get_connection()
        owns_conn = True

    try:
        current_total = _count_table(conn=db_conn, table="leads", user_id=user_id)
        return max(0, limit_value - current_total)
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def _ensure_max_counter(
    *,
    limit_key: str,
    user_id: Optional[int],
    entitlements: Optional[Dict[str, Any]],
    amount_to_add: int = 1,
    conn: Optional[sqlite3.Connection] = None,
    current_total: Optional[int] = None,
    detail: str,
    table: str,
    count_func=None,
) -> int:
    """
    Validates that ``current_total + amount_to_add`` would not exceed the configured limit.

    Returns remaining slots after adding (or a large number for unlimited cases).
    """

    if amount_to_add <= 0:
        return 0

    limit_value = _extract_count_limit(entitlements, limit_key=limit_key)
    if user_id is None or limit_value is None:
        return 1_000_000_000  # effectively unlimited

    if limit_value == 0:
        raise HTTPException(status_code=429, detail=detail)

    owns_conn = False
    db_conn = conn
    if db_conn is None:
        db_conn = get_connection()
        owns_conn = True

    count_func = count_func or (lambda conn, user_id, table: _count_table(conn=conn, table=table, user_id=user_id))

    try:
        total = current_total if current_total is not None else count_func(
            db_conn, user_id, table
        )
        if total + amount_to_add > limit_value:
            raise HTTPException(status_code=429, detail=detail)
        return max(0, limit_value - total - amount_to_add)
    finally:
        if owns_conn and db_conn:
            db_conn.close()


def _count_table(*, conn: sqlite3.Connection, table: str, user_id: int) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE user_id = ?", (user_id,)).fetchone()
    return int(row["total"]) if row else 0


def _count_active_agents(conn: sqlite3.Connection, user_id: int, _: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total
          FROM agents
         WHERE user_id = ?
           AND revoked_at IS NULL
           AND COALESCE(status, '') != 'disabled'
        """,
        (user_id,),
    ).fetchone()
    return int(row["total"]) if row else 0


def ensure_max_leads(
    *, user_id: Optional[int], entitlements: Optional[Dict[str, Any]], amount_to_add: int = 1, conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Ensures the user has capacity to add ``amount_to_add`` leads.

    Returns remaining slots after the addition (or a sentinel for unlimited).
    """

    return _ensure_max_counter(
        limit_key="max_leads",
        user_id=user_id,
        entitlements=entitlements,
        amount_to_add=amount_to_add,
        conn=conn,
        detail="Limite atingido de leads armazenados. Atualize seu plano.",
        table="leads",
    )


def ensure_max_agents_local(
    *, user_id: Optional[int], entitlements: Optional[Dict[str, Any]], amount_to_add: int = 1, conn: Optional[sqlite3.Connection] = None
) -> int:
    """
    Ensures the user has capacity to add ``amount_to_add`` local agents.

    Returns remaining slots after the addition (or a sentinel for unlimited).
    """

    return _ensure_max_counter(
        limit_key="max_agents_local",
        user_id=user_id,
        entitlements=entitlements,
        amount_to_add=amount_to_add,
        conn=conn,
        detail="Limite atingido de agentes locais. Atualize seu plano.",
        table="agents",
        count_func=_count_active_agents,
    )

