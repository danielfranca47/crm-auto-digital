from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MotherDecision(BaseModel):
    route_to: Literal["qualification", "apresentation", "follow-up", "closing"]
    perceived_category: Optional[Literal["qualification", "apresentation", "follow-up", "closing"]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    agent_mode: Optional[Literal["consultivo", "agenda", "direto"]] = None
    signals: Optional[dict] = None
    objective: Optional[str] = None
    next_action_hint: Optional[Literal["reply", "ask_qualification", "handoff", "ignore", "greet"]] = None


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
    confidence: float = Field(ge=0.0, le=1.0)
