"""
ingest_worker.py — Worker interno para processar jobs knowledge.ingest.internal.

Executado como loop em background no backend-crm (app.py), no mesmo padrão do
spy_media_worker: SELECT por tipo + CAS pending→in_progress, sem agente externo.

Pipeline por job: extrai o texto de cada fonte do lote → classifica nas
categorias do template via LLM (classifier.py) → grava knowledge_items com
source_type='ai_extracted' apenas nas categorias sem item existente do usuário
→ result final com covered/uncovered/skipped_existing.
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


_PREVIEW_CHARS = 120


def _extract_all_sources(payload: Dict[str, Any]) -> list:
    """Extrai o texto de todas as fontes do lote (campo 'text' fica em memória)."""
    from services.knowledge_ingest.extractors import extract_source

    results = []
    for source in payload.get("sources") or []:
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
    return results


def _existing_categories(user_id: int) -> set:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM knowledge_items WHERE user_id = ? AND category IS NOT NULL",
            (user_id,),
        ).fetchall()
        return {row["category"] for row in rows}
    finally:
        conn.close()


def _insert_ai_item(user_id: int, title: str, category: str, content: str) -> int:
    conn = get_connection()
    try:
        now_iso = datetime.utcnow().isoformat()
        cur = conn.execute(
            """
            INSERT INTO knowledge_items
                (user_id, title, source_type, content_text, file_path, category, active_in_funnel, created_at, updated_at)
            VALUES (?, ?, 'ai_extracted', ?, NULL, ?, 1, ?, ?)
            """,
            (user_id, title, content, category, now_iso, now_iso),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _process_ingest_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai fontes → classifica → grava itens ai_extracted. Retorna o result do job."""
    from services.knowledge_ingest.classifier import classify_sources

    user_id = int(payload.get("user_id") or 0)
    categories = payload.get("categories") or []
    context = payload.get("context") or {}

    sources = _extract_all_sources(payload)
    extracted = [s for s in sources if s["status"] == "extracted"]

    classified: Dict[str, Dict[str, Any]] = {}
    if extracted and categories:
        classified = classify_sources(extracted, categories, context)

    existing = _existing_categories(user_id) if user_id else set()

    covered = []
    uncovered = []
    skipped_existing = []
    for cat in categories:
        key = cat.get("key")
        if not key:
            continue
        entry = classified.get(key)
        if not entry:
            uncovered.append(key)
            continue
        if key in existing:
            skipped_existing.append(key)
            continue
        label = cat.get("label") or key
        item_id = _insert_ai_item(user_id, label, key, entry["content"])
        covered.append(
            {
                "category": key,
                "item_id": item_id,
                "preview": entry["content"][:_PREVIEW_CHARS],
            }
        )

    if any(c["category"] == "objections_faq" for c in covered):
        try:
            from services.meta_prompter_trigger import trigger_meta_prompter_for_knowledge

            trigger_meta_prompter_for_knowledge(user_id)
        except Exception as exc:
            logger.warning("[knowledge_ingest] meta_prompter trigger falhou user_id=%s: %s", user_id, exc)

    # Result final sem o texto integral das fontes (fica leve para polling/auditoria)
    slim_sources = [{k: v for k, v in s.items() if k != "text"} for s in sources]
    return {
        "phase": "done",
        "sources": slim_sources,
        "covered": covered,
        "uncovered": uncovered,
        "skipped_existing": skipped_existing,
    }


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
