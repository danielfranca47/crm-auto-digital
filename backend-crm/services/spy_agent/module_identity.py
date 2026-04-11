from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from .conversation_loader import format_conversations_for_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um especialista em análise de comunicação e configuração de agentes de IA.
Sua tarefa é analisar APENAS as mensagens do VENDEDOR nas conversas fornecidas e extrair padrões
de identidade e estilo de comunicação para configurar o AI Profile.

## O que cada campo realmente faz no sistema

`identity_mode` — define como o agente se apresenta ao lead:
- `virtual_assistant`: Agente se apresenta abertamente como IA/assistente virtual.
  Use quando: vendedor menciona "sou uma IA", "assistente virtual", usa nome impessoal.
- `human_agent`: Agente se apresenta como uma pessoa com nome próprio.
  Use quando: vendedor assina com nome ("Aqui é a Ana"), nunca menciona ser IA, usa linguagem humana natural.
- `user_clone`: Agente imita o estilo exato do dono do negócio como se fosse ele mesmo respondendo.
  Use quando: estilo de escrita é muito personalizado, informal e consistente — como se o próprio dono estivesse no celular.

`template_key` — define o roteiro base de abordagem:
- `sdr_padrao`: Linguagem objetiva e profissional, foco em qualificação rápida e agendamento.
- `consultor_especialista`: Linguagem elaborada, constrói autoridade e confiança antes de ofertar.
- `closer_agressivo`: Linguagem direta e persuasiva, cria urgência, empurra para fechamento rápido.
- `hybrid_scheduler`: Equilibra apresentação da oferta e agendamento — nem 100% consulta, nem 100% fechamento.

`response_style` — define quem lidera o ritmo da conversa:
- `active`: VENDEDOR lidera — faz perguntas proativamente, guia o lead para o próximo passo sem esperar iniciativa.
  Sinais: vendedor sempre termina com uma pergunta, nunca deixa o lead "no vácuo".
- `passive`: VENDEDOR reage — responde o que o lead pergunta, fornece informações quando solicitado.
  Sinais: maioria das mensagens do vendedor são respostas, raramente abre com perguntas.

`tone_of_voice` — tom geral do texto do vendedor. Descreva com adjetivos concretos.
  Ex: "informal e bem-humorado", "profissional e direto", "caloroso e empático", "técnico e detalhado"

## Campos alvo (Módulo de Identidade)
- `tone_of_voice` (str): Tom predominante. Ex: "descontraído e amigável", "profissional e objetivo", "caloroso e empático"
- `response_style` ("active"|"passive"): "active" = vendedor faz perguntas e lidera a conversa; "passive" = vendedor responde ao que o lead pergunta
- `identity_mode` ("virtual_assistant"|"human_agent"|"user_clone"): Como o vendedor se apresenta. "human_agent" se não menciona ser IA.
- `template_key` (str): Template mais próximo — "sdr_padrao", "consultor_especialista", "closer_agressivo" ou "hybrid_scheduler"

## Instrução de resposta
Responda EXCLUSIVAMENTE em JSON com este schema:
{
  "suggestions": [
    {
      "field": "nome_do_campo",
      "current_value": "valor atual (ou null)",
      "suggested_value": "novo valor sugerido",
      "rationale": "Evidência observada nas conversas (em português, máx 2 frases)"
    }
  ],
  "style_signals": {
    "emoji_frequency": "never|occasional|frequent",
    "avg_message_length": "short|medium|long",
    "formality_level": "informal|neutral|formal",
    "asks_questions": true
  },
  "confidence": 0.0-1.0,
  "analysis": "Resumo técnico do estilo de comunicação observado"
}

Regras:
1. Analise SOMENTE mensagens do VENDEDOR (marcadas com [VENDEDOR])
2. Baseie as sugestões em padrões consistentes, não em mensagens isoladas
3. Se o padrão atual parece correto, não inclua na lista
4. Seja conservador — só sugira o que está claramente evidenciado
"""


def analyze_identity(
    conversations: List[Dict[str, Any]],
    current_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Módulo 2: Extrai padrões de identidade e estilo de comunicação do vendedor.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[spy_agent:identity] OPENAI_API_KEY ausente")
        return {"module": "identity", "suggestions": [], "confidence": 0.0, "analysis": "OPENAI_API_KEY não configurado"}

    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key)
    except ImportError:
        return {"module": "identity", "suggestions": [], "confidence": 0.0, "analysis": "Biblioteca openai não instalada"}

    profile_snippet = {
        k: current_profile.get(k)
        for k in ("tone_of_voice", "response_style", "identity_mode", "template_key")
    }

    conv_text = format_conversations_for_llm(conversations)

    user_msg = f"""## AI Profile atual (campos relevantes)
{json.dumps(profile_snippet, ensure_ascii=False, indent=2)}

## Conversas observadas (analise APENAS as mensagens [VENDEDOR])
{conv_text}

Identifique o estilo de comunicação do vendedor e sugira atualizações ao AI Profile."""

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
        logger.warning("[spy_agent:identity] LLM error: %s", exc)
        return {"module": "identity", "suggestions": [], "confidence": 0.0, "analysis": f"LLM error: {exc}"}

    return {
        "module": "identity",
        "suggestions": parsed.get("suggestions", []),
        "style_signals": parsed.get("style_signals", {}),
        "confidence": float(parsed.get("confidence", 0.5)),
        "analysis": parsed.get("analysis", ""),
    }
