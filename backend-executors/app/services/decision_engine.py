from __future__ import annotations

import json
import logging
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app.contracts.qualification_contract import (
    SIGNALS_SCHEMA,
    compute_missing_fields,
    infer_extracted_fields,
    required_fields_for_mode,
)

from app.clients import crm_client
from app.core.config import settings
from app.schemas.decision import DecisionOutput
from app.services import fast_path, field_extractor, handoff_policy, llm_service
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


BUYING_SIGNAL_DEFAULTS: List[str] = [
    "quanto custa",
    "qual o valor",
    "como assino",
    "qual o contrato",
    "como faço para contratar",
    "aceita cartão",
    "tem parcelamento",
    "quando começa",
    "qual o prazo",
    "me manda a proposta",
]

_AGENT1_MODES = {"consultivo", "agenda"}


def _normalize_str(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _detect_buying_signals(message_text: str, keywords_list: Optional[List[str]]) -> bool:
    """Retorna True se message_text contém alguma keyword de compra (Agent 1)."""
    keywords = keywords_list if keywords_list else BUYING_SIGNAL_DEFAULTS
    normalized_msg = _normalize_str(message_text or "")
    for kw in keywords:
        if _normalize_str(kw) in normalized_msg:
            return True
    return False


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


def _is_followup_tick_context(context: Dict[str, Any]) -> bool:
    job = context.get("job") or {}
    job_type = str(job.get("type") or "").strip().lower()
    if job_type == "whatsapp.followup.tick":
        return True
    metadata = context.get("metadata") or {}
    return isinstance(metadata.get("followup_context"), dict) and bool(metadata.get("followup_context"))


def _format_history(history: list[Dict[str, Any]], limit: int = 10) -> str:
    last_messages = history[-limit:]
    lines = []
    for item in last_messages:
        role = item.get("model") or "unknown"
        body = item.get("body") or ""
        lines.append(f"{role}: {body}")
    return "\n".join(lines)


_SHORT_REPLIES = {
    "😂",
    "kk",
    "kkk",
    "rs",
    "rss",
}

_ESCAPE_HATCH_BLOCK = (
    "\nQUANDO NÃO SOUBER RESPONDER:\n"
    "- Se não tem informação suficiente para responder com confiança → retorne confidence < 0.5\n"
    "- Em message_text, faça uma pergunta de esclarecimento em vez de inventar\n"
    "- Se o lead fez uma pergunta técnica fora do knowledge fornecido, use:\n"
    "  'Vou confirmar essa informação com a equipa e já te respondo.'\n"
    "  E retorne signals_structured.handoff_requested = true\n"
)


def _build_validation_block(max_chars: Optional[int]) -> str:
    max_chars_label = str(max_chars) if max_chars else "N/D"
    return (
        "\nVALIDAÇÃO — VERIFICAR ANTES DE RETORNAR:\n"
        "- Se should_ask=true → field DEVE estar preenchido com o current_field\n"
        "- Se checkout_sent=true → message_text DEVE conter uma URL real (não placeholder)\n"
        "- Se did_complete_phase=true → recommended_next_category DEVE estar preenchido\n"
        "- confidence DEVE refletir a certeza real (não usar 0.85 como padrão)\n"
        f"- message_text NÃO deve exceder {max_chars_label} caracteres\n"
    )

def _inject_generated_parts(prompt: str, context: Dict[str, Any], phase: str) -> str:
    """Injeta blocos gerados pelo meta-prompter no prompt da filha (Fase 4 — Tarefa 4.2).

    Fase 4 é aditiva: se generated_prompt_parts for null/vazio, o prompt volta inalterado.
    """
    parts = context.get("generated_prompt_parts") or {}
    if not parts:
        return prompt

    # --- Few-shot examples ---
    few_shot_key = f"few_shot_{phase}"  # qualification, apresentation, followup
    examples = parts.get(few_shot_key)
    if examples:
        prompt += "\n\nEXEMPLOS DE REFERÊNCIA PARA ESTE NICHO (adapte ao contexto atual, não copie):\n"
        for ex in examples:
            prompt += f"\nCenário: {ex.get('scenario', '')}\n"
            prompt += f"Lead: \"{ex.get('inbound', '')}\"\n"
            prompt += f"Resposta esperada: {json.dumps(ex.get('expected_output', {}), ensure_ascii=False)}\n"

    # --- Tone rules ---
    tone_rules = parts.get("tone_rules")
    if tone_rules:
        prompt += "\n\nREGRAS DE TOM PARA ESTE NICHO:\n"
        for rule in tone_rules:
            prompt += f"- {rule}\n"

    # --- Qualification phrasing (apenas para filha qualification) ---
    if phase == "qualification":
        phrasing = parts.get("qualification_phrasing") or {}
        current_field = context.get("current_field")
        if not current_field:
            # Tentar derivar do contexto de qualificação
            qual_state = context.get("qualification_state") or {}
            current_field = qual_state.get("current_field")
        if current_field and current_field in phrasing:
            prompt += f"\n\nFORMAS NATURAIS DE PERGUNTAR '{current_field}' NESTE NICHO:\n"
            for p in phrasing[current_field]:
                prompt += f"- {p}\n"

    # --- Objection rewrites (para apresentation e follow-up) ---
    if phase in ("apresentation", "followup"):
        rewrites = parts.get("objection_rewrites")
        if rewrites:
            prompt += "\n\nOBJEÇÕES REFORMULADAS (formato LAER — usar quando o lead levantar objeção):\n"
            for obj in rewrites:
                prompt += (
                    f"\nObjeção: \"{obj.get('objection', '')}\"\n"
                    f"  Causa real: {obj.get('real_concern', '')}\n"
                    f"  Reconhecer: {obj.get('acknowledge', '')}\n"
                    f"  Explorar: {obj.get('explore', '')}\n"
                    f"  Responder: {obj.get('respond', '')}\n"
                    f"  Próximo passo: {obj.get('next_step', '')}\n"
                )

    return prompt


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




QUALIFICATION_FIELD_FALLBACK_LABELS = {
    "service_interest": "qual serviço/procedimento você busca",
    "urgency": "seu nível de urgência",
    "decision_role": "quem decide essa contratação",
    "constraints": "suas restrições principais",
    "availability_window": "melhor período/horário",
    "budget_or_price_acceptance": "faixa de investimento",
    "location_preference": "preferência de local (online/presencial)",
    "price_acceptance": "aceite do valor",
}


def _build_custom_instructions_block(ai_profile: Dict[str, Any]) -> str:
    """Gera bloco de instruções personalizadas do operador com prioridade máxima."""
    ci = (ai_profile.get("custom_instructions") or "").strip()
    if not ci:
        return ""
    return (
        "\nINSTRUÇÕES PERSONALIZADAS DO OPERADOR (prioridade máxima — seguir à risca):\n"
        f"{ci}\n"
    )


def _build_qualification_fields_block(ai_profile: Dict[str, Any], response_style: str) -> str:
    """Gera bloco de campos de qualificação configurados pelo usuário para injeção no prompt da filha.

    Modo ativo: expõe obrigatórios (com question) e desejáveis (nice_to_collect).
    Modo passivo: expõe apenas passive_hints (captura silenciosa) e closing_questions.
    Retorna string vazia se qualification_fields não estiver configurado.
    """
    qual_fields = ai_profile.get("qualification_fields")
    if not qual_fields or not isinstance(qual_fields, list):
        return ""

    if response_style == "passive":
        passive_fields = [
            f for f in qual_fields
            if isinstance(f, dict) and f.get("passive_hint") and f.get("mode") in ("required", "optional")
        ]
        closing_fields = [
            f for f in qual_fields
            if isinstance(f, dict) and f.get("allow_closing_question") and f.get("closing_question") and f.get("mode") != "off"
        ]
        if not passive_fields and not closing_fields:
            return ""
        block = "\nCAMPOS DE QUALIFICAÇÃO (MODO PASSIVO — captura silenciosa):\n"
        if passive_fields:
            block += "Registrar internamente se o lead mencionar (NÃO perguntar):\n"
            for f in passive_fields:
                label = f.get("label") or f.get("key", "")
                hint = f.get("passive_hint", "")
                tag = "[OBRIGATÓRIO]" if f.get("mode") == "required" else "[DESEJÁVEL]"
                block += f"- {label} {tag} (key: {f.get('key', '')}): {hint}\n"
        if closing_fields:
            block += "Closing questions permitidas (únicas perguntas permitidas no modo passivo):\n"
            for f in closing_fields:
                label = f.get("label") or f.get("key", "")
                cq = f.get("closing_question", "")
                block += f'- {label}: "{cq}"\n'
        return block
    else:
        required_fields = [f for f in qual_fields if isinstance(f, dict) and f.get("mode") == "required"]
        optional_fields = [f for f in qual_fields if isinstance(f, dict) and f.get("mode") == "optional"]
        if not required_fields and not optional_fields:
            return ""
        block = "\nCAMPOS DE QUALIFICAÇÃO CONFIGURADOS:\n"
        if required_fields:
            block += "OBRIGATÓRIOS — usar a question configurada ao perguntar:\n"
            for f in required_fields:
                label = f.get("label") or f.get("key", "")
                question = f.get("question", "")
                hint = f.get("passive_hint", "")
                line = f"- {label} (key: {f.get('key', '')})"
                if question:
                    line += f': pergunta → "{question}"'
                if hint:
                    line += f' | inferir: "{hint}"'
                block += line + "\n"
        if optional_fields:
            block += "DESEJÁVEIS — capturar se surgir oportunidade natural:\n"
            for f in optional_fields:
                label = f.get("label") or f.get("key", "")
                question = f.get("question", "")
                hint = f.get("passive_hint", "")
                line = f"- {label} (key: {f.get('key', '')})"
                if question:
                    line += f': pergunta → "{question}"'
                if hint:
                    line += f' | inferir: "{hint}"'
                block += line + "\n"
        return block


def _build_tone_block(ai_profile: Dict[str, Any], playbook: Dict[str, Any]) -> str:
    """Gera o bloco de regras de tom WhatsApp operacional (Tarefa 2.1)."""
    tone_of_voice = str(ai_profile.get("tone_of_voice") or "profissional")
    max_chars = playbook.get("max_chars") or "N/D"
    template_key = str(
        ai_profile.get("template_key") or playbook.get("template_key") or ""
    ).strip().lower()
    brand_name = str(ai_profile.get("brand_name") or "").strip()

    block = (
        f"\nTOM DE VOZ — REGRAS WHATSAPP:\n"
        f"- Tom configurado: {tone_of_voice}\n"
        f"- Comprimento máximo: {max_chars} caracteres\n"
        f"- Formato: 1 parágrafo curto ou 2–3 linhas. Sem bullet points. Sem formatação markdown.\n"
        f"- Linguagem: conversacional, como se escrevesse a um colega. Sem jargão corporativo.\n"
        f"- Abertura: nunca comece com 'Olá, tudo bem?' genérico se já houve conversa anterior. "
        f"Use o contexto: referir algo que o lead disse antes, ou o campo recém-coletado.\n"
        f"- Encerramento: sempre feche com UMA pergunta ou UM próximo passo claro. Nunca dois.\n"
        f"- PROIBIDO: emojis excessivos (máx 1 por mensagem), CAPS LOCK, exclamações consecutivas (!!), "
        f"linguagem de vendas agressiva ('IMPERDÍVEL', 'CORRA', 'NÃO PERCA').\n"
    )
    if template_key == "hybrid_scheduler":
        if brand_name:
            block += (
                f"- Persona: fale como se fosse o assistente pessoal do {brand_name}, não como vendedor.\n"
                f"- Referência ao profissional: use 'o/a {brand_name}' na terceira pessoa. "
                f"Ex: 'A Dra. Maria tem horário disponível terça e quinta.'\n"
            )
        else:
            block += (
                "- Persona: fale como se fosse o assistente pessoal do profissional, não como vendedor.\n"
                "- Referência ao profissional: use o nome do profissional na terceira pessoa.\n"
            )
    return block


def _select_current_field(missing_fields: list[str], filled_fields: list[str]) -> Optional[str]:
    if not missing_fields:
        return None
    filled = set(filled_fields or [])
    for field in missing_fields:
        if field not in filled:
            return field
    return None


def _fallback_question_for_field(field: Optional[str]) -> str:
    label = QUALIFICATION_FIELD_FALLBACK_LABELS.get(field or "", "esse ponto")
    return f"Pode me confirmar: {label}?"


def _normalize_question_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _question_similarity(a: str, b: str) -> float:
    na = _normalize_question_text(a)
    nb = _normalize_question_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()
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




def _compute_system_agent_mode(context: Dict[str, Any]) -> tuple[str, str]:
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}

    raw_mode = ai_profile.get("agent_mode")
    normalized = str(raw_mode or "").strip().lower().replace("_", "-")
    if normalized in {"consultivo", "agenda", "direto"}:
        return normalized, "ai_profile"
    if normalized == "closer":
        return "direto", "legacy"
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
            return "consultivo", "legacy"
        return "agenda", "legacy"
    template_key = str(ai_profile.get("template_key") or playbook.get("template_key") or "").lower()
    if "closer" in template_key:
        return "direto", "template_fallback"
    if "consult" in template_key:
        return "consultivo", "template_fallback"
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
            return "consultivo", "template_fallback"
        return "agenda", "template_fallback"
    return "agenda", "unknown"


def _normalize_agent_mode(context: Dict[str, Any], mother_decision: Optional[MotherDecision] = None) -> str:
    system_mode, _ = _compute_system_agent_mode(context)
    return system_mode


def _get_mother_mode_conflict(context: Dict[str, Any], mother_decision: Optional[MotherDecision]) -> tuple[Optional[str], bool]:
    if mother_decision is None:
        return None, False
    raw = mother_decision.agent_mode
    if raw is None:
        return None, False
    mother_mode = str(raw).strip().lower().replace("_", "-")
    if not mother_mode:
        return None, False
    system_mode, _ = _compute_system_agent_mode(context)
    return mother_mode, mother_mode != system_mode


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

def _resolve_presentation_variant(context: Dict[str, Any], mode_normalized: Optional[str] = None) -> tuple[str, str]:
    ai_profile = context.get("ai_profile") or {}
    metadata = context.get("metadata") or {}

    force_metadata_variant = bool(metadata.get("force_presentation_variant"))
    raw_metadata = str(metadata.get("presentation_variant") or "").strip().lower()
    if force_metadata_variant and raw_metadata in {"sales", "scheduler"}:
        return raw_metadata, "bundle_metadata_forced"

    raw_profile = str(ai_profile.get("presentation_variant") or "").strip().lower()
    if raw_profile in {"sales", "scheduler"}:
        return raw_profile, "ai_profile"

    # Metadata can fill only when profile is unavailable (no AI profile context).
    if not ai_profile and raw_metadata in {"sales", "scheduler"}:
        return raw_metadata, "bundle_metadata_fallback"

    mode = mode_normalized or _normalize_agent_mode(context)
    if mode == "direto":
        return "sales", "agent_mode_default"
    if mode in {"agenda", "consultivo"}:
        return "scheduler", "agent_mode_default"
    return "scheduler", "fallback"


def _resolve_hybrid_flow_style(context: Dict[str, Any]) -> Optional[str]:
    ai_profile = context.get("ai_profile") or {}
    metadata = context.get("metadata") or {}

    raw_metadata = str(metadata.get("hybrid_flow_style") or "").strip().lower()
    if raw_metadata in {"offer_then_schedule", "schedule_then_offer"}:
        return raw_metadata

    raw_profile = str(ai_profile.get("hybrid_flow_style") or "").strip().lower()
    if raw_profile in {"offer_then_schedule", "schedule_then_offer"}:
        return raw_profile
    return None


def _build_offer_pack_summary(context: Dict[str, Any]) -> dict:
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}

    offer_pack = ai_profile.get("offer_pack")
    if offer_pack is None:
        offer_pack = playbook.get("offer_pack")
    if isinstance(offer_pack, str):
        try:
            parsed = json.loads(offer_pack)
            offer_pack = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            offer_pack = None
    elif not isinstance(offer_pack, dict):
        offer_pack = None

    if not offer_pack:
        fallback_description = str(ai_profile.get("offer_description") or "").strip()
        if not fallback_description:
            return {"available": False, "source": "none", "items": [], "cta_text": None, "disclaimers": []}
        return {
            "available": False,
            "source": "offer_description_fallback",
            "items": [{"name": "Oferta principal", "description": fallback_description, "checkout_link": None}],
            "cta_text": None,
            "disclaimers": [],
        }

    items = offer_pack.get("items") if isinstance(offer_pack.get("items"), list) else []
    normalized_items = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        normalized_items.append({
            "name": item.get("name"),
            "price": item.get("price"),
            "description": item.get("description"),
            "bullets": item.get("bullets") if isinstance(item.get("bullets"), list) else [],
            "proof": item.get("proof") if isinstance(item.get("proof"), list) else [],
            "faq": item.get("faq") if isinstance(item.get("faq"), list) else [],
            "checkout_link": item.get("checkout_link"),
        })

    return {
        "available": bool(normalized_items),
        "source": "offer_pack",
        "items": normalized_items,
        "cta_text": offer_pack.get("cta_text"),
        "disclaimers": offer_pack.get("disclaimers") if isinstance(offer_pack.get("disclaimers"), list) else [],
        "media_url": offer_pack.get("media_url"),
        "media_type": offer_pack.get("media_type"),
        "anchor_price": offer_pack.get("anchor_price"),
        "guarantee_text": offer_pack.get("guarantee_text"),
        "upsell_message": offer_pack.get("upsell_message"),
    }


def _sanitize_signals_structured(signals: Optional[dict]) -> dict:
    if not isinstance(signals, dict):
        return {}
    return {k: v for k, v in signals.items() if k in SIGNALS_SCHEMA}


def _normalize_scheduler_child_signals(
    context: Dict[str, Any],
    mother_decision: MotherDecision,
    child_result: ChildResult,
    *,
    effective_route_to: str,
    presentation_variant: str,
) -> Optional[dict]:
    raw = child_result.signals_structured if isinstance(child_result.signals_structured, dict) else None

    template_key = str((context.get("ai_profile") or {}).get("template_key") or "").strip().lower()
    agent_mode = _normalize_agent_mode(context, mother_decision)
    is_scheduler_context = (
        effective_route_to == "apresentation"
        and presentation_variant == "scheduler"
        and (agent_mode == "agenda" or template_key == "hybrid_scheduler")
    )
    if not is_scheduler_context:
        return raw

    normalized = dict(raw or {})
    meeting_candidate = normalized.get("meeting_datetime_candidate")
    if isinstance(meeting_candidate, str):
        meeting_candidate = meeting_candidate.strip() or None
    elif meeting_candidate is not None:
        meeting_candidate = str(meeting_candidate).strip() or None

    meeting_proposed = normalized.get("meeting_proposed")
    if not isinstance(meeting_proposed, bool):
        meeting_proposed = False
    if meeting_candidate is not None:
        meeting_proposed = True
    if meeting_proposed is False:
        meeting_candidate = None

    normalized["meeting_proposed"] = meeting_proposed
    normalized["meeting_datetime_candidate"] = meeting_candidate
    return normalized


def _is_filled_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _qualification_state_from_context(context: Dict[str, Any]) -> dict:
    state = context.get("qualification_state")
    if not isinstance(state, dict):
        return {}
    if state.get("exists") is False:
        return {}
    data = state.get("data_json")
    if not isinstance(data, dict):
        data = {}
    state["data_json"] = data
    attempts = state.get("attempts_json")
    if not isinstance(attempts, dict):
        attempts = {}
    state["attempts_json"] = attempts
    asked = state.get("asked_questions_json")
    if not isinstance(asked, list):
        asked = []
    state["asked_questions_json"] = [item for item in asked if isinstance(item, dict)]
    last_question_text = state.get("last_question_text")
    if not isinstance(last_question_text, str):
        last_question_text = ""
    state["last_question_text"] = last_question_text
    return state


def _get_heuristic_reason(context: Dict[str, Any]) -> str:
    state = context.get("qualification_state")
    if not isinstance(state, dict):
        return "crm_no_state"
    if state.get("exists") is False:
        return "exists_false"
    return "state_absent"


def _get_required_fields_override(context: Dict[str, Any]) -> Optional[List[str]]:
    """Lê qualification_required_fields do ai_profile. None = usar defaults do modo."""
    ai_profile = context.get("ai_profile") or {}
    override = ai_profile.get("qualification_required_fields")
    if isinstance(override, list):
        return [str(f) for f in override if isinstance(f, str)]
    return None


def _build_mode_contract_context(context: Dict[str, Any], mother_decision: Optional[MotherDecision] = None) -> Dict[str, Any]:
    mode = _normalize_agent_mode(context, mother_decision)
    override = _get_required_fields_override(context)
    required_fields = required_fields_for_mode(mode, required_fields_override=override)
    qualification_state = _qualification_state_from_context(context)

    state_data = qualification_state.get("data_json") if qualification_state else None
    if isinstance(state_data, dict) and qualification_state:
        filled_fields = [field for field, value in state_data.items() if _is_filled_value(value)]
        missing_fields = [field for field in required_fields if field not in filled_fields]
        return {
            "agent_mode_normalized": mode,
            "required_fields": required_fields,
            "missing_fields": missing_fields,
            "extracted_fields": state_data,
            "filled_fields": filled_fields,
            "missing_fields_source": "state",
            "last_questioned_field": qualification_state.get("last_questioned_field"),
            "attempts_json": qualification_state.get("attempts_json") or {},
            "asked_questions_json": qualification_state.get("asked_questions_json") or [],
            "last_question_text": qualification_state.get("last_question_text") or "",
        }

    if int(getattr(settings, "qualification_heuristic_fallback", 1) or 0) == 0:
        return {
            "agent_mode_normalized": mode,
            "required_fields": required_fields,
            "missing_fields": list(required_fields),
            "extracted_fields": {},
            "filled_fields": [],
            "missing_fields_source": "state_unavailable",
            "last_questioned_field": None,
            "attempts_json": {},
            "asked_questions_json": [],
            "last_question_text": "",
        }

    extracted = infer_extracted_fields(context)
    missing_fields = compute_missing_fields(mode, extracted, required_fields_override=override)
    filled_fields = [field for field in required_fields if _is_filled_value(extracted.get(field))]
    return {
        "agent_mode_normalized": mode,
        "required_fields": required_fields,
        "missing_fields": missing_fields,
        "extracted_fields": extracted,
        "filled_fields": filled_fields,
        "missing_fields_source": "heuristic",
        "last_questioned_field": None,
        "attempts_json": {},
        "asked_questions_json": [],
        "last_question_text": "",
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

    lead_origin_label = metadata.get("lead_origin_label") or "INBOUND (lead veio te procurar)"
    _is_outbound_lead = (metadata.get("lead_origin") or "inbound") == "outbound"
    origin_opener = (
        ai_profile.get("origin_outbound_opener") if _is_outbound_lead else ai_profile.get("origin_inbound_opener")
    ) or ""

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
        f"- current_field: {json.dumps(_select_current_field(mode_contract['missing_fields'], mode_contract.get('filled_fields') or []), ensure_ascii=False)}\n"
        f"- asked_questions_for_current_field: {json.dumps([q.get('question_text') for q in (mode_contract.get('asked_questions_json') or []) if isinstance(q, dict) and q.get('field') == _select_current_field(mode_contract['missing_fields'], mode_contract.get('filled_fields') or [])][-2:], ensure_ascii=False)}\n"
        f"- last_question_text: {json.dumps(mode_contract.get('last_question_text') or '', ensure_ascii=False)}\n"
        f"- lead_origin: {lead_origin_label}\n"
        f"- origin_opener: {origin_opener}\n"
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

    lead_origin_label = metadata.get("lead_origin_label") or "INBOUND (lead veio te procurar)"
    _is_outbound_lead = (metadata.get("lead_origin") or "inbound") == "outbound"
    origin_opener = (
        ai_profile.get("origin_outbound_opener") if _is_outbound_lead else ai_profile.get("origin_inbound_opener")
    ) or ""

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    return (
        f"Você é o ROTEADOR MÃE de um CRM de vendas WhatsApp.\n\n"
        f"PAPEL: Decidir para qual fase do funil rotear o lead. Você NÃO gera mensagem para o lead.\n"
        f"ESCOPO: Retornar route_to + sinais + confidence. Nunca gerar message_text.\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary['template_key']}. Missing fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}.\n"
        "RECUSAS: Nunca retorne route_to=\"follow-up\" sem evidência textual de apresentação realizada. agent_mode DEVE ser null (vem do sistema).\n\n"
        "Antes de decidir o route_to, raciocine internamente:\n"
        "1. O lead tem missing_fields? Se sim → qualification (obrigatório)\n"
        "2. Há evidência de apresentação/sessão já realizada? Se sim, qual foi o resultado?\n"
        "3. O lead demonstrou intenção de compra/agendamento? Qual o nível?\n"
        "4. A mensagem é uma resposta a algo que o bot perguntou, ou é espontânea?\n\n"
        "Use o campo \"reason\" para documentar o raciocínio em 1-2 frases curtas.\n\n"
        "Retorne SOMENTE JSON válido no schema MotherDecision:\n"
        "{\n"
        '  "route_to": "qualification|apresentation|follow-up|closing",\n'
        '  "perceived_category": "qualification|apresentation|follow-up|closing|null",\n'
        '  "confidence": 0.0,\n'
        '  "reason": "curto",\n'
        '  "agent_mode": null (opcional; deixe null, o modo vem do perfil/sistema),\n'
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
        "- NÃO preencha agent_mode; deixe null. O modo é definido pelo perfil/sistema.\n"
        "- Preencha signals seguindo schema padronizado quando possível (intent_level, urgency_level, price_acceptance, meeting_scheduled, handoff_requested, missing_fields, stop_reason).\n"
        "- Em price_acceptance use SEMPRE string: no|unsure|yes (não use boolean).\n"
        "- Se o lead aceitar o preço/valor, use price_acceptance='yes'.\n"
        "- REGRA DE QUALIFICAÇÃO: se missing_fields não estiver vazio E a mensagem não for uma pergunta direta\n"
        "  do lead sobre oferta/serviços/preços → route_to DEVE ser \"qualification\".\n"
        "  Se o lead fez uma pergunta direta (sobre serviços, preços, como funciona, etc.) E missing_fields não\n"
        "  estiver vazio → use route_to=\"qualification\" + next_action_hint=\"reply\" (filha responde primeiro,\n"
        "  qualificação continua nos turnos seguintes). NUNCA force qualification sem next_action_hint=\"reply\"\n"
        "  quando o lead fizer uma pergunta direta.\n"
        "  EXCEÇÃO FECHO: sinal explícito de confirmação/booking em agent_mode=agenda/sdr_scheduler permite\n"
        "  route_to=\"apresentation\" — ver PRIORIDADE 1 EXCEÇÃO FECHO abaixo.\n"
        "- Enquanto houver missing_fields E sem sinal de fecho E sem pergunta direta, NÃO sugerir avanço para apresentation, follow-up ou closing.\n"
        "- perceived_category pode refletir o estágio atual do lead, mas route_to deve permanecer qualification até completar o contrato.\n"
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
        "REGRAS DE ROUTING — AVALIAR NESTA ORDEM (a primeira que coincidir vence):\n\n"
        "PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):\n"
        "- PRIORIDADE 1A: missing_fields NÃO vazio + mensagem SEM pergunta direta → route_to = \"qualification\"\n"
        "- PRIORIDADE 1B: missing_fields NÃO vazio + mensagem COM pergunta direta (serviços, preço, como\n"
        "  funciona, horários, etc.) → route_to = \"qualification\", next_action_hint = \"reply\"\n"
        "  (filha responde à pergunta antes de qualificar — NUNCA ignore uma pergunta direta do lead)\n"
        "  EXCEÇÃO FECHO (agent_mode=agenda/sdr_scheduler): se a mensagem contiver sinal EXPLÍCITO de\n"
        "  confirmação/booking (\"fica combinado\", \"perfeito\", \"pode ser\", \"fechado\", \"aceito\",\n"
        "  \"tá bom\", \"ok então\", \"combinado\", \"confirmado\", \"então fica assim\" ou equivalentes),\n"
        "  interprete price_acceptance='yes' e meeting_scheduled=true\n"
        "  → route_to = \"apresentation\" mesmo com missing_fields. Documentar no reason.\n\n"
        "PRIORIDADE 2 (sinais fortes):\n"
        "- Lead confirmou horário/data específica → route_to = \"apresentation\"\n"
        "- Lead disse \"quero comprar/assinar/fechar\" com intent_level=high → route_to = \"closing\"\n"
        "- Lead mencionou reunião/sessão passada + dúvida/objeção/feedback → route_to = \"follow-up\"\n\n"
        "PRIORIDADE 3 (sinais médios — usar confidence para desambiguar):\n"
        "- Lead mostrou interesse mas sem confirmação → route_to = \"apresentation\", confidence < 0.7\n"
        "- Lead pediu \"para pensar\" sem evidência de apresentação prévia → MANTER rota atual, não avançar\n\n"
        "PRIORIDADE 4 (sinais fracos — contexto decide):\n"
        "- Mensagem genérica (\"oi\", \"tudo bem\") → manter rota anterior, confidence baixa\n"
        "- Mensagem fora de contexto → route_to = rota atual, next_action_hint = \"reply\"\n\n"
        "SE EM DÚVIDA: mantenha a rota atual com confidence < 0.6.\n"
        "NUNCA retorne route_to=\"follow-up\" se não houver evidência textual de apresentação/sessão realizada.\n\n"
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
        "11) AGENDA sinal de fecho: inbound_message_text: \"Perfeito, fica combinado então\"\n"
        "   (missing_fields não vazio, agent_mode=agenda, sinal de fecho explícito)\n"
        '   -> {"route_to":"apresentation","perceived_category":"apresentation","confidence":0.85,"reason":"meeting_scheduled|fica combinado — sinal de fecho override","signals":{"meeting_scheduled":true,"price_acceptance":"yes"}}\n'
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
        f"- lead_origin: {lead_origin_label}\n"
        f"- origin_opener: {origin_opener}\n"
        f"- inbound_message_text: {message_text}\n"
        + (
            "\nMODO PASSIVO (response_style=passive): "
            "Se a mensagem do cliente for uma pergunta directa (sobre serviços, preços, localização, "
            "horários, massagista, catálogo de tratamentos, quais opções/massagens/tratamentos existem, "
            "menu de serviços, o que oferecem, o que fazem, quais são os valores, etc.) "
            "E missing_fields NÃO ESTIVER VAZIO, "
            "usa next_action_hint='reply' para sinalizar à filha que deve responder a pergunta primeiro. "
            "O route_to continua 'qualification' (os campos ainda precisam de ser coletados), "
            "mas a filha terá prioridade para responder antes de perguntar.\n"
            if (ai_profile.get("response_style") or "passive") == "passive"
            else ""
        )
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
    presentation_variant, presentation_variant_source = _resolve_presentation_variant(context, agent_mode_normalized)
    hybrid_flow_style = _resolve_hybrid_flow_style(context)
    offer_pack_summary = _build_offer_pack_summary(context)
    return (
        f"Você é uma LLM FILHA de um CRM de vendas WhatsApp.\n\n"
        f"PAPEL: Gerar a resposta adequada ao estágio do funil do lead.\n"
        f"ESCOPO: Responder apenas ao que o contexto fornecido permite. Nunca inventar informação.\n"
        f"TOM: {ai_summary.get('tone_of_voice') or 'profissional'} — conversacional, adaptado ao WhatsApp.\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary['template_key']}.\n"
        "RECUSAS: Nunca invente informação. Nunca prometa condições não presentes no contexto. Nunca dê conselhos médicos, jurídicos ou financeiros.\n\n"
        "Retorne SOMENTE JSON válido no schema ChildResult:\n"
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

    lead_origin_label = metadata.get("lead_origin_label") or "INBOUND (lead veio te procurar)"
    _is_outbound_lead = (metadata.get("lead_origin") or "inbound") == "outbound"
    origin_opener = (
        ai_profile.get("origin_outbound_opener") if _is_outbound_lead else ai_profile.get("origin_inbound_opener")
    ) or ""

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    presentation_variant, presentation_variant_source = _resolve_presentation_variant(context, agent_mode_normalized)
    hybrid_flow_style = _resolve_hybrid_flow_style(context)
    current_field = _select_current_field(
        list(mode_contract.get("missing_fields") or []),
        list(mode_contract.get("filled_fields") or []),
    )
    asked_for_current = [
        str(item.get("question_text") or "")
        for item in (mode_contract.get("asked_questions_json") or [])
        if isinstance(item, dict) and item.get("field") == current_field
    ][-2:]

    tone_block = _build_tone_block(ai_profile, playbook)
    response_style = (ai_profile.get("response_style") or "passive").strip().lower()

    # Fix P4: ESCOPO e RECUSAS condicionais ao response_style.
    # O bloco passivo aparece ANTES do PAPEL para ter precedência sobre qualquer instrução posterior.
    _escopo_line = (
        "Responder perguntas directas do cliente PRIMEIRO, usando offer_description e custom_instructions. "
        "Depois qualificar de forma natural. Pode apresentar serviços e valores quando perguntado. "
        "Não agenda reunião nesta fase. NUNCA faças perguntas abertas de qualificação — apenas closing_questions "
        "se configuradas (confirmações e alternativas binárias)."
        if response_style == "passive"
        else (
            "Responde SEMPRE à mensagem do cliente antes de qualificar. Se o cliente fez uma pergunta, "
            "responde usando offer_description e custom_instructions. Depois, se houver campos obrigatórios "
            "em falta, adicione UMA pergunta de qualificação natural ao final. "
            "Nunca respondas APENAS com uma pergunta de qualificação. Não agenda reuniões nesta fase."
        )
    )
    _recusas_line = (
        "Nunca invente informação. Nunca agende reunião nesta fase. "
        "Se a resposta não estiver em offer_description ou custom_instructions, diz que vais verificar (→ handoff). "
        "NUNCA faças perguntas abertas para coletar dados — guia persuasivamente para o próximo passo."
        if response_style == "passive"
        else (
            "Nunca invente informação. Nunca agende reunião nesta fase. "
            "Pode apresentar serviços e valores quando perguntado usando offer_description. "
            "Se não souber responder, diz que vais verificar (→ handoff)."
        )
    )
    _mother_hint = (mother_decision.next_action_hint or "").strip().lower()
    _passive_reply_now = response_style == "passive" and _mother_hint == "reply"
    _passive_header = (
        (
            "MODO PASSIVO ACTIVADO — RESPOSTA IMEDIATA OBRIGATÓRIA.\n"
            "A mãe sinalizou next_action_hint='reply': o cliente fez uma pergunta de catálogo/oferta/serviços.\n"
            "INSTRUÇÃO CRÍTICA: coloca TODA a resposta em message_text. NÃO perguntes nada neste turno.\n"
            "should_ask=false. question_text DEVE ficar vazio (\"\").\n"
            "Responde à pergunta do cliente usando offer_description e custom_instructions.\n"
            "A qualificação continua nos próximos turnos — NÃO neste.\n\n"
        )
        if _passive_reply_now
        else (
            "MODO PASSIVO ACTIVADO: Este agente responde primeiro, qualifica depois.\n"
            "PRIORIDADE ABSOLUTA: se a mensagem do cliente for uma pergunta directa (sobre serviços,\n"
            "preços, localização, horários, funcionamento, massagista, catálogo, menu, etc.), RESPONDE-A PRIMEIRO\n"
            "usando offer_description e custom_instructions antes de qualquer pergunta de qualificação.\n"
            "Só após responder, e de forma natural no mesmo turno ou no turno seguinte, recolhe campos em falta.\n"
            "NUNCA ignores uma pergunta directa para fazer uma pergunta de qualificação.\n\n"
            if response_style == "passive"
            else ""
        )
    )

    _qual_prompt = f"""{_passive_header}Você é a FILHA QUALIFICATION de um CRM de vendas WhatsApp.

PAPEL: Coletar campos de qualificação do lead, um por vez, através de perguntas naturais e contextuais.
ESCOPO: {_escopo_line}
TOM: {ai_summary["tone_of_voice"] or "profissional"} — conversacional e adaptado ao WhatsApp (mensagens curtas, sem formatação). Máx {playbook_summary["max_chars"] or "N/D"} caracteres.
FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary["template_key"]}. Campos obrigatórios: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}. Campo atual: {json.dumps(current_field, ensure_ascii=False)}.
RECUSAS: {_recusas_line}
{tone_block}
Retorne SOMENTE JSON válido no schema ChildResult:
{{
  "question_text": "string",
  "field": "service_interest|urgency|decision_role|constraints|availability_window|budget_or_price_acceptance|location_preference|price_acceptance|null",
  "should_ask": true,
  "message_text": "string (retrocompat opcional)",
  "did_complete_phase": false,
  "recommended_next_category": "apresentation|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "signals_structured": {{"missing_fields": ["..."], "handoff_requested": false}} (opcional),
  "confidence": 0.0
}}
Regras:
- Só pode perguntar 1 coisa por turno.
- Quando should_ask=true, field deve ser EXATAMENTE o current_field.
- Quando should_ask=true, question_text não pode ser vazio.
- Evite repetir frases de asked_questions_for_current_field; reformule.
- Se current_field já tiver sido preenchido, retorne should_ask=false, field=null, question_text="".
- NÃO agendar reunião aqui (só na rota apresentation, salvo pedido explícito do inbound).
- recommended_next_category pode ser null ou 'apresentation'.
- outcome e kanban_highlight devem ser null.

PROIBIÇÕES (violar qualquer uma é crítico):
1. NUNCA invente informações que não estejam no contexto fornecido.
2. NUNCA prometa descontos, prazos ou condições não presentes em offer_pack ou knowledge_items.
3. NUNCA dê conselhos médicos, jurídicos ou financeiros.
4. NUNCA mencione concorrentes pelo nome, a menos que estejam em knowledge_items.
5. NUNCA use urgência artificial — só mencione urgência se urgency_offer estiver preenchido.
6. NUNCA responda sobre assuntos fora do nicho do negócio — redirecione para o tema.
7. Se não souber a resposta, diga que vai verificar com a equipa (→ handoff), não improvise.
{_ESCAPE_HATCH_BLOCK}
{_build_validation_block(playbook_summary["max_chars"])}
ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})
Motivo MÃE: {mother_decision.reason}

CONTEXTO:
- lead: {json.dumps(lead_summary, ensure_ascii=False)}
- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}
- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}
- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}
- history: {history_text}
- agent_mode_normalized: {agent_mode_normalized}
- required_fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}
- missing_fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}
- current_field: {json.dumps(current_field, ensure_ascii=False)}
- asked_questions_for_current_field: {json.dumps(asked_for_current, ensure_ascii=False)}
- last_question_text: {json.dumps(mode_contract.get('last_question_text') or '', ensure_ascii=False)}
- lead_origin: {lead_origin_label}
- origin_opener: {origin_opener}
- inbound_message_text: {message_text}
- next_action_hint_mae: {mother_decision.next_action_hint or "null"}
{_build_qualification_fields_block(ai_profile, response_style)}{_build_custom_instructions_block(ai_profile)}"""
    return _inject_generated_parts(_qual_prompt, context, "qualification")

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
        "timezone": ai_profile.get("timezone"),
        "appointment_mode": ai_profile.get("appointment_mode"),
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
    presentation_variant, presentation_variant_source = _resolve_presentation_variant(context, agent_mode_normalized)
    hybrid_flow_style = _resolve_hybrid_flow_style(context)
    offer_pack_summary = _build_offer_pack_summary(context)

    # Estágio de aquecimento (Tarefa 3.8) — Agent 3 (hybrid_scheduler) pós-qualificação.
    # Trigger: mother_decision.route_to == "qualification" e missing_fields vazio
    # (qualificação recém-aprovada/auto-promovida para apresentation).
    _DEFAULT_SOCIAL_PROOF = (
        "Um profissional com o seu perfil já utilizou essa abordagem e conseguiu resultados expressivos. "
        "Posso te contar mais detalhes na nossa conversa."
    )
    _DEFAULT_SESSION_PREVIEW = (
        "Na sessão de aproximadamente 1h, vamos mapear sua situação atual, identificar os principais pontos de melhoria "
        "e sair com um plano de ação claro para você."
    )
    template_key_for_warming = str(ai_profile.get("template_key") or "").strip().lower()
    appointment_mode = str(ai_profile.get("appointment_mode") or "exploratory").strip().lower()
    knowledge_items = context.get("knowledge_items") or {}
    warming_injection = ""
    commercial_injection = ""
    if (
        template_key_for_warming == "hybrid_scheduler"
        and mother_decision.route_to == "qualification"
        and not mode_contract.get("missing_fields")
    ):
        if appointment_mode == "commercial":
            # Modo comercial: apresentar serviços/preços, tratar objeções, fechar compromisso, DEPOIS agendar.
            # Pagamento sempre presencial — nunca enviar link de checkout.
            social = (
                knowledge_items.get("social_proof")
                or str(ai_profile.get("warming_social_proof") or "").strip()
            )
            pricing       = knowledge_items.get("service_pricing_table", "")
            objections    = knowledge_items.get("commercial_objections", "")
            differentials = knowledge_items.get("service_differentials", "")
            promotion     = knowledge_items.get("active_promotion", "")
            payment       = knowledge_items.get("payment_policy", "")
            faq_commit    = knowledge_items.get("pre_commitment_faq", "")
            commercial_injection = (
                "\n- MODO COMERCIAL (hybrid_scheduler — compromisso antes do agendamento):\n"
                "  O lead concluiu a qualificação. Seu objetivo neste turno e nos seguintes é:\n"
                "  1. Aquecer com prova social (se disponível)\n"
                "  2. Apresentar os serviços/pacotes disponíveis com clareza\n"
                "  3. Tratar objeções conforme as respostas configuradas\n"
                "  4. Obter o compromisso verbal/escrito do lead com um serviço ou pacote específico\n"
                "  5. SÓ ENTÃO propor o agendamento\n"
                "  REGRA CRÍTICA: o pagamento é SEMPRE presencial na marcação — NUNCA envie link de checkout.\n"
                "  Não mencione modalidade 'exploratória' ou 'diagnóstico gratuito' — a sessão já tem valor definido.\n"
                + (
                    f"  PROVA SOCIAL (usar na fase de warming ou quando o lead demonstrar hesitação):\n"
                    f"  {social}\n"
                    f"  INSTRUÇÃO: Integre naturalmente na conversa. Nunca diga 'temos uma prova social'. Adapte ao perfil do lead se possível.\n"
                    if social else
                    "  PROVA SOCIAL: (não configurada — use tom acolhedor e destaque o diferencial do profissional)\n"
                )
                + (
                    f"  TABELA DE SERVIÇOS/PREÇOS (apresentar para contextualizar a oferta):\n"
                    f"  {pricing}\n"
                    f"  INSTRUÇÃO: Apresente com clareza. Nunca invente preços ou condições não listadas.\n"
                    if pricing else
                    "  TABELA DE SERVIÇOS/PREÇOS: (não configurada — pergunte o interesse antes de citar valores)\n"
                )
                + (
                    f"  OBJEÇÕES E RESPOSTAS (usar APENAS quando o lead levantar uma objeção):\n"
                    f"  {objections}\n"
                    f"  INSTRUÇÃO: Se o lead levantar uma objeção listada, use a resposta como base. Adapte ao tom. Nunca copie literalmente. Se a objeção não estiver listada, use empatia + reformulação de valor.\n"
                    if objections else
                    "  OBJEÇÕES E RESPOSTAS: (não configurada — use empatia e reformule o valor entregue)\n"
                )
                + (
                    f"  DIFERENCIAIS DO SERVIÇO (mencionar para reforçar valor):\n"
                    f"  {differentials}\n"
                    f"  INSTRUÇÃO: Integre naturalmente no pitch, não liste como bullet points.\n"
                    if differentials else ""
                )
                + (
                    f"  CONDIÇÃO ESPECIAL VIGENTE (mencionar quando relevante para fechar o compromisso):\n"
                    f"  {promotion}\n"
                    f"  INSTRUÇÃO: Cite apenas se vigente. Nunca crie urgência artificial.\n"
                    if promotion else ""
                )
                + (
                    f"  POLÍTICA DE PAGAMENTO PRESENCIAL (usar para esclarecer dúvidas sobre pagamento):\n"
                    f"  {payment}\n"
                    f"  INSTRUÇÃO: Reforce que o pagamento é presencial. Nunca envie link de checkout.\n"
                    if payment else ""
                )
                + (
                    f"  FAQ PRÉ-COMPROMISSO (usar APENAS quando o lead fizer uma pergunta diretamente coberta):\n"
                    f"  {faq_commit}\n"
                    f"  INSTRUÇÃO: Responda com base no FAQ. Se a pergunta não estiver coberta, diga que vai confirmar com a equipa.\n"
                    if faq_commit else ""
                )
                + "  Após o lead confirmar a escolha de serviço/pacote, proponha o agendamento normalmente.\n"
            )
        elif presentation_variant == "scheduler":
            # presentation_variant=scheduler — serviço presencial (massagem, spa, bem-estar, etc.)
            # Não há fase de warming B2B. Após qualificação concluída, confirmar disponibilidade e valor.
            warming_injection = (
                "\n- ESTÁGIO PÓS-QUALIFICAÇÃO (scheduler — serviço presencial): "
                "O lead indicou o serviço pretendido e a disponibilidade. O teu papel agora é:\n"
                "  1. Confirmar (ou verificar) a disponibilidade para o horário/dia mencionado\n"
                "  2. Informar o valor do serviço solicitado, se ainda não foi mencionado nesta conversa\n"
                "  3. Propor a confirmação da reserva de forma natural e acolhedora\n"
                "  REGRA CRÍTICA: usa linguagem de spa/serviço — 'agendar sessão', 'reservar', 'marcar experiência'. "
                "NUNCA uses linguagem de reunião B2B ('mapear situação', 'plano de ação', 'diagnóstico', "
                "'cliente com o teu perfil', 'resultados incríveis').\n"
            )
        else:
            # Modo exploratório (padrão): aquecer e propor sessão sem compromisso de compra.
            social_proof = str(ai_profile.get("warming_social_proof") or "").strip() or _DEFAULT_SOCIAL_PROOF
            session_preview = str(ai_profile.get("warming_session_preview") or "").strip() or _DEFAULT_SESSION_PREVIEW
            warming_injection = (
                "\n- ESTÁGIO WARMING (pós-qualificação aprovada para hybrid_scheduler): "
                "O lead acabou de concluir a qualificação. Antes de propor o agendamento, execute os 2 passos de aquecimento em UMA mensagem natural:\n"
                f"  1. PROVA SOCIAL: {social_proof}\n"
                f"  2. PRÉVIA DA SESSÃO: {session_preview}\n"
                "  Combine os 2 passos de forma fluida e, ao final, proponha o agendamento da sessão.\n"
                "  Não mencione os termos 'prova social' ou 'prévia da sessão' explicitamente — use linguagem natural.\n"
            )

    tone_block_apresentation = _build_tone_block(ai_profile, playbook)

    # Tarefa 1.3 — knowledge_items com directivas de uso para sdr_padrao / closer_agressivo
    # (e qualquer path que não use commercial_injection, onde knowledge não é injectado inline)
    _apres_knowledge_parts: list[str] = []
    if not commercial_injection:
        _social_proof_apres = knowledge_items.get("social_proof") or ""
        _pitch_script_apres = knowledge_items.get("pitch_script") or ""
        _product_details_apres = knowledge_items.get("product_details") or ""
        _objections_faq_apres = knowledge_items.get("objections_faq") or ""
        _service_faq_apres = knowledge_items.get("service_faq") or ""
        _guarantee_policy_apres = knowledge_items.get("guarantee_policy") or ""
        if _social_proof_apres:
            _apres_knowledge_parts.append(
                f"PROVA SOCIAL (usar na fase de aquecimento ou quando o lead demonstrar hesitação):\n"
                f"{_social_proof_apres}\n"
                f"INSTRUÇÃO: Integre naturalmente na conversa. Nunca diga 'temos uma prova social'. "
                f"Adapte ao perfil do lead se possível.\n"
            )
        if _pitch_script_apres:
            _apres_knowledge_parts.append(
                f"SCRIPT DE PITCH (usar como guia estrutural da apresentação, não copiar literalmente):\n"
                f"{_pitch_script_apres}\n"
                f"INSTRUÇÃO: Adapte ao contexto da conversa e ao tom de voz configurado. "
                f"Nunca copie o script palavra por palavra.\n"
            )
        if _product_details_apres:
            _apres_knowledge_parts.append(
                f"DETALHES DO PRODUTO/SERVIÇO (usar para enriquecer o pitch com informações precisas):\n"
                f"{_product_details_apres}\n"
                f"INSTRUÇÃO: Use apenas os dados presentes neste bloco. Nunca invente features ou condições não listadas.\n"
            )
        if _objections_faq_apres:
            _apres_knowledge_parts.append(
                f"OBJEÇÕES E RESPOSTAS (usar APENAS quando o lead levantar uma objeção):\n"
                f"{_objections_faq_apres}\n"
                f"INSTRUÇÃO: Se o lead levantar uma objeção listada, use a resposta configurada como base. "
                f"Adapte ao tom de voz e ao contexto. Nunca copie literalmente. "
                f"Se a objeção NÃO estiver listada, use empatia + reformulação de valor.\n"
            )
        if _service_faq_apres:
            _apres_knowledge_parts.append(
                f"FAQ DO SERVIÇO (usar APENAS quando o lead fizer uma pergunta diretamente coberta):\n"
                f"{_service_faq_apres}\n"
                f"INSTRUÇÃO: Responda com base no FAQ. Se a pergunta não estiver coberta, "
                f"diga que vai confirmar com a equipa.\n"
            )
        if _guarantee_policy_apres:
            _apres_knowledge_parts.append(
                f"POLÍTICA DE GARANTIA (mencionar para reforçar confiança quando relevante):\n"
                f"{_guarantee_policy_apres}\n"
                f"INSTRUÇÃO: Cite apenas quando o lead demonstrar hesitação sobre risco. "
                f"Nunca invente garantias não configuradas.\n"
            )
    standard_knowledge_block = (
        "\nKNOWLEDGE BASE (usar conforme as instruções de cada bloco):\n"
        + "\n".join(_apres_knowledge_parts)
    ) if _apres_knowledge_parts else ""

    # Fix P8: bloco de confirmação estruturada obrigatória.
    # Activa quando meeting_scheduled=true + presentation_variant=scheduler (modo agenda/hybrid).
    # O filho entra em "modo recibo" e deve emitir o resumo estruturado da reserva.
    _apres_meeting_scheduled = _extract_meeting_scheduled_signal(mother_decision)
    _extracted_fields_apres = mode_contract.get("extracted_fields") or {}
    _booking_confirmation_block = ""
    if _apres_meeting_scheduled and presentation_variant == "scheduler":
        _booking_confirmation_block = (
            "\nCONFIRMAÇÃO ESTRUTURADA OBRIGATÓRIA (meeting_scheduled=true + scheduler):\n"
            "O cliente confirmou a reserva. DEVES emitir o recibo de reserva no formato abaixo.\n"
            "Usa os valores de extracted_fields para preencher cada campo. "
            "Se um campo não estiver em extracted_fields, usa o que estiver no histórico ou em custom_instructions.\n"
            "Formato obrigatório (adapta o texto ao tom de voz, mantém a estrutura):\n"
            "✅ [nome do serviço] Reservada\n"
            "📋 Experiência: [service_interest]\n"
            "🕐 Horário: [hora de availability_window]\n"
            "📅 Dia: [dia de availability_window]\n"
            "👤 Massagista: [nome do massagista — de custom_instructions ou offer_description]\n"
            "Após o recibo, podes acrescentar a morada/sala se ainda não foi dada neste turno, "
            "ou uma frase de encerramento acolhedora.\n"
            "NÃO substituas o recibo por texto verbal solto. O recibo É a resposta principal.\n"
            f"extracted_fields disponíveis: {json.dumps(_extracted_fields_apres, ensure_ascii=False)}\n"
        )

    _apres_prompt = (
        f"Você é a FILHA APRESENTATION de um CRM de vendas WhatsApp.\n\n"
        f"PAPEL: Conduzir a fase de apresentação — agendamento (scheduler) ou oferta+fechamento (sales).\n"
        f"ESCOPO: Variant {presentation_variant}. Gera a mensagem de apresentação e preenche signals_structured.\n"
        f"TOM: {ai_summary.get('tone_of_voice') or 'profissional'} — direto e focado na ação. Máx {playbook_summary.get('max_chars') or 'N/D'} caracteres.\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary.get('template_key')}. Appointment mode: {ai_summary.get('appointment_mode') or 'exploratory'}.\n"
        "RECUSAS: Nunca invente features ou benefícios fora de knowledge_items. Nunca cite preço diferente de offer_pack. Nunca mencione \"veja a imagem/vídeo\" (mídia enviada automaticamente). Nunca envie link E peça permissão no mesmo turno.\n"
        + tone_block_apresentation
        + "\nRetorne SOMENTE JSON válido no schema ChildResult:\n"
        "{\n"
        '  "message_text": "string",\n'
        '  "did_complete_phase": false,\n'
        '  "recommended_next_category": null,\n'
        '  "outcome": null,\n'
        '  "kanban_highlight": null,\n'
        '  "signals": ["..."],\n'
        '  "signals_structured": {"missing_fields": ["..."], "handoff_requested": false, "meeting_proposed": false, "meeting_datetime_candidate": null} (opcional),\n'
        '  "confidence": 0.0\n'
        "}\n"
        "Regras:\n"
        "- Respeite presentation_variant para conduzir a apresentação (sem heurística por keyword).\n"
        "- Se presentation_variant=sales: apresente oferta objetiva (offer_pack quando disponível) e CTA para fechamento/checkout.\n"
        "- Se presentation_variant=scheduler: conduza agendamento (pedir dia/horário, confirmar, reagendar, enviar link).\n"
        "- Em presentation_variant=scheduler (modo agenda/hybrid), SEMPRE preencha signals_structured.meeting_proposed (bool) e signals_structured.meeting_datetime_candidate (ISO string ou null).\n"
        "  * Se houver proposta/confirmação com horário definido: meeting_proposed=true e meeting_datetime_candidate preenchido.\n"
        "  * Se estiver pedindo disponibilidade sem horário definido: meeting_proposed=true e meeting_datetime_candidate=null.\n"
        "  * Se não for contexto de agendamento: meeting_proposed=false e meeting_datetime_candidate=null.\n"
        "  * Preferência: ISO naive no horário local de ai_profile.timezone (ex: 2026-03-05T17:00:00); também aceito offset/Z.\n"
        "  * Nunca assumir timezone fixa; sempre respeitar ai_profile.timezone.\n"
        "  * Em confirmação final do agendamento, inclua 'meeting_scheduled' em signals para compatibilidade.\n"
        "- Em presentation_variant=sales, UM TURNO = UMA AÇÃO: ou CONFIRMAR (sem link) ou ENVIAR LINK (com link).\n"
        "- Formato CONFIRMAR (sem link): descreva oferta e peça confirmação (ex.: 'quer seguir?').\n"
        "  * Proibido URL real e proibido placeholder de link (ex.: [link_do_checkout]).\n"
        "  * Quando CONFIRMAR: signals_structured.checkout_sent=false.\n"
        "- Formato ENVIAR LINK (com link): oferta curta + link + próximo passo ('conclua e me confirme').\n"
        "  * Quando ENVIAR LINK: signals_structured.checkout_sent=true.\n"
        "  * Não pedir permissão para enviar link no mesmo turno (não usar 'posso enviar o link?' se checkout_sent=true).\n"
        "- Regra de consistência obrigatória:\n"
        "  * Se houver pergunta de confirmação (quer seguir?/posso enviar?/você confirma?), NÃO incluir link e checkout_sent=false.\n"
        "  * Se checkout_sent=true, incluir link (real ou placeholder) e NÃO pedir permissão para enviar link.\n"
        "- Se hybrid_flow_style estiver definido, combine oferta+agenda na ordem indicada.\n"
        "- Use tone_of_voice, brand_name e niche quando disponíveis.\n"
        "- Respeite playbook.max_chars se existir (senão, resposta curta).\n"
        "- recommended_next_category é informativo nesta rota; não é aplicado automaticamente na mudança de estágio.\n"
        "- outcome e kanban_highlight devem ser null.\n"
        "- signals_structured deve incluir: offer_presented, checkout_sent, presentation_variant e offer_item_name.\n"
        "- Mídia rica: se offer_pack_summary.media_url estiver preenchido, a mídia já será enviada automaticamente antes deste texto. NÃO mencione 'veja a imagem/vídeo' — assuma que o lead já recebeu e escreva o texto do pitch como sequência natural.\n"
        "- Se offer_pack_summary.anchor_price estiver preenchido, use o preço âncora no pitch (ex: 'De R$997 por apenas R$X').\n"
        "- Se offer_pack_summary.guarantee_text estiver preenchido, inclua a garantia na mensagem (ex: 'Com 7 dias de garantia').\n"
        "\nPROIBIÇÕES (violar qualquer uma é crítico):\n"
        "1. NUNCA invente informações que não estejam no contexto fornecido.\n"
        "2. NUNCA prometa descontos, prazos ou condições não presentes em offer_pack ou knowledge_items.\n"
        "3. NUNCA dê conselhos médicos, jurídicos ou financeiros.\n"
        "4. NUNCA mencione concorrentes pelo nome, a menos que estejam em knowledge_items.\n"
        "5. NUNCA use urgência artificial — só mencione urgência se urgency_offer estiver preenchido.\n"
        "6. NUNCA responda sobre assuntos fora do nicho do negócio — redirecione para o tema.\n"
        "7. Se não souber a resposta, diga que vai verificar com a equipa (→ handoff), não improvise.\n"
        "8. NUNCA mencione \"veja a imagem\" ou \"veja o vídeo\" — a mídia é enviada automaticamente pelo sistema.\n"
        "9. NUNCA envie link de checkout E peça permissão no mesmo turno.\n"
        "10. NUNCA cite preço diferente do que está em offer_pack.\n"
        + _ESCAPE_HATCH_BLOCK
        + _build_validation_block(playbook_summary.get("max_chars"))
        + "\n"
        + f"{commercial_injection if commercial_injection else warming_injection}"
        + (_booking_confirmation_block)
        + "Exemplos rápidos (sales):\n"
        "- EXEMPLO CONFIRMAR: message_text='Plano Starter por R$X com suporte Y. Quer seguir com a contratação?'\n"
        "  signals_structured={offer_presented:true, checkout_sent:false, presentation_variant:'sales', offer_item_name:'Plano Starter'}\n"
        "- EXEMPLO ENVIAR LINK: message_text='Perfeito! Aqui está seu link: https://exemplo.com/checkout-starter\\nConclua e me confirme por aqui.'\n"
        "  signals_structured={offer_presented:true, checkout_sent:true, presentation_variant:'sales', offer_item_name:'Plano Starter'}\n"
        "\n"
        f"ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})\n"
        f"Motivo MÃE: {mother_decision.reason}\n"
        + standard_knowledge_block
        + "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- agent_mode_normalized: {agent_mode_normalized}\n"
        f"- required_fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
        f"- missing_fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        f"- presentation_variant: {presentation_variant} (source={presentation_variant_source})\n"
        f"- hybrid_flow_style: {hybrid_flow_style or ''}\n"
        f"- offer_pack_summary: {json.dumps(offer_pack_summary, ensure_ascii=False)}\n"
        f"- warming_stage_active: {bool(warming_injection)}\n"
        f"- commercial_mode_active: {bool(commercial_injection)}\n"
        f"- extracted_fields: {json.dumps(mode_contract.get('extracted_fields') or {}, ensure_ascii=False)}\n"
        f"- inbound_message_text: {message_text}\n"
        + _build_custom_instructions_block(ai_profile)
    )
    return _inject_generated_parts(_apres_prompt, context, "apresentation")



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
    followup_ctx = metadata.get("followup_context") if isinstance(metadata.get("followup_context"), dict) else {}

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
        "followup_context": followup_ctx,
    }

    followup_summary = {
        "followup_goal": followup_ctx.get("followup_goal") or lead.get("followup_goal"),
        "outcome": followup_ctx.get("followup_outcome") or lead.get("outcome"),
        "followup_variant": followup_ctx.get("followup_variant"),
        "attempts": followup_ctx.get("followup_attempts"),
        "max_attempts": followup_ctx.get("followup_max_attempts"),
        "meeting_happened": followup_ctx.get("followup_meeting_happened"),
        "meeting_or_session_happened": followup_ctx.get("followup_meeting_or_session_happened"),
        "proposal_sent": followup_ctx.get("followup_proposal_sent"),
        "operator_note": followup_ctx.get("followup_operator_note"),
        "status": followup_ctx.get("followup_status"),
        "next_followup_at": followup_ctx.get("followup_next_followup_at"),
    }
    followup_variant = str(followup_summary.get("followup_variant") or "").strip().lower()
    variant_rule = ""
    if followup_variant == "sdr_scheduler":
        variant_rule = (
            "- Variante sdr_scheduler: follow-up consultivo pós-reunião; "
            "reforçar valor, síntese do contexto e próximo passo comercial.\n"
        )
    elif followup_variant == "cart_recovery":
        attempts_done = int(followup_summary.get("attempts") or 0)
        next_attempt = attempts_done + 1
        if next_attempt <= 1:
            attempt_instruction = (
                "Tentativa 1 — lembrete neutro: o pedido está reservado e o link ainda está disponível. "
                "Sem pressão — apenas informa e pergunta se há dúvida que impeça o pagamento."
            )
        elif next_attempt == 2:
            attempt_instruction = (
                "Tentativa 2 — benefício + objeção: reforce o principal benefício e antecipe a objeção "
                "mais comum do nicho. Tom amigável, resolva a dúvida que está impedindo o pagamento."
            )
        else:
            attempt_instruction = (
                "Tentativa 3 — urgência máxima: a oferta expira hoje. "
                "CTA direto para o link de pagamento. Não reabra qualificação."
            )
        variant_rule = (
            "- Variante cart_recovery (carrinho abandonado, Agent 2): "
            "recuperar pagamento pendente após link enviado. Mensagens curtas (máx 280 chars).\n"
            f"- Instrução para tentativa {next_attempt}/3: {attempt_instruction}\n"
        )
    elif followup_variant == "hybrid_scheduler":
        outcome = str(followup_summary.get("outcome") or "").strip().lower()
        if outcome == "interested_not_closed":
            outcome_instruction = (
                "Tom de continuidade: retome o contexto da sessão anterior, "
                "remova a objeção específica que foi levantada e ofereça nova data concreta para avançar."
            )
        elif outcome == "reschedule_needed":
            outcome_instruction = (
                "Tom leve e sem pressão: o lead não compareceu ou pediu remarcação. "
                "Ofereça 2-3 horários diretamente e encerre com uma pergunta fechada."
            )
        elif outcome == "converted":
            outcome_instruction = (
                "Tom de onboarding e boas-vindas: parabenize, confirme o próximo passo, "
                "envie link de pagamento ou instrução de acesso. Não reabra vendas."
            )
        else:
            outcome_instruction = (
                "Priorizar recuperação de no-show, confirmação de presença e reengajamento."
            )
        variant_rule = (
            "- Variante hybrid_scheduler (coaches/terapeutas/consultores solo): "
            "tom pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo.\n"
            f"- Regra por outcome ({outcome or 'indefinido'}): {outcome_instruction}\n"
        )

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    presentation_variant, presentation_variant_source = _resolve_presentation_variant(context, agent_mode_normalized)
    hybrid_flow_style = _resolve_hybrid_flow_style(context)
    is_followup_tick = _is_followup_tick_context(context)

    # Tarefa 1.3 — knowledge_items com directivas de uso
    knowledge_items = context.get("knowledge_items") or {}
    _followup_knowledge_parts: list[str] = []
    _social_proof_ki = knowledge_items.get("social_proof") or ""
    _objections_faq_ki = knowledge_items.get("objections_faq") or ""
    _service_faq_ki = knowledge_items.get("service_faq") or ""
    if _social_proof_ki:
        _followup_knowledge_parts.append(
            f"PROVA SOCIAL (usar na fase de warming ou quando o lead demonstrar hesitação):\n"
            f"{_social_proof_ki}\n"
            f"INSTRUÇÃO: Integre naturalmente na conversa. Nunca diga 'temos uma prova social'. "
            f"Adapte ao perfil do lead se possível.\n"
        )
    if _objections_faq_ki:
        _followup_knowledge_parts.append(
            f"OBJEÇÕES E RESPOSTAS (usar APENAS quando o lead levantar uma objeção):\n"
            f"{_objections_faq_ki}\n"
            f"INSTRUÇÃO: Se o lead levantar uma objeção listada, use a resposta configurada como base. "
            f"Adapte ao tom de voz e ao contexto. Nunca copie literalmente. "
            f"Se a objeção NÃO estiver listada, use empatia + reformulação de valor.\n"
        )
    if _service_faq_ki:
        _followup_knowledge_parts.append(
            f"FAQ DO SERVIÇO (usar APENAS quando o lead fizer uma pergunta diretamente coberta):\n"
            f"{_service_faq_ki}\n"
            f"INSTRUÇÃO: Responda com base no FAQ. Se a pergunta não estiver coberta, "
            f"diga que vai confirmar com a equipa.\n"
        )
    followup_knowledge_block = (
        "\nKNOWLEDGE BASE (usar conforme as instruções de cada bloco):\n"
        + "\n".join(_followup_knowledge_parts)
    ) if _followup_knowledge_parts else ""

    followup_priority_rule = (
        "- CONTEXTO PRIORITÁRIO (follow-up tick): use followup_contract_signals como fonte principal da resposta. "
        "Priorize meeting_or_session_happened, followup_goal, operator_note, outcome e followup_variant.\n"
        "- Se houver no-show/remarcação no contrato, conduza retomada e proposta de novo horário; "
        "não reabra qualificação antiga por padrão.\n"
        "- O histórico é memória contextual; ele NÃO é backlog de perguntas pendentes no follow-up automático.\n"
        "- Mesmo que o histórico tenha pergunta antiga sem resposta (ex.: localização/orçamento), não repita por padrão.\n"
        "- Só retome algo do histórico se estiver diretamente necessário para o objetivo do follow-up atual.\n"
        "- qualification_state e missing_fields são SOMENTE memória auxiliar (read-only) neste tick.\n"
        "- É proibido usar missing_fields de qualification como alvo de coleta/pergunta.\n"
        "- Só faça pergunta nova quando ela estiver diretamente ligada ao objetivo do follow-up atual "
        "(ex.: remarcação, confirmação de presença, próximo passo do follow-up).\n"
        if is_followup_tick
        else "- Faça no máximo 1 pergunta por mensagem e priorize o próximo missing_field.\n"
    )
    qualification_context_block = (
        f"qualification_context_read_only: {json.dumps({'required_fields': mode_contract['required_fields'], 'missing_fields': mode_contract['missing_fields']}, ensure_ascii=False)}\n"
        if is_followup_tick
        else (
            f"Required fields: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}\n"
            f"Missing fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}\n"
        )
    )
    tone_block_followup = _build_tone_block(ai_profile, playbook)

    _followup_prompt = (
        f"Você é a FILHA FOLLOW-UP de um CRM de vendas WhatsApp.\n\n"
        f"PAPEL: Re-engajar o lead pós-apresentação. Variante: {followup_variant or 'padrão'}.\n"
        f"ESCOPO: Nutrir, tratar objeções, reagendar. Nunca reabrir campos de qualificação antigos em ticks automáticos.\n"
        f"TOM: {ai_summary.get('tone_of_voice') or 'profissional'} — empático e orientado a ação. Máx {playbook_summary.get('max_chars') or 'N/D'} caracteres.\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary.get('template_key')}. is_followup_tick: {is_followup_tick}.\n"
        "RECUSAS: Nunca invente informação. Nunca use urgência artificial sem urgency_offer. Nunca reabra qualificação em follow-up tick.\n"
        + tone_block_followup
        + "\nRetorne SOMENTE JSON válido no schema ChildResult:\n"
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
        f"{variant_rule}"
        "- Use tone_of_voice, brand_name e niche quando disponíveis.\n"
        "- Respeite playbook.max_chars se existir (senão, resposta curta).\n"
        "- recommended_next_category pode ser follow-up, closing ou null.\n"
        f"{followup_priority_rule}"
        "- outcome e kanban_highlight devem ser null.\n"
        "\nPROIBIÇÕES (violar qualquer uma é crítico):\n"
        "1. NUNCA invente informações que não estejam no contexto fornecido.\n"
        "2. NUNCA prometa descontos, prazos ou condições não presentes em offer_pack ou knowledge_items.\n"
        "3. NUNCA dê conselhos médicos, jurídicos ou financeiros.\n"
        "4. NUNCA mencione concorrentes pelo nome, a menos que estejam em knowledge_items.\n"
        "5. NUNCA use urgência artificial — só mencione urgência se urgency_offer estiver preenchido.\n"
        "6. NUNCA responda sobre assuntos fora do nicho do negócio — redirecione para o tema.\n"
        "7. Se não souber a resposta, diga que vai verificar com a equipa (→ handoff), não improvise.\n"
        "8. NUNCA reabra campos de qualificação em ticks automáticos.\n"
        f"9. NUNCA exceda {playbook_summary.get('max_chars') or 'N/D'} caracteres nas mensagens de recovery.\n"
        + _ESCAPE_HATCH_BLOCK
        + _build_validation_block(playbook_summary.get("max_chars"))
        + "\n"
        f"ROTA MÃE: {mother_decision.route_to} (confidence={mother_decision.confidence})\n"
        f"Motivo MÃE: {mother_decision.reason}\n"
        f"Objetivo MÃE: {mother_decision.objective or ''}\n"
        f"Modo normalizado: {agent_mode_normalized}\n"
        f"{qualification_context_block}"
        f"is_followup_tick: {json.dumps(is_followup_tick, ensure_ascii=False)}\n"
        f"{followup_knowledge_block}\n"
        "\n"
        "CONTEXTO:\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- playbook: {json.dumps(playbook_summary, ensure_ascii=False)}\n"
        f"- metadata: {json.dumps(metadata_summary, ensure_ascii=False)}\n"
        f"- followup_contract_signals: {json.dumps(followup_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- inbound_message_text: {message_text}\n"
    )
    return _inject_generated_parts(_followup_prompt, context, "followup")


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
    presentation_variant, presentation_variant_source = _resolve_presentation_variant(context, agent_mode_normalized)
    hybrid_flow_style = _resolve_hybrid_flow_style(context)
    tone_block_closing = _build_tone_block(ai_profile, playbook)

    _closing_prompt = (
        f"Você é a FILHA CLOSING de um CRM de vendas WhatsApp.\n\n"
        f"PAPEL: Finalizar o fechamento conforme o modo do agente.\n"
        f"ESCOPO: Modo {agent_mode_normalized}. Consultivo: handoff para humano. Agenda: confirmar horário+pagamento. Direto: conduzir pagamento.\n"
        f"TOM: {ai_summary.get('tone_of_voice') or 'profissional'} — confiante e claro. Máx {playbook_summary.get('max_chars') or 'N/D'} caracteres.\n"
        f"FRAMEWORK: Template {playbook_summary.get('template_key')}. Campos verificados: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}. Missing: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}.\n"
        "RECUSAS: Nunca feche sozinho em modo consultivo (handoff obrigatório). Nunca emita outcome/kanban_highlight fora da categoria closing.\n"
        + tone_block_closing
        + "\nRetorne SOMENTE JSON válido no schema ChildResult:\n"
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
        "\nPROIBIÇÕES (violar qualquer uma é crítico):\n"
        "1. NUNCA invente informações que não estejam no contexto fornecido.\n"
        "2. NUNCA prometa descontos, prazos ou condições não presentes em offer_pack ou knowledge_items.\n"
        "3. NUNCA dê conselhos médicos, jurídicos ou financeiros.\n"
        "4. NUNCA mencione concorrentes pelo nome, a menos que estejam em knowledge_items.\n"
        "5. NUNCA use urgência artificial — só mencione urgência se urgency_offer estiver preenchido.\n"
        "6. NUNCA responda sobre assuntos fora do nicho do negócio — redirecione para o tema.\n"
        "7. Se não souber a resposta, diga que vai verificar com a equipa (→ handoff), não improvise.\n"
        + _ESCAPE_HATCH_BLOCK
        + _build_validation_block(playbook_summary.get("max_chars"))
        + "\n"
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
    # Fase "closing" não tem few_shot_closing nem objection_rewrites gerados pelo meta-prompter.
    # tone_rules já está injectado via _build_tone_block() acima — chamar _inject_generated_parts
    # aqui causaria duplicação de regras de tom. Retorna o prompt directamente.
    return _closing_prompt

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


def _enforce_qualification_route_when_missing(
    mother_decision: MotherDecision,
    mode_contract: Dict[str, Any],
) -> MotherDecision:
    missing_fields = list(mode_contract.get("missing_fields") or [])
    if not missing_fields:
        return mother_decision
    if mother_decision.route_to == "qualification":
        return mother_decision
    mother_decision.route_to = "qualification"
    reason = str(mother_decision.reason or "").strip()
    forced_reason = "qualification_incomplete_forced_route"
    mother_decision.reason = f"{reason}|{forced_reason}" if reason else forced_reason
    return mother_decision


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
    effective_route_override: Optional[str] = None,
    anti_loop_rule3_applied: bool = False,
) -> DecisionOutput:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    current_category = lead.get("category")
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    presentation_variant, presentation_variant_source = _resolve_presentation_variant(context, agent_mode_normalized)
    hybrid_flow_style = _resolve_hybrid_flow_style(context)
    _, system_agent_mode_source = _compute_system_agent_mode(context)
    mother_agent_mode_raw, mother_agent_mode_conflict = _get_mother_mode_conflict(context, mother_decision)
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

    template_key = str(ai_profile.get("template_key") or "").strip().lower()
    if template_key == "hybrid_scheduler" and suggested_category == "closing":
        suggested_category = "apresentation"
        reason_add = "guardrail_hybrid_scheduler_no_closing"
        category_reason = f"{category_reason}|{reason_add}" if category_reason else reason_add

    qualification_auto_promoted = False
    anti_loop_rule1_applied = False
    effective_route_to = effective_route_override or mother_decision.route_to
    missing_fields = list(mode_contract.get("missing_fields") or [])
    filled_fields = list(mode_contract.get("filled_fields") or [])
    current_field = _select_current_field(missing_fields, filled_fields)
    if (
        mother_decision.route_to == "qualification"
        and not current_field
    ):
        qualification_auto_promoted = True
        anti_loop_rule1_applied = True
        effective_route_to = "apresentation"
        suggested_category = "apresentation"
        auto_promote_reason = "qualification_complete_auto_promote:apresentation"
        category_reason = (
            f"{category_reason}|{auto_promote_reason}" if category_reason else auto_promote_reason
        )

    outcome, highlight = apply_outcome_guardrails(current_category, child_result)
    if template_key == "hybrid_scheduler":
        outcome = None
        highlight = None
    next_action = "ask_qualification" if effective_route_to == "qualification" else "reply"
    question_text = str(child_result.question_text or child_result.message_text or "").strip()
    message_text = question_text
    message_field_used: Optional[str] = None
    # Fix P7: passive mode reply-first override.
    # Se a mãe emitiu next_action_hint='reply' com response_style=passive, o cliente fez uma pergunta
    # de catálogo/serviços. Nesse caso, o filho deve ter respondido em message_text — usar essa
    # resposta diretamente em vez de question_text (a pergunta de qualificação).
    _response_style = (ai_profile.get("response_style") or "passive").strip().lower()
    _passive_reply_override = (
        effective_route_to == "qualification"
        and (mother_decision.next_action_hint or "").strip().lower() == "reply"
        and _response_style == "passive"
        and bool(child_result.message_text)
    )
    if _passive_reply_override:
        next_action = "reply"
        message_text = str(child_result.message_text).strip()
        message_field_used = None
    elif next_action == "ask_qualification":
        if not current_field:
            next_action = "reply"
            effective_route_to = "apresentation"
            qualification_auto_promoted = True
            anti_loop_rule1_applied = True
        else:
            message_field_used = current_field
            if not message_text:
                message_text = _fallback_question_for_field(current_field)
    reason = f"route:{mother_decision.route_to}|effective_route:{effective_route_to}|{mother_decision.reason}"
    # NOTE (ETAPA 4): decision_trace é observabilidade apenas; não dispara efeitos colaterais.
    # A Etapa 4 deverá consumir sinais estruturados para automações no CRM (appointment/bot_disabled).
    meeting_scheduled = _extract_meeting_scheduled_signal(mother_decision)
    child_signals_structured = _normalize_scheduler_child_signals(
        context,
        mother_decision,
        child_result,
        effective_route_to=effective_route_to,
        presentation_variant=presentation_variant,
    )
    decision = DecisionOutput(
        next_action=next_action,
        message_text=message_text,
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
            "effective_route_to": effective_route_to,
            "mother_perceived_category": mother_decision.perceived_category,
            "mother_confidence": mother_decision.confidence,
            "lead_current_category": current_category,
            "guardrail_reason": guardrail_reason,
            "qualification_auto_promoted": qualification_auto_promoted,
            "agent_mode": ai_profile.get("agent_mode"),
            "agent_mode_normalized": agent_mode_normalized,
            "system_agent_mode_source": system_agent_mode_source,
            "mother_agent_mode_raw": mother_agent_mode_raw,
            "mother_agent_mode_conflict": mother_agent_mode_conflict,
            "meeting_scheduled": meeting_scheduled,
            "mother_objective": mother_decision.objective,
            "next_action_hint": mother_decision.next_action_hint,
            "presentation_variant": presentation_variant,
            "presentation_variant_source": presentation_variant_source,
            "hybrid_flow_style": hybrid_flow_style,
            "required_fields": mode_contract['required_fields'],
            "missing_fields": mode_contract['missing_fields'],
            "filled_fields": filled_fields,
            "current_field": current_field,
            "question_field_used": message_field_used,
            "qualification_state_present": bool(_qualification_state_from_context(context)),
            "qualification_filled_fields": mode_contract.get("filled_fields") or [],
            "qualification_missing_fields_source": mode_contract.get("missing_fields_source") or "heuristic",
            "last_questioned_field": mode_contract.get("last_questioned_field"),
            "attempts": mode_contract.get("attempts_json") or {},
            "anti_loop_rule1_applied": anti_loop_rule1_applied,
            "anti_loop_rule3_applied": anti_loop_rule3_applied,
            "child_signals_structured": child_signals_structured,
            "child_recommended_next_category": child_result.recommended_next_category,
            "mother_signals": {
                "meeting_scheduled": meeting_scheduled,
                "intent_level": ((mother_decision.signals or {}).get("intent_level") if isinstance(mother_decision.signals, dict) else None),
                "urgency_level": ((mother_decision.signals or {}).get("urgency_level") if isinstance(mother_decision.signals, dict) else None),
                "price_acceptance": ((mother_decision.signals or {}).get("price_acceptance") if isinstance(mother_decision.signals, dict) else None),
                "handoff_requested": ((mother_decision.signals or {}).get("handoff_requested") if isinstance(mother_decision.signals, dict) else None),
                "stop_reason": ((mother_decision.signals or {}).get("stop_reason") if isinstance(mother_decision.signals, dict) else None),
                "presentation_variant": ((mother_decision.signals or {}).get("presentation_variant") if isinstance(mother_decision.signals, dict) else None),
                "offer_presented": ((mother_decision.signals or {}).get("offer_presented") if isinstance(mother_decision.signals, dict) else None),
                "checkout_sent": ((mother_decision.signals or {}).get("checkout_sent") if isinstance(mother_decision.signals, dict) else None),
                "offer_item_name": ((mother_decision.signals or {}).get("offer_item_name") if isinstance(mother_decision.signals, dict) else None),
            },
        },
    )
    decision = _apply_mode_guardrails(decision, context, mother_decision, child_result)

    # Mídia rica no pitch — Agent 2 (Tarefa 3.6)
    # Se estamos em rota de apresentation para agent closer e offer_pack tem media_url,
    # sinaliza o runner para enviar a mídia antes do texto do pitch.
    if effective_route_to == "apresentation" and agent_mode_normalized in ("closer", "direto", "direto_autonomo"):
        raw_op = ai_profile.get("offer_pack")
        if isinstance(raw_op, str):
            try:
                raw_op = json.loads(raw_op)
            except Exception:
                raw_op = None
        if isinstance(raw_op, dict):
            media_url = raw_op.get("media_url")
            if media_url and str(media_url).strip():
                decision.pre_send_media = {
                    "media_url": str(media_url).strip(),
                    "media_type": str(raw_op.get("media_type") or "image").strip(),
                }

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
    qualification_current_field: Optional[str] = None
    qualification_retry_count = 0
    qualification_validation_status = "n/a"
    qualification_repeated_similarity = 0.0
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
        mode_ctx_forced_route = _build_mode_contract_context(context, mother_decision)
        mother_decision = _enforce_qualification_route_when_missing(
            mother_decision,
            mode_ctx_forced_route,
        )
        lead = context.get("lead") or {}
        force_followup_route = _is_followup_tick_context(context)
        route_for_child = "follow-up" if force_followup_route else mother_decision.route_to
        anti_loop_rule3_applied = False
        mode_ctx_pre: Optional[dict] = None

        if force_followup_route and logger:
            job = context.get("job") or {}
            payload = job.get("payload") or {}
            logger.info(
                "event=followup_tick_route_priority route_override=%s mother_route_to=%s lead_category=%s job_id=%s lead_id=%s",
                route_for_child,
                mother_decision.route_to,
                lead.get("category"),
                job.get("id") or payload.get("job_id"),
                lead.get("id") or payload.get("lead_id"),
            )

        if mother_decision.route_to == "qualification" and not force_followup_route:
            mode_ctx_pre = _build_mode_contract_context(context, mother_decision)
            missing_pre = list(mode_ctx_pre.get("missing_fields") or [])
            normalized_current_category = _normalize_category(lead.get("category"))
            is_upper_stage = normalized_current_category in {"apresentation", "follow-up", "closing"}
            if is_upper_stage or not missing_pre:
                route_for_child = "apresentation"
                anti_loop_rule3_applied = True
                if logger:
                    job = context.get("job") or {}
                    payload = job.get("payload") or {}
                    logger.info(
                        "event=qualification_anti_loop_rule3 route_override=%s mother_route_to=%s lead_category=%s "
                        "job_id=%s lead_id=%s",
                        route_for_child,
                        mother_decision.route_to,
                        lead.get("category"),
                        job.get("id") or payload.get("job_id"),
                        lead.get("id") or payload.get("lead_id"),
                    )

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

        if mother_decision.route_to == "qualification" and not anti_loop_rule3_applied and not force_followup_route:
            mode_ctx_pre = mode_ctx_pre or _build_mode_contract_context(context, mother_decision)
            mode = mode_ctx_pre.get("agent_mode_normalized")
            required_fields = list(mode_ctx_pre.get("required_fields") or [])
            if mode_ctx_pre.get("missing_fields_source") == "heuristic" and logger:
                logger.info(
                    "event=qualification_heuristic_fallback_used reason=%s",
                    _get_heuristic_reason(context),
                )
            if mode_ctx_pre.get("missing_fields_source") == "state_unavailable" and logger:
                logger.info(
                    "event=qualification_heuristic_fallback_disabled reason=state_unavailable",
                )
            playbook = context.get("playbook") or {}
            must_collect = playbook.get("must_collect") if isinstance(playbook.get("must_collect"), list) else []
            for item in must_collect:
                if isinstance(item, str) and item not in required_fields:
                    required_fields.append(item)

            fields_schema = {field: "string|number|object|null" for field in required_fields}
            extraction = {"extracted": {}, "confidence": {}, "evidence": {}, "raw": ""}
            extraction_failed = False
            persist_failed = False
            try:
                extraction = field_extractor.extract_fields_llm(context, fields_schema)
            except Exception:
                extraction = {"extracted": {}, "confidence": {}, "evidence": {}, "raw": ""}
                extraction_failed = True
                if logger:
                    logger.info("event=qualification_extractor_fallback reason=extractor_failed")

            extracted = extraction.get("extracted") if isinstance(extraction.get("extracted"), dict) else {}
            new_extracted = {k: v for k, v in extracted.items() if k in required_fields and _is_filled_value(v)}
            if "price_acceptance" in required_fields and "budget_or_price_acceptance" in extracted and "price_acceptance" not in new_extracted:
                value = extracted.get("budget_or_price_acceptance")
                if _is_filled_value(value):
                    new_extracted["price_acceptance"] = value
                    if logger:
                        logger.info("event=qualification_price_field_mapped from=budget_or_price_acceptance to=price_acceptance")
            if "budget_or_price_acceptance" in required_fields and "price_acceptance" in extracted and "budget_or_price_acceptance" not in new_extracted:
                value = extracted.get("price_acceptance")
                if _is_filled_value(value):
                    new_extracted["budget_or_price_acceptance"] = value
                    if logger:
                        logger.info("event=qualification_price_field_mapped from=price_acceptance to=budget_or_price_acceptance")

            lead = context.get("lead") or {}
            metadata = context.get("metadata") or {}
            user_id = lead.get("user_id") or (context.get("job") or {}).get("payload", {}).get("user_id")
            lead_id = lead.get("id") or (context.get("job") or {}).get("payload", {}).get("lead_id")

            if lead_id and user_id and new_extracted:
                try:
                    updated_state = crm_client.upsert_lead_qualification_state(
                        lead_id=int(lead_id),
                        user_id=int(user_id),
                        patch={
                            "stage": "qualification",
                            "agent_mode_normalized": mode,
                            "playbook_key": playbook.get("template_key") or playbook.get("name"),
                            "playbook_version": "v1",
                            "data_json": new_extracted,
                            "confidence_json": extraction.get("confidence") if isinstance(extraction.get("confidence"), dict) else {},
                        },
                    )
                    context["qualification_state"] = updated_state
                except Exception:
                    persist_failed = True
                    if logger:
                        logger.info("event=qualification_state_persist_fallback reason=persist_failed")
                    pass

            mode_ctx = _build_mode_contract_context(context, mother_decision)
            if mode_ctx.get("missing_fields_source") == "heuristic" and logger and (extraction_failed or persist_failed):
                reason = "persist_failed" if persist_failed else "extractor_failed"
                logger.info("event=qualification_heuristic_fallback_used reason=%s", reason)
            missing = list(mode_ctx.get("missing_fields") or [])
            filled_fields = list(mode_ctx.get("filled_fields") or [])
            current_field = _select_current_field(missing, filled_fields)
            qualification_current_field = current_field
            if not current_field:
                route_for_child = "apresentation"
                qualification_validation_status = "n/a"
                if logger:
                    job = context.get("job") or {}
                    payload = job.get("payload") or {}
                    logger.info(
                        "event=qualification_auto_promote_runtime route_override=%s mother_route_to=%s job_id=%s lead_id=%s",
                        route_for_child,
                        mother_decision.route_to,
                        job.get("id") or payload.get("job_id"),
                        lead.get("id") or payload.get("lead_id"),
                    )
            last_field = mode_ctx.get("last_questioned_field")
            attempts_map = mode_ctx.get("attempts_json") if isinstance(mode_ctx.get("attempts_json"), dict) else {}
            has_progress = bool(new_extracted)

            if lead_id and user_id and current_field:
                try:
                    if current_field == last_field and not has_progress:
                        updated_state = crm_client.increment_lead_qualification_attempt(
                            lead_id=int(lead_id),
                            user_id=int(user_id),
                            field=current_field,
                        )
                        context["qualification_state"] = updated_state
                        attempts = int((updated_state.get("attempts_json") or {}).get(current_field) or 0)
                        if mode == "consultivo" and attempts >= 2:
                            return DecisionOutput(
                                next_action="handoff",
                                message_text="Perfeito — para avançar com precisão, vou te encaminhar para um especialista humano.",
                                questions=[],
                                reason="qualification_loop_handoff",
                                suggested_category="qualification",
                                category_reason="qualification_loop_handoff",
                                outcome=None,
                                kanban_highlight=None,
                                signals=["qualification_loop"],
                                confidence=mother_decision.confidence,
                                decision_trace={
                                    "agent_mode_normalized": mode,
                                    "qualification_state_present": True,
                                    "last_questioned_field": current_field,
                                    "attempts": updated_state.get("attempts_json") or {},
                                    "qualification_missing_fields_source": mode_ctx.get("missing_fields_source") or "state",
                                    "loop_handoff": True,
                                },
                            )
                        metadata["qualification_rephrase"] = True
                    else:
                        updated_state = crm_client.upsert_lead_qualification_state(
                            lead_id=int(lead_id),
                            user_id=int(user_id),
                            patch={"last_questioned_field": current_field},
                        )
                        context["qualification_state"] = updated_state
                except Exception:
                    pass
        if route_for_child == "qualification":
            child_prompt = _build_child_prompt_qualification(context, message_text, mother_decision)
        elif route_for_child == "apresentation":
            child_prompt = _build_child_prompt_apresentation(context, message_text, mother_decision)
        elif route_for_child == "follow-up":
            try:
                child_prompt = _build_child_prompt_follow_up(context, message_text, mother_decision)
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
        elif route_for_child == "closing":
            try:
                child_prompt = _build_child_prompt_closing(context, message_text, mother_decision)
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
        else:
            child_prompt = _build_child_prompt(context, message_text, mother_decision)
        stage = "child_call"
        child_result: Optional[ChildResult] = None
        validation_errors: list[str] = []
        attempts = 2 if route_for_child == "qualification" else 1
        for attempt_index in range(attempts):
            qualification_retry_count = attempt_index
            prompt_to_use = child_prompt
            if validation_errors and route_for_child == "qualification":
                prompt_to_use = (
                    f"{child_prompt}\n\nVALIDATION_ERRORS: {json.dumps(validation_errors, ensure_ascii=False)}\n"
                    "Corrija o JSON para field=current_field e reformule a pergunta sem repetir texto anterior."
                )
            child_text = llm_service.generate_child_result(route_for_child, prompt_to_use)
            stage = "child_parse"
            child_payload = _extract_json_payload(child_text)
            if child_payload is None:
                validation_errors = ["invalid_json"]
                qualification_validation_status = "invalid_json"
                continue
            child_payload = _normalize_null_strings(child_payload)
            if "question_text" not in child_payload and "message_text" in child_payload:
                child_payload["question_text"] = child_payload.get("message_text")
            stage = "child_validate"
            child_result = ChildResult.model_validate(child_payload)
            if route_for_child != "qualification":
                break

            mode_ctx_now = _build_mode_contract_context(context, mother_decision)
            missing_now = list(mode_ctx_now.get("missing_fields") or [])
            filled_now = list(mode_ctx_now.get("filled_fields") or [])
            current_field_now = _select_current_field(missing_now, filled_now)
            qualification_current_field = current_field_now
            asked_all = mode_ctx_now.get("asked_questions_json") if isinstance(mode_ctx_now.get("asked_questions_json"), list) else []
            asked_for_field = [
                str(item.get("question_text") or "")
                for item in asked_all
                if isinstance(item, dict) and item.get("field") == current_field_now
            ]
            candidate_question = str(child_result.question_text or child_result.message_text or "").strip()
            child_field = str(child_result.field or "").strip() or None
            if not current_field_now:
                qualification_validation_status = "no_current_field"
                break
            if child_field != current_field_now:
                validation_errors = [f"field_mismatch expected={current_field_now} got={child_field}"]
                qualification_validation_status = "field_mismatch"
                continue
            if not candidate_question:
                validation_errors = ["empty_question_text"]
                qualification_validation_status = "empty_question_text"
                continue
            last_same = asked_for_field[-1] if asked_for_field else ""
            sim = _question_similarity(candidate_question, last_same)
            qualification_repeated_similarity = sim
            if last_same and sim >= 0.92:
                validation_errors = [f"repeated_question similarity={sim:.2f}"]
                qualification_validation_status = "repeated_question"
                continue
            qualification_validation_status = "accepted"
            break

        if child_result is None:
            raise ValueError("llm returned invalid child payload")

        if (
            route_for_child == "qualification"
            and qualification_validation_status != "accepted"
            and qualification_current_field is not None
        ):
            fallback_field = qualification_current_field
            child_result.field = fallback_field
            child_result.question_text = _fallback_question_for_field(fallback_field)
            child_result.message_text = child_result.question_text
            qualification_validation_status = "fallback"

        stage = "compose"
        decision = compose_decision_output(
            context=context,
            mother_decision=mother_decision,
            child_result=child_result,
            effective_route_override=route_for_child,
            anti_loop_rule3_applied=anti_loop_rule3_applied,
        )
        if decision.next_action == "ask_qualification":
            trace_local = decision.decision_trace if isinstance(decision.decision_trace, dict) else {}
            field_used = trace_local.get("question_field_used")
            question_text = decision.message_text
            lead = context.get("lead") or {}
            user_id = lead.get("user_id") or (context.get("job") or {}).get("payload", {}).get("user_id")
            lead_id = lead.get("id") or (context.get("job") or {}).get("payload", {}).get("lead_id")
            job = context.get("job") or {}
            payload = job.get("payload") or {}
            job_ref = job.get("id") or payload.get("job_id")
            if lead_id and user_id and field_used and question_text:
                try:
                    crm_client.upsert_lead_qualification_state(
                        lead_id=int(lead_id),
                        user_id=int(user_id),
                        patch={
                            "last_questioned_field": field_used,
                            "last_question_text": question_text,
                            "asked_questions_json": [{
                                "field": field_used,
                                "question_text": question_text,
                                "created_at": datetime.utcnow().isoformat(),
                                "job_id": job_ref,
                            }],
                        },
                    )
                except Exception:
                    pass
        decision = _sanitize_category_decision(decision, context, logger_instance=logger)
        if decision.decision_trace and isinstance(decision.decision_trace, dict):
            decision.decision_trace["suggested_category_final"] = decision.suggested_category
            is_qualification_ask = (
                decision.decision_trace.get("effective_route_to") == "qualification"
                and decision.next_action == "ask_qualification"
                and route_for_child == "qualification"
            )
            if is_qualification_ask:
                decision.decision_trace["qualification_validation_status"] = qualification_validation_status
                decision.decision_trace["qualification_retry_count"] = qualification_retry_count
                decision.decision_trace["qualification_repeated_similarity"] = qualification_repeated_similarity
            else:
                decision.decision_trace.pop("qualification_validation_status", None)
                decision.decision_trace.pop("qualification_retry_count", None)
                decision.decision_trace.pop("qualification_repeated_similarity", None)
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
            if (
                trace.get("effective_route_to") == "qualification"
                and decision.next_action == "ask_qualification"
                and route_for_child == "qualification"
            ):
                logger.info(
                    "event=qualification_question job_id=%s lead_id=%s current_field=%s child_field=%s "
                    "validation_status=%s retry_count=%s repeated_similarity_score=%.2f last_questioned_field=%s missing_fields=%s",
                    log_context["job_id"],
                    log_context["lead_id"],
                    trace.get("current_field"),
                    trace.get("question_field_used"),
                    trace.get("qualification_validation_status"),
                    trace.get("qualification_retry_count"),
                    float(trace.get("qualification_repeated_similarity") or 0.0),
                    trace.get("last_questioned_field"),
                    trace.get("missing_fields"),
                )
            logger.info(
                "decision_qualification_anti_loop job_id=%s lead_id=%s missing_fields=%s filled_fields=%s "
                "current_field=%s question_field_used=%s effective_route_to=%s qualification_auto_promoted=%s "
                "anti_loop_rule1_applied=%s anti_loop_rule3_applied=%s next_action=%s",
                log_context["job_id"],
                log_context["lead_id"],
                trace.get("missing_fields"),
                trace.get("filled_fields"),
                trace.get("current_field"),
                trace.get("question_field_used"),
                trace.get("effective_route_to"),
                trace.get("qualification_auto_promoted"),
                trace.get("anti_loop_rule1_applied"),
                trace.get("anti_loop_rule3_applied"),
                decision.next_action,
            )
        # Detecção de sinal de compra — Agent 1 (Tarefa 3.7)
        # Só aplicável a modos consultivo/agenda; Agent 2 (direto) tem fluxo próprio.
        _ai_profile_for_signal = context.get("ai_profile") or {}
        _agent_mode_for_signal = _normalize_agent_mode(context, mother_decision)
        if _agent_mode_for_signal in _AGENT1_MODES and decision.next_action in ("reply", "ask_qualification"):
            _raw_keywords = _ai_profile_for_signal.get("buying_signal_keywords")
            if isinstance(_raw_keywords, str):
                try:
                    _raw_keywords = json.loads(_raw_keywords)
                except Exception:
                    _raw_keywords = None
            _keywords_list: Optional[List[str]] = (
                [str(k) for k in _raw_keywords if k]
                if isinstance(_raw_keywords, list)
                else None
            )
            if _detect_buying_signals(message_text, _keywords_list):
                _lead_for_signal = context.get("lead") or {}
                _lead_id_signal = _lead_for_signal.get("id") or (context.get("job") or {}).get("payload", {}).get("lead_id")
                if _lead_id_signal:
                    try:
                        crm_client.create_buying_signal_notification(int(_lead_id_signal))
                    except Exception:
                        pass
                # Se offer_pack tem checkout_link, incluir na mensagem automaticamente
                _offer_pack_raw = _ai_profile_for_signal.get("offer_pack")
                if isinstance(_offer_pack_raw, str):
                    try:
                        _offer_pack_raw = json.loads(_offer_pack_raw)
                    except Exception:
                        _offer_pack_raw = None
                _checkout_link: Optional[str] = None
                if isinstance(_offer_pack_raw, dict):
                    _checkout_link = str(_offer_pack_raw.get("checkout_link") or "").strip() or None
                    # Também verifica no primeiro item de items
                    if not _checkout_link:
                        _items = _offer_pack_raw.get("items")
                        if isinstance(_items, list) and _items and isinstance(_items[0], dict):
                            _checkout_link = str(_items[0].get("checkout_link") or "").strip() or None
                if _checkout_link and decision.message_text and _checkout_link not in decision.message_text:
                    decision.message_text = f"{decision.message_text}\n\n{_checkout_link}"
                if decision.decision_trace is None:
                    decision.decision_trace = {}
                decision.decision_trace["buying_signal_detected"] = True
                decision.decision_trace["checkout_link_injected"] = bool(_checkout_link)
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
