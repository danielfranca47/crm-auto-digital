"""
ingest_worker.py — Worker interno para processar jobs knowledge.ingest.internal.

Executado como loop em background no backend-crm (app.py), no mesmo padrão do
spy_media_worker: SELECT por tipo + CAS pending→in_progress, sem agente externo.

Fase atual (fundação): extrai o texto de cada fonte do lote e grava o resultado
no job (phase="extracted"). A classificação por LLM e a gravação dos
knowledge_items entram na fase seguinte da implementação.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from database import get_connection

logger = logging.getLogger(__name__)

_TYPE = "knowledge.ingest.internal"
# Lotes de ingestão são pesados (vision + scraping [+ LLM]); processa 1 por vez
# para não concorrer por rede/API no mesmo processo.
_BATCH_SIZE = 1


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _process_ingest_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai o texto de todas as fontes do lote. Retorna o result a gravar no job."""
    from services.knowledge_ingest.extractors import extract_source

    sources = payload.get("sources") or []
    results = []
    for source in sources:
        extraction = extract_source(source)
        entry: Dict[str, Any] = {
            "status": extraction["status"],
            "chars": extraction["chars"],
            "reason": extraction["reason"],
            "text": extraction["text"],
            "description": source.get("description") or "",
        }
        if source.get("kind") == "url":
            entry["url"] = source.get("url")
        else:
            entry["filename"] = source.get("filename")
        results.append(entry)
        logger.info(
            "[knowledge_ingest] fonte %s status=%s chars=%d",
            entry.get("url") or entry.get("filename"),
            entry["status"],
            entry["chars"],
        )

    return {"phase": "extracted", "sources": results}


def process_pending_knowledge_ingest_jobs(batch_size: int = _BATCH_SIZE) -> Dict[str, int]:
    """
    Processa até `batch_size` jobs knowledge.ingest.internal pendentes.
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
                continue

            try:
                payload: Dict[str, Any] = json.loads(row["payload"] or "{}")
                result = _process_ingest_job(payload)
                conn.execute(
                    """
                    UPDATE jobs
                       SET status = 'completed',
                           result = ?,
                           completed_at = ?,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (json.dumps(result, ensure_ascii=False), now, now, job_id),
                )
                processed += 1
                logger.info("[knowledge_ingest_worker] job concluído job_id=%d", job_id)
            except Exception as exc:
                logger.error("[knowledge_ingest_worker] falha job_id=%d: %s", job_id, exc, exc_info=True)
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
