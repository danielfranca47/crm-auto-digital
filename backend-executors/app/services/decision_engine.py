from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.schemas.decision import DecisionOutput
from app.services import fast_path, handoff_policy, llm_service

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

    return (
        "Você é um motor de decisão para um CRM. Retorne SOMENTE JSON válido com o formato:\n"
        '{ "next_action":"reply|ask_qualification|handoff|ignore",'
        ' "message_text":"string (obrigatório para reply/ask_qualification)",'
        ' "questions":["..."], "reason":"curto",'
        ' "suggested_category":"opcional (LeadStatus canônico)",'
        ' "category_reason":"opcional (curto)" }\n'
        "Regras:\n"
        "- next_action é obrigatório\n"
        "- questions só faz sentido se next_action == ask_qualification\n"
        "- message_text é obrigatório quando next_action == ask_qualification e deve conter a(s) pergunta(s) já formatada(s) para envio no WhatsApp\n"
        "- message_text pode ser vazio apenas em handoff ou ignore\n"
        "- reason deve ser curta\n"
        "- suggested_category só deve ser enviado quando houver sinal do lead no inbound_message_text (texto não vazio)\n"
        "- Exceção explícita: se o texto contiver palavras fortes como quero, comprar, agendar, reunião, preço, contratar, fechar\n"
        "Contexto:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- last_bot_message: {last_bot_message or ''}\n"
        f"- short_reply_hint: {short_reply_hint or ''}\n"
        f"- message_text: {message_text}\n"
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
        return handoff_policy.apply(context, fast_decision, logger=logger)

    prompt = _build_prompt(context, message_text)
    try:
        llm_text = llm_service.generate_decision_text(prompt)
        payload = _extract_json_payload(llm_text)
        if payload is None:
            raise ValueError("llm returned invalid json")
        decision = DecisionOutput.model_validate(payload)
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
