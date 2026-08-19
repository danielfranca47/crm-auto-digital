"""
playground.py — Endpoint de simulação de conversas com agentes de IA.

POST /api/playground/chat
  Auth: Bearer token normal do operador (require_crm_access)
  Body: PlaygroundChatRequest
  Response: PlaygroundChatResponse

Bypass completo de WhatsApp, UazAPI, fila de jobs e quota de conversas.
Reutiliza o decision engine (via backend-executors) e toda a infraestrutura
de qualification_state, messages e leads existente.
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import uuid4

import json

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from core_client import fetch_core_ai_profile, fetch_core_ai_profile_by_id
from services.audio_transcription import transcribe_audio_from_path
from services.humanization import compute_reply_delay, compute_typing_ms, split_by_punctuation
from database import get_connection
from security_core import CurrentUser, require_crm_access
from services.ai_orchestrator.orchestrator import build_context_bundle_for_playground
from services.qualification_guardrails import (
    QUALIFICATION_GATED_CATEGORIES,
    can_advance_score_gate,
)
from services.qualification_state import get_qualification_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playground", tags=["Playground"])

TEMP_AUDIO_DIR = Path("temp_audio")
TEMP_AUDIO_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Configuração do executors
# ---------------------------------------------------------------------------

def _get_executors_base() -> str:
    base = os.getenv("EXECUTORS_BASE_URL", "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=503,
            detail="EXECUTORS_BASE_URL não configurado — backend-executors indisponível",
        )
    return base


def _get_service_token() -> str:
    token = os.getenv("CORE_SERVICE_TOKEN") or os.getenv("CRM_SERVICE_TOKEN")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="CORE_SERVICE_TOKEN não configurado — não é possível chamar backend-executors",
        )
    return token


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class PlaygroundChatRequest(BaseModel):
    ai_profile_id: int = Field(..., description="ID do AiProfile no backend-core")
    message: str = Field("", description="Mensagem simulada do lead (vazio apenas em is_opener=True ou message_type=audio)")
    lead_id: Optional[int] = Field(None, description="ID do lead sandbox existente; null cria um novo")
    reset: bool = Field(False, description="Se true, limpa histórico e qualification_state antes de processar")
    scenario_type: Literal["inbound", "outbound", "followup"] = Field("inbound", description="Tipo de cenário: inbound, outbound ou followup (simula tick de follow-up com followup_context injectado)")
    followup_context: Optional[Dict[str, Any]] = Field(None, description="Contexto sintético de follow-up para scenario_type=followup. Campos: followup_variant, followup_outcome, followup_goal, followup_attempts, followup_max_attempts, followup_meeting_happened, followup_proposal_sent")
    is_opener: bool = Field(False, description="Se true e scenario_type=outbound, retorna a mensagem de abertura outbound sem processar mensagem do lead")
    message_type: Optional[str] = Field(None, description="Tipo da mensagem — 'audio' quando gravado no playground")
    audio_filename: Optional[str] = Field(None, description="Nome do ficheiro em temp_audio/ retornado pelo endpoint upload-audio")


class MotherDecision(BaseModel):
    """Saída da LLM Mãe (roteamento)."""
    route_to: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    signals: Optional[Dict[str, Any]] = None


class ChildResult(BaseModel):
    """Saída da LLM Filha (geração da mensagem)."""
    message_text: str = ""
    question_text: Optional[str] = None
    field: Optional[str] = None
    should_ask: bool = False
    did_complete_phase: bool = False
    recommended_next_category: Optional[str] = None
    outcome: Optional[str] = None
    kanban_highlight: Optional[str] = None
    confidence: float = 0.0
    signals_structured: Optional[Dict[str, Any]] = None
    media_keys_to_send: Optional[List[str]] = None


class QualificationStateSnapshot(BaseModel):
    """Estado de qualificação do lead no momento da resposta."""

    # Campos extras do get_qualification_state() (confidence_json, attempts_json, etc.)
    # são ignorados para expor apenas o que é relevante para o consumidor do playground.
    model_config = ConfigDict(extra="ignore")

    exists: bool = False
    data_json: Optional[Dict[str, Any]] = None
    missing_fields: List[str] = Field(default_factory=list)
    filled_fields: List[str] = Field(default_factory=list)
    power_score: int = 0
    priority_score: int = 0
    price_score: int = 0
    timing_score: int = 0
    qualification_total_score: int = 0


class LeadState(BaseModel):
    """Estado actual do lead após o processamento."""
    category: str
    qualification_state: Optional[QualificationStateSnapshot] = None


class DecisionTrace(BaseModel):
    """Metadados de debug do pipeline de decisão."""
    agent_mode: Optional[str] = None
    presentation_variant: Optional[str] = None
    mother_route: Optional[str] = None
    effective_route: Optional[str] = None
    guardrails_applied: List[str] = Field(default_factory=list)
    category_suggestion_cleared: bool = False
    meeting_scheduled: Optional[bool] = None
    required_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    qualification_total_score: Optional[int] = None
    qualification_score_threshold: Optional[int] = None
    qualification_advance_blocked: bool = False
    qualification_advance_blocked_reason: List[str] = Field(default_factory=list)
    ai_profile_id: int
    lead_id: int
    lead_is_sandbox: bool = True
    timestamp: str


class PreSendMediaItem(BaseModel):
    media_url: str
    media_type: str  # "image" | "video" | "audio" | "pdf"
    send_order: int = 0


class PlaygroundChatResponse(BaseModel):
    lead_id: int
    message_to_send: str
    next_action: str

    mother_decision: Optional[MotherDecision] = None
    child_result: Optional[ChildResult] = None
    lead_state: LeadState
    decision_trace: DecisionTrace
    pre_send_media: List[PreSendMediaItem] = Field(default_factory=list)
    simulated_delay_seconds: int = 0
    typing_seconds: float = 0.0
    message_parts: List[str] = Field(default_factory=list)
    audio_previews: List[str] = Field(default_factory=list)  # URLs de myaudio que seriam enviados como voz
    auto_messages: List[str] = Field(default_factory=list)   # Mensagens automáticas de blocos 'mensagem' (texto) — compat
    auto_items: List[dict] = Field(default_factory=list)     # Sequência ordenada: {type:"text",content:...} | {type:"media",...}
    phase_advances: List[str] = Field(default_factory=list)  # Labels de fases avançadas por blocos 'avancar_fase'
    phase_trigger_fired: bool = False                         # True quando phase_trigger disparou → frontend inverte ordem (auto antes do LLM)
    suppress_llm_response: bool = False                       # True quando trigger disparou com flag — frontend omite turno da LLM
    transcription: Optional[str] = None                      # Texto transcrito quando message_type=audio; None nos outros casos
    appointment_event: Optional[Dict[str, Any]] = None        # {action: created|rescheduled|canceled, start_at, end_at} — appointment real criado/alterado neste turno


# ---------------------------------------------------------------------------
# Fluxo de Venda — mapeamentos de fase
# ---------------------------------------------------------------------------

_PHASE_ID_TO_CATEGORY = {
    "p1":  "qualification",
    "p2":  "apresentation",
    "p3a": "apresentation",
    "p3b": "apresentation",
    "p4":  "followup",
    "p5":  "closing",
}

_PHASE_ID_LABELS = {
    "p0":  "Recepção",
    "p1":  "Qualificação",
    "p2":  "Apresentação",
    "p3a": "Pré-Agendamento",
    "p3b": "Agendamento",
    "p4":  "Follow Up",
    "p5":  "Fechamento",
}

# route_to → nome amigável, para rotular no Playground qual Filha respondeu de
# verdade quando a pendência é reenfileirada (ver "Saudação composta" em
# docs/architecture/llm-architecture.md). Mesmos valores de _PHASE_ID_LABELS,
# só que indexado por route_to em vez de phase_id.
_ROUTE_TO_LABELS = {
    "recepcao": "Recepção",
    "qualification": "Qualificação",
    "apresentation": "Apresentação",
    "pre-agendamento": "Pré-Agendamento",
    "agendamento": "Agendamento",
    "follow-up": "Follow Up",
    "closing": "Fechamento",
}

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _load_sandbox_lead(lead_id: int, user_id: int) -> Dict[str, Any]:
    """Carrega lead sandbox — lança 404 se não encontrado ou não é sandbox."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM leads WHERE id = ? AND user_id = ? AND is_playground = 1",
            (lead_id, user_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Lead sandbox não encontrado ou não pertence ao utilizador",
        )
    return dict(row)


def _create_sandbox_lead(user_id: int, origin: str = "playground") -> int:
    """Cria um novo lead sandbox e devolve o seu ID."""
    phone = f"playground_{uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO leads (user_id, companyName, contactName, phone, origin, category, is_playground)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (user_id, None, "Lead de Teste", phone, origin, "qualification"),
        )
        conn.commit()
        return cur.lastrowid


def _reset_sandbox_lead(lead_id: int, user_id: int) -> None:
    """Limpa histórico, qualification_state e appointments do lead sandbox.

    Sem o DELETE de appointments, compromissos "[Playground]" de testes
    anteriores acumulam na Agenda real e podem bloquear (409) agendamentos
    reais futuros no mesmo horário via _check_conflict.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM appointments WHERE lead_id = ?",
            (lead_id,),
        )
        cur.execute(
            "DELETE FROM messages WHERE lead_id = ?",
            (lead_id,),
        )
        cur.execute(
            "DELETE FROM lead_qualification_state WHERE lead_id = ?",
            (lead_id,),
        )
        cur.execute(
            "UPDATE leads SET category = 'qualification' WHERE id = ? AND user_id = ?",
            (lead_id, user_id),
        )
        conn.commit()


def _insert_message(lead_id: int, body: str, model: str) -> None:
    """Insere mensagem no histórico do lead sandbox."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (lead_id, channel, body, model) VALUES (?, 'whatsapp', ?, ?)",
            (lead_id, body, model),
        )
        conn.commit()


def _update_lead_category(lead_id: int, user_id: int, category: str) -> None:
    """Actualiza categoria do lead após sugestão do decision engine."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE leads SET category = ?, lastMovement = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (category, lead_id, user_id),
        )
        conn.commit()


def _check_qualification_gate(lead_id: int, user_id: int, current_category: str, target_category: str) -> Tuple[bool, List[str]]:
    """Gate de score para o caminho automático do bot (paridade com o executor real).

    Só o score (qualification_score_threshold) — campos obrigatórios já são aplicados
    pelo decision_engine antes de a IA sugerir a categoria; checar de novo aqui duplicaria
    a lógica que "audit: Fase 5" removeu de propósito do pipeline automático. Ver
    can_advance_score_gate() em qualification_guardrails.py.
    """
    if current_category != "qualification" or target_category not in QUALIFICATION_GATED_CATEGORIES:
        return True, []
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        return can_advance_score_gate(conn, lead_id, user_id)


def _mark_phase_triggered(lead_id: int, user_id: int, phase_id: str) -> None:
    """Regista que o phase_trigger de uma fase já disparou — impede re-disparo."""
    import json
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT phases_triggered FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id)
        ).fetchone()
        if row:
            try:
                existing: list = json.loads(row["phases_triggered"] or "[]")
            except (ValueError, TypeError):
                existing = []
            if phase_id not in existing:
                existing.append(phase_id)
                cur.execute(
                    "UPDATE leads SET phases_triggered = ? WHERE id = ? AND user_id = ?",
                    (json.dumps(existing), lead_id, user_id),
                )
                conn.commit()


def _mark_trigger_fired(lead_id: int, user_id: int, block_id: str) -> None:
    """Regista que um trigger com fire_once=True já disparou — impede re-disparo."""
    import json
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT triggers_fired FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id)
        ).fetchone()
        if row:
            try:
                existing: list = json.loads(row["triggers_fired"] or "[]")
            except (ValueError, TypeError):
                existing = []
            if block_id not in existing:
                existing.append(block_id)
                cur.execute(
                    "UPDATE leads SET triggers_fired = ? WHERE id = ? AND user_id = ?",
                    (json.dumps(existing), lead_id, user_id),
                )
                conn.commit()


def _mark_knowledge_shown(lead_id: int, user_id: int, categories: list) -> None:
    """Regista categorias narrativas de knowledge (social_proof, pitch_script,
    product_details) já mostradas ao lead — impede repetição em turnos futuros."""
    import json
    if not categories:
        return
    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT knowledge_categories_shown FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, user_id),
        ).fetchone()
        if row:
            try:
                existing: list = json.loads(row["knowledge_categories_shown"] or "[]")
            except (ValueError, TypeError):
                existing = []
            changed = False
            for category in categories:
                if category not in existing:
                    existing.append(category)
                    changed = True
            if changed:
                cur.execute(
                    "UPDATE leads SET knowledge_categories_shown = ? WHERE id = ? AND user_id = ?",
                    (json.dumps(existing), lead_id, user_id),
                )
                conn.commit()


def _call_executors_decide(context_bundle_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chama POST {EXECUTORS_BASE_URL}/api/internal/playground/decide de forma síncrona.
    Devolve a DecisionOutput como dict.
    """
    base = _get_executors_base()
    token = _get_service_token()
    url = f"{base}/api/internal/playground/decide"
    headers = {
        "X-Service-Token": token,
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=headers, json={"context_bundle": context_bundle_dict})
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao contactar backend-executors: {exc}",
        ) from exc

    if resp.status_code == 401:
        raise HTTPException(status_code=502, detail="Service token rejeitado pelo backend-executors")
    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"backend-executors retornou erro {resp.status_code}: {resp.text[:300]}",
        )

    return resp.json()


def _build_mother_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    trace = decision.get("decision_trace") or {}
    return {
        "route_to": trace.get("mother_route_to") or trace.get("effective_route_to"),
        "confidence": trace.get("mother_confidence", 0.0),
        "reason": decision.get("reason", ""),
        "signals": trace.get("mother_signals"),
    }


def _build_child_result(decision: Dict[str, Any]) -> Dict[str, Any]:
    trace = decision.get("decision_trace") or {}
    questions: List[str] = decision.get("questions") or []
    return {
        "message_text": decision.get("message_text", ""),
        "question_text": questions[0] if questions else None,
        "field": trace.get("current_field"),
        "should_ask": decision.get("next_action") == "ask_qualification",
        "did_complete_phase": bool(trace.get("child_recommended_next_category")),
        "recommended_next_category": trace.get("child_recommended_next_category"),
        "outcome": decision.get("outcome"),
        "kanban_highlight": decision.get("kanban_highlight"),
        "confidence": decision.get("confidence") or 0.0,
        "signals_structured": trace.get("child_signals_structured"),
    }


def _build_decision_trace(
    decision: Dict[str, Any],
    ai_profile_id: int,
    lead_id: int,
    *,
    qualification_total_score: Optional[int] = None,
    qualification_score_threshold: Optional[int] = None,
    qualification_advance_blocked: bool = False,
    qualification_advance_blocked_reason: Optional[List[str]] = None,
) -> Dict[str, Any]:
    trace = decision.get("decision_trace") or {}
    guardrails = [k for k, v in trace.items() if k.startswith("guardrail_") and v]
    return {
        "agent_mode": trace.get("agent_mode_normalized") or trace.get("agent_mode"),
        "presentation_variant": trace.get("presentation_variant"),
        "mother_route": trace.get("mother_route_to"),
        "effective_route": trace.get("effective_route_to"),
        "guardrails_applied": guardrails,
        "category_suggestion_cleared": (
            trace.get("suggested_category_final") is None
            and decision.get("suggested_category") is None
        ),
        "meeting_scheduled": trace.get("meeting_scheduled"),
        "required_fields": trace.get("required_fields") or [],
        "missing_fields": trace.get("missing_fields") or [],
        "qualification_total_score": qualification_total_score,
        "qualification_score_threshold": qualification_score_threshold,
        "qualification_advance_blocked": qualification_advance_blocked,
        "qualification_advance_blocked_reason": qualification_advance_blocked_reason or [],
        "ai_profile_id": ai_profile_id,
        "lead_id": lead_id,
        "lead_is_sandbox": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------

@router.post("/upload-audio")
async def upload_playground_audio(
    audio: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Recebe um ficheiro de áudio gravado no playground e guarda-o temporariamente."""
    ext = Path(audio.filename or "audio.ogg").suffix or ".ogg"
    filename = f"{uuid4().hex}{ext}"
    dest = TEMP_AUDIO_DIR / filename
    with dest.open("wb") as f:
        shutil.copyfileobj(audio.file, f)
    return {"filename": filename, "audio_url": f"/api/playground/audio/{filename}"}


@router.get("/audio/{filename}")
async def serve_playground_audio(
    filename: str,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Serve um ficheiro de áudio guardado temporariamente para reprodução no browser."""
    path = TEMP_AUDIO_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    return FileResponse(str(path), media_type="audio/ogg")


class TranscribeRequest(BaseModel):
    ai_profile_id: int


@router.post("/audio/{filename}/transcribe")
def transcribe_playground_audio(
    filename: str,
    body: TranscribeRequest,
    current_user: CurrentUser = Depends(require_crm_access),
):
    """Transcreve um áudio do playground sem chamar o LLM — usado pelo modo lote para obter
    o texto de cada áudio antes de combinar numa única chamada ao decision engine."""
    ai_profile = fetch_core_ai_profile_by_id(body.ai_profile_id, current_user.id)
    if not ai_profile.get("audio_transcription_enabled"):
        return {"transcription": None, "audio_enabled": False}
    audio_path = str(TEMP_AUDIO_DIR / filename)
    if not Path(audio_path).exists():
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    transcription = transcribe_audio_from_path(audio_path)
    return {"transcription": transcription, "audio_enabled": True}


@router.post("/chat", response_model=PlaygroundChatResponse)
def playground_chat(
    body: PlaygroundChatRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> PlaygroundChatResponse:
    """
    Simula uma conversa completa com um agente de IA sem necessidade de WhatsApp.

    Fluxo:
    1. Validação do ai_profile_id (pertence ao utilizador)
    2. Gestão do lead sandbox (cria ou reutiliza)
    3. Reset opcional (limpa histórico e qualification_state)
    4. Guarda mensagem inbound no histórico
    5. Constrói ContextBundle para o playground
    6. Chama decision engine via backend-executors
    7. Persiste categoria sugerida (se aplicável)
    8. Guarda mensagem outbound no histórico
    9. Retorna PlaygroundChatResponse completo
    """
    user_id = current_user.id

    # ── Gate de plano: limite mensal de playground ───────────────────────────
    from services.plan_gates import check_playground_limit
    _gate_conn = get_connection()
    try:
        check_playground_limit(user_id, current_user.entitlements, _gate_conn)
    finally:
        _gate_conn.close()

    # ── Passo 4: Fetch AI Profile (valida propriedade) ──────────────────────
    ai_profile = fetch_core_ai_profile_by_id(body.ai_profile_id, user_id)

    # ── Passo 2: Gestão do Lead Sandbox ─────────────────────────────────────
    lead_origin = body.scenario_type  # "inbound" ou "outbound"
    if body.lead_id is not None:
        _load_sandbox_lead(body.lead_id, user_id)  # 404 se não encontrado
        lead_id = body.lead_id
    else:
        origin_label = f"playground_{body.scenario_type}"
        lead_id = _create_sandbox_lead(user_id, origin=origin_label)

    # ── Passo 3: Reset (se solicitado) ───────────────────────────────────────
    if body.reset:
        _reset_sandbox_lead(lead_id, user_id)

    # ── Atalho: Outbound opener — retorna abertura sem processar mensagem do lead ──
    if body.is_opener and body.scenario_type == "outbound":
        opener = (ai_profile.get("origin_outbound_opener") or "").strip()
        if not opener:
            opener = "Olá! Tudo bem? Aqui é da equipe e gostaria de apresentar uma solução que pode ser interessante para você."
        _insert_message(lead_id, opener, "outbound")
        return PlaygroundChatResponse(
            lead_id=lead_id,
            message_to_send=opener,
            next_action="reply",
            lead_state={"category": "qualification", "qualification_state": None},
            decision_trace=DecisionTrace(
                agent_mode=ai_profile.get("agent_mode"),
                presentation_variant=ai_profile.get("presentation_variant"),
                mother_route="outbound_opener",
                effective_route="outbound_opener",
                ai_profile_id=body.ai_profile_id,
                lead_id=lead_id,
                lead_is_sandbox=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
        )

    # ── Passo 3b: Áudio ou mensagem de texto inbound ─────────────────────────
    effective_message = body.message
    _audio_transcription: Optional[str] = None  # devolvido na resposta para exibição no frontend

    if body.message_type == "audio" and body.audio_filename:
        audio_path = str(TEMP_AUDIO_DIR / body.audio_filename)
        audio_enabled = bool(ai_profile.get("audio_transcription_enabled"))

        if audio_enabled:
            transcription = transcribe_audio_from_path(audio_path)
            if transcription:
                _audio_transcription = transcription
                effective_message = f"[Áudio]: {transcription}"
            else:
                # falha de transcrição — simular media_fallback
                offer_pack = ai_profile.get("offer_pack") or {}
                fallback_msg = offer_pack.get("media_fallback_msg") or "Não consegui processar o áudio. Por favor, tente novamente."
                _insert_message(lead_id, "[Áudio]: (falha na transcrição)", "inbound")
                return PlaygroundChatResponse(
                    lead_id=lead_id,
                    message_to_send=fallback_msg,
                    next_action="none",
                    lead_state=LeadState(category="qualification"),
                    decision_trace=DecisionTrace(
                        agent_mode=ai_profile.get("agent_mode"),
                        presentation_variant=ai_profile.get("presentation_variant"),
                        mother_route="audio_transcription_failed",
                        effective_route="audio_transcription_failed",
                        ai_profile_id=body.ai_profile_id,
                        lead_id=lead_id,
                        lead_is_sandbox=True,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ),
                )
        else:
            # toggle desligado — simular comportamento de media_fallback
            offer_pack = ai_profile.get("offer_pack") or {}
            behavior = (offer_pack.get("media_fallback") or "ignorar").lower()
            msg_map = {
                "continuar": offer_pack.get("media_fallback_msg") or "Não consigo processar áudios. Por favor, envie uma mensagem de texto.",
                "pausar": (offer_pack.get("media_fallback_msg") or "Não consigo processar áudios."),
                "ignorar": "Áudio não aceito — ative 'Receber áudio' no AI Profile para testar esta funcionalidade.",
            }
            fallback_msg = msg_map.get(behavior, msg_map["ignorar"])
            _insert_message(lead_id, "[Áudio]: (transcrição desativada)", "inbound")
            return PlaygroundChatResponse(
                lead_id=lead_id,
                message_to_send=fallback_msg,
                next_action="none",
                lead_state=LeadState(category="qualification"),
                decision_trace=DecisionTrace(
                    agent_mode=ai_profile.get("agent_mode"),
                    presentation_variant=ai_profile.get("presentation_variant"),
                    mother_route="audio_disabled",
                    effective_route="audio_disabled",
                    ai_profile_id=body.ai_profile_id,
                    lead_id=lead_id,
                    lead_is_sandbox=True,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ),
            )

    # Follow-up tick: mensagem vazia é legítima — injeta contexto que replica o sinal real do executor
    if not effective_message and body.scenario_type == "followup":
        fu_ctx = body.followup_context or {}
        meeting_happened = fu_ctx.get("followup_meeting_happened", True)
        outcome = fu_ctx.get("followup_outcome", "warm")
        if meeting_happened:
            effective_message = f"[follow-up tick — reunião realizada, outcome={outcome}. Envia mensagem de reengajamento pós-reunião.]"
        else:
            effective_message = "[follow-up tick — reunião não aconteceu. Tenta recontactar e reagendar.]"

    if not effective_message:
        raise HTTPException(status_code=422, detail="message é obrigatório quando is_opener=False")
    _insert_message(lead_id, effective_message, "inbound")

    # ── Delay simulado (paridade com WhatsApp real) ───────────────────────────
    with get_connection() as _conn_pg:
        _pg_msg_row = _conn_pg.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        _pg_msg_count = int(_pg_msg_row["cnt"]) if _pg_msg_row else 0
    _pg_is_first = _pg_msg_count <= 1
    _simulated_delay = compute_reply_delay(dict(ai_profile), _pg_is_first)

    # ── Passo 5: Build Context Bundle ────────────────────────────────────────
    bundle = build_context_bundle_for_playground(
        user_id=user_id,
        ai_profile=ai_profile,
        lead_id=lead_id,
        message_text=effective_message,
        scenario_type=body.scenario_type,
        followup_context=body.followup_context if body.scenario_type == "followup" else None,
    )

    # Serializa para dict (compatível com decision_engine.decide(context: Dict))
    bundle_dict = bundle.model_dump(mode="json")

    # ── Passo 6: Chamar Decision Engine via executors ────────────────────────
    decision = _call_executors_decide(bundle_dict)

    # ── Passo 7: Persistir estado pós-decisão ────────────────────────────────
    suggested_category = decision.get("suggested_category")
    _pre_decision_category = str((bundle_dict.get("lead") or {}).get("category") or "").strip().lower()
    _qualification_gate_blocked = False
    _qualification_gate_missing: List[str] = []
    if suggested_category:
        _can_advance, _qualification_gate_missing = _check_qualification_gate(
            lead_id, user_id, _pre_decision_category, suggested_category,
        )
        if _can_advance:
            _update_lead_category(lead_id, user_id, suggested_category)
        else:
            _qualification_gate_blocked = True
            logger.info(
                "lead_category_blocked_incomplete_qualification lead_id=%s missing=%s suggested=%s origin=playground",
                lead_id, _qualification_gate_missing, suggested_category,
            )

    message_to_send = decision.get("message_text") or ""

    # ── Passo 7b: Processar system_actions do Fluxo de Venda ────────────────
    raw_system_actions = decision.get("system_actions") or []
    auto_messages = []
    auto_items = []
    phase_advances = []
    appointment_event: Optional[Dict[str, Any]] = None
    _pending_requeue_text: Optional[str] = None
    for action in raw_system_actions:
        atype = action.get("type")
        if atype == "appointment_event" and action.get("action"):
            appointment_event = {
                "action": action["action"],
                "start_at": action.get("start_at"),
                "end_at": action.get("end_at"),
            }
        elif atype == "send_message" and action.get("content"):
            auto_messages.append(action["content"])
            auto_items.append({
                "type": "text",
                "content": action["content"],
                "source": "sales_flow",
                "source_label": "Fluxo de Venda",
            })
        elif atype == "send_media" and action.get("media_url"):
            auto_items.append({
                "type": "media",
                "media_url": action["media_url"],
                "media_type": action.get("media_type") or "image",
            })
        elif atype == "advance_phase":
            target = action.get("target_phase")
            if not target:
                continue
            category = _PHASE_ID_TO_CATEGORY.get(target)
            if category:
                _update_lead_category(lead_id, user_id, category)
                label = _PHASE_ID_LABELS.get(target, target)
                phase_advances.append(f"{label} ({target})")
        elif atype == "mark_phase_triggered" and action.get("phase_id"):
            _mark_phase_triggered(lead_id, user_id, action["phase_id"])
        elif atype == "mark_trigger_fired" and action.get("block_id"):
            _mark_trigger_fired(lead_id, user_id, action["block_id"])
        elif atype == "mark_knowledge_shown" and action.get("categories"):
            _mark_knowledge_shown(lead_id, user_id, action["categories"])
        elif atype == "requeue_pending_message" and action.get("message_text"):
            _pending_requeue_text = str(action["message_text"]).strip()

    phase_trigger_fired = any(
        a.get("type") == "mark_phase_triggered" for a in raw_system_actions
    )

    # ── Passo 8: Guarda mensagens outbound ───────────────────────────────────
    if message_to_send:
        _insert_message(lead_id, message_to_send, "outbound")
    for auto_msg in auto_messages:
        _insert_message(lead_id, auto_msg, "outbound")

    # ── Passo 8b: Pedido comercial pendente — 2ª chamada síncrona ao decision
    # engine, replicando no Playground o novo job que o WhatsApp real criaria
    # (ver requeue_pending_message em executor.py). Sem fila/worker aqui: simula
    # o "próximo ciclo do pipeline" na MESMA request, para o operador ver as
    # duas bolhas de uma vez. A mensagem outbound da 1ª decisão já foi persistida
    # acima, então o histórico da 2ª chamada já inclui a saudação.
    if _pending_requeue_text:
        _insert_message(lead_id, _pending_requeue_text, "inbound")
        _bundle2 = build_context_bundle_for_playground(
            user_id=user_id,
            ai_profile=ai_profile,
            lead_id=lead_id,
            message_text=_pending_requeue_text,
            scenario_type=body.scenario_type,
            followup_context=body.followup_context if body.scenario_type == "followup" else None,
        )
        _decision2 = _call_executors_decide(_bundle2.model_dump(mode="json"))

        _suggested_category2 = _decision2.get("suggested_category")
        if _suggested_category2:
            with get_connection() as _conn_cat2:
                _row_cat2 = _conn_cat2.execute("SELECT category FROM leads WHERE id = ?", (lead_id,)).fetchone()
            _category_before_2 = str((_row_cat2["category"] if _row_cat2 else "") or "").strip().lower()
            _can_advance2, _qualification_gate_missing2 = _check_qualification_gate(
                lead_id, user_id, _category_before_2, _suggested_category2,
            )
            if _can_advance2:
                _update_lead_category(lead_id, user_id, _suggested_category2)
            else:
                _qualification_gate_blocked = True
                _qualification_gate_missing = _qualification_gate_missing2
                logger.info(
                    "lead_category_blocked_incomplete_qualification lead_id=%s missing=%s suggested=%s origin=playground_requeue",
                    lead_id, _qualification_gate_missing2, _suggested_category2,
                )

        _message_to_send2 = _decision2.get("message_text") or ""
        if _message_to_send2:
            if _decision2.get("reason") == "llm_failure":
                _source2, _source_label2 = "fallback", "Handoff (erro de decisão)"
            else:
                _effective_route2 = (_decision2.get("decision_trace") or {}).get("effective_route_to")
                _source2 = "child_llm"
                _source_label2 = _ROUTE_TO_LABELS.get(_effective_route2, _effective_route2 or "Bot")
            auto_items.append({
                "type": "text",
                "content": _message_to_send2,
                "source": _source2,
                "source_label": _source_label2,
            })
            auto_messages.append(_message_to_send2)
            _insert_message(lead_id, _message_to_send2, "outbound")

        for action2 in (_decision2.get("system_actions") or []):
            atype2 = action2.get("type")
            if atype2 == "appointment_event" and action2.get("action"):
                appointment_event = {
                    "action": action2["action"],
                    "start_at": action2.get("start_at"),
                    "end_at": action2.get("end_at"),
                }
            elif atype2 == "send_message" and action2.get("content"):
                auto_messages.append(action2["content"])
                auto_items.append({
                    "type": "text",
                    "content": action2["content"],
                    "source": "sales_flow",
                    "source_label": "Fluxo de Venda",
                })
                _insert_message(lead_id, action2["content"], "outbound")
            elif atype2 == "send_media" and action2.get("media_url"):
                auto_items.append({
                    "type": "media",
                    "media_url": action2["media_url"],
                    "media_type": action2.get("media_type") or "image",
                })
            elif atype2 == "advance_phase" and action2.get("target_phase"):
                _category2 = _PHASE_ID_TO_CATEGORY.get(action2["target_phase"])
                if _category2:
                    _update_lead_category(lead_id, user_id, _category2)
                    _label2 = _PHASE_ID_LABELS.get(action2["target_phase"], action2["target_phase"])
                    phase_advances.append(f"{_label2} ({action2['target_phase']})")
            elif atype2 == "mark_phase_triggered" and action2.get("phase_id"):
                _mark_phase_triggered(lead_id, user_id, action2["phase_id"])
                phase_trigger_fired = True
            elif atype2 == "mark_trigger_fired" and action2.get("block_id"):
                _mark_trigger_fired(lead_id, user_id, action2["block_id"])
            elif atype2 == "mark_knowledge_shown" and action2.get("categories"):
                _mark_knowledge_shown(lead_id, user_id, action2["categories"])
            elif atype2 == "requeue_pending_message":
                # Não recursiona — ver docs/architecture/llm-architecture.md.
                logger.warning(
                    "event=playground_double_requeue_ignored lead_id=%s user_id=%s",
                    lead_id, user_id,
                )

    # ── Passo 9: Construir Response ──────────────────────────────────────────
    # Re-fetch estado actual do lead e qualification após o engine ter (possivelmente) actualizado
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT category FROM leads WHERE id = ?", (lead_id,))
        lead_row = cur.fetchone()
    current_category = (lead_row["category"] if lead_row else "qualification") or "qualification"

    qualification_state = get_qualification_state(lead_id)

    lead_state = {
        "category": current_category,
        "qualification_state": qualification_state,
    }

    # Normalizar pre_send_media retornado pelo executor
    raw_media = decision.get("pre_send_media") or []
    if isinstance(raw_media, dict):
        raw_media = [raw_media]
    pre_send_media = [
        PreSendMediaItem(
            media_url=m.get("media_url", ""),
            media_type=m.get("media_type", "image"),
            send_order=m.get("send_order", 0),
        )
        for m in raw_media
        if m.get("media_url")
    ]

    _typing_ms = compute_typing_ms(message_to_send) if message_to_send else 0
    _message_parts = split_by_punctuation(message_to_send) if message_to_send else []
    _audio_previews = [
        m.media_url for m in pre_send_media if m.media_type in ("myaudio", "ptt")
    ]

    return PlaygroundChatResponse(
        lead_id=lead_id,
        message_to_send=message_to_send,
        next_action=decision.get("next_action", "reply"),
        mother_decision=_build_mother_decision(decision),
        child_result=_build_child_result(decision),
        lead_state=lead_state,
        decision_trace=_build_decision_trace(
            decision, body.ai_profile_id, lead_id,
            qualification_total_score=qualification_state.get("qualification_total_score"),
            qualification_score_threshold=ai_profile.get("qualification_score_threshold"),
            qualification_advance_blocked=_qualification_gate_blocked,
            qualification_advance_blocked_reason=_qualification_gate_missing,
        ),
        pre_send_media=pre_send_media,
        simulated_delay_seconds=_simulated_delay,
        typing_seconds=round(_typing_ms / 1000, 1),
        message_parts=_message_parts,
        audio_previews=_audio_previews,
        auto_messages=auto_messages,
        auto_items=auto_items,
        phase_advances=phase_advances,
        phase_trigger_fired=phase_trigger_fired,
        suppress_llm_response=bool(decision.get("suppress_llm_response")),
        transcription=_audio_transcription,
        appointment_event=appointment_event,
    )


# ---------------------------------------------------------------------------
# FeedbackAssist — Assistente IA para análise e correção de comportamentos
# ---------------------------------------------------------------------------

# Campos do AI Profile que podem ser expostos e alterados via assistente
_SAFE_PROFILE_FIELDS = [
    "brand_name", "name", "tone_of_voice", "response_style", "presentation_variant",
    "identity_mode", "custom_instructions", "qualification_required_fields",
    "qualification_score_threshold", "origin_inbound_opener", "origin_outbound_opener",
    "agent_mode", "template_key", "objection_common", "handoff_policy",
    "nurture_vs_discard_rule", "niche", "target_audience", "offer_description", "goals",
]

_FEEDBACK_ASSIST_SYSTEM_PROMPT = """Você é um especialista em configuração de agentes de IA de CRM.
Sua tarefa é analisar comportamentos problemáticos observados em sessões de playground e determinar se são resolvíveis por mudança de configuração do AI Profile ou se exigem correção de código.

## Campos do AI Profile e seus efeitos comportamentais

- `brand_name` (str): Nome da marca/empresa que o bot usa. Se o bot se apresenta com nome errado → altere este campo.
- `name` (str): Nome interno do perfil (não exibido ao lead).
- `tone_of_voice` (str): Tom geral da comunicação (ex: "profissional", "amigável", "direto").
- `response_style` ("active"|"passive"): "active" = bot é proativo e faz perguntas sem ser solicitado; "passive" = bot responde apenas ao que foi perguntado. Bot muito agressivo → mude para "passive".
- `presentation_variant` ("sales"|"scheduler"): "sales" = tom de venda direta/B2B; "scheduler" = foco em agendamento, tom gentil. Se bot usa linguagem de vendas agressiva num contexto de agenda → altere para "scheduler".
- `identity_mode` ("virtual_assistant"|"human_agent"|"user_clone"): Como o bot se apresenta. "human_agent" = simula humano real.
- `custom_instructions` (str): Instrução livre de alta prioridade injetada no prompt do agente. Use para regras específicas: nome do responsável, frases proibidas, restrições de nicho, como apresentar preços, etc.
- `qualification_required_fields` (list[str]): Campos que o bot DEVE coletar antes de avançar. Bot perguntando campos desnecessários ou não perguntando campos importantes → ajuste esta lista.
- `qualification_score_threshold` (int, padrão 6): Pontuação mínima para considerar um lead qualificado.
- `origin_inbound_opener` (str): Mensagem enviada pelo bot na PRIMEIRA interação com leads inbound. Se bot não envia mensagem de abertura → preencha este campo.
- `origin_outbound_opener` (str): Mensagem de abertura para leads outbound.
- `agent_mode` ("consultivo"|"agenda"|"direto"|"sdr_scheduler"|"closer"): Define o template macro de comportamento do agente. Mudança aqui tem impacto amplo.
- `template_key` (str): Template de persona base. Mudança tem impacto estrutural.
- `objection_common` (str): Resposta padrão para objeções comuns do nicho.
- `handoff_policy` ("disable_bot"|"keep_active_notify"|"ignore"): Comportamento ao transferir para humano.
- `nurture_vs_discard_rule` ("nurture"|"discard"): O que fazer com leads não qualificados.
- `niche` (str): Nicho de mercado. Afeta o contexto dos prompts gerados.
- `target_audience` (str): Público-alvo. Afeta o contexto dos prompts.
- `offer_description` (str): Descrição da oferta. Usada nos prompts de apresentação.
- `goals` (str): Objetivos do agente. Afeta priorização de ações.

## Problemas NÃO resolvíveis por configuração (exigem código)
- Lógica de roteamento da LLM Mãe (mother router — decisão de qual fluxo seguir)
- Cálculo de confidence ou scores de qualificação (power_score, priority_score, etc.)
- Disparo incorreto de guardrails (requer ajuste nos thresholds de código)
- Comportamento de guardrails específicos

## Instrução de resposta
Responda EXCLUSIVAMENTE em JSON com este schema:
{
  "action": "update_profile" | "explain_only" | "export_required",
  "fields_to_update": {field_name: new_value} | null,
  "explanation": "Explicação clara em português para o utilizador (máx. 3 parágrafos curtos)",
  "analysis": "Diagnóstico técnico resumido do comportamento observado (para log interno)",
  "is_config_fixable": true | false
}

Regras:
1. Se is_config_fixable=true E identificou campo(s) → action="update_profile", fields_to_update={campo: novo_valor}
2. Se is_config_fixable=false → action="explain_only", fields_to_update=null
3. Altere no máximo 2 campos por resposta — seja conservador
4. Nunca invente campos que não estão na lista acima
5. Seja direto na explanation — o utilizador não é técnico
6. O campo analysis é para log interno, pode ser mais técnico
"""


class FeedbackItemPayload(BaseModel):
    messageId: str
    messagePreview: str
    notes: str
    tags: List[str]


class ConversationMessagePayload(BaseModel):
    role: str
    text: str
    timestamp: str
    motherRoute: Optional[str] = None
    confidence: Optional[float] = None
    guardrails: Optional[List[str]] = None
    decisionTrace: Optional[Dict[str, Any]] = None


class PreviousAttempt(BaseModel):
    attempt_number: int
    user_question: str
    analysis: str
    fields_changed: Optional[Dict[str, Any]] = None
    outcome: str


class FeedbackAssistRequest(BaseModel):
    ai_profile_id: int
    conversation_messages: List[ConversationMessagePayload]
    feedback_items: List[FeedbackItemPayload]
    user_question: str = Field(..., min_length=1)
    attempt_number: int = Field(default=1, ge=1)
    previous_attempts: List[PreviousAttempt] = Field(default_factory=list)
    mode: Literal["edicao", "planejamento", "duvidas"] = Field(
        "edicao",
        description="Modo de trabalho do assistente: edicao (diagnóstico+edição), planejamento (plano sem edição), duvidas (só respostas)",
    )


class FeedbackAssistResponse(BaseModel):
    action: str
    fields_to_update: Optional[Dict[str, Any]] = None
    fields_current_values: Optional[Dict[str, Any]] = None
    explanation: str
    analysis: str
    is_config_fixable: bool
    attempt_number: int


def _format_conversation_for_prompt(messages: List[ConversationMessagePayload]) -> str:
    lines = []
    for msg in messages:
        role = "Lead" if msg.role == "lead" else "Bot"
        text_preview = msg.text[:300] + ("…" if len(msg.text) > 300 else "")
        lines.append(f"[{role}] {text_preview}")
        if msg.decisionTrace:
            t = msg.decisionTrace
            route = t.get("mother_route", "—")
            effective = t.get("effective_route", "—")
            conf = msg.confidence
            conf_str = f"{round(conf * 100)}%" if conf is not None else "—"
            guardrails = msg.guardrails or []
            lines.append(f"  → route={route}, effective={effective}, confidence={conf_str}, guardrails={guardrails}")
    return "\n".join(lines) if lines else "(sem mensagens)"


def _format_feedbacks_for_prompt(items: List[FeedbackItemPayload]) -> str:
    if not items:
        return "(nenhum feedback anotado)"
    lines = []
    for fb in items:
        lines.append(f'- Mensagem: "{fb.messagePreview}"')
        lines.append(f'  Tags: {", ".join(fb.tags) if fb.tags else "nenhuma"}')
        lines.append(f'  Nota: {fb.notes or "(sem nota)"}')
    return "\n".join(lines)


def _format_previous_attempts_for_prompt(attempts: List[PreviousAttempt]) -> str:
    if not attempts:
        return "(nenhuma tentativa anterior)"
    lines = []
    for a in attempts:
        lines.append(f"Tentativa {a.attempt_number}: {a.user_question}")
        lines.append(f"  Análise: {a.analysis}")
        if a.fields_changed:
            for field, change in a.fields_changed.items():
                lines.append(f"  Campo {field}: {change.get('from')} → {change.get('to')}")
        lines.append(f"  Resultado: {a.outcome}")
    return "\n".join(lines)


def _get_mode_instructions(
    mode: str,
    attempt_number: int,
    previous_attempts: List[PreviousAttempt],
) -> str:
    """Devolve instruções adicionais para o system prompt com base no modo selecionado."""
    is_first_interaction = attempt_number == 1 and len(previous_attempts) == 0

    if mode == "duvidas":
        return """
## MODO ATUAL: Dúvidas
O utilizador quer apenas fazer perguntas e receber explicações sobre o agente ou as configurações.
REGRAS OBRIGATÓRIAS:
- Nunca sugira alterações de campos do AI Profile.
- Nunca retorne action="update_profile".
- SEMPRE retorne action="explain_only" e fields_to_update=null.
- Responda de forma clara e educativa.
"""

    if mode == "planejamento":
        return """
## MODO ATUAL: Planejamento
O utilizador quer entender o problema e receber um plano de melhorias, sem aplicar nada agora.
REGRAS OBRIGATÓRIAS:
- Nunca retorne action="update_profile".
- SEMPRE retorne action="explain_only" e fields_to_update=null.
- Na sua explanation, devolva um PLANO NUMERADO com as melhorias sugeridas, ordenadas por impacto.
- Para cada passo do plano, indique: o campo a alterar (se aplicável), o valor sugerido e o efeito esperado.
- Seja detalhado e didático — este é um plano para o utilizador executar à sua própria velocidade.
"""

    # Modo "edicao"
    if is_first_interaction:
        return """
## MODO ATUAL: Edição — Fase de Diagnóstico (1ª mensagem)
Esta é a PRIMEIRA interação desta sessão. O utilizador precisa primeiro entender o diagnóstico antes de aplicar mudanças.
REGRAS OBRIGATÓRIAS:
- NÃO proponha campos para alterar ainda.
- NÃO retorne action="update_profile".
- SEMPRE retorne action="explain_only" e fields_to_update=null nesta resposta.
- Explique claramente: (1) qual é o problema identificado, (2) qual a causa provável, (3) o que poderia ser feito.
- Termine a explicação com uma frase convidando o utilizador a confirmar se quer prosseguir com as alterações sugeridas.
"""

    return """
## MODO ATUAL: Edição — Fase de Proposta
O utilizador já viu o diagnóstico e quer avançar com as alterações.
Pode agora propor campos para alterar se o problema for resolvível por configuração.
Se identificou campos a alterar → retorne action="update_profile" com fields_to_update preenchido.
"""


def _build_feedback_assist_user_message(
    ai_profile: Dict[str, Any],
    conv_messages: List[ConversationMessagePayload],
    feedback_items: List[FeedbackItemPayload],
    user_question: str,
    previous_attempts: List[PreviousAttempt],
) -> str:
    profile_safe = {k: ai_profile.get(k) for k in _SAFE_PROFILE_FIELDS if ai_profile.get(k) is not None}
    return f"""## Configuração atual do AI Profile
{json.dumps(profile_safe, ensure_ascii=False, indent=2)}

## Conversa simulada (com traces)
{_format_conversation_for_prompt(conv_messages)}

## Feedbacks anotados pelo utilizador
{_format_feedbacks_for_prompt(feedback_items)}

## Tentativas anteriores
{_format_previous_attempts_for_prompt(previous_attempts)}

## Pergunta do utilizador
{user_question}
"""


@router.post("/feedback-assist", response_model=FeedbackAssistResponse)
def playground_feedback_assist(
    body: FeedbackAssistRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> FeedbackAssistResponse:
    """
    Assistente IA para análise e correção de comportamentos observados no playground.

    Recebe o contexto completo (AI Profile + conversa + feedbacks anotados + pergunta do utilizador)
    e determina se o problema é resolvível por configuração ou exige código.
    Após 3 tentativas força export_required.
    """
    # Valida propriedade do ai_profile_id
    ai_profile = fetch_core_ai_profile_by_id(body.ai_profile_id, current_user.id)

    # Após 3 tentativas, encaminhar para exportação
    if body.attempt_number >= 3:
        return FeedbackAssistResponse(
            action="export_required",
            explanation=(
                "Após 3 tentativas de ajuste, o comportamento pode ter uma causa mais profunda "
                "que requer análise de código. Exporte o relatório completo e encaminhe para suporte — "
                "ele já inclui tudo que foi tentado aqui."
            ),
            analysis="Limite de tentativas de configuração atingido.",
            is_config_fixable=False,
            attempt_number=body.attempt_number,
        )

    # Verificar se OpenAI está disponível
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY não configurado — assistente de feedback indisponível",
        )

    try:
        from openai import OpenAI  # type: ignore
        client_openai = OpenAI(api_key=api_key)
    except ImportError:
        raise HTTPException(status_code=503, detail="Biblioteca openai não instalada no backend-crm")

    # Montar system prompt com instruções do modo
    mode_instructions = _get_mode_instructions(
        mode=body.mode,
        attempt_number=body.attempt_number,
        previous_attempts=body.previous_attempts,
    )
    system_prompt = _FEEDBACK_ASSIST_SYSTEM_PROMPT + mode_instructions

    # Montar mensagens para a LLM
    user_msg = _build_feedback_assist_user_message(
        ai_profile=dict(ai_profile) if not isinstance(ai_profile, dict) else ai_profile,
        conv_messages=body.conversation_messages,
        feedback_items=body.feedback_items,
        user_question=body.user_question,
        previous_attempts=body.previous_attempts,
    )

    try:
        raw = client_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        parsed = json.loads(raw.choices[0].message.content)
    except Exception as exc:
        logger.warning("FeedbackAssist LLM error: %s", exc)
        return FeedbackAssistResponse(
            action="explain_only",
            explanation="Não foi possível analisar o comportamento agora. Verifique a ligação e tente novamente.",
            analysis=f"LLM error: {exc}",
            is_config_fixable=False,
            attempt_number=body.attempt_number,
        )

    # Safety net: forçar explain_only quando o modo não permite edições
    is_first_edicao = (
        body.mode == "edicao"
        and body.attempt_number == 1
        and len(body.previous_attempts) == 0
    )
    force_explain_only = body.mode in ("duvidas", "planejamento") or is_first_edicao

    if force_explain_only:
        parsed["action"] = "explain_only"
        parsed["fields_to_update"] = None
        parsed["is_config_fixable"] = False

    # Enriquecer com valores atuais dos campos sugeridos
    fields_to_update = parsed.get("fields_to_update") or None
    fields_current_values: Optional[Dict[str, Any]] = None
    if fields_to_update and isinstance(fields_to_update, dict):
        profile_dict = dict(ai_profile) if not isinstance(ai_profile, dict) else ai_profile
        fields_current_values = {k: profile_dict.get(k) for k in fields_to_update}

    return FeedbackAssistResponse(
        action=parsed.get("action", "explain_only"),
        fields_to_update=fields_to_update,
        fields_current_values=fields_current_values,
        explanation=parsed.get("explanation", ""),
        analysis=parsed.get("analysis", ""),
        is_config_fixable=bool(parsed.get("is_config_fixable", False)),
        attempt_number=body.attempt_number,
    )


# ---------------------------------------------------------------------------
# Training — classificação de respostas do bot para aprendizado contínuo
# ---------------------------------------------------------------------------

class PlaygroundTrainingRequest(BaseModel):
    ai_profile_id: int
    lead_id: Optional[int] = None
    agent_mode: Optional[str] = None
    phase: Optional[str] = None       # qualification | apresentation | followup
    mother_route: Optional[str] = None
    lead_message: Optional[str] = None
    bot_message: str
    rating: Literal["ruim", "regular", "boa", "excelente"]
    comment: Optional[str] = None


class PlaygroundTrainingResponse(BaseModel):
    id: int


class TrainingExportItem(BaseModel):
    agent_mode: Optional[str] = None
    phase: Optional[str] = None
    mother_route: Optional[str] = None
    lead_message: Optional[str] = None
    bot_message: str
    rating: Literal["ruim", "regular", "boa", "excelente"]
    comment: Optional[str] = None


class TrainingImportRequest(BaseModel):
    items: List[TrainingExportItem]


@router.get("/training/export")
def playground_export_training(
    current_user: CurrentUser = Depends(require_crm_access),
) -> dict:
    """
    Exporta todos os itens de treinamento do usuário (sem dados sensíveis).
    Usado para gerar o contrato JSON de exportação do agente.
    """
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT agent_mode, phase, mother_route, lead_message,
                   bot_message, rating, comment
            FROM playground_training_items
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (str(current_user.id),),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return {"items": rows}


@router.post("/training/import")
def playground_import_training(
    body: TrainingImportRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> dict:
    """
    Importa itens de treinamento para o usuário atual.
    Substitui (DELETE + INSERT) todos os itens existentes do usuário.
    """
    profile = fetch_core_ai_profile(current_user.token or "")
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Configure seu perfil de IA antes de importar treinamento",
        )
    ai_profile_id = profile["id"]
    user_id = str(current_user.id)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM playground_training_items WHERE user_id = ?",
            (user_id,),
        )
        deleted = cur.rowcount
        for item in body.items:
            cur.execute(
                """
                INSERT INTO playground_training_items
                    (user_id, ai_profile_id, agent_mode, phase, mother_route,
                     lead_message, bot_message, rating, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    ai_profile_id,
                    item.agent_mode,
                    item.phase,
                    item.mother_route,
                    item.lead_message,
                    item.bot_message,
                    item.rating,
                    item.comment,
                ),
            )
        conn.commit()

    logger.info(
        "training_import user_id=%s profile=%s imported=%s deleted=%s",
        user_id, ai_profile_id, len(body.items), deleted,
    )
    return {"imported": len(body.items), "deleted": deleted}


@router.post("/training", response_model=PlaygroundTrainingResponse)
def playground_save_training(
    body: PlaygroundTrainingRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> PlaygroundTrainingResponse:
    """
    Persiste a classificação de uma resposta do bot como dado de treino.

    Esses dados são carregados pelo orquestrador e injetados no prompt
    como exemplos few-shot por fase/agent_mode, especializando o bot
    sem necessidade de alterar configurações manuais.
    """
    user_id = current_user.id

    # Valida propriedade do perfil
    fetch_core_ai_profile_by_id(body.ai_profile_id, user_id)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO playground_training_items
                (user_id, ai_profile_id, agent_mode, phase, mother_route,
                 lead_message, bot_message, rating, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(user_id),
                body.ai_profile_id,
                body.agent_mode,
                body.phase,
                body.mother_route,
                body.lead_message,
                body.bot_message,
                body.rating,
                body.comment,
            ),
        )
        conn.commit()
        item_id = cur.lastrowid

    logger.info(
        "training_saved user_id=%s profile=%s rating=%s phase=%s",
        user_id, body.ai_profile_id, body.rating, body.phase,
    )
    return PlaygroundTrainingResponse(id=item_id)
