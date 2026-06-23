from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.jobs_service import TYPE_WHATSAPP_FOLLOWUP_PREGENERATE, create_job


STOP_INBOUND_REPLY = "inbound_reply"
STOP_DEAL_CLOSED = "deal_closed"
STOP_EXPLICIT_REJECTION = "explicit_rejection"
STOP_HANDOFF_HUMAN = "handoff_human"
STOP_MAX_ATTEMPTS_REACHED = "max_attempts_reached"
STOP_MANUAL_CANCEL = "manual_cancel"

_FOLLOWUP_SEND_NEXT_SCHEDULE = {
    "sdr_scheduler": {
        1: timedelta(hours=24),
        2: timedelta(days=3),
        3: timedelta(days=7),
    },
    "hybrid_scheduler": {
        1: timedelta(hours=24),
        2: timedelta(hours=48),
    },
    # cart_recovery: após 1ª send → próxima em 24h; após 2ª send → próxima em 48h
    "cart_recovery": {
        1: timedelta(minutes=1440),
        2: timedelta(minutes=2880),
    },
}


def _parse_contract(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _json_dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_next_followup_at(
    *,
    variant: str,
    attempts_after_send: int,
    sent_at: datetime,
    cadence_override: Optional[List[int]] = None,
) -> Optional[str]:
    if cadence_override:
        idx = attempts_after_send - 1  # 0-based: after 1st send → cadence[0]
        if idx < len(cadence_override):
            return (sent_at + timedelta(minutes=int(cadence_override[idx]))).isoformat()
        return None
    rules = _FOLLOWUP_SEND_NEXT_SCHEDULE.get((variant or "").strip().lower(), {})
    delta = rules.get(attempts_after_send)
    if not delta:
        return None
    return (sent_at + delta).isoformat()


def _write_followup(
    conn,
    *,
    lead_id: int,
    contract: Dict[str, Any],
    status: Optional[str] = None,
    next_followup_at: Optional[str] = None,
) -> None:
    if status is not None:
        contract["status"] = status
    if next_followup_at is not None or next_followup_at is None:
        contract["next_followup_at"] = next_followup_at

    conn.execute(
        """
        UPDATE leads
           SET followup_contract = ?,
               followup_status = ?,
               next_followup_at = ?,
               lastMovement = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (
            _json_dumps(contract),
            contract.get("status"),
            contract.get("next_followup_at"),
            lead_id,
        ),
    )


def _load_lead_followup_row(conn, *, lead_id: int):
    return conn.execute(
        """
        SELECT id, user_id, category, bot_disabled, followup_status, next_followup_at, followup_contract
          FROM leads
         WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()


def stop_followup(
    conn,
    *,
    lead_id: int,
    stop_reason: str,
    status: str,
    user_id: Optional[int] = None,
    source_action: str = "followup_stopped",
    source_notes: Optional[Dict[str, Any]] = None,
) -> bool:
    row = _load_lead_followup_row(conn, lead_id=lead_id)
    if not row:
        return False

    contract = _parse_contract(row["followup_contract"])
    if not contract:
        return False

    contract["stop_reason"] = stop_reason
    contract["status"] = status
    contract["next_followup_at"] = None

    _write_followup(conn, lead_id=lead_id, contract=contract, status=status, next_followup_at=None)

    effective_user_id = user_id if user_id is not None else row["user_id"]
    notes = {"stop_reason": stop_reason, "status": status}
    if source_notes:
        notes.update(source_notes)
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, ?, ?, ?)
        """,
        (lead_id, source_action, _json_dumps(notes), effective_user_id),
    )
    return True


def stop_followup_on_inbound_reply(
    conn,
    *,
    lead_id: int,
    user_id: int,
    inbound_message_id: Optional[str] = None,
) -> bool:
    return stop_followup(
        conn,
        lead_id=lead_id,
        stop_reason=STOP_INBOUND_REPLY,
        status="paused",
        user_id=user_id,
        source_action="followup_stopped_inbound",
        source_notes={"inbound_message_id": inbound_message_id},
    )


def stop_followup_on_handoff(conn, *, lead_id: int, user_id: int, reason: Optional[str] = None) -> bool:
    return stop_followup(
        conn,
        lead_id=lead_id,
        stop_reason=STOP_HANDOFF_HUMAN,
        status="paused",
        user_id=user_id,
        source_action="followup_stopped_handoff",
        source_notes={"reason": reason},
    )


def stop_followup_for_lead_category(conn, *, lead_id: int, user_id: int, new_category: Optional[str]) -> bool:
    normalized = str(new_category or "").strip().lower()
    if normalized == "client-list":
        return stop_followup(
            conn,
            lead_id=lead_id,
            stop_reason=STOP_DEAL_CLOSED,
            status="closed",
            user_id=user_id,
            source_action="followup_stopped_category",
            source_notes={"category": normalized},
        )
    if normalized in {"prospect-refused", "disqualified"}:
        return stop_followup(
            conn,
            lead_id=lead_id,
            stop_reason=STOP_EXPLICIT_REJECTION,
            status="closed",
            user_id=user_id,
            source_action="followup_stopped_category",
            source_notes={"category": normalized},
        )
    return False


def progress_followup_after_auto_send(
    conn,
    *,
    lead_id: int,
    user_id: int,
    source_job_id: Optional[int] = None,
    ai_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row = _load_lead_followup_row(conn, lead_id=lead_id)
    if not row:
        return {"updated": False, "reason": "lead_not_found"}

    contract = _parse_contract(row["followup_contract"])
    if not contract:
        return {"updated": False, "reason": "contract_missing"}

    if str(contract.get("status") or "").lower() != "active":
        return {"updated": False, "reason": "contract_not_active"}

    if int(row["bot_disabled"] or 0) == 1:
        stop_followup_on_handoff(conn, lead_id=lead_id, user_id=user_id, reason="bot_disabled")
        return {"updated": True, "reason": "stopped_handoff"}

    sent_at = _now_utc()
    attempts_before = int(contract.get("attempts") or 0)
    attempts_after = attempts_before + 1
    max_attempts = int(contract.get("max_attempts") or 0)
    variant = str(contract.get("followup_variant") or "").strip().lower()

    contract["attempts"] = attempts_after
    contract["last_followup_at"] = sent_at.isoformat()

    if max_attempts > 0 and attempts_after >= max_attempts:
        contract["status"] = "closed"
        contract["stop_reason"] = STOP_MAX_ATTEMPTS_REACHED
        contract["next_followup_at"] = None
        _write_followup(conn, lead_id=lead_id, contract=contract, status="closed", next_followup_at=None)
        conn.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, NULL, NULL, 'followup_closed_max_attempts', ?, ?)
            """,
            (
                lead_id,
                _json_dumps(
                    {
                        "source_job_id": source_job_id,
                        "attempts": attempts_after,
                        "max_attempts": max_attempts,
                        "stop_reason": STOP_MAX_ATTEMPTS_REACHED,
                    }
                ),
                user_id,
            ),
        )
        return {"updated": True, "reason": "max_attempts_reached", "attempts": attempts_after}

    cadence_override: Optional[List[int]] = None
    if ai_profile:
        raw_cadence = ai_profile.get("followup_cadence")
        if isinstance(raw_cadence, list) and raw_cadence:
            cadence_override = [int(x) for x in raw_cadence]

    next_followup_at = _resolve_next_followup_at(
        variant=variant,
        attempts_after_send=attempts_after,
        sent_at=sent_at,
        cadence_override=cadence_override,
    )
    contract["next_followup_at"] = next_followup_at
    contract["stop_reason"] = None
    contract["status"] = "active"
    contract.pop("scheduled_message", None)  # limpar mensagem da tentativa anterior

    _write_followup(conn, lead_id=lead_id, contract=contract, status="active", next_followup_at=next_followup_at)
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'followup_progressed_auto', ?, ?)
        """,
        (
            lead_id,
            _json_dumps(
                {
                    "source_job_id": source_job_id,
                    "attempts": attempts_after,
                    "max_attempts": max_attempts,
                    "next_followup_at": next_followup_at,
                }
            ),
            user_id,
        ),
    )
    create_job(
        job_type=TYPE_WHATSAPP_FOLLOWUP_PREGENERATE,
        payload={"lead_id": lead_id, "user_id": user_id},
        user_id=user_id,
    )
    return {"updated": True, "reason": "progressed", "attempts": attempts_after, "next_followup_at": next_followup_at}


def start_cart_recovery_followup(
    conn,
    *,
    lead_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """Inicia follow-up automático de carrinho abandonado para Agent 2 (closer).

    Chamado quando o bot envia mensagem contendo link de pagamento (offer_pack).
    Cadência: 2h (1ª), 24h (2ª), 48h (3ª) — max_attempts=3.
    Não inicia se já existe contrato ativo.
    """
    row = _load_lead_followup_row(conn, lead_id=lead_id)
    if not row:
        return {"started": False, "reason": "lead_not_found"}

    existing = _parse_contract(row["followup_contract"])
    if existing and str(existing.get("status") or "").lower() == "active":
        return {"started": False, "reason": "contract_already_active"}

    now = _now_utc()
    first_followup_at = (now + timedelta(minutes=120)).isoformat()

    contract: Dict[str, Any] = {
        "followup_variant": "cart_recovery",
        "status": "active",
        "attempts": 0,
        "max_attempts": 3,
        "next_followup_at": first_followup_at,
        "followup_goal": "cart_recovery",
        "outcome": None,
        "proposal_sent": True,
        "operator_note": None,
        "meeting_or_session_happened": None,
    }

    conn.execute(
        """
        UPDATE leads
           SET followup_contract = ?,
               followup_status = 'active',
               next_followup_at = ?,
               bot_disabled = 0,
               lastMovement = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (
            _json_dumps(contract),
            first_followup_at,
            lead_id,
        ),
    )
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'cart_recovery_started', ?, ?)
        """,
        (
            lead_id,
            _json_dumps({"max_attempts": 3, "first_followup_at": first_followup_at}),
            user_id,
        ),
    )
    return {"started": True, "next_followup_at": first_followup_at}


_AUTO_INACTIVITY_VARIANT_BY_AGENT_TYPE = {
    "agent_1": "sdr_scheduler",
    "agent_3": "hybrid_scheduler",
}
_AUTO_INACTIVITY_MAX_ATTEMPTS_BY_VARIANT = {
    "sdr_scheduler": 4,
    "hybrid_scheduler": 3,
}
_AUTO_INACTIVITY_GOAL_BY_VARIANT = {
    "sdr_scheduler": "reengage",
    "hybrid_scheduler": "reengage_conversation",
}
_AUTO_INACTIVITY_FIRST_OFFSET_MINUTES = 30


def resolve_auto_inactivity_variant(agent_type: Optional[str]) -> Optional[str]:
    return _AUTO_INACTIVITY_VARIANT_BY_AGENT_TYPE.get(str(agent_type or "").strip().lower())


def start_followup_for_inactivity(
    conn,
    *,
    lead_id: int,
    user_id: int,
    agent_type: Optional[str],
) -> Dict[str, Any]:
    """Inicia follow-up automaticamente para lead silencioso em `apresentation`.

    Mesmo formato de contrato de start_followup_transition (leads.py), mas sem input
    do operador — usa defaults neutros ("reengage") e trigger="auto_inactivity" para
    distinguir do gesto manual na Central de Follow-ups.
    """
    row = _load_lead_followup_row(conn, lead_id=lead_id)
    if not row:
        return {"started": False, "reason": "lead_not_found"}

    existing = _parse_contract(row["followup_contract"])
    if existing and str(existing.get("status") or "").lower() in {"active", "scheduled"}:
        return {"started": False, "reason": "contract_already_active"}

    variant = resolve_auto_inactivity_variant(agent_type)
    if not variant:
        return {"started": False, "reason": "agent_type_not_eligible"}

    now = _now_utc()
    first_followup_at = (now + timedelta(minutes=_AUTO_INACTIVITY_FIRST_OFFSET_MINUTES)).isoformat()
    max_attempts = _AUTO_INACTIVITY_MAX_ATTEMPTS_BY_VARIANT.get(variant, 3)
    goal = _AUTO_INACTIVITY_GOAL_BY_VARIANT.get(variant)

    contract: Dict[str, Any] = {
        "phase": "follow-up",
        "version": 1,
        "followup_variant": variant,
        "trigger": "auto_inactivity",
        "status": "active",
        "attempts": 0,
        "max_attempts": max_attempts,
        "next_followup_at": first_followup_at,
        "last_followup_at": None,
        "stop_reason": None,
        "meeting_or_session_happened": None,
        "outcome": None,
        "proposal_sent": False,
        "followup_goal": goal,
        "operator_note": None,
        "created_at": now.isoformat(),
    }

    conn.execute(
        """
        UPDATE leads
           SET category = 'follow-up',
               bot_disabled = 0,
               bot_disabled_reason = NULL,
               followup_contract = ?,
               followup_status = 'active',
               next_followup_at = ?,
               followup_auto_trigger_last_fired_at = CURRENT_TIMESTAMP,
               lastMovement = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (_json_dumps(contract), first_followup_at, lead_id),
    )
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'followup_started_auto_inactivity', ?, ?)
        """,
        (lead_id, _json_dumps(contract), user_id),
    )
    # create_job() abre a própria conexão — chamar só depois do commit do caller,
    # senão a transação ainda aberta deste UPDATE causa "database is locked".
    return {"started": True, "next_followup_at": first_followup_at, "followup_variant": variant}


def _cancel_pending_jobs_for_lead(conn, *, lead_id: int) -> int:
    """Cancela jobs pendentes de follow-up para o lead via guard table. Retorna count."""
    rows = conn.execute(
        """
        SELECT g.id AS guard_id, g.job_id
          FROM followup_reconcile_guard g
          JOIN jobs j ON j.id = g.job_id
         WHERE g.lead_id = ?
           AND j.status = 'pending'
        """,
        (lead_id,),
    ).fetchall()

    cancelled = 0
    for r in rows:
        conn.execute(
            "UPDATE jobs SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
            (r["job_id"],),
        )
        conn.execute(
            "DELETE FROM followup_reconcile_guard WHERE id = ?",
            (r["guard_id"],),
        )
        cancelled += 1

    return cancelled


def pause_followup_manually(
    conn,
    *,
    lead_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """Pausa manualmente o follow-up. Só permitido se status=active ou scheduled."""
    row = _load_lead_followup_row(conn, lead_id=lead_id)
    if not row:
        return {"updated": False, "reason": "lead_not_found"}

    contract = _parse_contract(row["followup_contract"])
    if not contract:
        return {"updated": False, "reason": "contract_missing"}

    current_status = str(contract.get("status") or "").lower()
    if current_status not in {"active", "scheduled"}:
        return {"updated": False, "reason": "invalid_status", "current_status": current_status}

    _cancel_pending_jobs_for_lead(conn, lead_id=lead_id)

    now = _now_utc()
    contract["status"] = "manually_paused"
    contract["manually_paused_at"] = now.isoformat()
    contract["next_followup_at"] = None

    _write_followup(conn, lead_id=lead_id, contract=contract, status="manually_paused", next_followup_at=None)
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'followup_manually_paused', ?, ?)
        """,
        (lead_id, _json_dumps({"paused_at": now.isoformat()}), user_id),
    )
    return {"updated": True, "reason": "paused"}


def resume_followup_manually(
    conn,
    *,
    lead_id: int,
    user_id: int,
    ai_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Retoma follow-up manualmente pausado. Recalcula next_followup_at = now + cadence[attempts]."""
    row = _load_lead_followup_row(conn, lead_id=lead_id)
    if not row:
        return {"updated": False, "reason": "lead_not_found"}

    contract = _parse_contract(row["followup_contract"])
    if not contract:
        return {"updated": False, "reason": "contract_missing"}

    current_status = str(contract.get("status") or "").lower()
    if current_status != "manually_paused":
        return {"updated": False, "reason": "not_manually_paused", "current_status": current_status}

    attempts = int(contract.get("attempts") or 0)
    max_attempts = int(contract.get("max_attempts") or 0)
    variant = str(contract.get("followup_variant") or "").strip().lower()

    if max_attempts > 0 and attempts >= max_attempts:
        return {"updated": False, "reason": "max_attempts_reached"}

    cadence_override: Optional[List[int]] = None
    if ai_profile:
        raw_cadence = ai_profile.get("followup_cadence")
        if isinstance(raw_cadence, list) and raw_cadence:
            cadence_override = [int(x) for x in raw_cadence]

    now = _now_utc()
    # next_followup_at = now + cadence[attempts] (0-based)
    # _resolve_next_followup_at(attempts_after_send=attempts+1) → idx = attempts
    next_followup_at = _resolve_next_followup_at(
        variant=variant,
        attempts_after_send=attempts + 1,
        sent_at=now,
        cadence_override=cadence_override,
    )

    contract["status"] = "active"
    contract["next_followup_at"] = next_followup_at
    contract["manually_paused_at"] = None
    contract["stop_reason"] = None

    _write_followup(conn, lead_id=lead_id, contract=contract, status="active", next_followup_at=next_followup_at)
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'followup_manually_resumed', ?, ?)
        """,
        (
            lead_id,
            _json_dumps({"attempts": attempts, "next_followup_at": next_followup_at}),
            user_id,
        ),
    )
    return {"updated": True, "reason": "resumed", "next_followup_at": next_followup_at}


def cancel_followup_manually(
    conn,
    *,
    lead_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """Cancela manualmente o follow-up. Permitido em qualquer status exceto closed."""
    row = _load_lead_followup_row(conn, lead_id=lead_id)
    if not row:
        return {"updated": False, "reason": "lead_not_found"}

    contract = _parse_contract(row["followup_contract"])
    if not contract:
        return {"updated": False, "reason": "contract_missing"}

    current_status = str(contract.get("status") or "").lower()
    if current_status == "closed":
        return {"updated": False, "reason": "already_closed"}

    _cancel_pending_jobs_for_lead(conn, lead_id=lead_id)

    contract["status"] = "closed"
    contract["stop_reason"] = STOP_MANUAL_CANCEL
    contract["next_followup_at"] = None

    _write_followup(conn, lead_id=lead_id, contract=contract, status="closed", next_followup_at=None)
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'followup_manually_cancelled', ?, ?)
        """,
        (lead_id, _json_dumps({"stop_reason": STOP_MANUAL_CANCEL}), user_id),
    )
    return {"updated": True, "reason": "cancelled"}
