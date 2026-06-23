import json
import logging
import secrets as secrets_module
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app import models
from app.config import settings
from app.db import get_db
from .auth import get_current_user

router = APIRouter(prefix="", tags=["ai_profiles"])




def _normalize_offer_pack(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _normalize_sales_flow(value):
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict):
        return None
    if not isinstance(value.get("enabled"), bool):
        value["enabled"] = bool(value.get("enabled", False))
    if not isinstance(value.get("nodes"), list):
        value["nodes"] = []
    return value


def _normalize_profile_offer_pack(profile: models.AIProfile) -> models.AIProfile:
    try:
        profile.offer_pack = _normalize_offer_pack(getattr(profile, "offer_pack", None))
    except Exception:
        pass
    return profile

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


class PresentationVariant(str, Enum):
    sales = "sales"
    scheduler = "scheduler"


class HybridFlowStyle(str, Enum):
    offer_then_schedule = "offer_then_schedule"
    schedule_then_offer = "schedule_then_offer"


class ResponseStyle(str, Enum):
    active = "active"    # agente faz perguntas de qualificação
    passive = "passive"  # agente responde perguntas do cliente antes de qualificar


_TEMPLATE_OPENERS: dict = {
    "sdr_padrao": {
        "inbound": "Olá! Obrigado por entrar em contato. Me conta o que você está buscando.",
        "outbound": "Oi! Estou entrando em contato porque acredito que posso ajudar com [benefício da solução]. Tem um momento?",
    },
    "consultor_especialista": {
        "inbound": "Olá! Fico feliz com seu contato. Para te orientar melhor, me conta um pouco sobre sua situação atual.",
        "outbound": "Olá! Pesquisei sobre você e acredito que temos algo que pode ser muito valioso. Posso te falar em 2 minutos?",
    },
    "closer_agressivo": {
        "inbound": "Oi! Que bom que entrou em contato. Vamos direto ao ponto — o que você precisa?",
        "outbound": "Oi! Estou entrando em contato com uma solução específica para o seu perfil. Quando podemos conversar?",
    },
    "hybrid_scheduler": {
        "inbound": "Olá! Obrigado por entrar em contato. Me fala mais para eu entender como posso te ajudar.",
        "outbound": "Oi! Entrei em contato porque acredito que posso te ajudar. Quando tem 15 minutos para conversarmos?",
    },
}


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
    {
        "key": "hybrid_scheduler",
        "name": "Híbrido Agendador",
        "description": "Agenda com autonomia operacional (sem checkout).",
    },
]


class AIProfileBase(BaseModel):
    template_key: str
    name: str
    brand_name: str
    tone_of_voice: str
    timezone: Optional[str] = "UTC"
    language: Optional[str] = "pt-BR"
    niche: str
    target_audience: str
    offer_description: str
    goals: str
    custom_instructions: Optional[str] = None
    agent_mode: AgentMode = AgentMode.sdr_scheduler
    presentation_variant: Optional[PresentationVariant] = None
    hybrid_flow_style: Optional[HybridFlowStyle] = None
    offer_pack: Optional[dict] = None
    identity_mode: IdentityMode = IdentityMode.human_agent
    handoff_policy: HandoffPolicy = HandoffPolicy.keep_active_notify
    handoff_custom_text: Optional[str] = None
    requires_handoff: bool = False
    human_in_loop: bool = False
    followup_cadence: Optional[List[int]] = None
    followup_max_attempts: Optional[int] = None
    followup_first_offset: Optional[int] = None
    followup_allowed_hours: Optional[str] = None
    followup_auto_trigger_enabled: Optional[bool] = False
    followup_auto_trigger_inactivity_days: Optional[int] = 3
    followup_checkin_auto_trigger_enabled: Optional[bool] = False
    followup_checkin_inactivity_days: Optional[int] = 30
    origin_inbound_opener: Optional[str] = None
    origin_outbound_opener: Optional[str] = None
    followup_sdr_instructions: Optional[str] = None
    followup_recovery_instructions: Optional[str] = None
    followup_postsession_instructions: Optional[str] = None
    followup_checkin_instructions: Optional[str] = None
    followup_goal_instructions: Optional[dict] = None
    cart_recovery_attempt_instructions: Optional[List[Optional[str]]] = None
    followup_outcome_instructions: Optional[dict] = None
    objection_common: Optional[str] = None
    qualification_score_threshold: Optional[int] = None
    nurture_vs_discard_rule: Optional[str] = None
    appointment_reminder_offsets: Optional[List[int]] = None
    briefing_enabled: Optional[bool] = True
    briefing_channel: Optional[str] = "whatsapp"
    briefing_lead_time: Optional[int] = 120
    operator_whatsapp: Optional[str] = None
    buying_signal_keywords: Optional[List[str]] = None
    calendar_integration: Optional[str] = "none"
    payment_gateway: Optional[str] = None
    warming_social_proof: Optional[str] = None
    warming_session_preview: Optional[str] = None
    appointment_mode: Optional[str] = None
    scheduling_offer_style: Optional[str] = None
    availability_schedule: Optional[str] = None
    availability_mode: Optional[str] = "24h"
    meeting_management_enabled: bool = True
    response_style: Optional[ResponseStyle] = ResponseStyle.active
    qualification_required_fields: Optional[List[str]] = None
    qualification_fields: Optional[List[dict]] = None
    custom_variables: Optional[Dict[str, str]] = None
    first_reply_delay_min_seconds: Optional[int] = 0
    first_reply_delay_max_seconds: Optional[int] = 0
    reply_delay_min_seconds: Optional[int] = 0
    reply_delay_max_seconds: Optional[int] = 0
    multi_message_buffer_seconds: Optional[int] = 8
    audio_transcription_enabled: bool = False
    sales_flow: Optional[dict] = None


class AIProfileCreate(AIProfileBase):
    pass


class AIProfileUpdate(BaseModel):
    template_key: Optional[str] = None
    name: Optional[str] = None
    brand_name: Optional[str] = None
    tone_of_voice: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    niche: Optional[str] = None
    target_audience: Optional[str] = None
    offer_description: Optional[str] = None
    goals: Optional[str] = None
    custom_instructions: Optional[str] = None
    agent_mode: Optional[AgentMode] = None
    presentation_variant: Optional[PresentationVariant] = None
    hybrid_flow_style: Optional[HybridFlowStyle] = None
    offer_pack: Optional[dict] = None
    identity_mode: Optional[IdentityMode] = None
    handoff_policy: Optional[HandoffPolicy] = None
    handoff_custom_text: Optional[str] = None
    requires_handoff: Optional[bool] = None
    human_in_loop: Optional[bool] = None
    followup_cadence: Optional[List[int]] = None
    followup_max_attempts: Optional[int] = None
    followup_first_offset: Optional[int] = None
    followup_allowed_hours: Optional[str] = None
    followup_auto_trigger_enabled: Optional[bool] = None
    followup_auto_trigger_inactivity_days: Optional[int] = None
    followup_checkin_auto_trigger_enabled: Optional[bool] = None
    followup_checkin_inactivity_days: Optional[int] = None
    origin_inbound_opener: Optional[str] = None
    origin_outbound_opener: Optional[str] = None
    followup_sdr_instructions: Optional[str] = None
    followup_recovery_instructions: Optional[str] = None
    followup_postsession_instructions: Optional[str] = None
    followup_checkin_instructions: Optional[str] = None
    followup_goal_instructions: Optional[dict] = None
    cart_recovery_attempt_instructions: Optional[List[Optional[str]]] = None
    followup_outcome_instructions: Optional[dict] = None
    objection_common: Optional[str] = None
    qualification_score_threshold: Optional[int] = None
    nurture_vs_discard_rule: Optional[str] = None
    appointment_reminder_offsets: Optional[List[int]] = None
    briefing_enabled: Optional[bool] = None
    briefing_channel: Optional[str] = None
    briefing_lead_time: Optional[int] = None
    operator_whatsapp: Optional[str] = None
    buying_signal_keywords: Optional[List[str]] = None
    calendar_integration: Optional[str] = None
    payment_gateway: Optional[str] = None
    warming_social_proof: Optional[str] = None
    warming_session_preview: Optional[str] = None
    appointment_mode: Optional[str] = None
    scheduling_offer_style: Optional[str] = None
    availability_schedule: Optional[str] = None
    availability_mode: Optional[str] = None
    meeting_management_enabled: Optional[bool] = None
    response_style: Optional[ResponseStyle] = None
    qualification_required_fields: Optional[List[str]] = None
    qualification_fields: Optional[List[dict]] = None
    custom_variables: Optional[Dict[str, str]] = None
    first_reply_delay_min_seconds: Optional[int] = None
    first_reply_delay_max_seconds: Optional[int] = None
    reply_delay_min_seconds: Optional[int] = None
    reply_delay_max_seconds: Optional[int] = None
    multi_message_buffer_seconds: Optional[int] = None
    audio_transcription_enabled: Optional[bool] = None
    sales_flow: Optional[dict] = None


class AIProfileOut(AIProfileBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    payment_webhook_secret: Optional[str] = None
    payment_webhook_url: Optional[str] = None
    generated_prompt_parts: Optional[dict] = None
    prompt_parts_generated_at: Optional[datetime] = None
    prompt_parts_version: Optional[int] = None
    enabled_extensions: Optional[List[str]] = None
    sales_flow: Optional[dict] = None

    class Config:
        orm_mode = True


class ExtensionsUpdate(BaseModel):
    enabled_extensions: List[str]


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


# Campos cujas alterações disparam regeneração do meta-prompter
_META_PROMPTER_FIELDS = {"niche", "target_audience", "tone_of_voice", "offer_description"}


def _profile_to_meta_dict(profile: models.AIProfile) -> dict:
    """Extrai os campos relevantes para o meta-prompter do perfil ORM."""
    _am = profile.agent_mode
    try:
        _am_str = _am.value
    except AttributeError:
        _am_str = str(_am) if _am is not None else None
    return {
        "niche": profile.niche,
        "target_audience": profile.target_audience,
        "tone_of_voice": profile.tone_of_voice,
        "offer_description": profile.offer_description,
        "template_key": profile.template_key,
        "agent_mode": _am_str,
        "objection_common": getattr(profile, "objection_common", None),
        "language": getattr(profile, "language", None) or "pt-BR",
    }


def _trigger_meta_prompter_bg(user_id: int, ai_profile_data: dict) -> None:
    """Fire-and-forget: chama o backend-executors para regenerar os blocos de prompt."""
    base = (settings.EXECUTORS_BASE_URL or "").rstrip("/")
    token = settings.CORE_SERVICE_TOKEN
    if not base or not token:
        logger.debug("meta_prompter trigger ignorado: EXECUTORS_BASE_URL ou CORE_SERVICE_TOKEN ausente")
        return
    url = f"{base}/api/meta-prompter/generate/{user_id}"
    headers = {"X-Service-Token": token, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, headers=headers, json={"ai_profile": ai_profile_data})
        if not resp.is_success:
            logger.warning("meta_prompter trigger falhou user_id=%s status=%s", user_id, resp.status_code)
    except Exception as exc:
        logger.warning("meta_prompter trigger erro user_id=%s: %s", user_id, exc)


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
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == user_id).first()
    if "offer_pack" in data:
        data["offer_pack"] = _normalize_offer_pack(data.get("offer_pack"))
    if "sales_flow" in data:
        data["sales_flow"] = _normalize_sales_flow(data.get("sales_flow"))
    # Derivar qualification_required_fields a partir de qualification_fields quando presente
    if "qualification_fields" in data and data["qualification_fields"] is not None:
        fields = data["qualification_fields"]
        data["qualification_required_fields"] = [
            f["key"] for f in fields
            if isinstance(f, dict) and f.get("mode") == "required"
        ]
    # Default mode inference should happen only on create.
    # On update, omitted/null agent_mode must not rewrite existing mode.
    if not profile and data.get("agent_mode") is None:
        template_key = str(data.get("template_key") or "")
        if template_key.startswith("closer"):
            data["agent_mode"] = AgentMode.direto
        elif template_key.startswith("consult"):
            data["agent_mode"] = AgentMode.consultivo
        else:
            data["agent_mode"] = AgentMode.agenda

    if profile:
        for key, value in data.items():
            # PUT semantics for AIProfileUpdate: explicit null clears the field.
            if key in data:
                setattr(profile, key, value)
        profile.updated_at = datetime.utcnow()
    else:
        # Apply opener defaults from template if not explicitly provided
        template_key = str(data.get("template_key") or "")
        openers = _TEMPLATE_OPENERS.get(template_key, _TEMPLATE_OPENERS.get("sdr_padrao", {}))
        if data.get("origin_inbound_opener") is None:
            data["origin_inbound_opener"] = openers.get("inbound")
        if data.get("origin_outbound_opener") is None:
            data["origin_outbound_opener"] = openers.get("outbound")
        # Auto-gerar payment_webhook_secret único ao criar perfil
        if not data.get("payment_webhook_secret"):
            data["payment_webhook_secret"] = secrets_module.token_urlsafe(32)
        # Sugestão inicial de campos obrigatórios por modo (editável pelo usuário)
        _DEFAULT_QUAL_FIELDS = {
            "sdr_scheduler": ["service_interest", "availability_window"],
            "agenda":        ["service_interest", "availability_window"],
            "consultivo":    ["service_interest", "urgency", "decision_role"],
            "closer":        ["service_interest", "price_acceptance"],
            "direto":        ["service_interest", "price_acceptance"],
        }
        if data.get("qualification_required_fields") is None:
            mode = str(data.get("agent_mode") or "agenda")
            data["qualification_required_fields"] = _DEFAULT_QUAL_FIELDS.get(mode, [])
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
    return _normalize_profile_offer_pack(profile)


@router.get("/ai-templates", response_model=List[AITemplate])
async def list_ai_templates():
    return AI_TEMPLATES


@router.get("/ai-profiles/me", response_model=AIProfileOut)
async def get_my_ai_profile(
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == current_user.id).first()
    if not profile:
        profile = _upsert_ai_profile(
            db=db,
            user_id=current_user.id,
            data={
                "template_key": "",
                "name": "",
                "brand_name": "",
                "tone_of_voice": "",
                "niche": "",
                "target_audience": "",
                "offer_description": "",
                "goals": "",
            },
            require_all_fields_for_create=False,
        )
    return _normalize_profile_offer_pack(profile)


@router.post("/ai-profiles", response_model=AIProfileOut, status_code=status.HTTP_201_CREATED)
async def create_or_replace_ai_profile(
    payload: AIProfileCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_template_key(payload.template_key)
    profile = _upsert_ai_profile(db=db, user_id=current_user.id, data=payload.dict())
    # Trigger 1: onboarding wizard finalizado → gerar blocos de prompt
    background_tasks.add_task(_trigger_meta_prompter_bg, current_user.id, _profile_to_meta_dict(profile))
    return _normalize_profile_offer_pack(profile)


@router.put("/ai-profiles/me", response_model=AIProfileOut)
async def update_my_ai_profile(
    payload: AIProfileUpdate,
    background_tasks: BackgroundTasks,
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
    # Trigger 2: edição de campos relevantes → regenerar blocos de prompt
    if _META_PROMPTER_FIELDS & set(update_data.keys()):
        background_tasks.add_task(_trigger_meta_prompter_bg, current_user.id, _profile_to_meta_dict(profile))
    return _normalize_profile_offer_pack(profile)


@router.patch("/ai-profiles/me", response_model=AIProfileOut)
async def patch_my_ai_profile(
    payload: AIProfileUpdate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualização parcial do AI Profile. Campos omitidos não são sobrescritos.
    Se o perfil ainda não existir, cria com os campos fornecidos (sem exigir todos os obrigatórios)."""
    update_data = payload.dict(exclude_unset=True)
    if "template_key" in update_data:
        _validate_template_key(update_data.get("template_key"))

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data provided",
        )

    profile = _upsert_ai_profile(
        db=db,
        user_id=current_user.id,
        data=update_data,
        require_all_fields_for_create=False,
    )
    if _META_PROMPTER_FIELDS & set(update_data.keys()):
        background_tasks.add_task(_trigger_meta_prompter_bg, current_user.id, _profile_to_meta_dict(profile))
    return _normalize_profile_offer_pack(profile)


@router.patch("/ai-profiles/patch-by-user/{user_id}", response_model=AIProfileOut)
async def service_patch_ai_profile_by_user(
    user_id: int,
    payload: AIProfileUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    """Endpoint service-to-service: aplica PATCH parcial no AI Profile de um usuário pelo user_id."""
    update_data = payload.dict(exclude_unset=True)
    if "template_key" in update_data:
        _validate_template_key(update_data.get("template_key"))

    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No data provided")

    profile = _upsert_ai_profile(
        db=db,
        user_id=user_id,
        data=update_data,
        require_all_fields_for_create=False,
    )
    if _META_PROMPTER_FIELDS & set(update_data.keys()):
        background_tasks.add_task(_trigger_meta_prompter_bg, user_id, _profile_to_meta_dict(profile))
    return _normalize_profile_offer_pack(profile)


@router.get("/ai-profiles/resolve", response_model=AIProfileOut)
async def resolve_ai_profile(
    user_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    return _normalize_profile_offer_pack(profile)


@router.get("/ai-profiles/resolve-by-secret", response_model=AIProfileOut)
async def resolve_ai_profile_by_secret(
    token: str,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    """Resolve o AI profile pelo payment_webhook_secret. Usado pelo backend-crm para autenticar webhooks de pagamento."""
    profile = (
        db.query(models.AIProfile)
        .filter(models.AIProfile.payment_webhook_secret == token)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook secret não encontrado")
    return _normalize_profile_offer_pack(profile)


@router.get("/ai-profiles/{ai_profile_id}", response_model=AIProfileOut)
async def get_ai_profile_by_id(
    ai_profile_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    """Busca um AiProfile específico pelo ID via service token. Valida que pertence ao user_id."""
    profile = db.query(models.AIProfile).filter(models.AIProfile.id == ai_profile_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    if profile.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ai_profile_id não pertence ao utilizador")
    return _normalize_profile_offer_pack(profile)


@router.patch("/ai-profiles/{user_id}/generated-prompt-parts")
async def save_generated_prompt_parts(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    """Salva os blocos gerados pelo meta-prompter no ai_profile. Chamado pelo backend-executors."""
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    profile.generated_prompt_parts = payload.get("generated_prompt_parts")
    profile.prompt_parts_generated_at = datetime.utcnow()
    profile.prompt_parts_version = (profile.prompt_parts_version or 0) + 1
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return {"ok": True, "prompt_parts_version": profile.prompt_parts_version}


@router.post("/ai-profiles/me/regenerate-webhook-secret")
async def regenerate_webhook_secret(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenera o payment_webhook_secret do usuário. Retorna o novo secret e a URL gerada."""
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    new_secret = secrets_module.token_urlsafe(32)
    profile.payment_webhook_secret = new_secret
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return {
        "payment_webhook_secret": new_secret,
        "payment_webhook_url": profile.payment_webhook_url,
    }


@router.patch("/ai-profiles/admin/{user_id}/extensions")
async def admin_set_extensions(
    user_id: int,
    payload: ExtensionsUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
):
    """Admin: define as extensões ativas para um usuário (requer service token)."""
    profile = db.query(models.AIProfile).filter(models.AIProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI profile not found")
    profile.enabled_extensions = payload.enabled_extensions
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return {"ok": True, "enabled_extensions": profile.enabled_extensions}


@router.get("/ai-profiles/admin/all")
async def admin_list_all_ai_profiles(
    db: Session = Depends(get_db),
    _: str = Depends(_require_service_token),
) -> List[Dict[str, Any]]:
    """Admin: lista todos os AI profiles com campos relevantes para o painel (requer service token)."""
    profiles = db.query(models.AIProfile).order_by(models.AIProfile.user_id).all()
    result = []
    for p in profiles:
        result.append({
            "user_id": p.user_id,
            "template_key": p.template_key,
            "name": p.name,
            "brand_name": p.brand_name,
            "niche": p.niche,
            "target_audience": p.target_audience,
            "agent_mode": p.agent_mode,
            "presentation_variant": p.presentation_variant,
            "hybrid_flow_style": p.hybrid_flow_style,
            "offer_pack": _normalize_offer_pack(getattr(p, "offer_pack", None)),
            "qualification_score_threshold": p.qualification_score_threshold,
            "qualification_required_fields": p.qualification_required_fields,
            "qualification_fields": p.qualification_fields,
            "followup_max_attempts": p.followup_max_attempts,
            "prompt_parts_generated_at": p.prompt_parts_generated_at.isoformat() if p.prompt_parts_generated_at else None,
            "prompt_parts_version": p.prompt_parts_version,
            "enabled_extensions": p.enabled_extensions,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })
    return result
