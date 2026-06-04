from typing import Any, Dict, Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# -----------------------------
# Leads
# -----------------------------
class Lead(BaseModel):
    companyName: str
    contactName: Optional[str] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    email: Optional[str] = None
    # Valores aceitos: 'Manual', 'Planilha', 'WhatsApp', 'inbound', 'outbound'
    origin: Optional[str] = "Manual"
    category: str
    customMessage: Optional[str] = None
    observations: Optional[str] = None
    agent_type: Optional[str] = None
    priority: Optional[int] = 1

    # Pydantic v2
    model_config = ConfigDict(populate_by_name=True)


class LeadUpdate(BaseModel):
    companyName: Optional[str] = None
    contactName: Optional[str] = None
    phone: Optional[str] = None
    country_code: Optional[str] = None
    email: Optional[str] = None
    origin: Optional[str] = None
    category: Optional[str] = None
    customMessage: Optional[str] = None
    observations: Optional[str] = None
    agent_type: Optional[str] = None
    priority: Optional[int] = None
    lastMovement: Optional[datetime] = None
    prospection_context: Optional[str] = None


class StartFollowupPayload(BaseModel):
    lead_id: int
    agent_type: Literal["agent_1", "agent_3"]
    meeting_or_session_happened: Literal["yes", "no_show", "canceled", "needs_reschedule"]
    outcome: Optional[str] = None
    followup_goal: Optional[str] = None
    proposal_sent: Optional[bool] = None
    operator_note: Optional[str] = None


class QualificationPatchPayload(BaseModel):
    fields: Dict[str, Any]


class BotDisabledUpdate(BaseModel):
    disabled: bool
    reason: Optional[str] = None


# -----------------------------
# Mensagens (messages)
# -----------------------------
Channel = Literal["email", "whatsapp", "instagram", "call"]


class MessageBase(BaseModel):
    channel: Channel
    subject: Optional[str] = None      # para e-mail
    body: str = Field(min_length=5)    # conteúdo da copy
    model: Optional[str] = None        # ex.: "gpt-3.5-turbo"


class MessageCreate(MessageBase):
    lead_id: int


class MessageOut(MessageBase):
    id: int
    lead_id: int
    createdAt: datetime


# -----------------------------
# Compromissos / Agenda
# -----------------------------
AppointmentStatus = Literal["pending", "completed", "canceled"]
AppointmentOutcome = Literal["completed", "no_show", "rescheduled"]


class AppointmentCreate(BaseModel):
    """
    Payload de criação.
    - `lead_id` e `title` podem ficar ausentes para permitir usar o lead_id do path
      e um título padrão no backend.
    """
    lead_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    status: AppointmentStatus = "pending"
    location: Optional[str] = None


class AppointmentUpdate(BaseModel):
    """
    Payload de atualização (parcial).
    - NÃO inclui `lead_id` para evitar duplicidade com o valor do path param.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    location: Optional[str] = None


class AppointmentOut(BaseModel):
    id: int
    lead_id: int
    title: str
    description: Optional[str] = None
    type: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    status: AppointmentStatus
    outcome: Optional[AppointmentOutcome] = None
    outcome_note: Optional[str] = None
    outcome_at: Optional[datetime] = None
    location: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Permite instanciar a partir de objetos/rows (ex.: sqlite3.Row)
    model_config = ConfigDict(from_attributes=True)


class AppointmentOutcomeUpdate(BaseModel):
    outcome: AppointmentOutcome
    note: Optional[str] = None
    reschedule_start_at: Optional[datetime] = None
    reschedule_end_at: Optional[datetime] = None
    reactivate_bot: bool = True
    move_lead_to: Optional[str] = None


# -----------------------------
# Opções do Assistente IA
# -----------------------------
class AssistantOptions(BaseModel):
    create_cards_only: bool = False
    generate_copys: bool = True
    channels: List[Channel] = Field(
        default_factory=lambda: ["email", "whatsapp", "instagram", "call"]
    )
    language: str = "pt-BR"
    tone: str = "profissional"
    proposal: Literal["site"] = "site"


# -----------------------------
# Follow-up Edição Pré-Disparo
# -----------------------------

class ScheduledMessagePayload(BaseModel):
    content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None  # "image" | "doc" | "audio" | "video"


class SendNowPayload(BaseModel):
    content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None


# -----------------------------
# Knowledge Base
# -----------------------------
class KnowledgeCreate(BaseModel):
    title: str = Field(min_length=3)
    content_text: str = Field(min_length=20)
    category: Optional[str] = None
    active_in_funnel: Optional[int] = 1


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3)
    content_text: Optional[str] = Field(default=None, min_length=20)
    category: Optional[str] = None
    active_in_funnel: Optional[int] = None
    media_url: Optional[str] = None


class KnowledgeMediaOut(BaseModel):
    id: int
    knowledge_item_id: int
    media_url: str
    media_type: str
    language: str
    send_order: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class KnowledgeMediaUpdate(BaseModel):
    language: Optional[str] = None
    send_order: Optional[int] = None


class KnowledgeMediaReorder(BaseModel):
    items: List[dict]  # [{id: int, send_order: int}]


class KnowledgeItemOut(BaseModel):
    id: int
    user_id: int
    title: str
    source_type: Literal["manual", "file"]
    content_text: str
    file_path: Optional[str] = None
    category: Optional[str] = None
    active_in_funnel: int = 1
    media_url: Optional[str] = None
    media_items: List[KnowledgeMediaOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# Business Info
# -----------------------------
class BusinessInfoField(BaseModel):
    id: int
    field_key: str
    label: str
    value: Optional[str] = None
    enabled: int = 1
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


class BusinessInfoFieldUpdate(BaseModel):
    label: Optional[str] = None
    value: Optional[str] = None
    enabled: Optional[int] = None
    sort_order: Optional[int] = None


class BusinessInfoCustomCreate(BaseModel):
    field_key: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=2, max_length=128)
    value: Optional[str] = None
