"""
module_sales_pipeline.py — Análise do pipeline de vendas observado nas conversas espiãs.

Identifica etapas do processo de vendas sem depender das categorias do CRM.
Modelo genérico: Contato inicial → Qualificação → Proposta → Negociação → Fechamento/Perda
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from openai import OpenAI

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """Você é um especialista em análise de processos de vendas.
Sua tarefa é analisar conversas reais entre um vendedor e seus leads para mapear o
pipeline de vendas praticado — independentemente de qualquer configuração de sistema.

## Etapas que você deve identificar (use apenas as que realmente aparecem)
- `contato_inicial` — primeiro contato, apresentação
- `qualificacao` — coleta de informações do lead (necessidade, orçamento, prazo etc.)
- `proposta` — apresentação de oferta, preço, solução
- `negociacao` — tratativa de objeções, negociação de condições
- `fechamento` — confirmação de compra, pagamento, contrato
- `perda` — lead que desistiu ou parou de responder

## O que você deve entregar
Responda EXCLUSIVAMENTE em JSON com este schema:
{
  "stages_observed": ["lista das etapas identificadas nas conversas"],
  "avg_messages_to_proposal": <número médio de mensagens até aparecer uma proposta, ou null>,
  "avg_messages_to_close": <número médio de mensagens até o fechamento, ou null>,
  "main_friction_points": ["principais pontos de atrito ou objeção observados (máx 4)"],
  "conversion_signals": ["frases ou comportamentos que indicam avanço do lead (máx 4)"],
  "drop_off_signals": ["frases ou comportamentos que indicam desistência (máx 3)"],
  "recommended_agent_mode": "sdr_scheduler|agenda|consultivo|closer|direto — modo mais adequado ao padrão observado",
  "suggested_qualification_fields": ["lista de campos que o vendedor naturalmente coleta — valores: service_interest, urgency, decision_role, price_acceptance, availability_window, location, company_size, budget"],
  "confidence": <0.0 a 1.0>,
  "analysis": "Diagnóstico do pipeline de vendas observado (2-4 frases)",
  "suggestions": [
    {
      "field": "nome_do_campo_do_AI_Profile",
      "current_value": null,
      "suggested_value": "valor sugerido",
      "rationale": "Evidência observada (máx 2 frases)"
    }
  ]
}

## Campos do AI Profile que podem ser sugeridos neste módulo
- `agent_mode`, `presentation_variant`, `qualification_required_fields`, `handoff_policy`

## Instrução adicional
Se as conversas contiverem [ÁUDIO: ...] ou [IMAGEM: ...], use essas transcrições/descrições
para enriquecer sua análise como se fossem texto normal.
"""


def analyze_pipeline(
    conversations: List[Dict[str, Any]],
    current_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analisa o pipeline de vendas a partir das conversas e retorna sugestões.

    conversations: output de spy_conversation_loader.load_spy_conversations()
    current_profile: AI Profile atual do usuário (para contexto)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[spy:pipeline] OPENAI_API_KEY ausente — módulo desativado")
        return {"suggestions": [], "confidence": 0.0, "analysis": "API key não configurada"}

    client = OpenAI(api_key=api_key)

    profile_snippet = json.dumps(
        {k: current_profile.get(k) for k in ("agent_mode", "presentation_variant", "qualification_required_fields")},
        ensure_ascii=False,
    )

    # Formata conversas no estilo [VENDEDOR]/[LEAD] — mesmo formato dos outros módulos
    from services.spy_agent.conversation_loader import format_conversations_for_llm
    conv_text = format_conversations_for_llm(conversations, max_chars=300)

    user_prompt = (
        f"## Configuração atual do AI Profile\n{profile_snippet}\n\n"
        f"## Conversas observadas ({len(conversations)} leads)\n{conv_text}"
    )

    try:
        response = client.chat.completions.create(
            model=_MODEL,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
    except Exception as exc:
        logger.error("[spy:pipeline] erro na chamada LLM: %s", exc)
        return {"suggestions": [], "confidence": 0.0, "analysis": f"Erro na análise: {exc}"}

    if "suggestions" not in result:
        result["suggestions"] = []

    logger.info(
        "[spy:pipeline] análise concluída stages=%s confidence=%.2f",
        result.get("stages_observed", []),
        result.get("confidence", 0.0),
    )
    return result
