"""
meta_prompter.py — Endpoint para disparar geração de prompt parts por nicho.

POST /api/meta-prompter/generate/{user_id}
  Auth: X-Service-Token (CORE_SERVICE_TOKEN)
  Body: ai_profile JSON (opcional — se omitido, usa ai_profile do contexto da request)
  Efeito: gera os blocos via LLM e salva no backend-core
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel

from app.services import meta_prompter as meta_prompter_svc

router = APIRouter(prefix="/api/meta-prompter", tags=["meta-prompter"])


def _require_service_token(x_service_token: str = Header(None, alias="X-Service-Token")) -> str:
    expected = os.getenv("CRM_SERVICE_TOKEN") or os.getenv("CORE_SERVICE_TOKEN")
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return x_service_token


class GenerateRequest(BaseModel):
    ai_profile: Dict[str, Any]


class GenerateResponse(BaseModel):
    ok: bool
    user_id: int
    has_content: bool
    parts_keys: list


@router.post("/generate/{user_id}", response_model=GenerateResponse)
def generate_prompt_parts_for_user(
    user_id: int = Path(..., description="ID do usuário no backend-core"),
    body: GenerateRequest = ...,
    _: str = _require_service_token,
) -> GenerateResponse:
    """
    Gera os blocos de prompt personalizados para o nicho do usuário e salva no backend-core.

    Triggers:
    - Onboarding wizard finalizado
    - Edição de niche / target_audience / tone_of_voice / offer_description
    - Botão "Regenerar" no frontend (via backend-crm proxy ou direto)
    """
    parts = meta_prompter_svc.generate_and_save(user_id, body.ai_profile)
    has_content = bool(parts) and any(
        parts.get(k) for k in ("few_shot_qualification", "tone_rules", "objection_rewrites")
    )
    return GenerateResponse(
        ok=True,
        user_id=user_id,
        has_content=has_content,
        parts_keys=list(parts.keys()) if parts else [],
    )
