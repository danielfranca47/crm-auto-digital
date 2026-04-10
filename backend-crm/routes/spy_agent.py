"""
spy_agent.py — Endpoints do Agente Espião.

Fluxo:
  POST /api/spy-agent/start               → inicia período de observação
  GET  /api/spy-agent/session             → retorna sessão ativa + countdown
  GET  /api/spy-agent/conversation-sample → preview de dados disponíveis
  POST /api/spy-agent/apply               → aplica sugestões aceitas no AI Profile
  GET  /api/spy-agent/runs                → histórico de execuções
  GET  /api/spy-agent/instance-config     → retorna instância espiã configurada
  POST /api/spy-agent/instance-config     → define instância espiã
  DELETE /api/spy-agent/instance-config   → remove instância espiã
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core_client import fetch_core_whatsapp_connection_resolve
from database import get_connection
from security_core import CurrentUser, require_crm_access
from services.spy_agent.conversation_loader import get_conversation_sample_stats
from services.spy_agent.core_patch_client import patch_ai_profile_via_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spy-agent", tags=["SpyAgent"])

# ---------------------------------------------------------------------------
# Modelos de entrada/saída
# ---------------------------------------------------------------------------


class SpyAgentStartRequest(BaseModel):
    modules: List[str] = Field(default=["facts", "identity", "strategy"])
    observation_days: int = Field(default=14, ge=0)  # 0 = 24h (1 dia)
    use_optimized_strategy: bool = True
    spy_instance_id: Optional[str] = None  # se fornecido, salva como instância espiã


class SpyAgentInstanceConfigRequest(BaseModel):
    spy_instance_id: str


class SpyAgentApplySuggestion(BaseModel):
    module: str
    field: str
    value: Any


class SpyAgentApplyRequest(BaseModel):
    run_id: int
    accepted_suggestions: List[SpyAgentApplySuggestion]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_MODULES = {"facts", "identity", "strategy", "sales_pipeline"}

# Campos do AI Profile que podem ser atualizados pelo spy agent
_ALLOWED_FIELDS = {
    "niche", "offer_description", "target_audience", "warming_social_proof", "brand_name",
    "tone_of_voice", "response_style", "identity_mode", "template_key",
    "agent_mode", "presentation_variant", "qualification_required_fields", "handoff_policy",
}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _compute_end_at(observation_days: int) -> str:
    """Calcula observation_end_at. Se observation_days=0, usa 24h."""
    days = observation_days if observation_days > 0 else 1
    end = datetime.now(timezone.utc) + timedelta(days=days)
    return end.replace(microsecond=0).isoformat()


def _get_active_run(user_id: int, conn) -> Optional[Dict[str, Any]]:
    """Retorna a run mais recente do usuário que ainda não está aplicada."""
    row = conn.execute(
        """
        SELECT * FROM spy_agent_runs
         WHERE user_id = ?
         ORDER BY observation_start_at DESC
         LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def _build_session_response(run: Dict[str, Any], reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Monta o objeto de sessão para resposta da API."""
    now = datetime.now(timezone.utc)

    end_at_str = run.get("observation_end_at") or ""
    try:
        end_at = datetime.fromisoformat(end_at_str.replace("Z", "+00:00"))
        if end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        end_at = now

    start_at_str = run.get("observation_start_at") or ""
    try:
        start_at = datetime.fromisoformat(start_at_str.replace("Z", "+00:00"))
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        start_at = now

    days_total = run.get("observation_days") or 14
    days_elapsed = max(0, (now - start_at).days)
    days_remaining = max(0, (end_at - now).days)
    progress_pct = min(100, int(days_elapsed / max(days_total, 1) * 100))

    module_results = None
    compat_report = None

    if run.get("status") in ("completed", "analyzing"):
        module_results = []
        for r in reports:
            if r["module"] == "compatibility":
                try:
                    compat_report = json.loads(r["compatibility_json"] or "{}")
                except Exception:
                    pass
                continue
            try:
                suggestions = json.loads(r["suggestions_json"] or "[]")
            except Exception:
                suggestions = []
            module_results.append({
                "module": r["module"],
                "suggestions": suggestions,
                "confidence": 0.7,
                "analysis": "",
                "applied": bool(r.get("applied")),
            })

    return {
        "run_id": run["id"],
        "status": run["status"],
        "modules_requested": json.loads(run.get("modules_requested") or '[]'),
        "use_optimized_strategy": bool(run.get("use_optimized_strategy", 1)),
        "observation_start_at": start_at_str,
        "observation_end_at": end_at_str,
        "days_remaining": days_remaining,
        "days_elapsed": days_elapsed,
        "days_total": days_total,
        "progress_pct": progress_pct,
        "leads_collected_so_far": run.get("leads_sampled") or 0,
        "messages_collected_so_far": run.get("messages_sampled") or 0,
        "module_results": module_results,
        "compatibility_report": compat_report,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/session")
async def get_spy_agent_session(
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Retorna a sessão ativa do Agente Espião com countdown e resultados (se houver)."""
    conn = get_connection()
    try:
        run = _get_active_run(current_user.id, conn)
        if not run:
            return {"status": "not_started"}

        reports = conn.execute(
            "SELECT * FROM spy_agent_reports WHERE run_id = ? ORDER BY created_at",
            (run["id"],),
        ).fetchall()

        return _build_session_response(run, [dict(r) for r in reports])
    finally:
        conn.close()


@router.get("/conversation-sample")
async def get_conversation_sample(
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Preview das conversas disponíveis para análise, sem rodar LLM."""
    stats = get_conversation_sample_stats(current_user.id)
    # Detecta mídia no sample (leve — apenas conta)
    from services.spy_agent.conversation_loader import load_real_conversations, detect_media_types
    convs = load_real_conversations(current_user.id, limit_leads=5, limit_msgs_per_lead=10)
    media_counts = detect_media_types(convs)
    stats["media_counts"] = media_counts
    return stats


@router.post("/start")
async def start_spy_agent(
    body: SpyAgentStartRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Inicia o período de observação do Agente Espião."""
    modules = [m for m in body.modules if m in _VALID_MODULES]
    if not modules:
        raise HTTPException(status_code=400, detail="Selecione pelo menos um módulo válido")

    conn = get_connection()
    try:
        # Cancela run anterior em observação se existir
        conn.execute(
            """
            UPDATE spy_agent_runs SET status = 'failed', error = 'Substituída por nova sessão'
             WHERE user_id = ? AND status = 'observing'
            """,
            (current_user.id,),
        )

        end_at = _compute_end_at(body.observation_days)
        cur = conn.execute(
            """
            INSERT INTO spy_agent_runs
                (user_id, status, modules_requested, use_optimized_strategy,
                 observation_days, observation_start_at, observation_end_at)
            VALUES (?, 'observing', ?, ?, ?, ?, ?)
            """,
            (
                current_user.id,
                json.dumps(modules),
                1 if body.use_optimized_strategy else 0,
                body.observation_days if body.observation_days > 0 else 1,
                _now_utc_iso(),
                end_at,
            ),
        )
        conn.commit()
        run_id = cur.lastrowid

        # Salva instância espiã se fornecida
        if body.spy_instance_id:
            now = _now_utc_iso()
            conn.execute(
                """
                INSERT INTO spy_agent_config (user_id, spy_instance_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    spy_instance_id = excluded.spy_instance_id,
                    updated_at = excluded.updated_at
                """,
                (current_user.id, body.spy_instance_id, now, now),
            )
            conn.commit()

        run = dict(conn.execute("SELECT * FROM spy_agent_runs WHERE id = ?", (run_id,)).fetchone())
        return _build_session_response(run, [])
    finally:
        conn.close()


@router.post("/apply")
async def apply_spy_agent_suggestions(
    body: SpyAgentApplyRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Aplica as sugestões aceitas pelo usuário no AI Profile."""
    conn = get_connection()
    try:
        run = conn.execute(
            "SELECT * FROM spy_agent_runs WHERE id = ? AND user_id = ?",
            (body.run_id, current_user.id),
        ).fetchone()

        if not run:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")

        if dict(run)["status"] != "completed":
            raise HTTPException(status_code=400, detail="A análise ainda não foi concluída")

        # Filtra e valida campos
        patch_payload: Dict[str, Any] = {}
        for suggestion in body.accepted_suggestions:
            field = suggestion.field
            if field not in _ALLOWED_FIELDS:
                logger.warning("[spy_agent:apply] campo não permitido ignorado: %s", field)
                continue
            patch_payload[field] = suggestion.value

        if not patch_payload:
            return {"ok": True, "fields_updated": []}

        # Aplica no AI Profile via service token
        try:
            patch_ai_profile_via_service(current_user.id, patch_payload)
        except Exception as exc:
            logger.error("[spy_agent:apply] falha ao aplicar patch: %s", exc)
            raise HTTPException(status_code=502, detail=f"Falha ao atualizar AI Profile: {exc}")

        # Marca reports como aplicados
        now = _now_utc_iso()
        applied_modules = list({s.module for s in body.accepted_suggestions})
        for module in applied_modules:
            conn.execute(
                """
                UPDATE spy_agent_reports
                   SET applied = 1, applied_at = ?
                 WHERE run_id = ? AND module = ?
                """,
                (now, body.run_id, module),
            )
        conn.commit()

        return {"ok": True, "fields_updated": list(patch_payload.keys())}
    finally:
        conn.close()


@router.get("/runs")
async def list_spy_agent_runs(
    current_user: CurrentUser = Depends(require_crm_access),
) -> List[Dict[str, Any]]:
    """Lista o histórico de execuções do Agente Espião do usuário."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id as run_id, status, modules_requested,
                   observation_start_at, observation_end_at, completed_at,
                   observation_days, leads_sampled, messages_sampled
              FROM spy_agent_runs
             WHERE user_id = ?
             ORDER BY observation_start_at DESC
             LIMIT 20
            """,
            (current_user.id,),
        ).fetchall()
        return [
            {
                **dict(r),
                "modules_requested": json.loads(r["modules_requested"] or "[]"),
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Configuração da instância espiã
# ---------------------------------------------------------------------------


@router.get("/instance-config")
async def get_instance_config(
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Retorna a instância WhatsApp configurada para observação espiã."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT spy_instance_id, created_at, updated_at FROM spy_agent_config WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {"configured": False, "spy_instance_id": None}

    spy_instance_id = row["spy_instance_id"]

    # Enriquece com dados do core (phone_e164, status)
    phone_e164 = None
    connection_status = None
    try:
        conn_info = fetch_core_whatsapp_connection_resolve(spy_instance_id)
        phone_e164 = conn_info.get("phone_e164")
        connection_status = conn_info.get("connection_status")
    except Exception:
        pass

    return {
        "configured": True,
        "spy_instance_id": spy_instance_id,
        "phone_e164": phone_e164,
        "connection_status": connection_status,
        "updated_at": row["updated_at"],
    }


@router.post("/instance-config")
async def set_instance_config(
    body: SpyAgentInstanceConfigRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Define (ou atualiza) a instância WhatsApp a ser observada pelo Agente Espião."""
    now = _now_utc_iso()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO spy_agent_config (user_id, spy_instance_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                spy_instance_id = excluded.spy_instance_id,
                updated_at = excluded.updated_at
            """,
            (current_user.id, body.spy_instance_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "spy_instance_id": body.spy_instance_id}


@router.delete("/instance-config")
async def delete_instance_config(
    current_user: CurrentUser = Depends(require_crm_access),
) -> Dict[str, Any]:
    """Remove a instância espiã configurada."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM spy_agent_config WHERE user_id = ?",
            (current_user.id,),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True}
