# routes/knowledge.py
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from core_client import fetch_core_ai_profile_resolve
from database import get_connection
from models import (
    KnowledgeCreate,
    KnowledgeItemOut,
    KnowledgeMediaOut,
    KnowledgeMediaReorder,
    KnowledgeMediaUpdate,
    KnowledgeUpdate,
)
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
ALLOWED_MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".mp4",
    ".pdf",
    ".mp3", ".ogg", ".opus",
}

VALID_LANGUAGES = {"all", "pt", "en", "es"}


def _ext_to_media_type(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext in {"mp4"}:
        return "video"
    if ext in {"pdf"}:
        return "pdf"
    if ext in {"mp3", "ogg", "opus"}:
        return "audio"
    return "image"


def _load_media_items(cur, item_id: int) -> list:
    """Carrega todas as mídias de um item, ordenadas por send_order."""
    cur.execute(
        """
        SELECT id, knowledge_item_id, media_url, media_type, language, send_order, created_at
          FROM knowledge_item_media
         WHERE knowledge_item_id = ?
         ORDER BY send_order ASC, id ASC
        """,
        (item_id,),
    )
    rows = cur.fetchall()
    return [
        {k: row[k] for k in row.keys()} if hasattr(row, "keys") else dict(zip(
            ["id", "knowledge_item_id", "media_url", "media_type", "language", "send_order", "created_at"], row
        ))
        for row in rows
    ]


def _row_to_item(row, media_items: list | None = None) -> KnowledgeItemOut:
    data = {k: row[k] for k in row.keys()} if hasattr(row, "keys") else dict(row)
    data["media_items"] = media_items or []
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


# ─── List / Get ───────────────────────────────────────────────────────────────

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
        result = []
        for r in rows:
            media = _load_media_items(cur, r["id"])
            result.append(_row_to_item(r, media))
        return result
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
        media = _load_media_items(cur, item_id)
        return _row_to_item(row, media)
    finally:
        conn.close()


# ─── Create / Update / Delete ─────────────────────────────────────────────────

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

        cur.execute("SELECT * FROM knowledge_items WHERE id = ?", (cur.lastrowid,))
        row = cur.fetchone()
        return _row_to_item(row, [])
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
        media = _load_media_items(cur, item_id)
        result = _row_to_item(row, media)
    finally:
        conn.close()

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

        # Apagar mídias da tabela knowledge_item_media (arquivos físicos)
        all_media = _load_media_items(cur, item_id)
        for m in all_media:
            _try_delete_media_file(m["media_url"])

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

        # Legado: apagar media_url se não estava na tabela multi-media
        if media_url and not any(m["media_url"] == media_url for m in all_media):
            _try_delete_media_file(media_url)

        return {"ok": True}
    finally:
        conn.close()


# ─── Upload de arquivo de texto ───────────────────────────────────────────────

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
            (current_user.id, filename, extracted_text, str(dest), now_iso, now_iso),
        )
        conn.commit()
        cur.execute("SELECT * FROM knowledge_items WHERE id = ?", (cur.lastrowid,))
        row = cur.fetchone()
        return _row_to_item(row, [])
    finally:
        conn.close()


# ─── Endpoints de mídia (legado — retrocompatibilidade) ──────────────────────

@router.post("/{item_id}/upload-media", response_model=KnowledgeItemOut)
async def upload_media(
    item_id: int,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Legado: substitui a mídia única do item. Agora também cria entrada em knowledge_item_media."""
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
            detail="Formatos aceitos: jpg, png, webp, gif, mp4, pdf, mp3, ogg, opus",
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
    media_type = _ext_to_media_type(ext)

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
        # Também insere em knowledge_item_media se ainda não existir entrada com esta URL
        cur.execute(
            "SELECT id FROM knowledge_item_media WHERE knowledge_item_id = ? AND media_url = ?",
            (item_id, media_url),
        )
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO knowledge_item_media (knowledge_item_id, media_url, media_type, language, send_order, created_at)
                VALUES (?, ?, ?, 'all', 0, ?)
                """,
                (item_id, media_url, media_type, now_iso),
            )
        conn.commit()
        cur.execute(
            "SELECT * FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        row = cur.fetchone()
        media = _load_media_items(cur, item_id)
        return _row_to_item(row, media)
    finally:
        conn.close()


@router.delete("/{item_id}/media", response_model=KnowledgeItemOut)
async def delete_all_media(
    item_id: int,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Legado: remove todas as mídias do item."""
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

        all_media = _load_media_items(cur, item_id)
        for m in all_media:
            _try_delete_media_file(m["media_url"])

        old_media = existing["media_url"] if hasattr(existing, "__getitem__") else None
        if old_media and not any(m["media_url"] == old_media for m in all_media):
            _try_delete_media_file(old_media)

        cur.execute("DELETE FROM knowledge_item_media WHERE knowledge_item_id = ?", (item_id,))
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
        return _row_to_item(row, [])
    finally:
        conn.close()


# ─── Novos endpoints multi-mídia ─────────────────────────────────────────────

@router.post("/{item_id}/media", response_model=KnowledgeMediaOut)
async def add_media(
    item_id: int,
    file: UploadFile = File(...),
    language: str = Form("all"),
    send_order: int = Form(-1),
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Adiciona uma nova mídia ao item (sem substituir as existentes)."""
    if language not in VALID_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Idioma inválido. Use: {', '.join(VALID_LANGUAGES)}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Item não encontrado")
    finally:
        conn.close()

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Formatos aceitos: jpg, png, webp, gif, mp4, pdf, mp3, ogg, opus",
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
    media_type = _ext_to_media_type(ext)

    conn = get_connection()
    try:
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()

        # Se send_order=-1, colocar no final
        if send_order < 0:
            cur.execute(
                "SELECT COALESCE(MAX(send_order), -1) + 1 FROM knowledge_item_media WHERE knowledge_item_id = ?",
                (item_id,),
            )
            row_ord = cur.fetchone()
            send_order = row_ord[0] if row_ord else 0

        cur.execute(
            """
            INSERT INTO knowledge_item_media (knowledge_item_id, media_url, media_type, language, send_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item_id, media_url, media_type, language, send_order, now_iso),
        )
        new_id = cur.lastrowid

        # Atualiza media_url legado se for o primeiro
        cur.execute("SELECT media_url FROM knowledge_items WHERE id = ?", (item_id,))
        ki_row = cur.fetchone()
        if ki_row and not ki_row[0]:
            cur.execute(
                "UPDATE knowledge_items SET media_url = ?, updated_at = ? WHERE id = ?",
                (media_url, now_iso, item_id),
            )

        conn.commit()

        cur.execute("SELECT * FROM knowledge_item_media WHERE id = ?", (new_id,))
        row = cur.fetchone()
        data = {k: row[k] for k in row.keys()} if hasattr(row, "keys") else dict(zip(
            ["id", "knowledge_item_id", "media_url", "media_type", "language", "send_order", "created_at"], row
        ))
        return KnowledgeMediaOut(**data)
    finally:
        conn.close()


@router.patch("/{item_id}/media/{media_id}", response_model=KnowledgeMediaOut)
async def update_media_meta(
    item_id: int,
    media_id: int,
    payload: KnowledgeMediaUpdate,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Atualiza idioma ou ordem de envio de uma mídia específica."""
    if payload.language is not None and payload.language not in VALID_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Idioma inválido. Use: {', '.join(VALID_LANGUAGES)}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Verificar ownership via join
        cur.execute(
            """
            SELECT kim.id FROM knowledge_item_media kim
            JOIN knowledge_items ki ON ki.id = kim.knowledge_item_id
            WHERE kim.id = ? AND kim.knowledge_item_id = ? AND ki.user_id = ?
            """,
            (media_id, item_id, current_user.id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Mídia não encontrada")

        fields, values = [], []
        if payload.language is not None:
            fields.append("language = ?")
            values.append(payload.language)
        if payload.send_order is not None:
            fields.append("send_order = ?")
            values.append(payload.send_order)

        if not fields:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

        values.append(media_id)
        cur.execute(f"UPDATE knowledge_item_media SET {', '.join(fields)} WHERE id = ?", tuple(values))
        conn.commit()

        cur.execute("SELECT * FROM knowledge_item_media WHERE id = ?", (media_id,))
        row = cur.fetchone()
        data = {k: row[k] for k in row.keys()} if hasattr(row, "keys") else {}
        return KnowledgeMediaOut(**data)
    finally:
        conn.close()


@router.delete("/{item_id}/media/{media_id}")
async def delete_single_media(
    item_id: int,
    media_id: int,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Remove uma mídia específica do item."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT kim.id, kim.media_url FROM knowledge_item_media kim
            JOIN knowledge_items ki ON ki.id = kim.knowledge_item_id
            WHERE kim.id = ? AND kim.knowledge_item_id = ? AND ki.user_id = ?
            """,
            (media_id, item_id, current_user.id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mídia não encontrada")

        media_url = row["media_url"] if hasattr(row, "keys") else row[1]
        cur.execute("DELETE FROM knowledge_item_media WHERE id = ?", (media_id,))

        # Atualiza legado: se era a última, zera media_url no item
        cur.execute(
            "SELECT COUNT(*) FROM knowledge_item_media WHERE knowledge_item_id = ?", (item_id,)
        )
        count_row = cur.fetchone()
        remaining = count_row[0] if count_row else 0
        if remaining == 0:
            cur.execute(
                "UPDATE knowledge_items SET media_url = NULL WHERE id = ?", (item_id,)
            )
        else:
            # Atualiza legado para apontar à primeira mídia restante
            cur.execute(
                "SELECT media_url FROM knowledge_item_media WHERE knowledge_item_id = ? ORDER BY send_order ASC, id ASC LIMIT 1",
                (item_id,),
            )
            first = cur.fetchone()
            if first:
                cur.execute(
                    "UPDATE knowledge_items SET media_url = ? WHERE id = ?",
                    (first[0], item_id),
                )

        conn.commit()
        _try_delete_media_file(media_url)

        return {"ok": True}
    finally:
        conn.close()


@router.put("/{item_id}/media/reorder")
async def reorder_media(
    item_id: int,
    payload: KnowledgeMediaReorder,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Atualiza a ordem de envio de múltiplas mídias em lote."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Verificar ownership
        cur.execute(
            "SELECT id FROM knowledge_items WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Item não encontrado")

        for entry in payload.items:
            mid = entry.get("id")
            order = entry.get("send_order")
            if mid is None or order is None:
                continue
            cur.execute(
                "UPDATE knowledge_item_media SET send_order = ? WHERE id = ? AND knowledge_item_id = ?",
                (order, mid, item_id),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
