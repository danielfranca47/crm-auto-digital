from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.contracts.qualification_contract import (
    SIGNALS_SCHEMA,
    compute_missing_fields,
    infer_extracted_fields,
    required_fields_for_mode,
)

from app.schemas.decision import DecisionOutput
from app.services import fast_path, handoff_policy, llm_service
from app.services.orchestrator_models import ChildResult, MotherDecision

logger = logging.getLogger(__name__)

FALLBACK_DECISION = DecisionOutput(
    next_action="handoff",
    message_text="",
    questions=[],
    reason="llm_failure",
)

BOT_DISABLED_DECISION = DecisionOutput(
    next_action="ignore",
    message_text="",
    questions=[],
    reason="bot_disabled",
)


def _safe_get(data: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def _extract_message_text(context: Dict[str, Any]) -> str:
    metadata = context.get("metadata") or {}
    job = context.get("job") or {}
    payload = job.get("payload") or {}
    return (
        _safe_get(metadata, "inbound_message_text")
        or _safe_get(metadata, "message_text", "text", "body")
        or _safe_get(payload, "message_text", "text", "body")
        or ""
    )


def _format_history(history: list[Dict[str, Any]], limit: int = 10) -> str:
    last_messages = history[-limit:]
    lines = []
    for item in last_messages:
        role = item.get("model") or "unknown"
        body = item.get("body") or ""
        lines.append(f"{role}: {body}")
    return "\n".join(lines)


_SHORT_REPLIES = {
    "sim",
    "nao",
    "não",
    "ok",
    "blz",
    "beleza",
    "pode",
    "claro",
    "👍",
    "😂",
    "kk",
    "kkk",
    "rs",
    "rss",
}

DEFAULT_ALLOWED_LEAD_CATEGORIES = [
    "to-prospect",
    "in-progress",
    "qualification",
    "apresentation",
    "follow-up",
    "closing",
    "client-list",
    "prospect-refused",
    "disqualified",
]


def _normalize_short_reply(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _is_short_reply(text: str) -> bool:
    normalized = _normalize_short_reply(text)
    if not normalized:
        return False
    if normalized in _SHORT_REPLIES:
        return True
    if " " in normalized:
        return False
    return len(normalized) <= 12


def _find_last_outbound_message(history: list[Dict[str, Any]]) -> Optional[str]:
    for item in reversed(history):
        model = (item.get("model") or "").lower()
        if model == "outbound":
            body = str(item.get("body") or "").strip()
            if body:
                return body
    return None


def _get_allowed_lead_categories(context: Dict[str, Any]) -> list[str]:
    metadata = context.get("metadata") or {}
    allowed = metadata.get("allowed_lead_categories")
    if isinstance(allowed, list) and all(isinstance(item, str) for item in allowed):
        return allowed
    return DEFAULT_ALLOWED_LEAD_CATEGORIES




def _normalize_agent_mode(context: Dict[str, Any], mother_decision: Optional[MotherDecision] = None) -> str:
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}

    raw_mode = None
    if mother_decision is not None:
        raw_mode = mother_decision.agent_mode
    if raw_mode is None:
        raw_mode = ai_profile.get("agent_mode")

    normalized = str(raw_mode or "").strip().lower().replace("_", "-")
    if normalized in {"consultivo", "agenda", "direto"}:
        return normalized
    if normalized == "closer":
        return "direto"
    if normalized in {"sdr-scheduler", "sdr"}:
        indicators = [
            ai_profile.get("human_in_loop"),
            ai_profile.get("requires_handoff"),
            playbook.get("human_in_loop"),
            playbook.get("requires_handoff"),
            metadata.get("human_in_loop"),
            metadata.get("requires_handoff"),
        ]
        if any(bool(item) for item in indicators):
            return "consultivo"
        return "agenda"
    template_key = str(ai_profile.get("template_key") or playbook.get("template_key") or "").lower()
    if "closer" in template_key:
        return "direto"
    if "consult" in template_key:
        return "consultivo"
    if "scheduler" in template_key or "sdr" in template_key:
        indicators = [
            ai_profile.get("human_in_loop"),
            ai_profile.get("requires_handoff"),
            playbook.get("human_in_loop"),
            playbook.get("requires_handoff"),
            metadata.get("human_in_loop"),
            metadata.get("requires_handoff"),
        ]
        if any(bool(item) for item in indicators):
            return "consultivo"
        return "agenda"
    return "agenda"


def _extract_meeting_scheduled_signal(mother_decision: MotherDecision) -> bool:
    signals = mother_decision.signals
    if isinstance(signals, dict) and isinstance(signals.get("meeting_scheduled"), bool):
        return bool(signals.get("meeting_scheduled"))
    return "meeting_scheduled" in (mother_decision.reason or "")


def _has_handoff_indicators(context: Dict[str, Any]) -> bool:
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    indicators = [
        ai_profile.get("human_in_loop"),
        ai_profile.get("requires_handoff"),
        playbook.get("human_in_loop"),
        playbook.get("requires_handoff"),
        metadata.get("human_in_loop"),
        metadata.get("requires_handoff"),
    ]
    return any(bool(item) for item in indicators)

def _sanitize_signals_structured(signals: Optional[dict]) -> dict:
    if not isinstance(signals, dict):
        return {}
    return {k: v for k, v in signals.items() if k in SIGNALS_SCHEMA}


def _build_mode_contract_context(context: Dict[str, Any], mother_decision: Optional[MotherDecision] = None) -> Dict[str, Any]:
    mode = _normalize_agent_mode(context, mother_decision)
    extracted = infer_extracted_fields(context)
    missing_fields = compute_missing_fields(mode, extracted)
    required_fields = required_fields_for_mode(mode)
    return {
        "agent_mode_normalized": mode,
        "required_fields": required_fields,
        "missing_fields": missing_fields,
        "extracted_fields": extracted,
    }


def _apply_mode_guardrails(
    decision: DecisionOutput,
    context: Dict[str, Any],
    mother_decision: MotherDecision,
    child_result: ChildResult,
) -> DecisionOutput:
    mode_ctx = _build_mode_contract_context(context, mother_decision)
    mode = mode_ctx["agent_mode_normalized"]
    missing_fields = set(mode_ctx["missing_fields"])

    if mode == "consultivo" and decision.outcome == "won":
        decision.outcome = None

    if mode == "consultivo" and mother_decision.route_to == "closing":
        decision.reason = f"{decision.reason}|consultivo_handoff"
        if decision.decision_trace is None:
            decision.decision_trace = {}
        decision.decision_trace["next_action_hint"] = "handoff"
        if child_result.message_text and "humano" not in child_result.message_text.lower():
            decision.message_text = "Perfeito — vou te encaminhar para um especialista humano finalizar com você."

    if mode == "agenda" and ("availability_window" in missing_fields or "location_preference" in missing_fields):
        if mother_decision.route_to == "closing" or decision.suggested_category == "closing":
            decision.suggested_category = "qualification"
            decision.reason = f"{decision.reason}|guardrail_agenda_missing_booking"
            if decision.decision_trace is None:
                decision.decision_trace = {}
            decision.decision_trace["guardrail_agenda_missing_booking"] = True

    if mode == "direto":
        signals = _sanitize_signals_structured(mother_decision.signals)
        price_ok = signals.get("price_acceptance") in {"yes", True}
        intent_ok = signals.get("intent_level") in {"medium", "high"}
        if not (price_ok and intent_ok) and (mother_decision.route_to == "closing" or decision.suggested_category == "closing"):
            decision.suggested_category = "qualification"
            decision.reason = f"{decision.reason}|guardrail_direto_pullback"
            if decision.decision_trace is None:
                decision.decision_trace = {}
            decision.decision_trace["guardrail_direto_pullback"] = True

    return decision


def _sanitize_category_decision(
    decision: DecisionOutput,
    context: Dict[str, Any],
    logger_instance: Optional[logging.Logger] = None,
) -> DecisionOutput:
    allowed = _get_allowed_lead_categories(context)
    if decision.next_action == "ask_qualification":
        if decision.category_reason and "child_recommended" in decision.category_reason:
            return decision
        decision.suggested_category = None
        decision.category_reason = None
        return decision
    suggested = decision.suggested_category
    if suggested is None:
        return decision
    if suggested not in allowed:
        job = context.get("job") or {}
        payload = job.get("payload") or {}
        lead = context.get("lead") or {}
        log = logger_instance or logger
        log.info(
            "event=invalid_category_from_llm suggested_category=%s job_id=%s lead_id=%s user_id=%s",
            suggested,
            job.get("id") or payload.get("job_id"),
            lead.get("id") or payload.get("lead_id"),
            lead.get("user_id") or payload.get("user_id"),
        )
        decision.suggested_category = None
        decision.category_reason = None
    return decision


def _build_prompt(context: Dict[str, Any], message_text: str) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _safe_get(lead, "contactName", "companyName", "name"),
        "phone": _safe_get(lead, "phone", "phone_e164"),
        "segment": lead.get("segment"),
        "status": lead.get("status"),
        "category": lead.get("category"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "template_key": ai_profile.get("template_key"),
        "agent_mode": ai_profile.get("agent_mode"),
        "brand_name": ai_profile.get("brand_name"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "target_audience": ai_profile.get("target_audience"),
        "offer_description": ai_profile.get("offer_description"),
        "goals": ai_profile.get("goals"),
        "custom_instructions": ai_profile.get("custom_instructions"),
        "identity_mode": ai_profile.get("identity_mode"),
        "handoff_policy": ai_profile.get("handoff_policy"),
        "handoff_custom_text": ai_profile.get("handoff_custom_text"),
    }
    playbook_summary = {"template_key": playbook.get("template_key") or playbook.get("name")}
    metadata_summary = {
        "provider": metadata.get("provider"),
        "instance_id": metadata.get("instance_id"),
    }

    history_text = _format_history(history)
    last_bot_message = None
    short_reply_hint = None
    if _is_short_reply(message_text):
        last_bot_message = _find_last_outbound_message(history)
        if last_bot_message:
            short_reply_hint = (
                "message_text é resposta direta ao last_bot_message; não iniciar um novo assunto"
            )

    allowed_categories = _get_allowed_lead_categories(context)
    mode_contract = _build_mode_contract_context(context)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]

    return (
        "Você é um motor de decisão de um CRM (WhatsApp). Você deve retornar SOMENTE um JSON VÁLIDO (sem texto extra) no formato:\n"
        "\n"
        "{\n"
        '  "next_action": "reply|ask_qualification|handoff|ignore",\n'
        '  "message_text": "string (obrigatório quando next_action=reply ou ask_qualification; pode ser vazio em handoff/ignore)",\n'
        '  "questions": ["..."], \n'
        '  "reason": "curto",\n'
        '  "suggested_category": "opcional (um dos valores de ALLOWED_LEAD_CATEGORIES) ou null",\n'
        '  "category_reason": "opcional (curto) ou null"\n'
        "}\n"
        "\n"
        "REGRAS IMPORTANTES:\n"
        "1) Responda SOMENTE com JSON. Não use markdown. Não use texto antes/depois do JSON.\n"
        "2) next_action é obrigatório.\n"
        "3) questions:\n"
        '   - Só faz sentido quando next_action == "ask_qualification".\n'
        '   - Se next_action != "ask_qualification", retorne questions: [].\n'
        "4) message_text:\n"
        '   - É obrigatório quando next_action == "reply" OU "ask_qualification".\n'
        '   - Se next_action == "ask_qualification", message_text deve conter a pergunta pronta para WhatsApp (1 pergunta curta e objetiva).\n'
        "5) suggested_category e category_reason:\n"
        '   - suggested_category significa ESTÁGIO DO FUNIL (LeadStatus do CRM). NÃO é nicho/tema (ex.: "Marketing" é inválido).\n'
        "   - suggested_category só pode ser UM dos valores em ALLOWED_LEAD_CATEGORIES ou null.\n"
        '   - Se next_action == "ask_qualification", então:\n'
        "     - suggested_category DEVE ser null\n"
        "     - category_reason DEVE ser null\n"
        '     (mesmo se houver palavras fortes como "quero", "comprar", "preço", etc.)\n'
        '   - Se next_action != "ask_qualification", suggested_category só deve ser enviado quando houver sinal claro no inbound (texto não vazio e intenção explícita).\n'
        "   - Se você NÃO tiver certeza do suggested_category, retorne suggested_category=null e category_reason=null.\n"
        "   - Nunca invente categorias fora de ALLOWED_LEAD_CATEGORIES.\n"
        "   - Se o inbound for genérico/curto e não houver sinal explícito, suggested_category deve ser null.\n"
        "6) Handoff:\n"
        '   - Use next_action="handoff" apenas se o usuário explicitamente pedir humano/suporte/atendente, ou equivalente muito claro.\n'
        "   - Caso contrário, prefira reply ou ask_qualification.\n"
        "7) Short reply:\n"
        "   - Se short_reply_hint estiver presente, trate message_text como resposta direta ao last_bot_message e NÃO inicie novo assunto.\n"
        "\n"
        "TESTES MENTAIS (não copie texto literal; apenas use como guia):\n"
        "- Se o usuário só disser 'oi' ou algo genérico, você provavelmente deve perguntar UMA coisa (ask_qualification) e NÃO sugerir categoria.\n"
        "- Se o usuário pedir preço/contratar/fechar, responda objetivamente e só sugira categoria se estiver MUITO claro que é estágio do funil.\n"
        "- Se houver dúvida sobre o estágio, retorne suggested_category=null.\n"
        "\n"
        "CONTEXTO DO CRM (use para decidir):\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- ALLOWED_LEAD_CATEGORIES: {json.dumps(allowed_categories, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- last_bot_message: {last_bot_message or ''}\n"
        f"- short_reply_hint: {short_reply_hint or ''}\n"
        f"- agent_mode_normalized: {agent_mode_normalized}\n"
        f"- required_fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"- missing_fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        f"- inbound_message_text: {message_text}\n"
    )


def _build_mother_prompt(context: Dict[str, Any], message_text: str) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _safe_get(lead, "contactName", "companyName", "name"),
        "segment": lead.get("segment"),
        "status": lead.get("status"),
        "category": lead.get("category"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "template_key": ai_profile.get("template_key"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "target_audience": ai_profile.get("target_audience"),
        "agent_mode": ai_profile.get("agent_mode"),
    }
    playbook_summary = {"template_key": playbook.get("template_key") or playbook.get("name")}
    metadata_summary = {
        "provider": metadata.get("provider"),
        "instance_id": metadata.get("instance_id"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    return (
        "Você é um roteador MÃE de um CRM (WhatsApp). Retorne SOMENTE JSON válido:\n"
        "{\n"
        '  "route_to": "qualification|apresentation|follow-up|closing",\n'
        '  "perceived_category": "qualification|apresentation|follow-up|closing|null",\n'
        '  "confidence": 0.0,\n'
        '  "reason": "curto",\n'
        '  "agent_mode": "consultivo|agenda|direto|null (opcional)",\n'
        '  "signals": {"meeting_scheduled": true|false, "intent_level": "low|medium|high", "urgency_level": "low|medium|high", "price_acceptance": "no|unsure|yes"} (opcional),\n'
        '  "objective": "string curta opcional",\n'
        '  "next_action_hint": "reply|ask_qualification|handoff|ignore|null (opcional)"\n'
        "}\n"
        "Regras:\n"
        "- route_to é obrigatório e indica a próxima fase a focar.\n"
        "- perceived_category indica o estágio atual do lead (sua percepção).\n"
        "- Se estiver em dúvida e lead.category existir, mantenha perceived_category = lead.category (evite null).\n"
        "- Use perceived_category=null somente se lead.category estiver vazio E não houver sinal claro no inbound.\n"
        "- confidence entre 0 e 1.\n"
        "- reason curto.\n"
        "- Preencha signals seguindo schema padronizado quando possível (intent_level, urgency_level, price_acceptance, meeting_scheduled, handoff_requested, missing_fields, stop_reason).\n"
        "- Em price_acceptance use SEMPRE string: no|unsure|yes (não use boolean).\n"
        "- Se o lead aceitar o preço/valor, use price_acceptance='yes'.\n"
        "- Use missing_fields para decidir: enquanto faltarem campos mínimos do modo, prefira route_to=qualification.\n"
        "\n"
        "DEFINIÇÃO DO FUNIL (IMPORTANTE):\n"
        "- APRESENTATION inclui: agendar reunião, confirmar horário, marcar call, lembrar da reunião,\n"
        "  reagendar, enviar link da call, confirmar presença.\n"
        '  => route_to="apresentation" e perceived_category="apresentation".\n'
        "- FOLLOW-UP é SOMENTE após a apresentação quando o lead não fechou, com sinais de nutrição,\n"
        '  ex.: "vou pensar", "me chama mês que vem", "manda material", "preciso falar com sócio",\n'
        '  "agora não", "sem budget", "vamos ver depois".\n'
        "- REGRA FORTE FOLLOW-UP: só use follow-up se houver evidência de apresentação realizada,\n"
        "  seja por history (ex.: \"na call de ontem\", \"como falamos na apresentação\")\n"
        "  OU se lead.category atual já for follow-up/closing. Se for apenas apresentation e não houver\n"
        "  evidência textual de que a call aconteceu, prefira apresentation.\n"
        "  Se não houver evidência, mantenha qualification ou apresentation conforme o contexto.\n"
        "- Qualification: dúvidas iniciais (preço/como funciona/serve pra mim) sem combinação de horário/link.\n"
        "- Apresentation: qualquer ação de agendar/confirmar/reagendar/pedir link/confirmar presença.\n"
        "\n"
        # ETAPA 4 (roadmap): o marcador "meeting_scheduled" em reason é provisório.
        # Nesta etapa usamos sinal textual simples para orientar o executor, mas a Etapa 4
        # deve migrar isso para um sinal estruturado (ex.: fields JSON/signals) e o CRM
        # será responsável por criar appointment e setar bot_disabled.
        "POLÍTICA POR MODO (agent_mode):\n"
        "- consultivo: não fechar sozinho; qualificar, preparar handoff e agendar quando aplicável.\n"
        "- agenda: foco em vender até booking e confirmar presença.\n"
        "- direto: foco em fechamento objetivo e comercial.\n"
        "- sdr_scheduler: compatível com agenda/consultivo (normalização no executor).\n"
        "  - Se agendar/confirmar/reagendar/pedir link, route_to=apresentation e perceived_category=apresentation.\n"
        "  - Se confirmação de horário/link fechado (ex.: \"Fechou amanhã 17h\", \"pode confirmar\", \"manda o link\"),\n"
        '    prefira signals.meeting_scheduled=true e mantenha substring "meeting_scheduled" no reason por compatibilidade.\n'
        "- closer: foco em avançar até fechamento.\n"
        "  - Agendamento NÃO é objetivo final; meeting_scheduled deve ficar false, salvo agendamento real com necessidade operacional.\n"
        "  - Se inbound for claramente de fechamento (\"posso assinar\", \"manda contrato\", \"quero fechar\"),\n"
        "    route_to=closing e perceived_category=closing.\n"
        "\n"
        "EXEMPLOS (ultracurtos):\n"
        '1) inbound_message_text: "Amanhã 17h tá confirmado"\n'
        '   -> {"route_to":"apresentation","perceived_category":"apresentation","confidence":0.8,"reason":"meeting_scheduled|confirmou horário"}\n'
        '2) inbound_message_text: "Pode reagendar pra sexta?"\n'
        '   -> {"route_to":"apresentation","perceived_category":"apresentation","confidence":0.8,"reason":"meeting_scheduled|reagendar"}\n'
        '3) inbound_message_text: "Vou pensar, me chama mês que vem" (apresentação já ocorreu)\n'
        '   -> {"route_to":"follow-up","perceived_category":"follow-up","confidence":0.7,"reason":"nutrição pós-apresentação"}\n'
        '4) NEGATIVO: inbound_message_text: "Vou pensar" (sem evidência de apresentação)\n'
        '   -> NÃO use follow-up; mantenha qualification ou apresentation conforme contexto.\n'
        '5) NEGATIVO: inbound_message_text: "Qual o preço?"\n'
        '   -> NÃO use closing; prefira qualification.\n'
        "6) SDR: inbound_message_text: \"Fechou amanhã 17h, manda o link\"\n"
        '   -> {"route_to":"apresentation","perceived_category":"apresentation","confidence":0.85,"reason":"meeting_scheduled|confirmou horário"}\n'
        "7) SDR: inbound_message_text: \"Pode confirmar a reunião?\"\n"
        '   -> {"route_to":"apresentation","perceived_category":"apresentation","confidence":0.8,"reason":"meeting_scheduled|confirmou reunião"}\n'
        "8) CLOSER: inbound_message_text: \"Posso assinar hoje?\"\n"
        '   -> {"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"intenção de fechamento"}\n'
        "9) CLOSER: inbound_message_text: \"Manda contrato\"\n"
        '   -> {"route_to":"closing","perceived_category":"closing","confidence":0.85,"reason":"pedido de contrato"}\n'
        "10) CLOSER (negativo): inbound_message_text: \"Fechou amanhã 17h\"\n"
        '   -> {"route_to":"apresentation","perceived_category":"apresentation","confidence":0.8,"reason":"confirmou horário (no closer, sem meeting_scheduled)"}\n'
        "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- agent_mode_normalized: {agent_mode_normalized}\n"
        f"- required_fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"- missing_fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        f"- inbound_message_text: {message_text}\n"
    )


def _build_child_prompt(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _safe_get(lead, "contactName", "companyName", "name"),
        "category": lead.get("category"),
        "segment": lead.get("segment"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "template_key": ai_profile.get("template_key"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "agent_mode": ai_profile.get("agent_mode"),
    }
    playbook_summary = {"template_key": playbook.get("template_key") or playbook.get("name")}
    metadata_summary = {
        "provider": metadata.get("provider"),
        "instance_id": metadata.get("instance_id"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    return (
        "Você é uma LLM FILHA e deve responder SOMENTE JSON válido:\n"
        "{\n"
        '  "message_text": "string",\n'
        '  "did_complete_phase": false,\n'
        '  "recommended_next_category": "qualification|apresentation|follow-up|closing|null",\n'
        '  "outcome": "won|lost|null",\n'
        '  "kanban_highlight": "green|orange|null",\n'
        '  "signals": ["..."],\n'
        '  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false} (opcional),\n'
        '  "confidence": 0.0\n'
        "}\n"
        "Regras:\n"
        "- confidence entre 0 e 1.\n"
        "- recommended_next_category deve ser um estágio do funil ou null.\n"
        "- message_text é a resposta para o WhatsApp.\n"
        "\n"
        f"ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})\n"
        f"Motivo MÃE: {mother_decision.reason}\n"
        "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- agent_mode_normalized: {agent_mode_normalized}\n"
        f"- required_fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"- missing_fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        f"- inbound_message_text: {message_text}\n"
    )


def _build_child_prompt_qualification(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _safe_get(lead, "contactName", "companyName", "name"),
        "category": lead.get("category"),
        "segment": lead.get("segment"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "brand_name": ai_profile.get("brand_name"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "agent_mode": ai_profile.get("agent_mode"),
    }
    playbook_summary = {
        "template_key": playbook.get("template_key") or playbook.get("name"),
        "max_chars": playbook.get("max_chars"),
    }
    metadata_summary = {
        "provider": metadata.get("provider"),
        "instance_id": metadata.get("instance_id"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    return (
        "Você é a FILHA QUALIFICATION e deve responder SOMENTE JSON válido:\n"
        "{\n"
        '  "message_text": "string",\n'
        '  "did_complete_phase": false,\n'
        '  "recommended_next_category": "apresentation|null",\n'
        '  "outcome": null,\n'
        '  "kanban_highlight": null,\n'
        '  "signals": ["..."],\n'
        '  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false} (opcional),\n'
        '  "confidence": 0.0\n'
        "}\n"
        "Regras:\n"
        "- message_text é obrigatório e deve conter no máximo 1 pergunta objetiva por turno.\n"
        "- NÃO agendar reunião aqui (só agendar na rota apresentation, salvo pedido explícito do inbound).\n"
        "- Use tone_of_voice, brand_name e niche quando disponíveis.\n"
        "- Respeite playbook.max_chars se existir (senão, resposta curta).\n"
        "- recommended_next_category pode ser null ou 'apresentation' (micro-ajuste de avanço).\n- Priorize perguntar o próximo item de missing_fields (1 por vez).\n"
        "- outcome e kanban_highlight devem ser null.\n"
        "\n"
        f"ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})\n"
        f"Motivo MÃE: {mother_decision.reason}\n"
        "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- agent_mode_normalized: {agent_mode_normalized}\n"
        f"- required_fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"- missing_fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        f"- inbound_message_text: {message_text}\n"
    )


def _build_child_prompt_apresentation(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _safe_get(lead, "contactName", "companyName", "name"),
        "category": lead.get("category"),
        "segment": lead.get("segment"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "brand_name": ai_profile.get("brand_name"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "agent_mode": ai_profile.get("agent_mode"),
    }
    playbook_summary = {
        "template_key": playbook.get("template_key") or playbook.get("name"),
        "max_chars": playbook.get("max_chars"),
    }
    metadata_summary = {
        "provider": metadata.get("provider"),
        "instance_id": metadata.get("instance_id"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    return (
        "Você é a FILHA APRESENTATION e deve responder SOMENTE JSON válido:\n"
        "{\n"
        '  "message_text": "string",\n'
        '  "did_complete_phase": false,\n'
        '  "recommended_next_category": null,\n'
        '  "outcome": null,\n'
        '  "kanban_highlight": null,\n'
        '  "signals": ["..."],\n'
        '  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false} (opcional),\n'
        '  "confidence": 0.0\n'
        "}\n"
        "Regras:\n"
        "- message_text é obrigatório e deve lidar com agenda: pedir dia/horário, confirmar, reagendar, enviar link.\n"
        "- Se agent_mode for sdr_scheduler e mother_decision.reason contiver meeting_scheduled, confirme horário\n"
        "  e indique que enviará/confirmará o link (sem criar appointment).\n"
        "- Se agent_mode for closer, mantenha postura de avanço comercial, mas ainda trate o agendamento.\n"
        "- Use tone_of_voice, brand_name e niche quando disponíveis.\n"
        "- Respeite playbook.max_chars se existir (senão, resposta curta).\n"
        "- recommended_next_category deve ser null.\n"
        "- outcome e kanban_highlight devem ser null.\n"
        "\n"
        f"ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})\n"
        f"Motivo MÃE: {mother_decision.reason}\n"
        "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- agent_mode_normalized: {agent_mode_normalized}\n"
        f"- required_fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"- missing_fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        f"- inbound_message_text: {message_text}\n"
    )



def _build_child_prompt_follow_up(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _safe_get(lead, "contactName", "companyName", "name"),
        "category": lead.get("category"),
        "segment": lead.get("segment"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "brand_name": ai_profile.get("brand_name"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "agent_mode": ai_profile.get("agent_mode"),
    }
    playbook_summary = {
        "template_key": playbook.get("template_key") or playbook.get("name"),
        "max_chars": playbook.get("max_chars"),
    }
    metadata_summary = {
        "provider": metadata.get("provider"),
        "instance_id": metadata.get("instance_id"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    return (
        "Você é a FILHA FOLLOW-UP e deve responder SOMENTE JSON válido:\n"
        "{\n"
        '  "message_text": "string",\n'
        '  "did_complete_phase": false,\n'
        '  "recommended_next_category": "follow-up|closing|null",\n'
        '  "outcome": null,\n'
        '  "kanban_highlight": null,\n'
        '  "signals": ["..."],\n'
        '  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false} (opcional),\n'
        '  "confidence": 0.0\n'
        "}\n"
        "Regras por modo:\n"
        "- consultivo: fazer nutrição/retomada/reagendar e preparar handoff quando pedido de proposta/fechamento.\n"
        "- agenda: foco em no-show/reagendar/confirmar presença e reforçar próximos passos.\n"
        "- direto: tratar objeções e conduzir CTA para pagamento de forma objetiva.\n"
        "- Use tone_of_voice, brand_name e niche quando disponíveis.\n"
        "- Respeite playbook.max_chars se existir (senão, resposta curta).\n"
        "- recommended_next_category pode ser follow-up, closing ou null.\n- Faça no máximo 1 pergunta por mensagem e priorize o próximo missing_field.\n"
        "- outcome e kanban_highlight devem ser null.\n"
        "\n"
        f"ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})\n"
        f"Motivo MÃE: {mother_decision.reason}\n"
        f"Objetivo MÃE: {mother_decision.objective or ''}\n"
        f"Modo normalizado: {agent_mode_normalized}\n"
        f"Required fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"Missing fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- inbound_message_text: {message_text}\n"
    )


def _build_child_prompt_closing(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _safe_get(lead, "contactName", "companyName", "name"),
        "category": lead.get("category"),
        "segment": lead.get("segment"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "brand_name": ai_profile.get("brand_name"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "agent_mode": ai_profile.get("agent_mode"),
    }
    playbook_summary = {
        "template_key": playbook.get("template_key") or playbook.get("name"),
        "max_chars": playbook.get("max_chars"),
    }
    metadata_summary = {
        "provider": metadata.get("provider"),
        "instance_id": metadata.get("instance_id"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    return (
        "Você é a FILHA CLOSING e deve responder SOMENTE JSON válido:\n"
        "{\n"
        '  "message_text": "string",\n'
        '  "did_complete_phase": false,\n'
        '  "recommended_next_category": "closing|null",\n'
        '  "outcome": "won|lost|null",\n'
        '  "kanban_highlight": "green|orange|null",\n'
        '  "signals": ["..."],\n'
        '  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false} (opcional),\n'
        '  "confidence": 0.0\n'
        "}\n"
        "Regras por modo:\n"
        "- consultivo: não fechar sozinho; responder curto e sugerir encaminhamento para humano.\n"
        "- agenda: fechamento operacional (confirmar horário, políticas e pagamento quando aplicável).\n"
        "- direto: conduzir fechamento e confirmação de pagamento com objetividade.\n"
        "- Use tone_of_voice, brand_name e niche quando disponíveis.\n"
        "- Respeite playbook.max_chars se existir (senão, resposta curta).\n"
        "- Faça no máximo 1 pergunta por mensagem e priorize o próximo missing_field.\n"
        "\n"
        f"ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})\n"
        f"Motivo MÃE: {mother_decision.reason}\n"
        f"Objetivo MÃE: {mother_decision.objective or ''}\n"
        f"Modo normalizado: {agent_mode_normalized}\n"
        f"Required fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"Missing fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- inbound_message_text: {message_text}\n"
    )

def _extract_json_payload(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None


def _truncate_snip(text: Optional[str], limit: int = 300) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _normalize_null_strings(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    targets = {"outcome", "kanban_highlight", "recommended_next_category", "perceived_category"}
    normalized = dict(payload)
    for key in targets:
        if key not in normalized:
            continue
        value = normalized.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"null", "none", ""}:
                normalized[key] = None
    return normalized


def _normalize_category(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).strip().lower().replace("_", "-")
    return normalized or None


_ALLOWED_ADVANCE = {
    "qualification": {"apresentation"},
    "apresentation": {"closing", "follow-up"},
    "follow-up": {"closing"},
}

_STAGE_ORDER = ["qualification", "apresentation", "follow-up", "closing"]
_STAGE_INDEX = {stage: index for index, stage in enumerate(_STAGE_ORDER)}


def _is_sdr_escalate_closing(context: Dict[str, Any], mother_decision: MotherDecision) -> bool:
    normalized_mode = _normalize_agent_mode(context, mother_decision)
    if normalized_mode != "agenda":
        return False

    ai_profile = context.get("ai_profile") or {}
    raw_mode = str(ai_profile.get("agent_mode") or "").strip().lower()
    should_block = raw_mode in {"sdr_scheduler", "sdr"} or _has_handoff_indicators(context)
    if not should_block:
        return False

    route = _normalize_category(mother_decision.route_to)
    perceived = _normalize_category(mother_decision.perceived_category)
    return route == "closing" or perceived == "closing"


def apply_outcome_guardrails(
    current_category: Optional[str],
    child_result: ChildResult,
) -> tuple[Optional[str], Optional[str]]:
    normalized_current = _normalize_category(current_category)
    # Guardrail UX: kanban_highlight/outcome são sinais visuais
    # e só podem ser emitidos quando o lead estiver em 'closing'.
    # Nunca permitir highlight fora dessa fase, mesmo que a LLM retorne.
    outcome = child_result.outcome
    highlight = child_result.kanban_highlight
    if not normalized_current:
        return outcome, highlight
    if normalized_current != "closing":
        return None, None
    return outcome, highlight


def apply_mother_category_guardrails(
    current_category: Optional[str],
    mother_decision: MotherDecision,
) -> tuple[Optional[str], Optional[str], str]:
    normalized_current = _normalize_category(current_category)
    perceived = _normalize_category(mother_decision.perceived_category)
    if not perceived:
        return None, None, "missing_perceived"
    if perceived not in _STAGE_INDEX:
        return None, None, "invalid"
    if normalized_current and normalized_current not in _STAGE_INDEX:
        normalized_current = None

    if not normalized_current:
        category_reason = (
            f"mother_perceived:{perceived}|confidence:{mother_decision.confidence:.2f}|"
            f"reason:{mother_decision.reason}"
        )
        return perceived, category_reason, "no_current_accept"

    if normalized_current == perceived:
        return None, None, "same_stage"

    current_index = _STAGE_INDEX.get(normalized_current)
    perceived_index = _STAGE_INDEX.get(perceived)
    if current_index is None or perceived_index is None:
        return None, None, "invalid"

    if perceived_index < current_index:
        return None, None, "backwards_block"

    allowed_next = _ALLOWED_ADVANCE.get(normalized_current, set())
    if perceived in allowed_next:
        category_reason = (
            f"mother_perceived:{perceived}|confidence:{mother_decision.confidence:.2f}|"
            f"reason:{mother_decision.reason}"
        )
        return perceived, category_reason, "ok"

    if len(allowed_next) != 1:
        return None, None, "jump_blocked"
    next_allowed = next(iter(allowed_next))
    if mother_decision.confidence >= 0.70:
        category_reason = (
            f"mother_perceived:{perceived}|confidence:{mother_decision.confidence:.2f}|"
            f"reason:{mother_decision.reason}"
        )
        return next_allowed, category_reason, "jump_clamped"
    return None, None, "jump_blocked_low_conf"


def _apply_child_micro_adjustment(
    *,
    base_category: Optional[str],
    child_result: ChildResult,
    category_reason: Optional[str],
    mother_route_to: str,
) -> tuple[Optional[str], Optional[str]]:
    if mother_route_to != "qualification":
        return base_category, category_reason
    recommended = _normalize_category(child_result.recommended_next_category)
    if not recommended:
        return base_category, category_reason
    if not child_result.did_complete_phase:
        return base_category, category_reason
    normalized_base = _normalize_category(base_category)
    if not normalized_base:
        return base_category, category_reason
    allowed_next = _ALLOWED_ADVANCE.get(normalized_base, set())
    if recommended not in allowed_next:
        return base_category, category_reason
    reason = category_reason or ""
    if reason:
        reason = f"{reason}|child_recommended:{recommended}"
    else:
        reason = f"child_recommended:{recommended}"
    return recommended, reason


def compose_decision_output(
    *,
    context: Dict[str, Any],
    mother_decision: MotherDecision,
    child_result: ChildResult,
) -> DecisionOutput:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    current_category = lead.get("category")
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    suggested_category, category_reason, guardrail_reason = apply_mother_category_guardrails(
        current_category,
        mother_decision,
    )
    suggested_category, category_reason = _apply_child_micro_adjustment(
        base_category=suggested_category or current_category,
        child_result=child_result,
        category_reason=category_reason,
        mother_route_to=mother_decision.route_to,
    )
    outcome, highlight = apply_outcome_guardrails(current_category, child_result)
    next_action = "ask_qualification" if mother_decision.route_to == "qualification" else "reply"
    reason = f"route:{mother_decision.route_to}|{mother_decision.reason}"
    # NOTE (ETAPA 4): decision_trace é observabilidade apenas; não dispara efeitos colaterais.
    # A Etapa 4 deverá consumir sinais estruturados para automações no CRM (appointment/bot_disabled).
    meeting_scheduled = _extract_meeting_scheduled_signal(mother_decision)
    decision = DecisionOutput(
        next_action=next_action,
        message_text=child_result.message_text or "",
        questions=[],
        reason=reason,
        suggested_category=suggested_category,
        category_reason=category_reason,
        outcome=outcome,
        kanban_highlight=highlight,
        signals=child_result.signals,
        confidence=child_result.confidence,
        decision_trace={
            "mother_route_to": mother_decision.route_to,
            "mother_perceived_category": mother_decision.perceived_category,
            "mother_confidence": mother_decision.confidence,
            "lead_current_category": current_category,
            "guardrail_reason": guardrail_reason,
            "agent_mode": ai_profile.get("agent_mode"),
            "agent_mode_normalized": agent_mode_normalized,
            "meeting_scheduled": meeting_scheduled,
            "mother_objective": mother_decision.objective,
            "next_action_hint": mother_decision.next_action_hint,
            "required_fields": mode_contract['required_fields'],
            "missing_fields": mode_contract['missing_fields'],
            "child_signals_structured": child_result.signals_structured if isinstance(child_result.signals_structured, dict) else None,
            "mother_signals": {
                "meeting_scheduled": meeting_scheduled,
                "intent_level": ((mother_decision.signals or {}).get("intent_level") if isinstance(mother_decision.signals, dict) else None),
                "urgency_level": ((mother_decision.signals or {}).get("urgency_level") if isinstance(mother_decision.signals, dict) else None),
                "price_acceptance": ((mother_decision.signals or {}).get("price_acceptance") if isinstance(mother_decision.signals, dict) else None),
                "handoff_requested": ((mother_decision.signals or {}).get("handoff_requested") if isinstance(mother_decision.signals, dict) else None),
                "stop_reason": ((mother_decision.signals or {}).get("stop_reason") if isinstance(mother_decision.signals, dict) else None),
            },
        },
    )
    decision = _apply_mode_guardrails(decision, context, mother_decision, child_result)
    return decision


def decide(context: Dict[str, Any], logger: Optional[logging.Logger] = None) -> DecisionOutput:
    metadata = context.get("metadata") or {}
    if metadata.get("bot_disabled"):
        if logger:
            logger.info(
                "decision bot_disabled next_action=%s reason=%s",
                BOT_DISABLED_DECISION.next_action,
                BOT_DISABLED_DECISION.reason,
            )
        return BOT_DISABLED_DECISION

    message_text = _extract_message_text(context)
    fast_decision = fast_path.try_fast_handoff(message_text)
    if fast_decision:
        if logger:
            logger.info(
                "decision fast_path next_action=%s reason=%s",
                fast_decision.next_action,
                fast_decision.reason,
            )
        fast_decision = _sanitize_category_decision(fast_decision, context, logger_instance=logger)
        return handoff_policy.apply(context, fast_decision, logger=logger)

    stage = "start"
    mother_text: Optional[str] = None
    child_text: Optional[str] = None
    try:
        mother_prompt = _build_mother_prompt(context, message_text)
        stage = "mother_call"
        mother_text = llm_service.generate_mother_route(mother_prompt)
        stage = "mother_parse"
        mother_payload = _extract_json_payload(mother_text)
        if mother_payload is None:
            raise ValueError("llm returned invalid mother json")
        mother_payload = _normalize_null_strings(mother_payload)
        stage = "mother_validate"
        mother_decision = MotherDecision.model_validate(mother_payload)

        if _is_sdr_escalate_closing(context, mother_decision):
            reason = f"guardrail_sdr_escalate_closing|{mother_decision.reason}"
            return DecisionOutput(
                next_action="ignore",
                message_text="",
                questions=[],
                reason=reason,
                suggested_category="closing",
                category_reason="guardrail_sdr_escalate_closing",
                outcome=None,
                kanban_highlight=None,
                signals=[],
                confidence=mother_decision.confidence,
                decision_trace={
                    "mother_route_to": mother_decision.route_to,
                    "mother_perceived_category": mother_decision.perceived_category,
                    "mother_confidence": mother_decision.confidence,
                    "agent_mode": (context.get("ai_profile") or {}).get("agent_mode"),
                    "agent_mode_normalized": _normalize_agent_mode(context, mother_decision),
                    "guardrail_sdr_escalate_closing": True,
                    "suppressed_reply": True,
                },
            )
        if mother_decision.route_to == "qualification":
            child_prompt = _build_child_prompt_qualification(context, message_text, mother_decision)
        elif mother_decision.route_to == "apresentation":
            child_prompt = _build_child_prompt_apresentation(context, message_text, mother_decision)
        elif mother_decision.route_to == "follow-up":
            try:
                child_prompt = _build_child_prompt_follow_up(context, message_text, mother_decision)
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
        elif mother_decision.route_to == "closing":
            try:
                child_prompt = _build_child_prompt_closing(context, message_text, mother_decision)
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
        else:
            child_prompt = _build_child_prompt(context, message_text, mother_decision)
        stage = "child_call"
        child_text = llm_service.generate_child_result(mother_decision.route_to, child_prompt)
        stage = "child_parse"
        child_payload = _extract_json_payload(child_text)
        if child_payload is None:
            raise ValueError("llm returned invalid child json")
        child_payload = _normalize_null_strings(child_payload)
        stage = "child_validate"
        child_result = ChildResult.model_validate(child_payload)

        stage = "compose"
        decision = compose_decision_output(
            context=context,
            mother_decision=mother_decision,
            child_result=child_result,
        )
        decision = _sanitize_category_decision(decision, context, logger_instance=logger)
        if decision.decision_trace and isinstance(decision.decision_trace, dict):
            decision.decision_trace["suggested_category_final"] = decision.suggested_category
        if logger:
            job = context.get("job") or {}
            payload = job.get("payload") or {}
            lead = context.get("lead") or {}
            log_context = {
                "job_id": job.get("id") or payload.get("job_id"),
                "lead_id": lead.get("id") or payload.get("lead_id"),
                "user_id": lead.get("user_id") or payload.get("user_id"),
            }
            trace = decision.decision_trace if isinstance(decision.decision_trace, dict) else {}
            logger.info(
                "decision_mother_category route_to=%s perceived=%s mother_conf=%.2f lead_current=%s "
                "suggested=%s guardrail=%s job_id=%s lead_id=%s user_id=%s",
                trace.get("mother_route_to"),
                trace.get("mother_perceived_category"),
                trace.get("mother_confidence") or 0.0,
                trace.get("lead_current_category"),
                decision.suggested_category,
                trace.get("guardrail_reason"),
                log_context["job_id"],
                log_context["lead_id"],
                log_context["user_id"],
            )
            logger.info(
                "decision llm next_action=%s reason=%s",
                decision.next_action,
                decision.reason,
            )
        return handoff_policy.apply(context, decision, logger=logger)
    except Exception as exc:
        if logger:
            logger.warning(
                "event=llm_orchestrator_error stage=%s exc_type=%s exc=%s mother_text_snip=%s child_text_snip=%s",
                stage,
                type(exc).__name__,
                exc,
                _truncate_snip(mother_text),
                _truncate_snip(child_text),
            )
            logger.warning(
                "decision fallback next_action=%s reason=%s",
                FALLBACK_DECISION.next_action,
                FALLBACK_DECISION.reason,
            )
        return handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)
