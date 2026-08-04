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

import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.clients import crm_client
from app.core.config import settings
from app.schemas.decision import DecisionOutput
from app.services import decision_engine, meeting_scheduler

router = APIRouter(prefix="/api/internal/playground", tags=["playground-internal"])
logger = logging.getLogger(__name__)


def _require_service_token(
    x_service_token: str = Header(None, alias="X-Service-Token"),
) -> str:
    valid_tokens = {
        t for t in [
            settings.crm_service_token,
            settings.core_service_token,
            os.getenv("CRM_SERVICE_TOKEN"),
            os.getenv("CORE_SERVICE_TOKEN"),
        ] if t
    }
    if not valid_tokens or x_service_token not in valid_tokens:
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

    Quando a IA confirma um horário (decision_trace.meeting_scheduled), cria o
    appointment real tagueado "[Playground]" — mesma lógica de parsing/conflito
    do fluxo WhatsApp real, sem reminders/briefing/push Google Calendar.

    Quando a IA detecta cancelamento/reagendamento (caminho de gestão pós-confirmação,
    ver decision_engine.py::_decide_post_meeting_management), aplica a mesma ação real
    no appointment existente — mesma paridade com app/runners/whatsapp.py.
    """
    result = decision_engine.decide(body.context_bundle, logger=logger)
    events: List[dict] = []
    conflict_message = meeting_scheduler.handle_meeting_scheduled(
        body.context_bundle, result, client=crm_client, is_playground=True, events=events,
    )
    conflict_message = conflict_message or meeting_scheduler.handle_meeting_cancel_or_reschedule(
        body.context_bundle, result, client=crm_client, events=events,
    )
    actions = list(result.system_actions or [])
    if conflict_message:
        actions.append({"type": "send_message", "content": conflict_message})
    if events:
        actions.append({"type": "appointment_event", **events[-1]})
    if actions:
        result.system_actions = actions
    return result
