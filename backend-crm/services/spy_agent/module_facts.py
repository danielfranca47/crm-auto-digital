from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from .conversation_loader import format_conversations_for_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um especialista em configuração de agentes de CRM.
Sua tarefa é analisar conversas de WhatsApp de uma empresa e extrair fatos objetivos do negócio
que estejam ausentes ou incompletos no AI Profile atual.

## Campos alvo (Módulo de Fatos)
- `niche` (str): Nicho/setor da empresa. Ex: "Clínica odontológica", "Agência de marketing digital"
- `offer_description` (str): Descrição da oferta principal. O que a empresa vende/oferece.
- `target_audience` (str): Perfil do cliente ideal mencionado nas conversas.
- `warming_social_proof` (str): Provas sociais mencionadas (depoimentos, resultados, números).
- `brand_name` (str): Nome real da empresa (se diferente do perfil atual).

## Instrução de resposta
Responda EXCLUSIVAMENTE em JSON com este schema:
{
  "suggestions": [
    {
      "field": "nome_do_campo",
      "current_value": "valor atual (ou null)",
      "suggested_value": "novo valor sugerido",
      "rationale": "Por que sugerimos isso (em português, máx 2 frases)"
    }
  ],
  "confidence": 0.0-1.0,
  "analysis": "Resumo técnico dos fatos extraídos das conversas"
}

Regras:
1. Só sugira campos onde há evidência clara nas conversas
2. Não invente informações. Se não há evidência, omita o campo
3. Se o valor atual já está correto, não inclua na lista de sugestões
4. suggested_value deve ser uma string concisa e direta (máx 200 chars por campo)
5. Se não encontrou nada relevante, retorne suggestions=[]
"""


def analyze_facts(
    conversations: List[Dict[str, Any]],
    current_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Módulo 1: Extrai fatos objetivos do negócio a partir das conversas.
    Retorna dict com suggestions, confidence e analysis.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[spy_agent:facts] OPENAI_API_KEY ausente — módulo de fatos ignorado")
        return {"module": "facts", "suggestions": [], "confidence": 0.0, "analysis": "OPENAI_API_KEY não configurado"}

    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key)
    except ImportError:
        return {"module": "facts", "suggestions": [], "confidence": 0.0, "analysis": "Biblioteca openai não instalada"}

    profile_snippet = {
        k: current_profile.get(k)
        for k in ("niche", "offer_description", "target_audience", "warming_social_proof", "brand_name")
    }

    conv_text = format_conversations_for_llm(conversations)

    user_msg = f"""## AI Profile atual (campos relevantes)
{json.dumps(profile_snippet, ensure_ascii=False, indent=2)}

## Conversas observadas
{conv_text}

Extraia os fatos do negócio presentes nas conversas e sugira atualizações para os campos do AI Profile."""

    try:
        raw = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        parsed = json.loads(raw.choices[0].message.content)
    except Exception as exc:
        logger.warning("[spy_agent:facts] LLM error: %s", exc)
        return {"module": "facts", "suggestions": [], "confidence": 0.0, "analysis": f"LLM error: {exc}"}

    return {
        "module": "facts",
        "suggestions": parsed.get("suggestions", []),
        "confidence": float(parsed.get("confidence", 0.5)),
        "analysis": parsed.get("analysis", ""),
    }
