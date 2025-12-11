# backend/routes/prospeccao.py
import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
from database import get_connection
from services import jobs_service
from security_core import CurrentUser, get_current_user

router = APIRouter(prefix="/api/prospeccao", tags=["Prospecção"])
logger = logging.getLogger(__name__)

# ------------------ MODELOS ------------------
class MessageSelectionUpsert(BaseModel):
    lead_id: int
    channel: str   # 'email'|'whatsapp'|'instagram'|'call'
    message_id: int

class ProspectionLogCreate(BaseModel):
    lead_id: int
    action: str   # 'copied'|'wa_opened'|'mail_opened'|'sent'|'replied'|'moved_stage'|'scheduled_followup'|'queued'|'failed'
    channel: Optional[str] = None
    message_id: Optional[int] = None
    notes: Optional[str] = None

# salvar/atualizar copy manual no messages (+ selecionar canal)
class SaveMessageReq(BaseModel):
    lead_id: int
    channel: str                  # 'email' | 'whatsapp' | 'instagram' | 'call'
    body: str
    subject: Optional[str] = None # usado p/ e-mail
    select: bool = True           # se True, faz upsert em message_selections

# WhatsApp queue
class WhatsEnqueueRequest(BaseModel):
    lead_ids: List[int]
    # Mensagem opcional enviada pelo front; se presente, vira a mensagem principal
    # (ou override) usada para todos os leads, com fallback para selection/customMessage.
    message: Optional[str] = None
    # Overrides específicos por lead (lead_id -> mensagem). Se existir, tem prioridade
    # sobre `message` e sobre o que estiver salvo no lead.
    lead_messages: Optional[Dict[int, str]] = None

class WhatsMarkRequest(BaseModel):
    lead_id: int
    message_id: int
    ok: bool
    notes: Optional[str] = None

# ------------------ HELPERS ------------------
_ALLOWED_CHANNELS = {"email", "whatsapp", "instagram", "call"}


def _require_lead_for_user(conn, lead_id: int, user_id: int) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM leads WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    )
    if cur.fetchone() is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")


def _log(conn, lead_id: int, action: str, channel: Optional[str], message_id: Optional[int], notes: Optional[str], user_id: int) -> None:
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (lead_id, channel, message_id, action, notes, user_id),
    )

# ------------------ ROTAS EXISTENTES ------------------
@router.post("/select-message")
def select_message(payload: MessageSelectionUpsert, current_user: CurrentUser = Depends(get_current_user)):
    if payload.channel not in _ALLOWED_CHANNELS:
        raise HTTPException(status_code=400, detail="Canal inválido")

    with get_connection() as conn:
        _require_lead_for_user(conn, payload.lead_id, current_user.id)
        conn.execute(
            """
            INSERT INTO message_selections (lead_id, channel, message_id)
            VALUES (?, ?, ?)
            ON CONFLICT(lead_id, channel)
            DO UPDATE SET message_id=excluded.message_id, selectedAt=CURRENT_TIMESTAMP
            """,
            (payload.lead_id, payload.channel, payload.message_id),
        )
        conn.commit()
    return {"ok": True}

@router.get("/selection/{lead_id}")
def get_selection_by_lead(lead_id: int, current_user: CurrentUser = Depends(get_current_user)):
    with get_connection() as conn:
        _require_lead_for_user(conn, lead_id, current_user.id)
        rows = conn.execute(
            "SELECT channel, message_id FROM message_selections WHERE lead_id=?",
            (lead_id,),
        ).fetchall()
    data: Dict[str, int] = {r["channel"]: r["message_id"] for r in rows}
    return {"ok": True, "selections": data, "updatedAt": datetime.utcnow().isoformat()}

@router.post("/log")
def create_log(payload: ProspectionLogCreate, current_user: CurrentUser = Depends(get_current_user)):
    with get_connection() as conn:
        _require_lead_for_user(conn, payload.lead_id, current_user.id)
        conn.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (payload.lead_id, payload.channel, payload.message_id, payload.action, payload.notes, current_user.id),
        )
        conn.commit()
    return {"ok": True}

# ------------------ NOVA ROTA: salvar mensagem ------------------
@router.post("/save-message")
def save_message(req: SaveMessageReq, current_user: CurrentUser = Depends(get_current_user)):
    if req.channel not in _ALLOWED_CHANNELS:
        raise HTTPException(status_code=400, detail="Canal inválido")
    body = (req.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="body vazio")

    with get_connection() as conn:
        cur = conn.cursor()
        _require_lead_for_user(conn, req.lead_id, current_user.id)

        # Grava a mensagem como 'manual'
        cur.execute(
            """
            INSERT INTO messages (lead_id, channel, subject, body, model)
            VALUES (?, ?, ?, ?, 'manual')
            """,
            (req.lead_id, req.channel, req.subject, body),
        )
        msg_id = cur.lastrowid

        # Sincroniza também no lead (apenas para WhatsApp — útil para exibição rápida)
        if req.channel == "whatsapp":
            cur.execute(
                "UPDATE leads SET customMessage=? WHERE id=? AND user_id = ?",
                (body, req.lead_id, current_user.id),
            )

        # Marca como seleção ativa do canal (upsert)
        if req.select:
            cur.execute(
                """
                INSERT INTO message_selections (lead_id, channel, message_id)
                VALUES (?, ?, ?)
                ON CONFLICT(lead_id, channel)
                DO UPDATE SET message_id=excluded.message_id, selectedAt=CURRENT_TIMESTAMP
                """,
                (req.lead_id, req.channel, msg_id),
            )

        _log(conn, req.lead_id, "updated_message", req.channel, msg_id, "manual", current_user.id)
        conn.commit()

    return {"ok": True, "message_id": int(msg_id)}

# ------------------ WHATSAPP QUEUE ------------------
@router.post("/whatsapp/enqueue")
def whatsapp_enqueue(req: WhatsEnqueueRequest, current_user: CurrentUser = Depends(get_current_user)):
    logger.info(
        "/whatsapp/enqueue payload lead_ids=%s message_present=%s lead_messages=%s",
        req.lead_ids,
        bool((req.message or "").strip()),
        list((req.lead_messages or {}).keys()),
    )
    try:
        result = jobs_service.enqueue_whatsapp_jobs(
            req.lead_ids,
            message=(req.message or "").strip() or None,
            lead_messages=req.lead_messages,
            user_id=current_user.id,
        )
        job_ids = [item.get("job_id") for item in result.get("queued", [])]
        logger.info(
            "/whatsapp/enqueue created jobs ids=%s skipped=%s", job_ids, result.get("skipped")
        )
        return {"ok": True, **result}
    except Exception:
        logger.exception("/whatsapp/enqueue failed")
        raise HTTPException(status_code=500, detail="Erro ao enfileirar WhatsApp")

@router.get("/whatsapp/queue")
def whatsapp_queue(limit: int = Query(5, ge=1, le=50), current_user: CurrentUser = Depends(get_current_user)):
    return jobs_service.get_whatsapp_queue(limit, user_id=current_user.id)

@router.post("/whatsapp/mark")
def whatsapp_mark(req: WhatsMarkRequest):
    raise HTTPException(status_code=410, detail="Fluxo do worker foi substituído pelo Agente Local")

# ======== WHATSAPP: resultados recentes e resumo (somente leitura) ========

@router.get("/whatsapp/recent")
def whatsapp_recent(since_secs: int = 300, current_user: CurrentUser = Depends(get_current_user)):
    """
    Retorna itens processados (sent/failed) nos últimos N segundos.
    Usado pelo front para mover cards automaticamente.
    """
    return jobs_service.get_whatsapp_recent(since_secs, user_id=current_user.id)


@router.get("/whatsapp/summary")
def whatsapp_summary(current_user: CurrentUser = Depends(get_current_user)):
    """
    Contadores rápidos para o banner do front.
    """
    return jobs_service.get_whatsapp_summary(user_id=current_user.id)
