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

    @field_validator("questions", mode="after")
    @classmethod
    def normalize_questions(
        cls, value: list[str], info
    ) -> list[str]:
        if info.data.get("next_action") != "ask_qualification":
            return []
        return value
