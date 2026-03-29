"""
meta_prompter.py — Geração dinâmica de blocos de prompt por nicho (Fase 4).

Chama a LLM para gerar blocos personalizáveis (few-shot examples, tone rules,
objection rewrites, qualification phrasing, outreach scenarios) com base no
ai_profile do usuário. O resultado é armazenado em ai_profiles.generated_prompt_parts
no backend-core via chamada service-to-service.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stub de fallback (sem API key configurada)
# ---------------------------------------------------------------------------

def _stub_prompt_parts() -> Dict[str, Any]:
    return {
        "few_shot_qualification": [],
        "few_shot_apresentation": [],
        "few_shot_followup": [],
        "tone_rules": [],
        "objection_rewrites": [],
        "qualification_phrasing": {},
        "outreach_scenarios": [],
    }


# ---------------------------------------------------------------------------
# Construção do prompt do meta-prompter
# ---------------------------------------------------------------------------

def _build_meta_prompt(ai_profile: Dict[str, Any]) -> str:
    niche = ai_profile.get("niche") or ""
    target_audience = ai_profile.get("target_audience") or ""
    tone_of_voice = ai_profile.get("tone_of_voice") or "profissional"
    offer_description = ai_profile.get("offer_description") or ""
    template_key = ai_profile.get("template_key") or "sdr_padrao"
    agent_mode = ai_profile.get("agent_mode") or "agenda"
    objections_faq = ai_profile.get("objection_common") or ""
    language = "pt-BR"
    max_chars = 320

    # Campos obrigatórios derivados do agent_mode
    _required_by_mode: Dict[str, list] = {
        "consultivo": ["service_interest", "urgency", "decision_role", "constraints", "availability_window", "budget_or_price_acceptance"],
        "agenda": ["service_interest", "urgency", "decision_role", "availability_window"],
        "direto": ["service_interest", "urgency", "decision_role"],
    }
    required_fields = _required_by_mode.get(agent_mode, ["service_interest", "urgency", "decision_role"])

    template_description = {
        "sdr_padrao": "qualificar + agendar reunião",
        "closer_agressivo": "qualificar + vender diretamente",
        "hybrid_scheduler": "aquecer relacionamento + agendar sessão",
        "consultor_especialista": "diagnóstico consultivo + agendamento",
    }.get(template_key, template_key)

    return f"""Você é um META-PROMPTER especializado em criar blocos de prompt para agentes de vendas WhatsApp.

CONTEXTO DO AGENTE:
- Nicho: {niche}
- Público-alvo: {target_audience}
- Tom de voz: {tone_of_voice}
- Oferta: {offer_description}
- Template: {template_key} (fluxo: {template_description})
- Modo: {agent_mode}
- Objeções configuradas pelo usuário: {objections_faq if objections_faq else "(não configuradas)"}
- Campos de qualificação obrigatórios: {json.dumps(required_fields, ensure_ascii=False)}

SUA TAREFA:
Gerar os seguintes blocos em JSON, personalizados para este nicho específico:

1. "few_shot_qualification": Array de 2-3 exemplos de interação na fase de qualificação.
   Cada exemplo: {{"scenario": "descrição curta", "inbound": "mensagem do lead", "expected_output": {{"question_text": "...", "field": "campo", "should_ask": true, "confidence": 0.xx}}}}
   REGRAS: As perguntas devem soar naturais para ESTE nicho. Usar o tom configurado.
   Cobrir: 1 lead cooperativo, 1 lead hesitante, 1 lead com resposta ambígua.

2. "few_shot_apresentation": Array de 2 exemplos de interação na fase de apresentação.
   Para template scheduler/hybrid_scheduler: exemplos de proposta de agendamento natural.
   Para template sales/closer_agressivo: exemplos de pitch curto com oferta.

3. "few_shot_followup": Array de 2 exemplos de reengagement pós-apresentação.
   Para sdr_padrao/consultor_especialista: follow-up consultivo pós-reunião.
   Para closer_agressivo: cart recovery (mensagem curta, máx 280 chars).
   Para hybrid_scheduler: follow-up pós-sessão com tom pessoal.

4. "tone_rules": Array de 3-5 regras concretas de comunicação para este nicho.
   NÃO use adjetivos vagos. Use instruções operacionais diretas.
   Exemplos bons: "tratar por tu", "evitar jargão X", "referir contexto Y do lead".
   Exemplos ruins: "ser simpático", "tom profissional".

5. "objection_rewrites": Array com as objeções reformuladas no formato LAER.
   Cada item: {{"objection": "...", "real_concern": "o que o lead realmente quer dizer", "acknowledge": "validar", "explore": "pergunta exploratória", "respond": "argumento de valor", "next_step": "CTA concreto"}}
   Se objections_faq estiver vazio, gere as 3 objeções mais comuns DESTE nicho.

6. "qualification_phrasing": Objeto com chave = campo de qualificação, valor = array de 2 formas naturais de perguntar este campo NESTE nicho.
   Campos: {json.dumps(required_fields, ensure_ascii=False)}
   Ex para fisioterapia: {{"service_interest": ["O que te traz aqui hoje?", "É uma situação de recuperação ou prevenção?"]}}

7. "outreach_scenarios": Array de 2-3 cenários de prospecção específicos para este nicho.
   Cada cenário: {{"scenario_key": "identificador", "description": "quando usar", "email_angle": "ângulo do e-mail", "whatsapp_angle": "ângulo do WhatsApp", "cta": "call-to-action sugerido"}}
   Os cenários devem refletir situações reais de prospecção NESTE nicho, não cenários genéricos de website.

REGRAS GERAIS:
- Idioma: {language}
- Tom SEMPRE consistente com tone_of_voice configurado
- Mensagens de exemplo com máximo de {max_chars} caracteres
- NUNCA use placeholders genéricos ([nome], [serviço]) — use linguagem natural contextual
- Os exemplos devem parecer conversas WhatsApp reais, não templates de CRM
- Retorne SOMENTE JSON válido, sem texto adicional
"""


# ---------------------------------------------------------------------------
# Chamada à LLM
# ---------------------------------------------------------------------------

def _call_llm(prompt: str) -> str:
    """Chama a LLM para gerar os blocos de prompt. Usa o mesmo endpoint de llm_service."""
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": settings.llm_model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    timeout = httpx.Timeout(max(settings.llm_timeout_seconds, 60.0))
    with httpx.Client(timeout=timeout) as client:
        response = client.post(settings.llm_api_base, headers=headers, json=payload)
    response.raise_for_status()

    # Extrair output_text (mesmo padrão de llm_service._extract_output_text)
    body = response.json()
    output_text = body.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text
    output_items = body.get("output") or []
    chunks: list[str] = []
    for item in output_items:
        contents = item.get("content") if isinstance(item, dict) else None
        if not isinstance(contents, list):
            continue
        for content in contents:
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                chunks.append(content["text"])
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def generate_prompt_parts(ai_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chama a LLM meta-prompter para gerar blocos personalizáveis do prompt
    com base nos dados do ai_profile.

    Retorna dict com chaves:
    - few_shot_qualification: list[dict]
    - few_shot_apresentation: list[dict]
    - few_shot_followup: list[dict]
    - tone_rules: list[str]
    - objection_rewrites: list[dict]  (formato LAER)
    - qualification_phrasing: dict[str, list[str]]
    - outreach_scenarios: list[dict]

    Se llm_api_key não estiver configurado, retorna stub vazio (sem blocos).
    """
    if not settings.llm_api_key:
        logger.info("meta_prompter: llm_api_key não configurado — retornando stub vazio")
        return _stub_prompt_parts()

    prompt = _build_meta_prompt(ai_profile)
    try:
        raw = _call_llm(prompt)
        parts = json.loads(raw)
        if not isinstance(parts, dict):
            logger.warning("meta_prompter: resposta LLM não é dict — usando stub")
            return _stub_prompt_parts()
        # Garantir chaves esperadas com defaults seguros
        defaults = _stub_prompt_parts()
        for key, default_val in defaults.items():
            if key not in parts or parts[key] is None:
                parts[key] = default_val
        return parts
    except Exception as exc:
        logger.error("meta_prompter: erro ao gerar prompt parts — %s", exc)
        return _stub_prompt_parts()


# ---------------------------------------------------------------------------
# Salvar no backend-core via service-to-service
# ---------------------------------------------------------------------------

def save_prompt_parts_to_core(user_id: int, parts: Dict[str, Any]) -> bool:
    """
    Envia os blocos gerados para backend-core via PATCH service-to-service.
    Retorna True se sucesso, False se falhou (não lança exceção — é best-effort).
    """
    token = settings.core_service_token
    if not token:
        logger.warning("meta_prompter: CORE_SERVICE_TOKEN não configurado — não foi possível salvar")
        return False

    base_url = settings.core_api_base.rstrip("/")
    url = f"{base_url}/ai-profiles/{user_id}/generated-prompt-parts"
    headers = {"X-Service-Token": token, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.patch(url, headers=headers, json={"generated_prompt_parts": parts})
        if response.is_success:
            logger.info("meta_prompter: prompt parts salvas para user_id=%s", user_id)
            return True
        logger.warning(
            "meta_prompter: falha ao salvar para user_id=%s status=%s body=%s",
            user_id,
            response.status_code,
            response.text[:200],
        )
        return False
    except Exception as exc:
        logger.error("meta_prompter: erro de rede ao salvar — %s", exc)
        return False


def generate_and_save(user_id: int, ai_profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Gera os blocos de prompt para o ai_profile e salva no backend-core.
    Retorna os blocos gerados (ou None se falhou a geração).
    """
    parts = generate_prompt_parts(ai_profile)
    # Stub vazio não vale a pena salvar — só salvar se houver conteúdo
    has_content = any(
        parts.get(k) for k in ("few_shot_qualification", "tone_rules", "objection_rewrites")
    )
    if has_content:
        save_prompt_parts_to_core(user_id, parts)
    return parts
