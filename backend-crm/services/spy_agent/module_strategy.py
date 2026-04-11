from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from .conversation_loader import format_conversations_for_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_LEARN = """Você é um especialista em estratégia de vendas e configuração de agentes de IA.
Sua tarefa é analisar threads completos de conversa de vendas e extrair a estratégia comercial praticada.

## O que cada agent_mode realmente faz no sistema

`sdr_scheduler` (sinônimo: `agenda`):
  Bot age como SDR: qualifica brevemente e empurra para agendar reunião/visita.
  Fluxo: saudação → 2–3 perguntas de qualificação → proposta de horário/data.
  Use quando: o fechamento ocorre em reunião/visita presencial; o WhatsApp é canal de triagem.
  Sinais nas conversas: vendedor pergunta disponibilidade, propõe horários específicos, convida para ligação ou visita.

`consultivo`:
  Bot conduz venda consultiva completa via chat — diagnóstico profundo antes de qualquer oferta.
  Fluxo: saudação → 5–8 perguntas de diagnóstico → solução personalizada → objeções → fechamento no chat.
  Use quando: serviço de ticket alto, exige confiança, ciclo de venda médio/longo (dias ou semanas).
  Sinais: vendedor faz muitas perguntas antes de citar preço, personaliza a proposta, cita problema específico do lead.

`direto` (sinônimo: `closer`):
  Bot apresenta oferta rapidamente e fecha no próprio chat.
  Fluxo: saudação → 1–2 perguntas rápidas → preço → fechamento imediato.
  Use quando: produto/serviço tem preço fixo, não exige personalização, ciclo curto (e-commerce, infoproduto, assinatura simples).
  Sinais: preço mencionado cedo, senso de urgência ("só hoje", "vagas limitadas"), fechamento no mesmo dia.

## O que cada qualification_required_fields realmente faz
Campos marcados aqui bloqueiam a progressão do lead no pipeline até serem coletados.
Escolha APENAS os que o vendedor realmente pergunta em TODAS as conversas:
- `service_interest`: qual serviço/produto específico o lead quer
- `urgency`: quão urgente é a necessidade (agora, dentro de X meses, sem pressa)
- `decision_role`: se o lead tem autonomia para decidir a compra
- `price_acceptance`: se o lead reconheceu o preço sem desistir
- `availability_window`: disponibilidade de horário (essencial para modos agenda/sdr)
- `location`: localização geográfica (relevante quando serviço é presencial)
- `company_size`: tamanho da empresa (B2B com ticket variável por porte)
- `budget`: faixa de orçamento disponível

## O que cada handoff_policy realmente faz
- `disable_bot`: bot para completamente quando humano assume — ideal se vendedor prefere tomar a conversa sem interferência
- `keep_active_notify`: bot continua mas registra o handoff internamente — para times que monitoram e assumem seletivamente
- `ignore`: bot ignora sinais de transferência e continua respondendo — para fluxos 100% automatizados

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

## O que cada agent_mode realmente faz no sistema

`sdr_scheduler` (sinônimo: `agenda`):
  Bot qualifica brevemente e empurra para agendar reunião/visita. O fechamento ocorre fora do chat.
  Use quando: serviço que exige visita/reunião presencial; WhatsApp é só triagem.
  Sinais: conversas terminam em "vou te mandar horários", "podemos marcar uma visita?", agendamentos.

`consultivo`:
  Bot faz diagnóstico aprofundado (5–8 perguntas) antes de apresentar qualquer oferta.
  Ticket alto, ciclo médio/longo, confiança é fator crítico de compra.
  Sinais: vendedor pergunta muito antes de citar preço, personaliza proposta, ciclo de dias/semanas.

`direto` (sinônimo: `closer`):
  Bot apresenta oferta rapidamente e fecha no chat — ciclo curto, preço fixo.
  Use quando: produto/serviço simples, sem personalização, venda no mesmo dia.
  Sinais: preço citado cedo, urgência ("só hoje"), fechamento em poucas mensagens.

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
