from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DecisionOutput(BaseModel):
    next_action: Literal["reply", "ask_qualification", "handoff", "ignore"]
    message_text: str = ""
    questions: list[str] = Field(default_factory=list)
    reason: str
    suggested_category: Optional[str] = None
    category_reason: Optional[str] = None
    outcome: Optional[Literal["won", "lost"]] = None
    kanban_highlight: Optional[Literal["green", "orange"]] = None
    signals: list[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    decision_trace: Optional[dict] = None
    # Mídia rica (Tarefa 3.6): enviada antes do texto do pitch para Agent 2
    pre_send_media: Optional[dict] = None

    @field_validator("questions", mode="after")
    @classmethod
    def normalize_questions(
        cls, value: list[str], info
    ) -> list[str]:
        if info.data.get("next_action") != "ask_qualification":
            return []
        return value
