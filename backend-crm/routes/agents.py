from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services import jobs_service
from security_core import CurrentUser, get_current_user

router = APIRouter(prefix="/api/agents", tags=["Agents"])


class ReportJobRequest(BaseModel):
    agent_id: str
    token: str
    job_id: int
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class RegisterAgentRequest(BaseModel):
    agent_id: str = Field(..., description="Identificador único do agente local")
    token: str = Field(..., description="Token simples de autenticação")
    name: Optional[str] = Field(None, description="Nome amigável do agente")
    capabilities: Optional[List[str]] = Field(None, description="Lista de tipos de job suportados")
    version: Optional[str] = Field(None, description="Versão do agente")


class RegisterAgentResponse(BaseModel):
    ok: bool = True
    agent: dict


class ProvisionAgentRequest(BaseModel):
    name: Optional[str] = Field(None, description="Nome amigável do agente")


class ProvisionAgentResponse(BaseModel):
    agent_id: str
    agent_token: str
    name: Optional[str]
    user_id: int
    status: str


class ManualWhatsappJobRequest(BaseModel):
    phone: str = Field(..., description="Número completo com DDI, apenas dígitos")
    message: str = Field(..., description="Mensagem a ser enviada")
    lead_id: Optional[int] = Field(None, description="Lead relacionado (opcional)")
    message_id: Optional[int] = Field(None, description="Mensagem salva relacionada (opcional)")


@router.post("/provision", response_model=ProvisionAgentResponse)
def provision_agent(payload: ProvisionAgentRequest, current_user: CurrentUser = Depends(get_current_user)):
    return jobs_service.provision_agent(user_id=current_user.id, name=payload.name)


@router.post("/register", response_model=RegisterAgentResponse)
def register_agent(payload: RegisterAgentRequest):
    agent = jobs_service.register_agent(
        agent_id=payload.agent_id,
        token=payload.token,
        name=payload.name,
        capabilities=payload.capabilities,
        version=payload.version,
    )
    return {"ok": True, "agent": agent}


@router.get("/next-job")
def next_job(
    agent_id: str = Query(..., description="ID do agente"),
    token: str = Query(..., description="Token do agente"),
    types: Optional[str] = Query(None, description="Lista separada por vírgula de tipos aceitos"),
):
    accepted_types = [t.strip() for t in types.split(",") if t.strip()] if types else None
    job = jobs_service.fetch_next_job(
        agent_id=agent_id,
        token=token,
        accepted_types=accepted_types,
    )
    return {"job": job}


@router.post("/report")
def report_job(payload: ReportJobRequest):
    return jobs_service.report_job(
        agent_id=payload.agent_id,
        token=payload.token,
        job_id=payload.job_id,
        status=payload.status,
        result=payload.result,
        error=payload.error,
    )


@router.get("/overview")
def overview(seconds: int = Query(120, ge=10, le=600, description="Janela para considerar agente online"), current_user: CurrentUser = Depends(get_current_user)):
    return jobs_service.get_jobs_overview(seconds=seconds, user_id=current_user.id)


@router.get("/jobs/summary")
def job_summary(current_user: CurrentUser = Depends(get_current_user)):
    return jobs_service.get_whatsapp_summary(user_id=current_user.id)


@router.post("/jobs/manual-whatsapp")
def manual_whatsapp_job(payload: ManualWhatsappJobRequest, current_user: CurrentUser = Depends(get_current_user)):
    if not payload.phone or not payload.message:
        raise HTTPException(status_code=400, detail="phone e message são obrigatórios")

    job = jobs_service.create_job(
        job_type="whatsapp_send",
        payload={
            "lead_id": payload.lead_id,
            "message_id": payload.message_id,
            "phone": payload.phone,
            "body": payload.message,
            "source": "manual",
        },
        user_id=current_user.id,
    )
    return {"ok": True, "job": job}
