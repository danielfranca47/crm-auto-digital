import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core_client import fetch_core_ai_profile_resolve
from database import get_connection
from security_core import CurrentUser, require_crm_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qualification", tags=["Qualification"])

_SDR_MODES = {"sdr_scheduler", "agenda"}

_SYSTEM_PROMPT = """Você é um especialista em configuração de agentes de vendas via WhatsApp.
Sua tarefa é ler os critérios de qualificação de um negócio (escritos em linguagem natural)
e transformá-los em campos de qualificação estruturados para um agente de IA.

## Tipos de agente e como tratar cada um

### SDR / sdr_scheduler / agenda (Alto Ticket, B2B, agendamento de reunião)
O agente faz qualificação profunda antes de agendar uma demo. Os campos são agrupados em 3 filtros:

**F1 — Perfil e Fit** (group: "f1"):
Perguntas de enquadramento — confirma se o lead se encaixa no perfil ideal.
Critérios típicos: segmento de atuação, porte da empresa, região, se é o decisor.
Perguntas curtas e naturais, tom de conversa — nunca parecendo interrogatório.

**F2 — Intenção e Dor** (group: "f2"):
Perguntas abertas de diagnóstico — descobre se há problema real e urgente.
Critérios típicos: maior dificuldade atual, já tentou outra solução, resultado esperado.
Tom consultivo: "entender para ajudar", não "filtrar para vender".

**F3 — 4Ps: Poder, Prioridade, Preço, Timing** (group: "f3"):
Confirmação das condicionantes finais antes de propor agendamento.
Critérios típicos: quem toma decisão, urgência, orçamento, quando quer implementar.
Perguntas podem ser mais diretas aqui.

### closer / direto (Low Ticket, B2C, venda direta na conversa)
Sem grupos — lista plana. Qualificação rápida (2-4 perguntas). Foco: confirmar fit e ir ao pitch.
NÃO use o campo "group" nesses casos.

### consultivo / hybrid_scheduler
Sem grupos — lista plana. Qualificação moderada, foco em entender a dor antes de apresentar.
NÃO use o campo "group" nesses casos.

## Regras obrigatórias

- Crie no máximo 8 campos no total (SDR: máximo 3 por filtro F1/F2/F3)
- Marque como "required" apenas o que é decisivo para qualificar/desqualificar o lead
- Use "optional" para informações úteis mas não bloqueantes
- Nunca crie perguntas redundantes (ex: não crie "faturamento" E "porte da empresa" separados — escolha o mais natural)
- A `question` deve soar natural em WhatsApp — conversacional, nunca estilo formulário
- A `passive_hint` instrui a IA a capturar a informação silenciosamente se o lead mencionar — descreva quando inferir
- A `key` deve ser snake_case único, sem acentos ou caracteres especiais (use prefixo "custom_" para campos não padrão)
- O `label` deve ser em português, curto e claro (2-4 palavras)

## Formato de saída (JSON obrigatório)

Retorne APENAS o seguinte JSON, sem texto adicional fora do objeto:

{
  "fields": [
    {
      "key": "annual_revenue",
      "label": "Faturamento Anual",
      "question": "Qual é o faturamento anual da empresa, aproximadamente?",
      "passive_hint": "Capturar se o lead mencionar valores de faturamento, porte ou número de funcionários",
      "mode": "required",
      "group": "f1"
    }
  ],
  "explanation": "Breve explicação (1-2 frases) das decisões tomadas na geração dos campos"
}

Para agentes que não são SDR/agenda, omita o campo "group" de todos os objetos."""


def _build_user_prompt(
    agent_mode: str,
    niche: Optional[str],
    target_audience: Optional[str],
    criteria_text: str,
) -> str:
    is_sdr = agent_mode in _SDR_MODES
    group_instruction = (
        'Use os grupos f1, f2 e f3 conforme o guia para classificar cada campo.'
        if is_sdr
        else 'NÃO use o campo "group" — lista plana de campos.'
    )
    return (
        f"Tipo de agente: {agent_mode}\n"
        f"Nicho: {niche or 'não informado'}\n"
        f"Público-alvo: {target_audience or 'não informado'}\n\n"
        f"Critérios de qualificação definidos pelo operador:\n---\n{criteria_text}\n---\n\n"
        f"{group_instruction}"
    )


def _load_criteria_text(user_id: int) -> Optional[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT content_text FROM knowledge_items
            WHERE user_id = ? AND category = 'qualification_criteria' AND active_in_funnel = 1
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row["content_text"] if hasattr(row, "__getitem__") else row[0]


def _call_openai(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY não configurada")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as exc:
        logger.error("generate-fields OpenAI error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Erro ao chamar LLM: {exc}")


class GenerateFieldsResponse(BaseModel):
    fields: List[Dict[str, Any]]
    explanation: str


@router.post("/generate-fields", response_model=GenerateFieldsResponse)
async def generate_qualification_fields(
    current_user: CurrentUser = Depends(require_crm_access),
) -> GenerateFieldsResponse:
    criteria_text = _load_criteria_text(current_user.id)
    if not criteria_text or not criteria_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Nenhum conteúdo encontrado em 'Critérios de Qualificação' na base de conhecimento. Preencha esse campo antes de gerar.",
        )

    ai_profile = fetch_core_ai_profile_resolve(current_user.id) or {}
    agent_mode = ai_profile.get("agent_mode") or "sdr_scheduler"
    niche = ai_profile.get("niche")
    target_audience = ai_profile.get("target_audience")

    user_prompt = _build_user_prompt(agent_mode, niche, target_audience, criteria_text)
    result = _call_openai(_SYSTEM_PROMPT, user_prompt)

    raw_fields = result.get("fields")
    if not isinstance(raw_fields, list):
        raise HTTPException(status_code=502, detail="LLM retornou formato inesperado")

    cleaned: List[Dict[str, Any]] = []
    is_sdr = agent_mode in _SDR_MODES
    for f in raw_fields:
        if not isinstance(f, dict) or not f.get("key"):
            continue
        field: Dict[str, Any] = {
            "key": str(f["key"]),
            "label": str(f.get("label", f["key"])),
            "question": str(f.get("question", "")),
            "passive_hint": str(f.get("passive_hint", "")),
            "mode": f.get("mode", "required") if f.get("mode") in {"required", "optional", "off"} else "required",
        }
        if is_sdr and f.get("group") in {"f1", "f2", "f3"}:
            field["group"] = f["group"]
        cleaned.append(field)

    return GenerateFieldsResponse(
        fields=cleaned,
        explanation=str(result.get("explanation", "")),
    )


_FILTER_SYSTEM_PROMPT = """Você é um especialista em configuração de agentes de vendas via WhatsApp.
Sua tarefa é sugerir campos de qualificação para um filtro específico de um agente de IA, com base
nas informações de contexto do negócio fornecidas pelo usuário.

## Filtros SDR e o que cada um representa

**F1 — Perfil e Fit**:
Perguntas de enquadramento — validam se o lead se encaixa no perfil ideal do negócio.
Exemplos: segmento, porte, região, se é o decisor.
Tom: direto, natural, rápido.

**F2 — Intenção e Dor**:
Perguntas abertas de diagnóstico — revelam contexto, urgência e dor real do lead.
Exemplos: maior dificuldade atual, já tentou outra solução, resultado esperado.
Tom: consultivo, empático, exploratório.

**F3 — 4Ps (Poder, Prioridade, Preço, Timing)**:
Confirmação das condicionantes finais antes de propor o próximo passo.
Exemplos: quem decide, urgência, budget, quando quer implementar.
Tom: mais direto, mas ainda conversacional.

## Como gerar os campos

Use o contexto do negócio (nicho, produto, público-alvo, objetivos, instruções customizadas) para
inferir os critérios mais relevantes para o filtro solicitado. Você NÃO precisa de critérios
explícitos — deduza com base no tipo de negócio e no perfil do cliente ideal.

## Regras obrigatórias

- Gere no máximo 3 campos para o filtro solicitado
- Todos os campos devem ter o campo "group" igual ao filtro solicitado (f1, f2 ou f3)
- Nunca repita keys que estiverem na lista "existing_keys" fornecida
- Use "required" para campos decisivos para qualificar/desqualificar; "optional" para os demais
- A `question` deve soar natural em WhatsApp — conversacional, nunca estilo formulário
- A `passive_hint` instrui a IA a capturar silenciosamente se o lead mencionar — descreva quando inferir
- A `key` deve ser snake_case único, sem acentos (use prefixo "custom_" para campos não padrão)
- O `label` deve ser em português, curto e claro (2-4 palavras)

## Formato de saída (JSON obrigatório)

Retorne APENAS o seguinte JSON, sem texto adicional fora do objeto:

{
  "fields": [
    {
      "key": "main_pain",
      "label": "Dor Principal",
      "question": "Qual é a maior dificuldade que você enfrenta hoje com [tema]?",
      "passive_hint": "Capturar se o lead mencionar problemas, dificuldades ou frustrações",
      "mode": "required",
      "group": "f2"
    }
  ],
  "explanation": "Breve explicação (1-2 frases) das decisões tomadas"
}"""


def _build_filter_user_prompt(
    group: str,
    agent_mode: str,
    niche: Optional[str],
    target_audience: Optional[str],
    offer_description: Optional[str],
    goals: Optional[str],
    custom_instructions: Optional[str],
    brand_name: Optional[str],
    existing_keys: List[str],
    criteria_text: Optional[str],
) -> str:
    filter_names = {"f1": "F1 — Perfil e Fit", "f2": "F2 — Intenção e Dor", "f3": "F3 — 4Ps"}
    lines = [
        f"Filtro alvo: {filter_names.get(group, group)} (group: \"{group}\")",
        f"Tipo de agente: {agent_mode}",
        f"Nicho: {niche or 'não informado'}",
        f"Público-alvo: {target_audience or 'não informado'}",
        f"Produto/serviço: {offer_description or 'não informado'}",
        f"Objetivos do agente: {goals or 'não informado'}",
        f"Marca: {brand_name or 'não informado'}",
    ]
    if custom_instructions:
        lines.append(f"Instruções customizadas: {custom_instructions}")
    if criteria_text:
        lines.append(f"\nCritérios de qualificação (base de conhecimento):\n---\n{criteria_text}\n---")
    if existing_keys:
        lines.append(f"\nKeys já existentes (NÃO repita): {', '.join(existing_keys)}")
    lines.append(f"\nGere até 3 campos para o filtro {group.upper()}.")
    return "\n".join(lines)


class GenerateFieldsForFilterRequest(BaseModel):
    group: Literal["f1", "f2", "f3"]
    existing_keys: List[str] = []


@router.post("/generate-fields-for-filter", response_model=GenerateFieldsResponse)
async def generate_fields_for_filter(
    body: GenerateFieldsForFilterRequest,
    current_user: CurrentUser = Depends(require_crm_access),
) -> GenerateFieldsResponse:
    ai_profile = fetch_core_ai_profile_resolve(current_user.id) or {}

    agent_mode = ai_profile.get("agent_mode") or "sdr_scheduler"
    niche = ai_profile.get("niche")
    target_audience = ai_profile.get("target_audience")
    offer_description = ai_profile.get("offer_description")
    goals = ai_profile.get("goals")
    custom_instructions = ai_profile.get("custom_instructions")
    brand_name = ai_profile.get("brand_name")

    criteria_text = _load_criteria_text(current_user.id)

    user_prompt = _build_filter_user_prompt(
        group=body.group,
        agent_mode=agent_mode,
        niche=niche,
        target_audience=target_audience,
        offer_description=offer_description,
        goals=goals,
        custom_instructions=custom_instructions,
        brand_name=brand_name,
        existing_keys=body.existing_keys,
        criteria_text=criteria_text,
    )

    result = _call_openai(_FILTER_SYSTEM_PROMPT, user_prompt)

    raw_fields = result.get("fields")
    if not isinstance(raw_fields, list):
        raise HTTPException(status_code=502, detail="LLM retornou formato inesperado")

    cleaned: List[Dict[str, Any]] = []
    existing_set = set(body.existing_keys)
    for f in raw_fields:
        if not isinstance(f, dict) or not f.get("key"):
            continue
        key = str(f["key"])
        if key in existing_set:
            continue
        field: Dict[str, Any] = {
            "key": key,
            "label": str(f.get("label", key)),
            "question": str(f.get("question", "")),
            "passive_hint": str(f.get("passive_hint", "")),
            "mode": f.get("mode", "required") if f.get("mode") in {"required", "optional", "off"} else "required",
            "group": body.group,
        }
        cleaned.append(field)
        if len(cleaned) >= 3:
            break

    return GenerateFieldsResponse(
        fields=cleaned,
        explanation=str(result.get("explanation", "")),
    )
