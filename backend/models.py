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
