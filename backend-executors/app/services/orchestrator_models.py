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
}

# route_to é obrigatório e não tem default seguro, por isso fica fora do mecanismo
# de tolerância acima (que degrada para None). Em vez de tolerância genérica, corrige
# apenas aliases conhecidos e recorrentes da LLM antes da validação do Literal — valores
# realmente desconhecidos continuam a levantar ValidationError e caem no fallback normal.
_ROUTE_TO_ALIASES: dict[str, str] = {
    "presentation": "apresentation",  # typo recorrente: falta o "a-" do enum em PT
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
    detected_intents: list[str] = Field(default_factory=list)
    # Ramo escolhido por nó de ramificação (bloco `condicao` do Fluxo de Venda) ativo nesta
    # fase — chave é o id do bloco `condicao`, valor é o id do ramo (branch) escolhido. Ver
    # docs/architecture/sales-flow.md, secção "Lógica de Ramificação".
    branch_selections: dict[str, str] = Field(default_factory=dict)

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

    @field_validator("route_to", mode="before")
    @classmethod
    def _normalize_route_to_alias(cls, value):
        if isinstance(value, str):
            alias_target = _ROUTE_TO_ALIASES.get(value.strip())
            if alias_target is not None:
                logger.warning(
                    "event=mother_decision_route_to_alias_coerced value=%r normalized=%r",
                    value,
                    alias_target,
                )
                return alias_target
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
    # Preenchido apenas pela Filha Recepção quando a mensagem do lead mistura saudação
    # com pedido comercial. Trecho literal (não resumido) do que não é saudação/social,
    # para reenfileiramento como novo job inbound — ver "Saudação composta" em
    # docs/architecture/llm-architecture.md.
    pending_commercial_text: Optional[str] = None
