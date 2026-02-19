from datetime import datetime
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from .auth import get_current_user

router = APIRouter(prefix="", tags=["ai_profiles"])


class IdentityMode(str, Enum):
    virtual_assistant = "virtual_assistant"
    human_agent = "human_agent"
    user_clone = "user_clone"


class HandoffPolicy(str, Enum):
    disable_bot = "disable_bot"
    keep_active_notify = "keep_active_notify"
    ignore = "ignore"


class AgentMode(str, Enum):
    sdr_scheduler = "sdr_scheduler"
    closer = "closer"
    consultivo = "consultivo"
    agenda = "agenda"
    direto = "direto"


AI_TEMPLATES = [
    {
        "key": "sdr_padrao",
        "name": "SDR Padrão",
        "description": "Agente de vendas geral, tom profissional e amigável, foca em qualificação e agendamento de reunião.",
    },
    {
        "key": "consultor_especialista",
        "name": "Consultor Especialista",
        "description": "Tom consultivo, ideal para processos de venda mais longos, diagnóstico e educação.",
    },
    {
        "key": "closer_agressivo",
        "name": "Closer Agressivo Controlado",
        "description": "Mais direto e orientado a fechamento, ainda respeitando limites profissionais.",
    },
]


class AIProfileBase(BaseModel):
    template_key: str
    name: str
    brand_name: str
    tone_of_voice: str
    timezone: Optional[str] = "UTC"
    niche: str
    target_audience: str
    offer_description: str
    goals: str
    custom_instructions: Optional[str] = None
    agent_mode: AgentMode = AgentMode.sdr_scheduler
    identity_mode: IdentityMode = IdentityMode.human_agent
    handoff_policy: HandoffPolicy = HandoffPolicy.keep_active_notify
    handoff_custom_text: Optional[str] = None
    requires_handoff: bool = False
    human_in_loop: bool = False


class AIProfileCreate(AIProfileBase):
    pass


class AIProfileUpdate(BaseModel):
    template_key: Optional[str] = None
    name: Optional[str] = None
    brand_name: Optional[str] = None
    tone_of_voice: Optional[str] = None
    timezone: Optional[str] = None
    niche: Optional[str] = None
    target_audience: Optional[str] = None
    offer_description: Optional[str] = None
    goals: Optional[str] = None
    custom_instructions: Optional[str] = None
    agent_mode: Optional[AgentMode] = None
    identity_mode: Optional[IdentityMode] = None
    handoff_policy: Optional[HandoffPolicy] = None
    handoff_custom_text: Optional[str] = None
    requires_handoff: Optional[bool] = None
    human_in_loop: Optional[bool] = None


class AIProfileOut(AIProfileBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class AITemplate(BaseModel):
    key: str
    name: str
    description: str


def _validate_template_key(template_key: Optional[str]) -> None:
    if template_key is None:
        return
    allowed_keys = {tpl["key"] for tpl in AI_TEMPLATES}
    if template_key not in allowed_keys:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template_key")


async def _require_service_token(x_service_token: str = Header(None)) -> str:
    expected = settings.CORE_SERVICE_TOKEN
    if not expected or x_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    return x_service_token


def _upsert_ai_profile(
    *,
    db: Session,
    user_id: int,
    data: dict,
    require_all_fields_for_create: bool = True,
) -> models.AIProfile:
    if data.get("agent_mode") is None:
        template_key = str(data.get("template_key") or "")
        if template_key.startswith("closer"):
            data["agent_mode"] = AgentMode.direto
        elif template_key.startswith("consult"):
            data["agent_mode"] = AgentMode.consultivo
        else:
            data["agent_mode"] = AgentMode.agenda
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == user_id).first()

    if profile:
        for key, value in data.items():
            if value is not None:
                setattr(profile, key, value)
        profile.updated_at = datetime.utcnow()
    else:
        required_fields = {
            "template_key",
            "name",
            "brand_name",
            "tone_of_voice",
            "niche",
            "target_audience",
            "offer_description",
            "goals",
        }
        if require_all_fields_for_create:
            missing = [field for field in required_fields if data.get(field) is None]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing fields for new AI profile: {', '.join(missing)}",
                )
        profile = models.AIProfile(user_id=user_id, **data)
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/ai-templates", response_model=List[AITemplate])
async def list_ai_templates():
    return AI_TEMPLATES


@router.get("/ai-profiles/me", response_model=AIProfileOut)
async def get_my_ai_profile(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    return profile


@router.post("/ai-profiles", response_model=AIProfileOut, status_code=status.HTTP_201_CREATED)
async def create_or_replace_ai_profile(
    payload: AIProfileCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_template_key(payload.template_key)
    profile = _upsert_ai_profile(db=db, user_id=current_user.id, data=payload.dict())
    return profile


@router.put("/ai-profiles/me", response_model=AIProfileOut)
async def update_my_ai_profile(
    payload: AIProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = payload.dict(exclude_unset=True)
    if "template_key" in update_data:
        _validate_template_key(update_data.get("template_key"))

    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == current_user.id).first()

    if not profile and not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data provided to create or update AI profile",
        )

    profile = _upsert_ai_profile(
        db=db,
        user_id=current_user.id,
        data=update_data,
        require_all_fields_for_create=True,
    )
    return profile


@router.get("/ai-profiles/resolve", response_model=AIProfileOut)
async def resolve_ai_profile(
    user_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    return profile
