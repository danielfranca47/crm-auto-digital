from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import get_connection

logger = logging.getLogger(__name__)

TYPE_FOLLOWUP_TICK = "whatsapp.followup.tick"
_RECONCILE_GUARD_STATUS_ENQUEUED = "enqueued"


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _now_iso_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _parse_allowed_hours(allowed_hours: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse 'HH:MM-HH:MM' → (start_h, start_m, end_h, end_m) or None."""
    m = re.match(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$", (allowed_hours or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))


def _is_within_allowed_hours(now_utc: datetime, allowed_hours: str) -> bool:
    parsed = _parse_allowed_hours(allowed_hours)
    if not parsed:
        return True  # invalid config → allow all
    sh, sm, eh, em = parsed
    now_mins = now_utc.hour * 60 + now_utc.minute
    start_mins = sh * 60 + sm
    end_mins = eh * 60 + em
    if start_mins <= end_mins:
        return start_mins <= now_mins < end_mins
    # crosses midnight
    return now_mins >= start_mins or now_mins < end_mins


def _next_window_start_iso(now_utc: datetime, start_h: int, start_m: int) -> str:
    """Return ISO string for the next occurrence of start_h:start_m (UTC)."""
    candidate = now_utc.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    if candidate <= now_utc:
        candidate += timedelta(days=1)
    return candidate.isoformat()


def _parse_naive_utc(value: Optional[str]) -> Optional[datetime]:
    """Parse timestamp do SQLite ('YYYY-MM-DD HH:MM:SS') para datetime UTC-aware."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace(" ", "T"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fetch_profile_cache(user_ids: set) -> Dict[int, Dict[str, Any]]:
    """Fetch AI profiles for a set of user_ids via HTTP; returns a cache dict."""
    try:
        from core_client import fetch_core_ai_profile_resolve
    except ImportError:
        return {}

    cache: Dict[int, Dict[str, Any]] = {}
    for uid in user_ids:
        try:
            profile = fetch_core_ai_profile_resolve(int(uid))
            cache[uid] = profile or {}
        except Exception as exc:
            logger.warning("followup.reconcile_profile_fetch_error user_id=%s err=%s", uid, exc)
            cache[uid] = {}
    return cache


def reconcile_due_followups(*, limit: int = 100, dry_run: bool = False) -> Dict[str, Any]:
    """
    Detecta follow-ups vencidos elegíveis e enfileira jobs canônicos idempotentes.

    Elegibilidade:
      - followup_status = 'active'
      - next_followup_at <= now
      - bot_disabled = 0
      - category = 'follow-up'

    Se o AI Profile do usuário definir followup_allowed_hours ('HH:MM-HH:MM'),
    o reconciliador adia next_followup_at para o início da próxima janela permitida
    em vez de enfileirar o job.
    """

    # ── 1. Leitura sem lock exclusivo ──────────────────────────────────────
    with get_connection() as read_conn:
        rows = read_conn.execute(
            """
            SELECT id, user_id, category, followup_status, next_followup_at, followup_contract
              FROM leads
             WHERE followup_status = 'active'
               AND COALESCE(bot_disabled, 0) = 0
               AND category = 'follow-up'
               AND next_followup_at IS NOT NULL
               AND datetime(next_followup_at) <= CURRENT_TIMESTAMP
             ORDER BY datetime(next_followup_at) ASC, id ASC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return {
            "scanned": 0,
            "eligible": 0,
            "enqueued": 0,
            "skipped_duplicate": 0,
            "skipped_dry_run": 0,
            "skipped_outside_window": 0,
            "job_type": TYPE_FOLLOWUP_TICK,
            "items": [],
        }

    # ── 2. Busca AI profiles para verificar janelas permitidas ─────────────
    user_ids = {row["user_id"] for row in rows}
    profile_cache = _fetch_profile_cache(user_ids)
    now_utc = datetime.now(timezone.utc)

    # ── 3. Particionamento: fora da janela vs. elegíveis ───────────────────
    outside_window: List[Dict[str, Any]] = []
    to_process: List[Any] = []

    for row in rows:
        profile = profile_cache.get(row["user_id"]) or {}
        allowed_hours = profile.get("followup_allowed_hours") or ""
        if allowed_hours and not _is_within_allowed_hours(now_utc, allowed_hours):
            outside_window.append({"row": row, "allowed_hours": allowed_hours})
        else:
            to_process.append(row)

    # ── 4. Adiar leads fora da janela ──────────────────────────────────────
    skipped_outside_window = 0
    for item in outside_window:
        row = item["row"]
        allowed_hours = item["allowed_hours"]
        lead_id = int(row["id"])
        user_id = row["user_id"]

        parsed = _parse_allowed_hours(allowed_hours)
        if not parsed:
            to_process.append(row)  # config inválida → deixa processar normal
            continue

        sh, sm, _, _ = parsed
        next_start = _next_window_start_iso(now_utc, sh, sm)

        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE leads
                       SET next_followup_at = ?,
                           lastMovement = CURRENT_TIMESTAMP
                     WHERE id = ?
                    """,
                    (next_start, lead_id),
                )
                conn.execute(
                    """
                    INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
                    VALUES (?, NULL, NULL, 'followup_deferred_outside_window', ?, ?)
                    """,
                    (
                        lead_id,
                        _json_dumps({"allowed_hours": allowed_hours, "deferred_to": next_start}),
                        user_id,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning(
                "followup.reconcile_defer_error lead_id=%s err=%s", lead_id, exc
            )

        skipped_outside_window += 1
        logger.info(
            "followup.reconcile_deferred_outside_window lead_id=%s user_id=%s next=%s",
            lead_id,
            user_id,
            next_start,
        )

    # ── 5. Enfileirar jobs para leads elegíveis ────────────────────────────
    scanned = len(rows)
    eligible = len(to_process)
    enqueued = 0
    skipped_duplicate = 0
    skipped_dry_run = 0
    skipped_circuit_breaker = 0
    items: List[Dict[str, Any]] = []

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")

        for row in to_process:
            lead_id = int(row["id"])
            user_id = row["user_id"]
            due_at = str(row["next_followup_at"])

            logger.info(
                "followup.reconcile_due_detected lead_id=%s user_id=%s due_at=%s",
                lead_id,
                user_id,
                due_at,
            )

            existing_guard = cur.execute(
                """
                SELECT g.id AS guard_id, g.job_id, j.status AS job_status, j.error AS job_error
                  FROM followup_reconcile_guard g
             LEFT JOIN jobs j ON j.id = g.job_id
                 WHERE g.lead_id = ?
                   AND g.due_at = ?
                 LIMIT 1
                """,
                (lead_id, due_at),
            ).fetchone()

            if existing_guard and str(existing_guard["job_status"] or "").lower() == "failed":
                # Determina se a falha é retryable para aplicar circuit breaker
                _is_retryable = True
                try:
                    _err_raw = existing_guard["job_error"] or ""
                    if _err_raw:
                        _err_obj = json.loads(_err_raw)
                        _is_retryable = bool(_err_obj.get("details", {}).get("retryable", True))
                except Exception:
                    pass

                if not _is_retryable:
                    # Falha definitiva: aplica cooldown de 24h para evitar loop infinito
                    _cooldown_hours = 24
                    _next_retry_at = (
                        datetime.now(timezone.utc) + timedelta(hours=_cooldown_hours)
                    ).replace(microsecond=0).isoformat()
                    cur.execute(
                        "DELETE FROM followup_reconcile_guard WHERE id = ?",
                        (existing_guard["guard_id"],),
                    )
                    cur.execute(
                        """
                        UPDATE leads
                           SET next_followup_at = ?,
                               lastMovement = CURRENT_TIMESTAMP
                         WHERE id = ?
                        """,
                        (_next_retry_at, lead_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
                        VALUES (?, NULL, NULL, 'followup_circuit_breaker', ?, ?)
                        """,
                        (
                            lead_id,
                            _json_dumps({
                                "reason": "non_retryable_failure",
                                "failed_job_id": existing_guard["job_id"],
                                "cooldown_hours": _cooldown_hours,
                                "next_retry_at": _next_retry_at,
                            }),
                            user_id,
                        ),
                    )
                    logger.info(
                        "followup.reconcile_circuit_breaker lead_id=%s user_id=%s failed_job_id=%s next_retry_at=%s",
                        lead_id,
                        user_id,
                        existing_guard["job_id"],
                        _next_retry_at,
                    )
                    skipped_circuit_breaker += 1
                    continue  # não re-enfileira para este lead

                cur.execute(
                    "DELETE FROM followup_reconcile_guard WHERE id = ?",
                    (existing_guard["guard_id"],),
                )
                logger.info(
                    "followup.reconcile_release_failed_guard lead_id=%s user_id=%s due_at=%s failed_job_id=%s",
                    lead_id,
                    user_id,
                    due_at,
                    existing_guard["job_id"],
                )

            guard_insert = cur.execute(
                """
                INSERT OR IGNORE INTO followup_reconcile_guard (
                    lead_id,
                    due_at,
                    status,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (lead_id, due_at, _RECONCILE_GUARD_STATUS_ENQUEUED),
            )
            if guard_insert.rowcount == 0:
                skipped_duplicate += 1
                logger.info(
                    "followup.reconcile_skip_duplicate lead_id=%s user_id=%s due_at=%s",
                    lead_id,
                    user_id,
                    due_at,
                )
                cur.execute(
                    """
                    INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
                    VALUES (?, NULL, NULL, 'followup_reconcile_skipped_duplicate', ?, ?)
                    """,
                    (
                        lead_id,
                        _json_dumps({"due_at": due_at, "reason": "guard_exists"}),
                        user_id,
                    ),
                )
                continue

            if dry_run:
                skipped_dry_run += 1
                cur.execute(
                    "DELETE FROM followup_reconcile_guard WHERE lead_id = ? AND due_at = ?",
                    (lead_id, due_at),
                )
                continue

            payload: Dict[str, Any] = {
                "lead_id": lead_id,
                "user_id": user_id,
                "due_at": due_at,
                "source": "followup_reconciler",
                "enqueued_at": _now_iso_utc(),
            }
            payload_txt = _json_dumps(payload)

            cur.execute(
                """
                INSERT INTO jobs (
                    user_id,
                    type,
                    payload,
                    status,
                    priority,
                    attempts,
                    assigned_agent_id,
                    created_at,
                    updated_at,
                    scheduled_at,
                    started_at,
                    completed_at,
                    result,
                    error
                ) VALUES (?, ?, ?, 'pending', 0, 0, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL, NULL, NULL)
                """,
                (user_id, TYPE_FOLLOWUP_TICK, payload_txt),
            )
            job_id = int(cur.lastrowid)
            enqueued += 1

            cur.execute(
                """
                UPDATE followup_reconcile_guard
                   SET job_id = ?,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE lead_id = ? AND due_at = ?
                """,
                (job_id, lead_id, due_at),
            )

            cur.execute(
                """
                INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
                VALUES (?, NULL, NULL, 'followup_job_enqueued', ?, ?)
                """,
                (
                    lead_id,
                    _json_dumps({"job_id": job_id, "job_type": TYPE_FOLLOWUP_TICK, "due_at": due_at}),
                    user_id,
                ),
            )

            logger.info(
                "followup.reconcile_job_enqueued lead_id=%s user_id=%s due_at=%s job_id=%s",
                lead_id,
                user_id,
                due_at,
                job_id,
            )
            items.append({"lead_id": lead_id, "job_id": job_id, "due_at": due_at})

        conn.commit()

    return {
        "scanned": scanned,
        "eligible": eligible,
        "enqueued": enqueued,
        "skipped_duplicate": skipped_duplicate,
        "skipped_dry_run": skipped_dry_run,
        "skipped_outside_window": skipped_outside_window,
        "skipped_circuit_breaker": skipped_circuit_breaker,
        "job_type": TYPE_FOLLOWUP_TICK,
        "items": items,
    }


def scan_inactive_leads_for_auto_followup(*, limit: int = 100) -> Dict[str, Any]:
    """
    Detecta leads silenciosos em `apresentation` e inicia follow-up automaticamente.

    Elegibilidade:
      - category = 'apresentation', bot_disabled = 0, is_playground = 0
      - sem contrato de follow-up activo/scheduled
      - AI Profile do usuário com followup_auto_trigger_enabled = true
      - inatividade (última msg inbound, fallback lastMovement) >=
        followup_auto_trigger_inactivity_days
      - qualificação completa (mesmo guardrail do start-followup manual)
      - agent_type elegível (agent_1/agent_3)
      - fora do cooldown (followup_auto_trigger_last_fired_at)
    """
    from services.qualification_guardrails import can_advance_from_qualification
    from services.followup_state import start_followup_for_inactivity, resolve_auto_inactivity_variant

    with get_connection() as read_conn:
        rows = read_conn.execute(
            """
            SELECT id, user_id, agent_type, lastMovement, followup_auto_trigger_last_fired_at
              FROM leads
             WHERE category = 'apresentation'
               AND COALESCE(bot_disabled, 0) = 0
               AND COALESCE(is_playground, 0) = 0
               AND (followup_status IS NULL OR followup_status NOT IN ('active', 'scheduled'))
             ORDER BY id ASC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return {"scanned": 0, "started": 0, "items": []}

    user_ids = {row["user_id"] for row in rows}
    profile_cache = _fetch_profile_cache(user_ids)
    now_utc = datetime.now(timezone.utc)

    started = 0
    items: List[Dict[str, Any]] = []

    for row in rows:
        lead_id = int(row["id"])
        user_id = row["user_id"]
        profile = profile_cache.get(user_id) or {}

        if not profile.get("followup_auto_trigger_enabled"):
            continue

        variant = resolve_auto_inactivity_variant(row["agent_type"])
        if not variant:
            continue

        try:
            inactivity_days = int(profile.get("followup_auto_trigger_inactivity_days") or 3)
        except (TypeError, ValueError):
            inactivity_days = 3
        threshold = timedelta(days=max(inactivity_days, 1))

        last_fired_at = _parse_naive_utc(row["followup_auto_trigger_last_fired_at"])
        if last_fired_at and now_utc - last_fired_at < threshold:
            continue  # cooldown ainda activo

        with get_connection() as conn:
            last_inbound_row = conn.execute(
                """
                SELECT MAX(createdAt) AS last_at FROM messages
                 WHERE lead_id = ? AND channel = 'whatsapp' AND model = 'inbound'
                """,
                (lead_id,),
            ).fetchone()
        last_inbound_at = _parse_naive_utc(last_inbound_row["last_at"] if last_inbound_row else None)
        last_movement_at = _parse_naive_utc(row["lastMovement"])

        candidates = [d for d in (last_inbound_at, last_movement_at) if d]
        if not candidates:
            continue  # sem nenhum sinal de actividade — não dá para avaliar inactividade
        last_activity_at = max(candidates)
        if now_utc - last_activity_at < threshold:
            continue  # ainda não está inactivo o suficiente

        with get_connection() as conn:
            can_advance, _missing = can_advance_from_qualification(conn, lead_id, user_id)
            if not can_advance:
                conn.rollback()
                continue

            result = start_followup_for_inactivity(
                conn, lead_id=lead_id, user_id=user_id, agent_type=row["agent_type"]
            )
            if result.get("started"):
                conn.commit()
                started += 1
                items.append(
                    {"lead_id": lead_id, "user_id": user_id, "followup_variant": result.get("followup_variant")}
                )
                logger.info(
                    "followup.auto_inactivity_started lead_id=%s user_id=%s variant=%s",
                    lead_id,
                    user_id,
                    result.get("followup_variant"),
                )
            else:
                conn.rollback()

    return {"scanned": len(rows), "started": started, "items": items}
