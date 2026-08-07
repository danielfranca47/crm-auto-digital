"""
ingest_worker.py — Worker interno para processar jobs knowledge.ingest.internal.

Executado como loop em background no backend-crm (app.py), no mesmo padrão do
spy_media_worker: SELECT por tipo + CAS pending→in_progress, sem agente externo.

Pipeline por job: extrai o texto de cada fonte do lote → classifica nas
categorias do template via LLM (classifier.py) → propõe o conteúdo por
categoria em jobs.result (nada é gravado em knowledge_items ainda) → result
final com proposed/uncovered/skipped_existing. A gravação efetiva só acontece
via apply_ingest_review(), quando o utilizador aprova as categorias propostas
(ver POST /api/knowledge/ingest/{job_id}/apply em routes/knowledge_ingest.py).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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

    proposed = []
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
        proposed.append(
            {
                "category": key,
                "label": label,
                "content": entry["content"],
                "preview": entry["content"][:_PREVIEW_CHARS],
            }
        )

    # Result final sem o texto integral das fontes (fica leve para polling/auditoria).
    # Nada é gravado em knowledge_items aqui — "proposed" só vira item real via
    # apply_ingest_review(), quando o utilizador aprova a categoria.
    slim_sources = [{k: v for k, v in s.items() if k != "text"} for s in sources]
    return {
        "phase": "done",
        "sources": slim_sources,
        "proposed": proposed,
        "applied": [],
        "uncovered": uncovered,
        "skipped_existing": skipped_existing,
    }


def apply_ingest_review(
    job_id: int,
    user_id: int,
    approved_keys: List[str],
    edited_content: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Grava em knowledge_items as categorias aprovadas dentre as propostas de um
    job já concluído (ver POST /api/knowledge/ingest/{job_id}/apply).

    edited_content (categoria -> texto) permite gravar uma correção feita pelo
    utilizador na tela de revisão em vez do texto original do classificador —
    cai para o texto original se a categoria não tiver edição ou vier vazia
    (evita gravar um item em branco por um campo limpo sem querer).

    Idempotente: reaplicar uma key já aplicada não duplica o item — volta em
    "already_applied". Levanta LookupError se o job não existir/não pertencer
    ao usuário, ValueError se ainda não estiver 'completed'.
    """
    edited_content = edited_content or {}
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT type, status, result FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        ).fetchone()
        if not row or row["type"] != _TYPE:
            raise LookupError("job de ingestão não encontrado")
        if row["status"] != "completed":
            raise ValueError("job de ingestão ainda não foi concluído")

        result: Dict[str, Any] = json.loads(row["result"] or "{}")
        proposed = result.get("proposed") or []
        applied = result.get("applied") or []
        proposed_by_key = {p.get("category"): p for p in proposed if p.get("category")}
        applied_keys = {a["category"] for a in applied}

        existing = _existing_categories(user_id)

        applied_now = []
        already_applied = []
        now_existing = []
        for key in dict.fromkeys(approved_keys or []):
            if key in applied_keys:
                already_applied.append(key)
                continue
            entry = proposed_by_key.get(key)
            if not entry:
                continue
            if key in existing:
                now_existing.append(key)
                continue
            content = (edited_content.get(key) or "").strip() or (entry.get("content") or "")
            item_id = _insert_ai_item(user_id, entry.get("label") or key, key, content)
            applied_entry = {
                "category": key,
                "item_id": item_id,
                "preview": content[:_PREVIEW_CHARS],
            }
            applied.append(applied_entry)
            applied_keys.add(key)
            applied_now.append(applied_entry)

        # Todo o lote apresentado nesta chamada foi decidido: aplicado, já aplicado,
        # colidiu com item existente (now_existing) ou descartado por desmarcação —
        # nada fica pendente de revisão depois de um apply, mesmo com 0 aprovados
        # (ver find_pending_review_job_id, que depende de proposed vazio para saber
        # que a revisão já foi concluída).
        result["applied"] = applied
        result["proposed"] = []

        conn.execute(
            "UPDATE jobs SET result = ?, updated_at = ? WHERE id = ?",
            (json.dumps(result, ensure_ascii=False), _now_utc_iso(), job_id),
        )
        conn.commit()
    finally:
        conn.close()

    if any(e["category"] == "objections_faq" for e in applied_now):
        try:
            from services.meta_prompter_trigger import trigger_meta_prompter_for_knowledge

            trigger_meta_prompter_for_knowledge(user_id)
        except Exception as exc:
            logger.warning("[knowledge_ingest] meta_prompter trigger falhou user_id=%s: %s", user_id, exc)

    logger.info(
        "[knowledge_ingest] apply job_id=%d user_id=%s aplicadas=%d ja_aplicadas=%d ja_existentes=%d",
        job_id, user_id, len(applied_now), len(already_applied), len(now_existing),
    )
    return {"applied": applied_now, "already_applied": already_applied, "now_existing": now_existing}


def find_pending_review_job_id(user_id: int) -> Optional[int]:
    """
    Último job completed do usuário cujo apply nunca foi chamado (proposed ainda não
    vazio) — ver POST /api/knowledge/ingest/pending. Mesmo padrão de
    jobs_service.find_pending_inbound_job.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id FROM jobs
             WHERE user_id = ?
               AND type = ?
               AND status = 'completed'
               AND json_array_length(result, '$.proposed') > 0
             ORDER BY completed_at DESC, id DESC
             LIMIT 1
            """,
            (user_id, _TYPE),
        ).fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


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
