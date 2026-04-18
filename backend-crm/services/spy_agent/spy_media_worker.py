"""
spy_media_worker.py — Worker interno para processar jobs spy.media.process.

Executado como loop em background no backend-crm (app.py).
Áudio → Whisper, Imagem → GPT-4o Vision.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from database import get_connection

logger = logging.getLogger(__name__)

_TYPE = "spy.media.process"
_BATCH_SIZE = 5


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def process_pending_spy_media_jobs(batch_size: int = _BATCH_SIZE) -> Dict[str, int]:
    """
    Processa até `batch_size` jobs spy.media.process pendentes.
    Retorna contadores: processed, failed.
    """
    from services.spy_agent.media_processor import process_spy_media_job

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
            (_TYPE, now, batch_size),
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
                # Outro worker (improvável, mas defensivo) já pegou
                continue

            payload: Dict[str, Any] = {}
            try:
                payload = json.loads(row["payload"] or "{}")
                process_spy_media_job(payload)
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
                logger.info("[spy_media_worker] job concluído job_id=%d", job_id)
            except Exception as exc:
                logger.error("[spy_media_worker] falha job_id=%d: %s", job_id, exc)
                # Verifica tentativas para decidir entre retry e falha definitiva
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
