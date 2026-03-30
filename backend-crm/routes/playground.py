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
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core_client import fetch_core_ai_profile_by_id
from database import get_connection
from security_core import CurrentUser, require_crm_access
from services.ai_orchestrator.orchestrator import build_context_bundle_for_playground
from services.qualification_state import get_qualification_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playground", tags=["Playground"])

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
    message: str = Field(..., min_length=1, description="Mensagem simulada do lead")
    lead_id: Optional[int] = Field(None, description="ID do lead sandbox existente; null cria um novo")
    reset: bool = Field(False, description="Se true, limpa histórico e qualification_state antes de processar")


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
    ai_profile_id: int
    lead_id: int
    lead_is_sandbox: bool = True
    timestamp: str


class PlaygroundChatResponse(BaseModel):
    lead_id: int
    message_to_send: str
    next_action: str

    mother_decision: Optional[MotherDecision] = None
    child_result: Optional[ChildResult] = None
    lead_state: LeadState
    decision_trace: DecisionTrace


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


def _create_sandbox_lead(user_id: int) -> int:
    """Cria um novo lead sandbox e devolve o seu ID."""
    phone = f"playground_{uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO leads (user_id, companyName, contactName, phone, origin, category, is_playground)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (user_id, "Playground Test", "Lead de Teste", phone, "playground", "qualification"),
        )
        conn.commit()
        return cur.lastrowid


def _reset_sandbox_lead(lead_id: int, user_id: int) -> None:
    """Limpa histórico e qualification_state do lead sandbox."""
    with get_connection() as conn:
        cur = conn.cursor()
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
        "ai_profile_id": ai_profile_id,
        "lead_id": lead_id,
        "lead_is_sandbox": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------

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

    # ── Passo 4: Fetch AI Profile (valida propriedade) ──────────────────────
    ai_profile = fetch_core_ai_profile_by_id(body.ai_profile_id, user_id)

    # ── Passo 2: Gestão do Lead Sandbox ─────────────────────────────────────
    if body.lead_id is not None:
        _load_sandbox_lead(body.lead_id, user_id)  # 404 se não encontrado
        lead_id = body.lead_id
    else:
        lead_id = _create_sandbox_lead(user_id)

    # ── Passo 3: Reset (se solicitado) ───────────────────────────────────────
    if body.reset:
        _reset_sandbox_lead(lead_id, user_id)

    # ── Passo 3b: Guarda mensagem inbound ────────────────────────────────────
    _insert_message(lead_id, body.message, "inbound")

    # ── Passo 5: Build Context Bundle ────────────────────────────────────────
    bundle = build_context_bundle_for_playground(
        user_id=user_id,
        ai_profile=ai_profile,
        lead_id=lead_id,
        message_text=body.message,
    )

    # Serializa para dict (compatível com decision_engine.decide(context: Dict))
    bundle_dict = bundle.model_dump(mode="json")

    # ── Passo 6: Chamar Decision Engine via executors ────────────────────────
    decision = _call_executors_decide(bundle_dict)

    # ── Passo 7: Persistir estado pós-decisão ────────────────────────────────
    suggested_category = decision.get("suggested_category")
    if suggested_category:
        _update_lead_category(lead_id, user_id, suggested_category)

    message_to_send = decision.get("message_text") or ""

    # ── Passo 8: Guarda mensagem outbound ────────────────────────────────────
    if message_to_send:
        _insert_message(lead_id, message_to_send, "outbound")

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

    return PlaygroundChatResponse(
        lead_id=lead_id,
        message_to_send=message_to_send,
        next_action=decision.get("next_action", "reply"),
        mother_decision=_build_mother_decision(decision),
        child_result=_build_child_result(decision),
        lead_state=lead_state,
        decision_trace=_build_decision_trace(decision, body.ai_profile_id, lead_id),
    )
