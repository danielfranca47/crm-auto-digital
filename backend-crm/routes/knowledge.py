# routes/knowledge.py
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from core_client import fetch_core_ai_profile_resolve
from database import get_connection
from models import KnowledgeCreate, KnowledgeItemOut, KnowledgeUpdate
from security_core import CurrentUser, require_crm_access

logger = logging.getLogger(__name__)


def _trigger_meta_prompter_for_knowledge(user_id: int) -> None:
    """Fire-and-forget: regenera os blocos de prompt após edição de objections_faq."""
    base = os.getenv("EXECUTORS_BASE_URL", "").rstrip("/")
    token = os.getenv("CORE_SERVICE_TOKEN")
    if not base or not token:
        logger.debug("meta_prompter knowledge trigger ignorado: EXECUTORS_BASE_URL ou CORE_SERVICE_TOKEN ausente")
        return
    try:
        ai_profile = fetch_core_ai_profile_resolve(user_id)
    except Exception as exc:
        logger.warning("meta_prompter knowledge trigger: falha ao resolver ai_profile user_id=%s: %s", user_id, exc)
        return
    if not ai_profile:
        return
    url = f"{base}/api/meta-prompter/generate/{user_id}"
    headers = {"X-Service-Token": token, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, headers=headers, json={"ai_profile": ai_profile})
        if not resp.is_success:
            logger.warning("meta_prompter knowledge trigger falhou user_id=%s status=%s", user_id, resp.status_code)
    except Exception as exc:
        logger.warning("meta_prompter knowledge trigger erro user_id=%s: %s", user_id, exc)

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])

UPLOAD_BASE = Path("data/uploads/knowledge")
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)

MEDIA_BASE = Path("data/uploads/knowledge/media")
MEDIA_BASE.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".csv", ".xlsx"}
ALLOWED_MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".pdf"}


def _row_to_item(row) -> KnowledgeItemOut:
    data = {k: row[k] for k in row.keys()} if hasattr(row, "keys") else dict(row)
    return KnowledgeItemOut(**data)


def _extract_text_from_file(fp: Path) -> str:
    suffix = fp.suffix.lower()

    if suffix == ".txt":
        try:
            return fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return fp.read_text(encoding="latin-1")

    if suffix == ".csv":
        df = pd.read_csv(fp)
        return df.head(200).to_csv(index=False)

    if suffix == ".xlsx":
        xls = pd.ExcelFile(fp)
        sheet = "Leads" if "Leads" in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet)
        return df.head(200).to_csv(index=False)

    raise HTTPException(status_code=400, detail="Extensão de arquivo não suportada")


@router.get("", response_model=list[KnowledgeItemOut])
async def list_items(current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM knowledge_items
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (current_user.id,),
        )
        rows = cur.fetchall()
        return [_row_to_item(r) for r in rows]
    finally:
        conn.close()


@router.get("/{item_id}", response_model=KnowledgeItemOut)
async def get_item(item_id: int, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item não encontrado")
        return _row_to_item(row)
    finally:
        conn.close()


@router.post("", response_model=KnowledgeItemOut)
async def create_manual_item(
    payload: KnowledgeCreate, current_user: CurrentUser = Depends(require_crm_access)
):
    conn = get_connection()
    try:
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        active = payload.active_in_funnel if payload.active_in_funnel is not None else 1
        cur.execute(
            """
            INSERT INTO knowledge_items (user_id, title, source_type, content_text, file_path, category, active_in_funnel, created_at, updated_at)
            VALUES (?, ?, 'manual', ?, NULL, ?, ?, ?, ?)
            """,
            (current_user.id, payload.title, payload.content_text, payload.category, active, now_iso, now_iso),
        )
        conn.commit()

        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ?",
            (cur.lastrowid,),
        )
        row = cur.fetchone()
        return _row_to_item(row)
    finally:
        conn.close()


@router.put("/{item_id}", response_model=KnowledgeItemOut)
async def update_item(
    item_id: int,
    payload: KnowledgeUpdate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_crm_access),
):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Item não encontrado")

        fields, values = [], []
        if payload.title is not None:
            fields.append("title = ?")
            values.append(payload.title)
        if payload.content_text is not None:
            fields.append("content_text = ?")
            values.append(payload.content_text)
        if payload.category is not None:
            fields.append("category = ?")
            values.append(payload.category)
        if payload.active_in_funnel is not None:
            fields.append("active_in_funnel = ?")
            values.append(payload.active_in_funnel)
        if payload.media_url is not None:
            fields.append("media_url = ?")
            values.append(payload.media_url)

        if not fields:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

        fields.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.extend([item_id, current_user.id])

        cur.execute(
            f"UPDATE knowledge_items SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values),
        )
        conn.commit()

        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        row = cur.fetchone()
        result = _row_to_item(row)
    finally:
        conn.close()

    # Trigger 3: edição de objections_faq → regenerar blocos de prompt
    effective_category = payload.category if payload.category is not None else (existing["category"] if hasattr(existing, "__getitem__") else None)
    if effective_category == "objections_faq" and payload.content_text is not None:
        background_tasks.add_task(_trigger_meta_prompter_for_knowledge, current_user.id)

    return result


@router.delete("/{item_id}")
async def delete_item(item_id: int, current_user: CurrentUser = Depends(require_crm_access)):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item não encontrado")

        file_path = row["file_path"] if hasattr(row, "__getitem__") else None
        media_url = row["media_url"] if hasattr(row, "__getitem__") else None
        cur.execute(
            "DELETE FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        conn.commit()

        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass

        # Apagar mídia associada se for um arquivo local
        if media_url:
            _try_delete_media_file(media_url)

        return {"ok": True}
    finally:
        conn.close()


@router.post("/upload", response_model=KnowledgeItemOut)
async def upload_file(
    file: UploadFile = File(...), current_user: CurrentUser = Depends(require_crm_access)
):
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Apenas arquivos .txt, .csv ou .xlsx são suportados",
        )

    dest = UPLOAD_BASE / f"{uuid.uuid4()}{ext}"
    try:
        content = await file.read()
        dest.write_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar upload: {exc}")

    try:
        extracted_text = _extract_text_from_file(dest)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Falha ao ler arquivo: {exc}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO knowledge_items (user_id, title, source_type, content_text, file_path, active_in_funnel, created_at, updated_at)
            VALUES (?, ?, 'file', ?, ?, 1, ?, ?)
            """,
            (
                current_user.id,
                filename,
                extracted_text,
                str(dest),
                now_iso,
                now_iso,
            ),
        )
        conn.commit()

        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ?",
            (cur.lastrowid,),
        )
        row = cur.fetchone()
        return _row_to_item(row)
    finally:
        conn.close()


def _try_delete_media_file(media_url: str) -> None:
    """Tenta apagar o arquivo de mídia se for uma URL local do servidor."""
    try:
        public_base = os.getenv("CRM_PUBLIC_BASE_URL", "").rstrip("/")
        if public_base and media_url.startswith(public_base + "/static/knowledge-media/"):
            fname = media_url.split("/static/knowledge-media/")[-1]
            fpath = MEDIA_BASE / fname
            fpath.unlink(missing_ok=True)
    except Exception:
        pass


@router.post("/{item_id}/upload-media", response_model=KnowledgeItemOut)
async def upload_media(
    item_id: int,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Faz upload de uma imagem/vídeo/PDF para ser enviado ao lead quando o agente usar esta seção."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Item não encontrado")
    finally:
        conn.close()

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Formatos aceitos: .jpg, .jpeg, .png, .webp, .gif, .mp4, .pdf",
        )

    uid = uuid.uuid4().hex
    dest = MEDIA_BASE / f"{uid}{ext}"
    try:
        content = await file.read()
        dest.write_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar mídia: {exc}")

    public_base = os.getenv("CRM_PUBLIC_BASE_URL", "").rstrip("/")
    media_url = f"{public_base}/static/knowledge-media/{uid}{ext}"

    # Apagar mídia anterior se existir
    old_media = existing["media_url"] if hasattr(existing, "__getitem__") else None
    if old_media:
        _try_delete_media_file(old_media)

    conn = get_connection()
    try:
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        cur.execute(
            "UPDATE knowledge_items SET media_url = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (media_url, now_iso, item_id, current_user.id),
        )
        conn.commit()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        row = cur.fetchone()
        return _row_to_item(row)
    finally:
        conn.close()


@router.delete("/{item_id}/media", response_model=KnowledgeItemOut)
async def delete_media(
    item_id: int,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Remove a mídia associada a um item de conhecimento."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Item não encontrado")

        old_media = existing["media_url"] if hasattr(existing, "__getitem__") else None
        if old_media:
            _try_delete_media_file(old_media)

        now_iso = datetime.utcnow().isoformat()
        cur.execute(
            "UPDATE knowledge_items SET media_url = NULL, updated_at = ? WHERE id = ? AND user_id = ?",
            (now_iso, item_id, current_user.id),
        )
        conn.commit()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        row = cur.fetchone()
        return _row_to_item(row)
    finally:
        conn.close()
