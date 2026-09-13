# routes/uploads.py
import uuid, os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
import pandas as pd
import numpy as np    # <-- ADICIONE
from datetime import datetime, date

from security_core import CurrentUser, require_crm_access

router = APIRouter()

BASE = Path("data/uploads/ai")
BASE.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB — planilha de leads não deveria passar disso
UPLOAD_CHUNK_SIZE = 1024 * 1024

def _read_df(fp: Path, limit: int = 20) -> pd.DataFrame:
    if fp.suffix.lower() == ".csv":
        df = pd.read_csv(fp)
    else:
        xls = pd.ExcelFile(fp)
        sheet = "Leads" if "Leads" in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet)
    # normaliza headers
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df.head(limit)

def _df_to_records_safe(df: pd.DataFrame) -> list[dict]:
    """Converte DataFrame em lista de dicts, trocando NaN/NaT por None e datetimes por ISO."""
    df = df.copy()

    # 1) NaN/NaT -> None
    df = df.replace({np.nan: None})
    # 2) Colunas datetime -> string ISO (evita erro de serialização)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    # 3) Objetos que ainda sejam Timestamp/Date em células isoladas
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, (pd.Timestamp, datetime, date)):
                r[k] = v.isoformat(sep=" ")
            # valores infinitos também não são válidos em JSON
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                r[k] = None
    return records

@router.post("/uploads")
async def upload_planilha(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_crm_access),
):
    # aceita .xlsx/.csv (adicione ".xls" se quiser)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".xlsx", ".csv", ".xls"]:
        raise HTTPException(400, "Apenas .xlsx, .csv ou xls")

    uid = str(uuid.uuid4())
    user_dir = BASE / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{uid}{ext}"
    try:
        size = 0
        with open(dest, "wb") as f:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    f.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        413,
                        f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Falha ao salvar upload: {e}")

    # gera amostra segura para JSON
    try:
        df = _read_df(dest, limit=20)
        sample = _df_to_records_safe(df)
    except Exception as e:
        raise HTTPException(400, f"Falha ao ler arquivo: {e}")

    return {
        "ok": True,
        "upload_id": uid,
        "filename": file.filename,
        "ext": ext,
        "columns": list(df.columns),
        "sample": sample,   # agora sem NaN
    }
