# routes/knowledge.py
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from database import get_connection
from models import KnowledgeCreate, KnowledgeItemOut, KnowledgeUpdate
from security_core import CurrentUser, require_crm_access

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge"])

UPLOAD_BASE = Path("data/uploads/knowledge")
UPLOAD_BASE.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".csv", ".xlsx"}


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
        cur.execute(
            """
            INSERT INTO knowledge_items (user_id, title, source_type, content_text, file_path, category, created_at, updated_at)
            VALUES (?, ?, 'manual', ?, NULL, ?, ?, ?)
            """,
            (current_user.id, payload.title, payload.content_text, payload.category, now_iso, now_iso),
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
        return _row_to_item(row)
    finally:
        conn.close()


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
            INSERT INTO knowledge_items (user_id, title, source_type, content_text, file_path, created_at, updated_at)
            VALUES (?, ?, 'file', ?, ?, ?, ?)
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
