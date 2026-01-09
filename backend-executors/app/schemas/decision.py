from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DecisionOutput(BaseModel):
    next_action: Literal["reply", "ask_qualification", "handoff", "ignore"]
    message_text: str = ""
    questions: list[str] = Field(default_factory=list)
    reason: str

    @field_validator("questions", mode="after")
    @classmethod
    def normalize_questions(
        cls, value: list[str], info
    ) -> list[str]:
        if info.data.get("next_action") != "ask_qualification":
            return []
        return value
