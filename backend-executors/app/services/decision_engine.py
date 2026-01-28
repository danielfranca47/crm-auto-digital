from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.schemas.decision import DecisionOutput
from app.services import fast_path, handoff_policy, llm_service

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


def _sanitize_category_decision(
    decision: DecisionOutput,
    context: Dict[str, Any],
    logger_instance: Optional[logging.Logger] = None,
) -> DecisionOutput:
    allowed = _get_allowed_lead_categories(context)
    if decision.next_action == "ask_qualification":
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

    prompt = _build_prompt(context, message_text)
    try:
        llm_text = llm_service.generate_decision_text(prompt)
        payload = _extract_json_payload(llm_text)
        if payload is None:
            raise ValueError("llm returned invalid json")
        decision = DecisionOutput.model_validate(payload)
        decision = _sanitize_category_decision(decision, context, logger_instance=logger)
        if logger:
            logger.info(
                "decision llm next_action=%s reason=%s",
                decision.next_action,
                decision.reason,
            )
        return handoff_policy.apply(context, decision, logger=logger)
    except Exception:
        if logger:
            logger.warning(
                "decision fallback next_action=%s reason=%s",
                FALLBACK_DECISION.next_action,
                FALLBACK_DECISION.reason,
            )
        return handoff_policy.apply(context, FALLBACK_DECISION, logger=logger)
