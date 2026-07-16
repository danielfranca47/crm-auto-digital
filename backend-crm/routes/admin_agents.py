"""
Admin endpoints — Agentes e AI Profiles.

Fase 4a do painel admin SaaS. Todos os endpoints requerem JWT admin emitido pelo backend-core
(validado por require_crm_admin, que chama /admin/stats no core).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from core_client import (
    fetch_core_admin_ai_profile_user,
    fetch_core_admin_ai_profiles,
    fetch_core_admin_users,
    require_crm_admin,
)
from services.ai_playbooks import PLAYBOOKS

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])

# ---------------------------------------------------------------------------
# Metadados dos playbooks (nomes, descrições, modo canônico)
# ---------------------------------------------------------------------------

_PLAYBOOK_META: Dict[str, Dict[str, str]] = {
    "sdr_padrao": {
        "name": "SDR Padrão",
        "description": "Qualificação e conversão balanceada — ideal para equipes com leads variados.",
        "canonical_agent_mode": "agenda",
    },
    "consultor_especialista": {
        "name": "Consultor Especialista",
        "description": "Atendimento consultivo aprofundado para vendas complexas e tickets altos.",
        "canonical_agent_mode": "consultivo",
    },
    "closer_agressivo": {
        "name": "Closer Direto",
        "description": "Foco em fechamento rápido e direto — baixa tolerância a hesitação.",
        "canonical_agent_mode": "direto",
    },
    "closer_agressivo_cart_recovery": {
        "name": "Closer — Recuperação de Carrinho",
        "description": "Recuperação de pagamento pendente após link enviado. 3 mensagens escalonadas.",
        "canonical_agent_mode": "direto",
    },
    "hybrid_scheduler": {
        "name": "Hybrid Scheduler",
        "description": "Para coaches, terapeutas e consultores solo — foco em agendamento com tom pessoal.",
        "canonical_agent_mode": "agenda",
    },
    "hybrid_scheduler_followup": {
        "name": "Hybrid Scheduler — Follow-up",
        "description": "Ramificações de acompanhamento para o Hybrid Scheduler (pós-apresentação).",
        "canonical_agent_mode": "agenda",
    },
}

# ---------------------------------------------------------------------------
# Estágios canônicos do sistema
# ---------------------------------------------------------------------------

_CANONICAL_STAGES: List[Dict[str, str]] = [
    {
        "key": "qualification",
        "label": "Qualificação",
        "description": "Coleta as informações essenciais do lead antes de avançar para a oferta.",
    },
    {
        "key": "apresentation",
        "label": "Apresentação",
        "description": "Apresenta a solução com base nos dados coletados na qualificação.",
    },
    {
        "key": "followup",
        "label": "Follow-up",
        "description": "Retoma contato após a apresentação para superar objeções e avançar.",
    },
    {
        "key": "closing",
        "label": "Fechamento",
        "description": "Conduz o lead ao fechamento com CTA direto.",
    },
]

# ---------------------------------------------------------------------------
# Valores padrão por agent_mode (para cálculo de diff no endpoint de detalhe)
# ---------------------------------------------------------------------------

_AGENT_MODE_QUAL_DEFAULTS: Dict[str, List[str]] = {
    "sdr_scheduler": ["service_interest", "availability_window"],
    "agenda": ["service_interest", "availability_window"],
    "consultivo": ["service_interest", "urgency", "decision_role"],
    "closer": ["service_interest", "price_acceptance"],
    "direto": ["service_interest", "price_acceptance"],
}

_SYSTEM_DEFAULTS: Dict[str, Any] = {
    "presentation_variant": None,
    "hybrid_flow_style": None,
    "offer_pack": None,
    "qualification_score_threshold": 6,
    "followup_max_attempts": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_stage_for_playbook(stage: Dict[str, str], playbook: Dict[str, Any]) -> Dict[str, Any]:
    """Enriquece um estágio canônico com dados específicos do playbook."""
    stage_key = stage["key"]
    extra: Dict[str, Any] = {}

    if stage_key == "qualification":
        extra["sample_questions"] = playbook.get("qualification_questions", [])
        extra["tone_rule"] = playbook.get("tone_rule")
    elif stage_key == "followup":
        extra["followup_attempts"] = playbook.get("followup_attempts")
        extra["followup_outcomes"] = playbook.get("followup_outcomes")
    elif stage_key == "apresentation":
        extra["warming"] = playbook.get("warming")

    return {**stage, **{k: v for k, v in extra.items() if v is not None}}


def _diff_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Compara o AI profile de um usuário com os valores padrão e retorna os campos que diferem."""
    agent_mode = str(profile.get("agent_mode") or "agenda")
    default_qual_fields = _AGENT_MODE_QUAL_DEFAULTS.get(agent_mode, [])

    diff: Dict[str, Any] = {}

    # Campos fixos a comparar
    for field, default_val in _SYSTEM_DEFAULTS.items():
        user_val = profile.get(field)
        if user_val != default_val:
            diff[field] = {"default": default_val, "user": user_val}

    # qualification_required_fields — compara contra default do modo
    user_qual = profile.get("qualification_required_fields") or []
    if sorted(user_qual) != sorted(default_qual_fields):
        diff["qualification_required_fields"] = {
            "default": default_qual_fields,
            "user": user_qual,
        }

    return diff


# ---------------------------------------------------------------------------
# Endpoint 1: GET /admin/agents/overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def admin_agents_overview(
    _: dict = Depends(require_crm_admin),
) -> Dict[str, Any]:
    """
    Retorna todos os agent_modes disponíveis com seus estágios e configuração ativa,
    lida diretamente do estado real do sistema (não hardcoded de documentação).
    """
    queried_at = datetime.now(timezone.utc).isoformat()
    agent_modes = []

    for key, playbook in PLAYBOOKS.items():
        meta = _PLAYBOOK_META.get(key, {})
        stages = [_build_stage_for_playbook(s, playbook) for s in _CANONICAL_STAGES]

        agent_modes.append({
            "key": key,
            "name": meta.get("name", key),
            "description": meta.get("description", ""),
            "canonical_agent_mode": meta.get("canonical_agent_mode", "agenda"),
            "max_chars": playbook.get("max_chars"),
            "response_style": playbook.get("response_style"),
            "default_next_action": playbook.get("default_next_action"),
            "tone_rule": playbook.get("tone_rule"),
            "has_warming": "warming" in playbook,
            "has_followup_attempts": "followup_attempts" in playbook,
            "has_followup_outcomes": "followup_outcomes" in playbook,
            "stages": stages,
        })

    return {
        "queried_at": queried_at,
        "total": len(agent_modes),
        "agent_modes": agent_modes,
    }


# ---------------------------------------------------------------------------
# Endpoint 2: GET /admin/agents/users
# ---------------------------------------------------------------------------

@router.get("/users")
async def admin_agents_users(
    _: dict = Depends(require_crm_admin),
) -> Dict[str, Any]:
    """
    Retorna lista de usuários com os campos do AI profile relevantes para o painel de agentes:
    agent_mode, presentation_variant, hybrid_flow_style, offer_pack e limites de qualificação.
    Inclui email e nome do usuário para identificação rápida.
    """
    queried_at = datetime.now(timezone.utc).isoformat()

    profiles = fetch_core_admin_ai_profiles()
    users_raw = fetch_core_admin_users()

    # Índice rápido: user_id → {email, name}
    users_index: Dict[int, Dict[str, Optional[str]]] = {
        u["id"]: {"email": u.get("email"), "name": u.get("name")}
        for u in users_raw
        if isinstance(u.get("id"), int)
    }

    result = []
    for p in profiles:
        user_id = p.get("user_id")
        user_info = users_index.get(user_id, {})
        agent_mode = str(p.get("agent_mode") or "agenda")

        result.append({
            "user_id": user_id,
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "brand_name": p.get("brand_name"),
            "niche": p.get("niche"),
            "template_key": p.get("template_key"),
            "agent_mode": p.get("agent_mode"),
            "presentation_variant": p.get("presentation_variant"),
            "hybrid_flow_style": p.get("hybrid_flow_style"),
            "offer_pack": p.get("offer_pack"),
            "cold_outreach_channel": p.get("cold_outreach_channel"),
            "qualification_score_threshold": p.get("qualification_score_threshold"),
            "qualification_required_fields": p.get("qualification_required_fields"),
            "qualification_fields": p.get("qualification_fields"),
            "followup_max_attempts": p.get("followup_max_attempts"),
            "prompt_parts_version": p.get("prompt_parts_version"),
            "prompt_parts_generated_at": p.get("prompt_parts_generated_at"),
            "enabled_extensions": p.get("enabled_extensions"),
            "updated_at": p.get("updated_at"),
            # Campos derivados úteis para o painel
            "qual_fields_default": _AGENT_MODE_QUAL_DEFAULTS.get(agent_mode, []),
            "has_custom_config": bool(_diff_profile(p)),
        })

    return {
        "queried_at": queried_at,
        "total": len(result),
        "users": result,
    }


# ---------------------------------------------------------------------------
# Endpoint 3: GET /admin/agents/users/{user_id}
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}")
async def admin_agents_user_detail(
    user_id: int,
    _: dict = Depends(require_crm_admin),
) -> Dict[str, Any]:
    """
    Detalhe completo do AI profile de um usuário com diff em relação aos valores padrão
    do seu agent_mode. Campos customizados são destacados no retorno.
    """
    queried_at = datetime.now(timezone.utc).isoformat()

    profile = fetch_core_admin_ai_profile_user(user_id)
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="AI profile não encontrado para este usuário")

    agent_mode = str(profile.get("agent_mode") or "agenda")
    template_key = str(profile.get("template_key") or "sdr_padrao")
    playbook = PLAYBOOKS.get(template_key) or PLAYBOOKS.get("sdr_padrao", {})
    meta = _PLAYBOOK_META.get(template_key, {})

    diff = _diff_profile(profile)
    stages = [_build_stage_for_playbook(s, playbook) for s in _CANONICAL_STAGES]

    return {
        "queried_at": queried_at,
        "user_id": user_id,
        # Dados do AI Profile
        "profile": {
            "template_key": template_key,
            "name": profile.get("name"),
            "brand_name": profile.get("brand_name"),
            "niche": profile.get("niche"),
            "target_audience": profile.get("target_audience"),
            "agent_mode": profile.get("agent_mode"),
            "presentation_variant": profile.get("presentation_variant"),
            "hybrid_flow_style": profile.get("hybrid_flow_style"),
            "offer_pack": profile.get("offer_pack"),
            "cold_outreach_channel": profile.get("cold_outreach_channel"),
            "qualification_score_threshold": profile.get("qualification_score_threshold"),
            "qualification_required_fields": profile.get("qualification_required_fields"),
            "qualification_fields": profile.get("qualification_fields"),
            "followup_max_attempts": profile.get("followup_max_attempts"),
            "enabled_extensions": profile.get("enabled_extensions"),
            "prompt_parts_version": profile.get("prompt_parts_version"),
            "prompt_parts_generated_at": profile.get("prompt_parts_generated_at"),
            "updated_at": profile.get("updated_at"),
        },
        # Playbook ativo para o template_key deste usuário
        "playbook": {
            "key": template_key,
            "name": meta.get("name", template_key),
            "description": meta.get("description", ""),
            "canonical_agent_mode": meta.get("canonical_agent_mode", agent_mode),
            "max_chars": playbook.get("max_chars"),
            "response_style": playbook.get("response_style"),
            "tone_rule": playbook.get("tone_rule"),
            "stages": stages,
        },
        # Diff: campos que diferem dos valores padrão do agent_mode
        "diff": diff,
        "has_custom_config": bool(diff),
        "default_qual_fields_for_mode": _AGENT_MODE_QUAL_DEFAULTS.get(agent_mode, []),
    }
