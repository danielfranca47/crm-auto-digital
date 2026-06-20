from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Campos opcionais com enum fechado: um valor fora do conjunto degrada para None em vez de
# derrubar a decisão inteira da Mãe via ValidationError (route_to fica fora de propósito —
# é obrigatório e não tem default seguro).
_OPTIONAL_ENUM_FIELDS: dict[str, frozenset[str]] = {
    "perceived_category": frozenset({"qualification", "apresentation", "pre-agendamento", "agendamento", "follow-up", "closing"}),
    "agent_mode": frozenset({"consultivo", "agenda", "direto"}),
    "next_action_hint": frozenset({"reply", "ask_qualification", "handoff", "ignore", "greet"}),
    "compound_follow_through": frozenset({"qualification", "apresentation", "pre-agendamento", "agendamento", "follow-up", "closing"}),
}


class MotherDecision(BaseModel):
    route_to: Literal["qualification", "apresentation", "pre-agendamento", "agendamento", "follow-up", "closing", "recepcao"]
    perceived_category: Optional[Literal["qualification", "apresentation", "pre-agendamento", "agendamento", "follow-up", "closing"]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    agent_mode: Optional[Literal["consultivo", "agenda", "direto"]] = None
    signals: Optional[dict] = None
    objective: Optional[str] = None
    next_action_hint: Optional[Literal["reply", "ask_qualification", "handoff", "ignore", "greet"]] = None
    compound_follow_through: Optional[Literal["qualification", "apresentation", "pre-agendamento", "agendamento", "follow-up", "closing"]] = None
    detected_intents: list[str] = Field(default_factory=list)

    @field_validator(*_OPTIONAL_ENUM_FIELDS.keys(), mode="before")
    @classmethod
    def _coerce_unknown_enum_to_none(cls, value, info):
        if value is None:
            return None
        allowed = _OPTIONAL_ENUM_FIELDS.get(info.field_name)
        if allowed is not None and value not in allowed:
            logger.warning(
                "event=mother_decision_invalid_enum_coerced field=%s value=%r",
                info.field_name,
                value,
            )
            return None
        return value


class ChildResult(BaseModel):
    message_text: str = ""
    question_text: Optional[str] = None
    field: Optional[str] = None
    should_ask: Optional[bool] = None
    did_complete_phase: bool = False
    recommended_next_category: Optional[str] = None
    outcome: Optional[Literal["won", "lost"]] = None
    kanban_highlight: Optional[Literal["green", "orange"]] = None
    signals: list[str] = Field(default_factory=list)
    signals_structured: Optional[dict] = None
    media_keys_to_send: Optional[list[str]] = None
    confidence: float = Field(ge=0.0, le=1.0)
