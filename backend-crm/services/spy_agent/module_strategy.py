from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from .conversation_loader import format_conversations_for_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_LEARN = """Você é um especialista em estratégia de vendas e configuração de agentes de IA.
Sua tarefa é analisar threads completos de conversa de vendas e extrair a estratégia comercial praticada.

## Campos alvo (Módulo de Estratégia — Aprender com conversas)
- `agent_mode` ("sdr_scheduler"|"agenda"|"consultivo"|"closer"|"direto"): Modo que melhor representa a abordagem
- `presentation_variant` ("sales"|"scheduler"): Foco principal das conversas
- `qualification_required_fields` (list[str]): Campos que o vendedor sempre busca coletar. Valores válidos: service_interest, urgency, decision_role, price_acceptance, availability_window, location, company_size, budget
- `handoff_policy` ("disable_bot"|"keep_active_notify"|"ignore"): Como o vendedor trata transferências

## Instrução de resposta
Responda EXCLUSIVAMENTE em JSON com este schema:
{
  "suggestions": [
    {
      "field": "nome_do_campo",
      "current_value": "valor atual (ou null)",
      "suggested_value": "novo valor",
      "rationale": "Evidência observada (máx 2 frases)"
    }
  ],
  "strategy_signals": {
    "mentions_price_early": true,
    "uses_objection_handling": true,
    "closes_actively": true,
    "asks_for_appointment": true,
    "sales_cycle_type": "curto|médio|longo"
  },
  "recommended_agent_mode": "o modo mais adequado ao estilo observado",
  "confidence": 0.0-1.0,
  "analysis": "Diagnóstico técnico da estratégia de vendas observada"
}
"""

_SYSTEM_PROMPT_OPTIMIZED = """Você é um especialista em estratégia de vendas e configuração de agentes de IA.
Sua tarefa é analisar threads de conversa e inferir apenas o tipo de negócio e o perfil básico
de interação — SEM copiar a estratégia atual do vendedor.

O objetivo é recomendar o melhor `agent_mode` com base em sinais objetivos:
- Tipo de oferta (produto vs serviço)
- Ticket (inferido das conversas)
- Estilo de interação (ativo vs passivo)
- Ciclo de venda (curto, médio, longo)

## Instrução de resposta
Responda EXCLUSIVAMENTE em JSON com este schema:
{
  "suggestions": [
    {
      "field": "agent_mode",
      "current_value": "valor atual (ou null)",
      "suggested_value": "modo recomendado",
      "rationale": "Justificativa baseada nos sinais objetivos"
    }
  ],
  "strategy_signals": {
    "is_service": true,
    "estimated_ticket_range": "baixo|médio|alto",
    "interaction_style": "ativo|passivo",
    "sales_cycle_type": "curto|médio|longo"
  },
  "recommended_agent_mode": "o modo mais adequado",
  "confidence": 0.0-1.0,
  "analysis": "Análise dos sinais objetivos — sem replicar estratégia do vendedor"
}
"""


def analyze_strategy(
    conversations: List[Dict[str, Any]],
    current_profile: Dict[str, Any],
    use_optimized_strategy: bool = True,
) -> Dict[str, Any]:
    """
    Módulo 3: Extrai estratégia de vendas.
    Se use_optimized_strategy=True, apenas infere agent_mode sem copiar táticas.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[spy_agent:strategy] OPENAI_API_KEY ausente")
        return {"module": "strategy", "suggestions": [], "confidence": 0.0, "analysis": "OPENAI_API_KEY não configurado"}

    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key)
    except ImportError:
        return {"module": "strategy", "suggestions": [], "confidence": 0.0, "analysis": "Biblioteca openai não instalada"}

    system_prompt = _SYSTEM_PROMPT_OPTIMIZED if use_optimized_strategy else _SYSTEM_PROMPT_LEARN

    profile_snippet = {
        k: current_profile.get(k)
        for k in ("agent_mode", "presentation_variant", "qualification_required_fields", "handoff_policy")
    }

    conv_text = format_conversations_for_llm(conversations)

    mode_label = "SINAIS OBJETIVOS APENAS (não replicar estratégia)" if use_optimized_strategy else "APRENDER COM CONVERSAS"
    user_msg = f"""## Modo de análise: {mode_label}

## AI Profile atual (campos relevantes)
{json.dumps(profile_snippet, ensure_ascii=False, indent=2)}

## Conversas observadas
{conv_text}

Analise as conversas e retorne as sugestões conforme o schema."""

    try:
        raw = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        parsed = json.loads(raw.choices[0].message.content)
    except Exception as exc:
        logger.warning("[spy_agent:strategy] LLM error: %s", exc)
        return {"module": "strategy", "suggestions": [], "confidence": 0.0, "analysis": f"LLM error: {exc}"}

    return {
        "module": "strategy",
        "suggestions": parsed.get("suggestions", []),
        "strategy_signals": parsed.get("strategy_signals", {}),
        "recommended_agent_mode": parsed.get("recommended_agent_mode"),
        "confidence": float(parsed.get("confidence", 0.5)),
        "analysis": parsed.get("analysis", ""),
    }
