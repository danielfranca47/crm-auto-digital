"""
classify_worker.py — Worker interno para processar jobs
collab_monitor.classify.local.

Executado como loop em background no backend-crm (app.py), mesmo padrão de
services/spy_agent/spy_media_worker.py. Lê o histórico de um lead monitorado,
chama o classificador read-only (classifier.py) e, se houver estágio
sugerido e a mudança for um avanço válido no funil, atualiza leads.category.

Nunca chama orchestrator/decision_engine/guardrail do pipeline real — mesmo
princípio de isolamento de monitor_inbound_handler.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import get_connection
from services.jobs_service import TYPE_COLLAB_MONITOR_CLASSIFY

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5

# Ordem do funil para o guardrail de não-retrocesso. "monitoring" é o estado
# inicial de todo lead monitorado (find_or_create_monitor_lead) — qualquer
# estágio real listado abaixo conta como avanço a partir dele.
_FUNNEL_ORDER = {
    "monitoring": 0,
    "qualification": 1,
    "apresentation": 2,
    "follow-up": 3,
    "closing": 4,
    "client-list": 5,
}

# Saídas do funil — terminais. Uma vez aplicadas, só reativação manual pelo
# Kanban (mesmo comportamento unidirecional de services/lead_category_policy.py
# para closing/disqualified/prospect-refused).
_EXIT_CATEGORIES = {"prospect-refused", "disqualified"}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_valid_forward_move(old_category: Optional[str], new_category: str) -> bool:
    """Guardrail de não-retrocesso: só aplica se for avanço no funil ou saída."""
    old_norm = (old_category or "monitoring").strip().lower()
    if old_norm in _EXIT_CATEGORIES:
        return False  # terminal — só reativação manual

    if new_category in _EXIT_CATEGORIES:
        return True

    old_rank = _FUNNEL_ORDER.get(old_norm)
    new_rank = _FUNNEL_ORDER.get(new_category)
    if old_rank is None or new_rank is None:
        # categoria atual fora do conjunto conhecido (ex.: lead movido
        # manualmente para prospecção) — não arrisca mover sozinho.
        return False
    return new_rank > old_rank


def _apply_classification(conn, *, lead_id: int, user_id: int) -> Dict[str, Any]:
    from services.collab_monitor.classifier import classify_monitor_lead

    row = conn.execute(
        "SELECT category FROM leads WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    ).fetchone()
    if not row:
        return {"applied": False, "reason": "lead_not_found"}

    old_category = row["category"]
    result = classify_monitor_lead(lead_id)
    suggested = result.get("suggested_category")

    if not suggested:
        return {"applied": False, "reason": "no_signal"}

    if suggested == old_category:
        return {"applied": False, "reason": "unchanged"}

    if not _is_valid_forward_move(old_category, suggested):
        logger.info(
            "[collab_monitor:classify_worker] retrocesso ignorado lead_id=%s old=%s suggested=%s",
            lead_id,
            old_category,
            suggested,
        )
        return {"applied": False, "reason": "backward_move_blocked"}

    conn.execute(
        "UPDATE leads SET category = ?, lastMovement = CURRENT_TIMESTAMP WHERE id = ?",
        (suggested, lead_id),
    )
    notes = {
        "old_category": old_category,
        "new_category": suggested,
        "category_reason": result.get("category_reason"),
        "source": "collab_monitor_classifier",
    }
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, NULL, NULL, 'collab_monitor_category_changed', ?, ?)
        """,
        (lead_id, json.dumps(notes, ensure_ascii=False), user_id),
    )
    logger.info(
        "[collab_monitor:classify_worker] categoria atualizada lead_id=%s %s -> %s",
        lead_id,
        old_category,
        suggested,
    )
    return {"applied": True}


def process_pending_collab_monitor_classify_jobs(batch_size: int = _BATCH_SIZE) -> Dict[str, int]:
    """
    Processa até `batch_size` jobs collab_monitor.classify.local pendentes.
    Retorna contadores: processed, failed.
    """
    now = _now_utc_iso()
    processed = 0
    failed = 0

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, payload
              FROM jobs
             WHERE type = ?
               AND status = 'pending'
               AND attempts < 3
               AND (scheduled_at IS NULL OR scheduled_at <= ?)
             ORDER BY created_at ASC
             LIMIT ?
            """,
            (TYPE_COLLAB_MONITOR_CLASSIFY, now, batch_size),
        ).fetchall()

        for row in rows:
            job_id = int(row["id"])

            # Tenta adquirir o job (CAS: muda de pending → in_progress só se ainda pending)
            updated = conn.execute(
                """
                UPDATE jobs
                   SET status = 'in_progress',
                       started_at = ?,
                       attempts = attempts + 1,
                       updated_at = ?
                 WHERE id = ? AND status = 'pending'
                """,
                (now, now, job_id),
            ).rowcount
            conn.commit()

            if not updated:
                continue

            payload: Dict[str, Any] = {}
            try:
                payload = json.loads(row["payload"] or "{}")
                lead_id = int(payload["lead_id"])
                user_id = int(payload["user_id"])
                _apply_classification(conn, lead_id=lead_id, user_id=user_id)
                conn.execute(
                    """
                    UPDATE jobs
                       SET status = 'completed',
                           completed_at = ?,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (now, now, job_id),
                )
                processed += 1
                logger.info("[collab_monitor:classify_worker] job concluído job_id=%d", job_id)
            except Exception as exc:
                logger.error("[collab_monitor:classify_worker] falha job_id=%d: %s", job_id, exc)
                attempts_row = conn.execute(
                    "SELECT attempts FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
                attempts = int(attempts_row["attempts"]) if attempts_row else 3
                new_status = "failed" if attempts >= 3 else "pending"
                conn.execute(
                    """
                    UPDATE jobs
                       SET status = ?,
                           error = ?,
                           completed_at = CASE WHEN ? = 'failed' THEN ? ELSE NULL END,
                           started_at = CASE WHEN ? = 'pending' THEN NULL ELSE started_at END,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (new_status, str(exc)[:500], new_status, now, new_status, now, job_id),
                )
                failed += 1
            conn.commit()
    finally:
        conn.close()

    return {"processed": processed, "failed": failed}
