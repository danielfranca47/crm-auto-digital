# backend/routes/prospeccao.py
import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
from database import get_connection
from services import jobs_service, rate_limit_service
from security_core import CurrentUser, require_crm_access

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

class EmailEnqueueRequest(BaseModel):
    lead_ids: List[int]
    subject: Optional[str] = None
    # Mesma semântica do WhatsEnqueueRequest: mensagem opcional que vira o corpo
    # principal (ou override) para todos os leads, com fallback para selection.
    message: Optional[str] = None
    lead_messages: Optional[Dict[int, str]] = None


class WhatsMarkRequest(BaseModel):
    lead_id: int
    message_id: int
    ok: bool
    notes: Optional[str] = None

class GenerateCopyRequest(BaseModel):
    company_name: str
    sector: str = ""
    contact_name: str = ""
    channel: str = "whatsapp"
    tone: str = "profissional e próximo"
    custom_prompt_template: str = ""

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
def select_message(payload: MessageSelectionUpsert, current_user: CurrentUser = Depends(require_crm_access)):
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
def get_selection_by_lead(lead_id: int, current_user: CurrentUser = Depends(require_crm_access)):
    with get_connection() as conn:
        _require_lead_for_user(conn, lead_id, current_user.id)
        rows = conn.execute(
            "SELECT channel, message_id FROM message_selections WHERE lead_id=?",
            (lead_id,),
        ).fetchall()
    data: Dict[str, int] = {r["channel"]: r["message_id"] for r in rows}
    return {"ok": True, "selections": data, "updatedAt": datetime.utcnow().isoformat()}

@router.post("/log")
def create_log(payload: ProspectionLogCreate, current_user: CurrentUser = Depends(require_crm_access)):
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
def save_message(req: SaveMessageReq, current_user: CurrentUser = Depends(require_crm_access)):
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
def whatsapp_enqueue(req: WhatsEnqueueRequest, current_user: CurrentUser = Depends(require_crm_access)):
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
            entitlements=current_user.entitlements,
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
def whatsapp_queue(limit: int = Query(5, ge=1, le=50), current_user: CurrentUser = Depends(require_crm_access)):
    return jobs_service.get_whatsapp_queue(limit, user_id=current_user.id)

@router.post("/whatsapp/mark")
def whatsapp_mark(req: WhatsMarkRequest):
    raise HTTPException(status_code=410, detail="Fluxo do worker foi substituído pelo Agente Local")

# ------------------ EMAIL QUEUE (cold outreach) ------------------
@router.post("/email/enqueue")
def email_enqueue(req: EmailEnqueueRequest, current_user: CurrentUser = Depends(require_crm_access)):
    logger.info(
        "/email/enqueue payload lead_ids=%s message_present=%s lead_messages=%s",
        req.lead_ids,
        bool((req.message or "").strip()),
        list((req.lead_messages or {}).keys()),
    )
    try:
        result = jobs_service.enqueue_email_jobs(
            req.lead_ids,
            subject=req.subject,
            message=(req.message or "").strip() or None,
            lead_messages=req.lead_messages,
            user_id=current_user.id,
            entitlements=current_user.entitlements,
        )
        job_ids = [item.get("job_id") for item in result.get("queued", [])]
        logger.info(
            "/email/enqueue created jobs ids=%s skipped=%s", job_ids, result.get("skipped")
        )
        return {"ok": True, **result}
    except Exception:
        logger.exception("/email/enqueue failed")
        raise HTTPException(status_code=500, detail="Erro ao enfileirar email")

# ======== WHATSAPP: resultados recentes e resumo (somente leitura) ========

@router.get("/whatsapp/recent")
def whatsapp_recent(since_secs: int = 300, current_user: CurrentUser = Depends(require_crm_access)):
    """
    Retorna itens processados (sent/failed) nos últimos N segundos.
    Usado pelo front para mover cards automaticamente.
    """
    return jobs_service.get_whatsapp_recent(since_secs, user_id=current_user.id)


@router.get("/whatsapp/summary")
def whatsapp_summary(current_user: CurrentUser = Depends(require_crm_access)):
    """
    Contadores rápidos para o banner do front.
    """
    return jobs_service.get_whatsapp_summary(user_id=current_user.id)


# ======== GERAÇÃO DE COPY IA ========

@router.post("/generate-copy")
def generate_copy(req: GenerateCopyRequest, current_user: CurrentUser = Depends(require_crm_access)):
    """
    Gera mensagem de prospecção via LLM para um lead avulso (sem lead_id).
    Usado pelo agent-local para pré-preencher a mensagem antes de enviar.
    """
    import os
    from core_client import fetch_core_ai_profile
    logger.info("generate-copy user_id=%s company=%s", current_user.id, req.company_name)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Serviço de IA não configurado (OPENAI_API_KEY ausente)")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        contact_part = f" para {req.contact_name}" if req.contact_name.strip() else ""
        sector_part = f" no setor de {req.sector}" if req.sector.strip() else ""
        channel_label = {"whatsapp": "WhatsApp", "email": "email", "instagram": "Instagram", "call": "chamada"}.get(req.channel, req.channel)

        try:
            ai_profile = fetch_core_ai_profile(current_user.token or "") or {}
        except Exception:
            ai_profile = {}

        ap_name = ai_profile.get("name") or ""
        ap_brand = ai_profile.get("brand_name") or ""
        ap_niche = ai_profile.get("niche") or ""
        ap_offer = ai_profile.get("offer_description") or ""
        ap_audience = ai_profile.get("target_audience") or ""

        business_ctx = ""
        if ap_brand or ap_niche or ap_offer or ap_audience:
            parts = []
            if ap_brand: parts.append(f"Empresa remetente: {ap_brand}")
            if ap_niche: parts.append(f"Nicho: {ap_niche}")
            if ap_offer: parts.append(f"Oferta: {ap_offer}")
            if ap_audience: parts.append(f"Público-alvo: {ap_audience}")
            business_ctx = "\n".join(parts) + "\n"
        sender_part = f"Remetente: Nome={ap_name or '—'}; Empresa={ap_brand or '—'}\n" if (ap_name or ap_brand) else ""

        if req.custom_prompt_template.strip():
            _var_map = {
                "[empresa]": req.company_name,
                "[nome da empresa do lead]": req.company_name,
                "[setor]": req.sector,
                "[contacto]": req.contact_name,
                "[canal]": channel_label,
                "[tom]": req.tone,
                "[nicho]": ap_niche,
                "[oferta]": ap_offer,
                "[marca]": ap_brand,
            }
            script = req.custom_prompt_template
            for ph, val in _var_map.items():
                script = script.replace(ph, val or "")
            prompt = (
                f"Usa este script como referência e gera uma mensagem de prospecção "
                f"personalizada para a empresa {req.company_name}. "
                f"Adapta o tom e os detalhes para soar natural e directo — não copies "
                f"literalmente, gera uma variação. "
                f"NUNCA uses placeholders como [Seu Nome] ou [Sua Empresa]. "
                f"Máximo 3 frases curtas. Responde APENAS com o texto da mensagem.\n\n"
                f"Script de referência:\n{script}"
            )
        else:
            prompt = (
                f"{business_ctx}"
                f"{sender_part}"
                f"Escreve uma mensagem de prospecção via {channel_label} para a empresa {req.company_name}"
                f"{sector_part}{contact_part}. "
                f"Tom: {req.tone}. "
                f"A oferta deve reflectir o nicho e o produto/serviço do remetente acima — "
                f"não inventes temas genéricos (ex.: marketing digital, limpeza de equipamentos) "
                f"que não tenham relação com a oferta indicada. "
                f"NUNCA uses placeholders como [Seu Nome] ou [Sua Empresa]; usa os dados reais do remetente fornecidos "
                f"ou, na ausência deles, fala apenas em nome da empresa do destinatário sem te apresentares por nome. "
                f"Máximo 3 frases curtas e directas. Não uses saudações genéricas. "
                f"Apresenta uma proposta de valor clara e termina com uma pergunta ou CTA simples. "
                f"Responde APENAS com o texto da mensagem, sem explicações adicionais."
            )

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.7,
        )
        message = response.choices[0].message.content.strip()
        return {"message": message}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate-copy falhou")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar mensagem: {exc}")


# ======== HISTÓRICO DE PROSPECÇÃO ========

@router.get("/history")
def get_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    channel: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(require_crm_access),
):
    """
    Histórico de acções de prospecção do utilizador.
    JOIN prospection_logs + leads para devolver nome, telefone e (para email) o
    endereço de destino do lead.
    Usado pelo agent-local (assinantes) e pela página 'Leads do Agente' no CRM.
    """
    where = "WHERE pl.user_id = ?"
    params: List = [current_user.id, current_user.id]
    if channel:
        where += " AND pl.channel = ?"
        params.append(channel)
    params.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                pl.id,
                pl.lead_id,
                pl.action,
                pl.channel,
                pl.notes,
                pl.createdAt AS created_at,
                COALESCE(l.companyName, l.contactName, 'Lead') AS lead_name,
                l.phone,
                COALESCE(pl.email, CASE WHEN pl.channel = 'email' THEN l.email END) AS email
            FROM prospection_logs pl
            LEFT JOIN leads l ON l.id = pl.lead_id AND l.user_id = ?
            {where}
            ORDER BY pl.createdAt DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()

    return [
        {
            "id": r["id"],
            "lead_id": r["lead_id"],
            "lead_name": r["lead_name"] or "Lead",
            "phone": r["phone"] or "",
            "email": r["email"] or "",
            "channel": r["channel"] or "",
            "action": r["action"],
            "notes": r["notes"] or "",
            "created_at": str(r["created_at"]).replace(" ", "T") if r["created_at"] else "",
        }
        for r in rows
    ]
