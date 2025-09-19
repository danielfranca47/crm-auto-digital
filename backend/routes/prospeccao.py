# backend/routes/prospeccao.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
from database import get_connection
import re

router = APIRouter(prefix="/api/prospeccao", tags=["Prospecção"])

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

class WhatsMarkRequest(BaseModel):
    lead_id: int
    message_id: int
    ok: bool
    notes: Optional[str] = None

# ------------------ HELPERS ------------------
_ALLOWED_CHANNELS = {"email", "whatsapp", "instagram", "call"}

def _ensure_queue_indexes(conn):
    # Index para acelerar a busca dos pendentes por enqueuedAt
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_whats_queue_status_enq
        ON prospection_whatsapp_queue(status, enqueuedAt)
    """)

def _sanitize_phone(p: str) -> str:
    """Mantém só dígitos. Suporta números já com CC (ex.: 351..., 55..., etc.)."""
    digits = re.sub(r"\D+", "", p or "")
    return digits

def _pick_whatsapp_message(conn, lead_id: int):
    """Tenta pegar a mensagem de WhatsApp selecionada; senão, a mais recente do canal."""
    cur = conn.cursor()
    # 1) Seleção fixa
    row = cur.execute(
        """
        SELECT m.id, m.body
          FROM message_selections s
          JOIN messages m ON m.id = s.message_id
         WHERE s.lead_id=? AND s.channel='whatsapp'
         ORDER BY s.selectedAt DESC
         LIMIT 1
        """,
        (lead_id,),
    ).fetchone()
    if row:
        return int(row["id"]), row["body"]

    # 2) Mais recente do canal
    row = cur.execute(
        """
        SELECT id, body
          FROM messages
         WHERE lead_id=? AND channel='whatsapp'
         ORDER BY createdAt DESC
         LIMIT 1
        """,
        (lead_id,),
    ).fetchone()
    if row:
        return int(row["id"]), row["body"]

    # (Opcional) fallback ao customMessage do lead — ver comentários no seu original
    return None, None

def _log(conn, lead_id: int, action: str, channel: Optional[str] = None,
         message_id: Optional[int] = None, notes: Optional[str] = None):
    conn.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (lead_id, channel, message_id, action, notes),
    )

# ------------------ ROTAS EXISTENTES ------------------
@router.post("/select-message")
def select_message(payload: MessageSelectionUpsert):
    if payload.channel not in _ALLOWED_CHANNELS:
        raise HTTPException(status_code=400, detail="Canal inválido")

    with get_connection() as conn:
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
def get_selection_by_lead(lead_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT channel, message_id FROM message_selections WHERE lead_id=?",
            (lead_id,),
        ).fetchall()
    data: Dict[str, int] = {r["channel"]: r["message_id"] for r in rows}
    return {"ok": True, "selections": data, "updatedAt": datetime.utcnow().isoformat()}

@router.post("/log")
def create_log(payload: ProspectionLogCreate):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.lead_id, payload.channel, payload.message_id, payload.action, payload.notes),
        )
        conn.commit()
    return {"ok": True}

# ------------------ NOVA ROTA: salvar mensagem ------------------
@router.post("/save-message")
def save_message(req: SaveMessageReq):
    if req.channel not in _ALLOWED_CHANNELS:
        raise HTTPException(status_code=400, detail="Canal inválido")
    body = (req.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="body vazio")

    with get_connection() as conn:
        cur = conn.cursor()

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
            cur.execute("UPDATE leads SET customMessage=? WHERE id=?", (body, req.lead_id))

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

        _log(conn, req.lead_id, "updated_message", req.channel, msg_id, "manual")
        conn.commit()

    return {"ok": True, "message_id": int(msg_id)}

# ------------------ WHATSAPP QUEUE ------------------
@router.post("/whatsapp/enqueue")
def whatsapp_enqueue(req: WhatsEnqueueRequest):
    queued = []
    skipped = []
    with get_connection() as conn:
        _ensure_queue_indexes(conn)  # <<< garante índices
        cur = conn.cursor()
        for lead_id in req.lead_ids:
            # Telefone do lead
            lead = cur.execute("SELECT phone FROM leads WHERE id=?", (lead_id,)).fetchone()
            if not lead or not (lead["phone"] or "").strip():
                skipped.append({"lead_id": lead_id, "reason": "sem_telefone"})
                continue
            phone = _sanitize_phone(lead["phone"])
            if not phone:
                skipped.append({"lead_id": lead_id, "reason": "telefone_invalido"})
                continue

            # Mensagem do WhatsApp
            msg_id, body = _pick_whatsapp_message(conn, lead_id)
            if not msg_id or not body:
                skipped.append({"lead_id": lead_id, "reason": "sem_mensagem"})
                continue

            # Evita duplicar pendência do mesmo lead+message
            exists = cur.execute(
                """
                SELECT 1 FROM prospection_whatsapp_queue
                 WHERE lead_id=? AND message_id=? AND status='pending'
                 LIMIT 1
                """,
                (lead_id, msg_id),
            ).fetchone()
            if exists:
                skipped.append({"lead_id": lead_id, "reason": "ja_pendente"})
                continue

            cur.execute(
                """
                INSERT INTO prospection_whatsapp_queue (lead_id, message_id, phone, body, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (lead_id, msg_id, phone, body),
            )
            _log(conn, lead_id, "queued", "whatsapp", msg_id, f"phone={phone}")
            queued.append({"lead_id": lead_id, "message_id": msg_id})

        conn.commit()

    return {"ok": True, "queued": queued, "skipped": skipped}

@router.get("/whatsapp/queue")
def whatsapp_queue(limit: int = Query(5, ge=1, le=50)):
    with get_connection() as conn:
        _ensure_queue_indexes(conn)  # <<< garante índices
        rows = conn.execute(
            """
            SELECT id, lead_id, message_id, phone, body, attempts, enqueuedAt
              FROM prospection_whatsapp_queue
             WHERE status='pending'
             ORDER BY enqueuedAt ASC, id ASC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items = [dict(r) for r in rows]
    return items

@router.post("/whatsapp/mark")
def whatsapp_mark(req: WhatsMarkRequest):
    with get_connection() as conn:
        status = "sent" if req.ok else "failed"
        notes = req.notes or ("" if req.ok else "erro_desconhecido")
        conn.execute(
            """
            UPDATE prospection_whatsapp_queue
               SET status=?, processedAt=CURRENT_TIMESTAMP,
                   attempts = attempts + 1,
                   lastError = ?
             WHERE lead_id=? AND message_id=? AND status='pending'
            """,
            (status, notes, req.lead_id, req.message_id),
        )
        _log(conn, req.lead_id, status, "whatsapp", req.message_id, notes)
        conn.commit()
    return {"ok": True}

# ======== WHATSAPP: resultados recentes e resumo (somente leitura) ========

@router.get("/whatsapp/recent")
def whatsapp_recent(since_secs: int = 300):
    """
    Retorna itens processados (sent/failed) nos últimos N segundos.
    Usado pelo front para mover cards automaticamente.
    """
    since_secs = max(30, min(int(since_secs), 3600))  # 30s..1h
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, lead_id, message_id, status, lastError, enqueuedAt, processedAt
              FROM prospection_whatsapp_queue
             WHERE status IN ('sent','failed')
               AND processedAt IS NOT NULL
               AND processedAt >= datetime('now', ?)
             ORDER BY processedAt DESC
             LIMIT 200
            """,
            (f"-{since_secs} seconds",),
        ).fetchall()
        return [dict(r) for r in rows]


@router.get("/whatsapp/summary")
def whatsapp_summary():
    """
    Contadores rápidos para o banner do front.
    """
    with get_connection() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM prospection_whatsapp_queue WHERE status='pending'"
        ).fetchone()["c"]

        sent_today = conn.execute(
            """
            SELECT COUNT(*) AS c
              FROM prospection_whatsapp_queue
             WHERE status='sent'
               AND date(processedAt) = date('now')
            """
        ).fetchone()["c"]

        failed_today = conn.execute(
            """
            SELECT COUNT(*) AS c
              FROM prospection_whatsapp_queue
             WHERE status='failed'
               AND date(processedAt) = date('now')
            """
        ).fetchone()["c"]

    return {
        "pending": int(pending),
        "sent_today": int(sent_today),
        "failed_today": int(failed_today),
    }
