from __future__ import annotations

from pydantic import BaseModel


class InboundEvent(BaseModel):
    user_id: int
    lead_id: int
    channel: str = "whatsapp"
    message_text: str
    received_at: str | None = None
    phone: str | None = None
    message_id: str | None = None
    instance_id: str | None = None
    provider: str | None = None
