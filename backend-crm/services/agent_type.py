from __future__ import annotations

import logging
from typing import Optional

from core_client import fetch_core_ai_profile, fetch_core_ai_profile_resolve

logger = logging.getLogger(__name__)


AgentType = str

# Mapeamento de template_key para playbook de follow-up dedicado.
# Usado pelo decision_engine para selecionar instruções específicas por agente.
FOLLOWUP_PLAYBOOK_MAP: dict[str, str] = {
    "hybrid_scheduler": "hybrid_scheduler_followup",
}


def map_template_key_to_agent_type(template_key: Optional[str]) -> AgentType:
    template = str(template_key or "").strip().lower()
    if template == "hybrid_scheduler":
        return "agent_3"
    if template.startswith("closer"):
        return "agent_2"
    return "agent_1"


def resolve_agent_type_for_user(*, user_id: Optional[int] = None, token: Optional[str] = None) -> AgentType:
    """Resolve o snapshot operacional de agente para o CRM.

    Ordem de resolução:
    1) token (quando disponível)
    2) user_id via service token
    3) fallback seguro do MVP: agent_1
    """
    if token:
        try:
            profile = fetch_core_ai_profile(token)
            return map_template_key_to_agent_type((profile or {}).get("template_key"))
        except Exception as exc:
            logger.warning("agent_type_resolve token_failed reason=%s", exc)

    if user_id:
        try:
            profile = fetch_core_ai_profile_resolve(int(user_id))
            return map_template_key_to_agent_type((profile or {}).get("template_key"))
        except Exception as exc:
            logger.warning("agent_type_resolve user_id_failed user_id=%s reason=%s", user_id, exc)

    return "agent_1"
