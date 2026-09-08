"""
classifier.py — Classificação read-only de estágio do funil para leads
monitorados (WhatsApp de colaborador).

Lê o histórico de mensagens de um lead e sugere em qual estágio do Kanban a
conversa está agora. Nunca decide resposta, nunca aciona envio — mesmo
princípio de isolamento de services/collab_monitor/monitor_inbound_handler.py.

Estilo de prompt (1 chamada LLM, JSON estruturado) reaproveitado de
services/spy_agent/module_sales_pipeline.py. A postura conservadora
("null quando incerto, nunca inventar categoria") reaproveita a mesma técnica
já validada em backend-executors/app/services/decision_engine.py para
suggested_category — só essa camada de prompt transfere para este contexto,
já que a camada de guardrail por código da mãe depende de qualification_state
que não existe para conversas conduzidas por um humano (colaborador).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from openai import OpenAI

from services.ai_orchestrator.history import get_recent_history
from services.spy_agent.conversation_loader import format_conversations_for_llm

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

# Subconjunto de LeadStatus (frontend-crm/src/types/crm.ts) aplicável a um
# lead monitorado já em conversa — exclui estágios só de prospecção
# ("to-prospect", "in-progress") e o próprio "monitoring" (estado inicial).
ALLOWED_MONITOR_CATEGORIES = [
    "qualification",
    "apresentation",
    "follow-up",
    "closing",
    "client-list",
    "prospect-refused",
    "disqualified",
]

_SYSTEM_PROMPT = """Você é um especialista em análise de funil de vendas.
Sua tarefa é ler uma conversa real de WhatsApp entre um vendedor (colaborador
humano) e um lead, e identificar em qual estágio do funil essa conversa está
AGORA — sem inventar, sem supor.

## Estágios possíveis (use SOMENTE estes valores)
- qualification — vendedor ainda está entendendo a necessidade do lead
- apresentation — vendedor já apresentou oferta/proposta/preço
- follow-up — negociação em andamento, lead pediu tempo ou está sendo acompanhado
- closing — fechamento em curso (pagamento, contrato, confirmação de compra)
- client-list — compra já confirmada, lead virou cliente
- prospect-refused — lead recusou explicitamente ou demonstrou desistência clara
- disqualified — lead claramente fora do perfil/público-alvo

## Regra mais importante: seja conservador
- Só retorne um estágio quando houver sinal EXPLÍCITO e claro na conversa.
- Se a conversa for curta, genérica, ambígua, ou você não tiver certeza,
  retorne suggested_category=null.
- Nunca invente um estágio fora da lista acima.
- category_reason DEVE ser null sempre que suggested_category for null.

## Formato de resposta — responda SOMENTE com este JSON, sem texto antes/depois:
{
  "suggested_category": "um dos valores acima, ou null",
  "category_reason": "motivo curto (1 frase), ou null"
}
"""


def classify_monitor_lead(lead_id: int, history_limit: int = 30) -> Dict[str, Any]:
    """
    Lê o histórico de mensagens de um lead monitorado e sugere o estágio do
    funil correspondente.

    Retorna {"suggested_category": str|None, "category_reason": str|None}.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[collab_monitor:classifier] OPENAI_API_KEY ausente — classificação desativada")
        return {"suggested_category": None, "category_reason": None}

    history = get_recent_history(lead_id, limit=history_limit)
    if not history:
        return {"suggested_category": None, "category_reason": None}

    conv_text = format_conversations_for_llm(
        [{"lead_id": lead_id, "messages": history}], max_chars=500
    )

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"## Conversa\n{conv_text}"},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
    except Exception as exc:
        logger.error("[collab_monitor:classifier] erro na chamada LLM lead_id=%s: %s", lead_id, exc)
        return {"suggested_category": None, "category_reason": None}

    suggested = result.get("suggested_category")
    if suggested not in ALLOWED_MONITOR_CATEGORIES:
        if suggested is not None:
            logger.warning(
                "[collab_monitor:classifier] categoria inválida retornada pela LLM lead_id=%s value=%r",
                lead_id,
                suggested,
            )
        suggested = None

    return {
        "suggested_category": suggested,
        "category_reason": (result.get("category_reason") or None) if suggested else None,
    }
