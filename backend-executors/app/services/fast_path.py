from __future__ import annotations

import unicodedata
from typing import Optional

from app.schemas.decision import DecisionOutput

HANDOFF_KEYWORDS = [
    "humano",
    "atendente",
    "falar com atendente",
    "pessoa real",
    "suporte",
    "ligar",
    "telefone",
    "reclamacao",
    "reclamação",
    "chamar atendente",
    "falar com humano",
    "atendimento",
]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower().strip()


def try_fast_handoff(message_text: str) -> Optional[DecisionOutput]:
    normalized = normalize_text(message_text)
    if not normalized:
        return None
    for keyword in HANDOFF_KEYWORDS:
        if keyword in normalized:
            return DecisionOutput(
                next_action="handoff",
                message_text="",
                questions=[],
                reason="keyword_handoff",
            )
    return None
