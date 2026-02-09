from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# -----------------------------
# Leads
# -----------------------------
class Lead(BaseModel):
    companyName: str
    contactName: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    origin: Optional[str] = "Manual"
    category: str
    customMessage: Optional[str] = None
    observations: Optional[str] = None
    priority: Optional[int] = 1

    # Pydantic v2
    model_config = ConfigDict(populate_by_name=True)


class LeadUpdate(BaseModel):
    companyName: Optional[str] = None
    contactName: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    origin: Optional[str] = None
    category: Optional[str] = None
    customMessage: Optional[str] = None
    observations: Optional[str] = None
    priority: Optional[int] = None
    lastMovement: Optional[datetime] = None


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
    location: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Permite instanciar a partir de objetos/rows (ex.: sqlite3.Row)
    model_config = ConfigDict(from_attributes=True)


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
# Knowledge Base
# -----------------------------
class KnowledgeCreate(BaseModel):
    title: str = Field(min_length=3)
    content_text: str = Field(min_length=20)


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3)
    content_text: Optional[str] = Field(default=None, min_length=20)


class KnowledgeItemOut(BaseModel):
    id: int
    user_id: int
    title: str
    source_type: Literal["manual", "file"]
    content_text: str
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
