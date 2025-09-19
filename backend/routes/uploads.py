# routes/uploads.py
import uuid, os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import numpy as np    # <-- ADICIONE
from datetime import datetime, date

router = APIRouter()

BASE = Path("data/uploads/ai")
BASE.mkdir(parents=True, exist_ok=True)

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
async def upload_planilha(file: UploadFile = File(...)):
    # aceita .xlsx/.csv (adicione ".xls" se quiser)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".xlsx", ".csv", ".xls"]:
        raise HTTPException(400, "Apenas .xlsx, .csv ou xls")

    uid = str(uuid.uuid4())
    dest = BASE / f"{uid}{ext}"
    try:
        content = await file.read()
        with open(dest, "wb") as f:
            f.write(content)
    except Exception as e:
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
