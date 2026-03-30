"""
playground_internal.py — Endpoint interno para execução síncrona do decision engine.
Usado exclusivamente pelo backend-crm/routes/playground.py.

POST /api/internal/playground/decide
  Auth: X-Service-Token (CRM_SERVICE_TOKEN ou CORE_SERVICE_TOKEN)
  Body: { "context_bundle": {...} }
  Response: DecisionOutput (JSON)

Não enfileira jobs, não acede ao WhatsApp, não consome quota de conversas.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.schemas.decision import DecisionOutput
from app.services import decision_engine

router = APIRouter(prefix="/api/internal/playground", tags=["playground-internal"])


def _require_service_token(
    x_service_token: str = Header(None, alias="X-Service-Token"),
) -> str:
    expected = os.getenv("CRM_SERVICE_TOKEN") or os.getenv("CORE_SERVICE_TOKEN")
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=401, detail="Invalid service token")
    return x_service_token


class PlaygroundDecideRequest(BaseModel):
    context_bundle: Dict[str, Any]


@router.post("/decide", response_model=DecisionOutput)
def playground_decide(
    body: PlaygroundDecideRequest,
    _: str = Depends(_require_service_token),
) -> DecisionOutput:
    """
    Executa o decision engine de forma síncrona para o playground.
    Recebe um context_bundle completo e devolve DecisionOutput.
    Não enfileira jobs — chamada directa ao engine.
    """
    result = decision_engine.decide(body.context_bundle)
    return result
