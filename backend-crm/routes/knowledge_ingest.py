# routes/knowledge_ingest.py
"""
Ingestão de materiais para a base de conhecimento (Camada 4).

POST /api/knowledge/ingest        — recebe lote de fontes (arquivos + URLs) e enfileira
                                    o job knowledge.ingest.internal (worker interno).
GET  /api/knowledge/ingest/{id}   — status do job para polling do frontend.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from database import get_connection
from security_core import CurrentUser, require_crm_access
from services.jobs_service import TYPE_KNOWLEDGE_INGEST, create_job, get_job
from services.knowledge_ingest.extractors import (
    IMAGE_EXTENSIONS,
    SUPPORTED_FILE_EXTENSIONS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge/ingest", tags=["Knowledge Ingest"])

INGEST_UPLOAD_BASE = Path("data/uploads/knowledge/ingest")
INGEST_UPLOAD_BASE.mkdir(parents=True, exist_ok=True)

MAX_SOURCES_PER_BATCH = 6
MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB


def _has_active_ingest_job(user_id: int) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM jobs
             WHERE type = ? AND user_id = ? AND status IN ('pending','in_progress')
             LIMIT 1
            """,
            (TYPE_KNOWLEDGE_INGEST, user_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _sanitize_result(result: Any) -> Any:
    """Remove o texto integral das fontes do result (payload de polling fica leve)."""
    if not isinstance(result, dict):
        return result
    sanitized = dict(result)
    sources = sanitized.get("sources")
    if isinstance(sources, list):
        slim = []
        for src in sources:
            if isinstance(src, dict):
                src = {k: v for k, v in src.items() if k != "text"}
            slim.append(src)
        sanitized["sources"] = slim
    return sanitized


@router.post("")
async def create_ingest_batch(
    files: List[UploadFile] = File(default=[]),
    meta: str = Form(...),
    current_user: CurrentUser = Depends(require_crm_access),
):
    try:
        meta_obj: Dict[str, Any] = json.loads(meta)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="meta deve ser JSON válido")

    raw_sources = meta_obj.get("sources") or []
    if not isinstance(raw_sources, list) or not raw_sources:
        raise HTTPException(status_code=400, detail="meta.sources é obrigatório")
    if len(raw_sources) > MAX_SOURCES_PER_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo de {MAX_SOURCES_PER_BATCH} fontes por lote",
        )

    if _has_active_ingest_job(current_user.id):
        raise HTTPException(
            status_code=409,
            detail="Já existe uma ingestão em andamento. Aguarde a conclusão.",
        )

    files_by_name: Dict[str, UploadFile] = {}
    for f in files:
        if f.filename:
            files_by_name[f.filename] = f

    accepted_sources: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    saved_paths: List[Path] = []

    for raw in raw_sources:
        if not isinstance(raw, dict):
            rejected.append({"source": raw, "reason": "formato_invalido"})
            continue
        kind = raw.get("kind")
        description = (raw.get("description") or "").strip()

        if kind == "url":
            url = (raw.get("url") or "").strip()
            if not url:
                rejected.append({"url": url, "reason": "url_vazia"})
                continue
            accepted_sources.append({"kind": "url", "url": url, "description": description})
            continue

        if kind == "file":
            filename = raw.get("filename") or ""
            upload = files_by_name.get(filename)
            if upload is None:
                rejected.append({"filename": filename, "reason": "arquivo_nao_enviado"})
                continue
            ext = Path(filename).suffix.lower()
            if ext not in SUPPORTED_FILE_EXTENSIONS:
                rejected.append({"filename": filename, "reason": "extensao_nao_suportada"})
                continue
            content = await upload.read()
            limit = MAX_IMAGE_BYTES if ext in IMAGE_EXTENSIONS else MAX_FILE_BYTES
            if len(content) > limit:
                rejected.append({"filename": filename, "reason": "arquivo_muito_grande"})
                continue
            dest = INGEST_UPLOAD_BASE / f"{uuid.uuid4().hex}{ext}"
            try:
                dest.write_bytes(content)
            except Exception as exc:
                rejected.append({"filename": filename, "reason": f"falha_ao_salvar: {exc}"})
                continue
            saved_paths.append(dest)
            accepted_sources.append(
                {
                    "kind": "file",
                    "path": str(dest),
                    "filename": filename,
                    "ext": ext,
                    "description": description,
                }
            )
            continue

        rejected.append({"source": raw, "reason": "kind_invalido"})

    if not accepted_sources:
        for p in saved_paths:
            p.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail={"message": "Nenhuma fonte válida no lote", "rejected": rejected},
        )

    payload = {
        "user_id": current_user.id,
        "sources": accepted_sources,
        "context": meta_obj.get("context") or {},
        "categories": meta_obj.get("categories") or [],
    }
    job = create_job(
        job_type=TYPE_KNOWLEDGE_INGEST,
        payload=payload,
        user_id=current_user.id,
    )
    logger.info(
        "[knowledge_ingest] lote criado job_id=%s user_id=%s fontes=%d rejeitadas=%d",
        job["id"],
        current_user.id,
        len(accepted_sources),
        len(rejected),
    )

    return {
        "job_id": job["id"],
        "status": job["status"],
        "accepted": len(accepted_sources),
        "rejected": rejected,
    }


@router.get("/{job_id}")
async def get_ingest_status(
    job_id: int,
    current_user: CurrentUser = Depends(require_crm_access),
):
    job = get_job(job_id, user_id=current_user.id)
    if not job or job.get("type") != TYPE_KNOWLEDGE_INGEST:
        raise HTTPException(status_code=404, detail="Job de ingestão não encontrado")

    return {
        "job_id": job["id"],
        "status": job["status"],
        "result": _sanitize_result(job.get("result")),
        "error": job.get("error"),
    }
