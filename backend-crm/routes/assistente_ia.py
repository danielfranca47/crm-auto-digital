# routes/assistente_ia.py
from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel, field_validator
from typing import List, Literal, Optional, Dict
from pathlib import Path
from automations.assistente_ia.processor import AssistIAProcessor
from database import get_connection
import pandas as pd
from datetime import datetime
from security_core import CurrentUser, require_crm_access
from core_client import fetch_core_ai_profile

router = APIRouter()

ALLOWED_CHANNELS = {"email", "whatsapp", "instagram", "call"}


def _require_lead_for_user(conn, lead_id: int, user_id: int) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM leads WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    )
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

# ===================== MODELOS =====================

class AssistIAProcessRequest(BaseModel):
    upload_id: str
    create_cards: bool = True
    generate_copys: bool = False
    channels: List[str] = []
    overwrite: Literal["skip","update","duplicate"] = "update"
    limit: Optional[int] = None
    tone: Optional[str] = "profissional e próximo"
    language: Optional[str] = "pt-PT"
    column_map: Optional[Dict[str, str]] = None

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v):
        unknown = set(v) - ALLOWED_CHANNELS
        if unknown:
            raise ValueError(f"Canais inválidos: {', '.join(sorted(unknown))}")
        return v

class MessageUpsert(BaseModel):
    """Upsert de mensagem manual (email/whatsapp/instagram/call)."""
    lead_id: int
    channel: Literal["email", "whatsapp", "instagram", "call"]
    body: str
    subject: Optional[str] = None
    # Se vier, atualiza essa mensagem; se não vier, insere uma nova
    message_id: Optional[int] = None
    model: Optional[str] = None
    # Atualiza/define a seleção do canal para essa mensagem
    select: bool = True

    @field_validator("body")
    @classmethod
    def _trim_body(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Corpo da mensagem (body) é obrigatório.")
        return v

# ===================== ROTAS (processar/health/messages) =====================

@router.post("/processar")
def processar(req: AssistIAProcessRequest, current_user: CurrentUser = Depends(require_crm_access)):
    base_dir = Path("data/uploads/ai")
    base_dir.mkdir(parents=True, exist_ok=True)

    candidate_paths = [
        base_dir / f"{req.upload_id}.xlsx",
        base_dir / f"{req.upload_id}.csv",
    ]
    file_path = next((p for p in candidate_paths if p.exists()), None)
    if not file_path:
        raise HTTPException(status_code=404, detail="Arquivo de upload não encontrado (xlsx/csv).")

    ai_profile: Dict = {}
    try:
        ai_profile = fetch_core_ai_profile(current_user.token or "") or {}
    except Exception:
        pass

    processor = AssistIAProcessor()
    try:
        result = processor.process(
            file_path=file_path,
            create_cards=req.create_cards,
            generate_copys=req.generate_copys,
            channels=req.channels,
            overwrite=req.overwrite,
            limit=req.limit,
            tone=req.tone,
            language=req.language,
            user_id=current_user.id,
            entitlements=current_user.entitlements,
            column_map=req.column_map or {},
            ai_profile=ai_profile,
        )
        return {"ok": True, **result}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao processar: {e}")

# Temporário para health-check do cliente LLM
@router.get("/health")
def health():
    import os
    try:
        import openai as openai_mod
        openai_version = getattr(openai_mod, "__version__", "unknown")
    except Exception:
        openai_mod = None
        openai_version = "not_imported"

    from automations.assistente_ia.llm import LLMClient
    llm = LLMClient()
    return {
        "openai_imported": openai_mod is not None,
        "openai_version": openai_version,
        "api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "enabled": llm.enabled,
        "model": llm.model,
    }

@router.get("/messages/{lead_id}")
def get_messages(lead_id: int, latest: bool = True, current_user: CurrentUser = Depends(require_crm_access)):
    try:
        with get_connection() as conn:
            _require_lead_for_user(conn, lead_id, current_user.id)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, channel, subject, body, model, createdAt
                FROM messages
                WHERE lead_id = ?
                ORDER BY createdAt DESC
            """, (lead_id,))
            rows = [dict(r) for r in cur.fetchall()]
            if latest:
                seen = set()
                out = []
                for r in rows:
                    ch = r["channel"]
                    if ch in seen:
                        continue
                    seen.add(ch)
                    out.append(r)
                rows = out
            return {"ok": True, "messages": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# >>> NOVO: upsert de mensagem manual <<<
@router.post("/messages/upsert")
def upsert_message(req: MessageUpsert, current_user: CurrentUser = Depends(require_crm_access)):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            _require_lead_for_user(conn, req.lead_id, current_user.id)
            message_id = req.message_id

            if message_id:
                # Atualiza mensagem existente (garante lead_id bate)
                cur.execute(
                    """
                    UPDATE messages
                       SET subject = ?, body = ?, model = ?
                     WHERE id = ? AND lead_id = ?
                    """,
                    (req.subject, req.body, req.model, message_id, req.lead_id),
                )
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Mensagem não encontrada para este lead.")
            else:
                # Insere nova mensagem
                cur.execute(
                    """
                    INSERT INTO messages (lead_id, channel, subject, body, model)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (req.lead_id, req.channel, req.subject, req.body, req.model),
                )
                message_id = int(cur.lastrowid)

            # Atualiza seleção do canal (idempotente)
            if req.select:
                cur.execute(
                    """
                    INSERT INTO message_selections (lead_id, channel, message_id)
                    VALUES (?, ?, ?)
                    ON CONFLICT(lead_id, channel)
                    DO UPDATE SET message_id = excluded.message_id,
                                  selectedAt = CURRENT_TIMESTAMP
                    """,
                    (req.lead_id, req.channel, message_id),
                )

            # Marca movimento do lead
            cur.execute(
                "UPDATE leads SET lastMovement = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (req.lead_id, current_user.id),
            )

            conn.commit()

        return {"ok": True, "message_id": int(message_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar mensagem: {e}")

# ===================== PRÉVIA (preview) =====================

def _read_preview_table(file_path: Path, limit: int = 200) -> pd.DataFrame:
    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    else:
        xls = pd.ExcelFile(file_path)
        sheet = "Leads" if "Leads" in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df.head(limit)

@router.post("/preview")
def preview(req: dict = Body(...), current_user: CurrentUser = Depends(require_crm_access)):
    upload_id = req.get("upload_id")
    overwrite = req.get("overwrite", "update")
    column_map: Dict[str, str] = req.get("column_map") or {}
    if not upload_id:
        raise HTTPException(400, "upload_id é obrigatório")

    base = Path("data/uploads/ai")
    fp = next((p for p in [base / f"{upload_id}.xlsx", base / f"{upload_id}.csv"] if p.exists()), None)
    if not fp:
        raise HTTPException(404, "Arquivo não encontrado")

    df = _read_preview_table(fp, limit=200)

    def _resolve(r, field: str, *fallback_keys: str) -> str:
        # use column_map first, then fallback_keys (all lowercased in df)
        mapped = column_map.get(field, "")
        if mapped:
            val = r.get(mapped.lower().strip())
            if val is not None:
                return str(val).strip()
        for k in fallback_keys:
            val = r.get(k)
            if val is not None:
                return str(val).strip()
        return ""

    phones = set()
    emails = set()
    names  = set()
    for _, r in df.iterrows():
        phone = _resolve(r, "telefone", "phone", "telefone")
        email = _resolve(r, "", "email")
        name  = _resolve(r, "empresa", "companyname", "name", "empresa")
        if phone: phones.add(phone)
        if email: emails.add(email)
        if name:  names.add(name)

    with get_connection() as conn:
        cur = conn.cursor()
        dup_phone = set()
        if phones:
            q = (
                f"SELECT phone FROM leads WHERE phone IN ({','.join(['?']*len(phones))}) "
                "AND user_id = ?"
            )
            for (p,) in cur.execute(q, (*phones, current_user.id)).fetchall():
                dup_phone.add(str(p))
        dup_email = set()
        if emails:
            q = (
                f"SELECT email FROM leads WHERE email IN ({','.join(['?']*len(emails))}) "
                "AND user_id = ?"
            )
            for (e,) in cur.execute(q, (*emails, current_user.id)).fetchall():
                dup_email.add(str(e))
        dup_name = set()
        if names:
            q = (
                f"SELECT companyName FROM leads WHERE companyName IN ({','.join(['?']*len(names))}) "
                "AND user_id = ?"
            )
            for (n,) in cur.execute(q, (*names, current_user.id)).fetchall():
                dup_name.add(str(n))

    rows = []
    stats = {"total": int(df.shape[0]), "dups_phone": 0, "dups_email": 0, "dups_name": 0,
             "pred_create": 0, "pred_update": 0, "pred_skip": 0}
    for _, r in df.iterrows():
        phone = _resolve(r, "telefone", "phone", "telefone")
        email = _resolve(r, "", "email")
        name  = _resolve(r, "empresa", "companyname", "name", "empresa")
        is_dp = bool(phone and phone in dup_phone)
        is_de = bool(email and email in dup_email)
        is_dn = bool(name  and name  in dup_name)

        if is_dp or is_de or is_dn:
            if overwrite == "skip":
                action = "skip"; stats["pred_skip"] += 1
            elif overwrite == "update":
                action = "update"; stats["pred_update"] += 1
            else:
                action = "create"; stats["pred_create"] += 1
        else:
            action = "create"; stats["pred_create"] += 1

        stats["dups_phone"] += int(is_dp)
        stats["dups_email"] += int(is_de)
        stats["dups_name"]  += int(is_dn)

        rows.append({
            "company": name, "email": email, "phone": phone,
            "dup_phone": is_dp, "dup_email": is_de, "dup_name": is_dn,
            "pred_action": action,
        })

    return {"ok": True, "stats": stats, "rows": rows[:30]}
