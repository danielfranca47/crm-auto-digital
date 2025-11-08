"""Rotas para comunicação com agentes locais de automação."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from services import jobs_service
from services.jobs_service import AgentAuthError, COMPLETED, FAILED

router = APIRouter(prefix="/api/agents", tags=["Agentes"])


class AgentRegisterPayload(BaseModel):
    agent_id: str = Field(..., description="Identificador único definido pelo instalador do agente")
    name: str = Field(..., description="Nome amigável do agente (PC do usuário, por exemplo)")
    token: str = Field(..., description="Token compartilhado entre backend e agente")


class JobReportPayload(BaseModel):
    job_id: int
    status: str = Field(..., pattern="^(completed|failed)$")
    result: Optional[dict] = None
    error: Optional[str] = None


class TestJobPayload(BaseModel):
    type: str = Field("whatsapp_send", description="Tipo de job a ser criado")
    payload: dict = Field(default_factory=dict)
    priority: int = 0


class AgentAuth:
    def __init__(self, agent: dict):
        self.agent = agent


async def _agent_credentials(
    agent_id: str = Header(..., alias="X-Agent-Id"),
    token: str = Header(..., alias="X-Agent-Token"),
) -> AgentAuth:
    try:
        agent = jobs_service.authenticate_agent(agent_id, token)
    except AgentAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return AgentAuth(agent)


@router.post("/register")
def register_agent(payload: AgentRegisterPayload):
    """Registra ou atualiza um agente local."""
    data = jobs_service.register_agent(payload.agent_id, payload.name, payload.token)
    return {"ok": True, "agent": data}


@router.get("/next-job")
def get_next_job(
    types: Optional[List[str]] = Query(default=None, description="Lista de tipos aceitos"),
    auth: AgentAuth = Depends(_agent_credentials),
):
    job = jobs_service.assign_next_job(auth.agent["id"], accepted_types=types)
    return {"job": job}


@router.post("/report")
def report_job(payload: JobReportPayload, auth: AgentAuth = Depends(_agent_credentials)):
    status_value = COMPLETED if payload.status == "completed" else FAILED
    job = jobs_service.report_job_result(
        auth.agent["id"],
        payload.job_id,
        status=status_value,
        result=payload.result,
        error=payload.error,
    )
    return {"ok": True, "job": job}


@router.get("/overview")
def overview(hours: int = Query(24, ge=1, le=168)):
    return jobs_service.overview(hours=hours)


@router.post("/test-job")
def create_test_job(payload: TestJobPayload):
    job_id = jobs_service.enqueue_job(payload.type, payload.payload, priority=payload.priority)
    return {"ok": True, "job_id": job_id}
