from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime

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

    # Pydantic v2: substitui allow_population_by_field_name
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


class AppointmentBase(BaseModel):
    description: str
    start_at: datetime
    end_at: Optional[datetime] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

# -----------------------------
# Canais de copy
# -----------------------------
Channel = Literal["email", "whatsapp", "instagram", "call"]

# -----------------------------
# Mensagens (messages)
# -----------------------------
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
AppointmentType = Literal["meeting", "call", "follow-up", "presentation"]
AppointmentStatus = Literal["scheduled", "completed", "canceled"]


class AppointmentBase(BaseModel):
    lead_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    type: AppointmentType
    status: AppointmentStatus = "scheduled"
    start_time: datetime
    end_time: Optional[datetime] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    lead_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[AppointmentType] = None
    status: Optional[AppointmentStatus] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class AppointmentOut(AppointmentBase):
    id: int
    created_at: datetime
    updated_at: datetime

# -----------------------------
# Opções do Assistente IA
# -----------------------------
class AssistantOptions(BaseModel):
    create_cards_only: bool = False
    generate_copys: bool = True
    # evitar default mutável
    channels: List[Channel] = Field(default_factory=lambda: ["email", "whatsapp", "instagram", "call"])
    language: str = "pt-BR"
    tone: str = "profissional"
    proposal: Literal["site"] = "site"


# -----------------------------
# Appointments
# -----------------------------
AppointmentStatus = Literal["pending", "completed", "canceled"]


class AppointmentBase(BaseModel):
    lead_id: int
    title: str
    description: Optional[str] = None
    type: Optional[str] = None
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus = "pending"
    location: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    lead_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    location: Optional[str] = None


class AppointmentOut(AppointmentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
