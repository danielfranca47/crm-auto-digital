from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from automations.assistente_ia.variable_resolver import (
    build_resolution_context_from_db,
    resolve_template,
)
from core_client import fetch_core_ai_profile, fetch_core_ai_profile_resolve
from database import get_connection
from security_core import CurrentUser
from services.ai_playbooks import get_playbook
from services.ai_orchestrator.history import get_recent_history
from services.ai_orchestrator.inbound_event import InboundEvent
from services.qualification_state import get_qualification_state

logger = logging.getLogger(__name__)

# Campos do AI Profile que podem conter tokens {{variavel}}
_TEMPLATE_FIELDS = [
    "origin_inbound_opener",
    "origin_outbound_opener",
    "handoff_custom_text",
    "warming_social_proof",
    "warming_session_preview",
]
# Campos dentro de offer_pack que também podem ter tokens
_OFFER_PACK_TEMPLATE_FIELDS = ["guarantee_text", "upsell_message"]


def _resolve_profile_templates(
    ai_profile: Dict[str, Any],
    lead_id: int,
    user_id: int,
) -> None:
    """
    Resolve variáveis dinâmicas ({{lead.nome}}, {{saudacao}}, etc.) nos campos
    de template do ai_profile, alterando o dict in-place.
    Não lança exceção — em caso de erro, os campos permanecem sem substituição.
    """
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            ctx = build_resolution_context_from_db(
                conn=conn,
                lead_id=lead_id,
                user_id=user_id,
                ai_profile=ai_profile,
            )
        for field in _TEMPLATE_FIELDS:
            raw = ai_profile.get(field)
            if raw:
                ai_profile[field] = resolve_template(raw, ctx)
        offer_pack = ai_profile.get("offer_pack")
        if isinstance(offer_pack, dict):
            for field in _OFFER_PACK_TEMPLATE_FIELDS:
                raw = offer_pack.get(field)
                if raw:
                    offer_pack[field] = resolve_template(raw, ctx)
    except Exception:
        logger.exception("_resolve_profile_templates failed — using raw template text")


def _resolve_presentation_contract(
    *,
    ai_profile: Dict[str, Any] | None,
    agent_mode_normalized: str,
) -> Dict[str, Any]:
    profile = ai_profile or {}
    raw_variant = str(profile.get("presentation_variant") or "").strip().lower()
    raw_hybrid = str(profile.get("hybrid_flow_style") or "").strip().lower()

    valid_variants = {"sales", "scheduler"}
    valid_hybrid_styles = {"offer_then_schedule", "schedule_then_offer"}

    if raw_variant in valid_variants:
        variant = raw_variant
        source = "ai_profile"
    elif agent_mode_normalized == "direto":
        variant = "sales"
        source = "agent_mode_default"
    elif agent_mode_normalized in {"agenda", "consultivo"}:
        variant = "scheduler"
        source = "agent_mode_default"
    else:
        variant = "scheduler"
        source = "fallback"

    hybrid_style = raw_hybrid if raw_hybrid in valid_hybrid_styles else None
    if hybrid_style and source != "ai_profile":
        source = f"{source}+hybrid"

    offer_pack = profile.get("offer_pack")
    if isinstance(offer_pack, str):
        try:
            parsed = json.loads(offer_pack)
            offer_pack = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            offer_pack = None
    elif not isinstance(offer_pack, dict):
        offer_pack = None

    return {
        "presentation_variant": variant,
        "presentation_variant_source": source,
        "hybrid_flow_style": hybrid_style,
        "offer_pack": offer_pack,
    }

def _normalize_agent_mode_for_bundle(ai_profile: Dict[str, Any] | None, template_key: str | None) -> str:
    profile = ai_profile or {}
    mode = str(profile.get("agent_mode") or "").strip().lower()
    if mode in {"consultivo", "agenda", "direto"}:
        return mode
    if mode == "closer":
        return "direto"
    if mode in {"sdr_scheduler", "sdr"}:
        return "agenda"
    template_norm = str(template_key or "")
    if template_norm.startswith("hybrid_scheduler"):
        return "agenda"
    if template_norm.startswith("closer"):
        return "direto"
    if template_norm.startswith("consult"):
        return "consultivo"
    return "agenda"


def _build_qualification_context(ai_profile: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Lê qualification_fields do AI Profile e constrói dois blocos para injeção no prompt:
    - must_collect_with_questions: campos mode=required com question e passive_hint
    - nice_to_collect: campos mode=optional com question e passive_hint
    Mantém backward compat: se qualification_fields não existe, usa qualification_required_fields.
    """
    profile = ai_profile or {}
    qual_fields = profile.get("qualification_fields")

    if not isinstance(qual_fields, list) or len(qual_fields) == 0:
        # Backward compat: sem qualification_fields, usa a lista simples de keys
        required_keys = profile.get("qualification_required_fields")
        if isinstance(required_keys, list) and len(required_keys) > 0:
            return {"must_collect": required_keys}
        return {}

    must_collect_with_questions = [
        {
            "key": f["key"],
            "label": f.get("label", f["key"]),
            "question": f.get("question"),
            "passive_hint": f.get("passive_hint"),
        }
        for f in qual_fields
        if isinstance(f, dict) and f.get("mode") == "required"
    ]
    nice_to_collect = [
        {
            "key": f["key"],
            "label": f.get("label", f["key"]),
            "question": f.get("question"),
            "passive_hint": f.get("passive_hint"),
        }
        for f in qual_fields
        if isinstance(f, dict) and f.get("mode") == "optional"
    ]

    result: Dict[str, Any] = {}
    if must_collect_with_questions:
        result["must_collect_with_questions"] = must_collect_with_questions
        # Mantém must_collect (lista de keys) para backward compat com executors
        result["must_collect"] = [f["key"] for f in must_collect_with_questions]
    if nice_to_collect:
        result["nice_to_collect"] = nice_to_collect
    return result


def apply_mode_overrides(
    playbook: Dict[str, Any],
    agent_mode_normalized: str,
    ai_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    merged = dict(playbook or {})
    if agent_mode_normalized == "consultivo":
        merged.update({
            "max_chars": 700,
            "qualification_depth": "high",
            "max_questions_per_turn": 1,
            "must_handoff_on_high_intent": True,
        })
    elif agent_mode_normalized == "agenda":
        merged.update({
            "max_chars": 350,
            "qualification_depth": "medium",
        })
        # qualification_fields (novo formato rico) tem precedência sobre qualification_required_fields
        new_format = (ai_profile or {}).get("qualification_fields")
        has_new_format = isinstance(new_format, list) and len(new_format) > 0
        if not has_new_format:
            # Só injeta must_collect se o AI Profile definiu campos explicitamente (formato legado)
            profile_fields = (ai_profile or {}).get("qualification_required_fields")
            if isinstance(profile_fields, list) and len(profile_fields) > 0:
                merged.update({"must_collect": profile_fields})
            # profile_fields == None → não configurado, sem override automático
            # profile_fields == [] → lista vazia explícita = modo passivo, sem must_collect
    elif agent_mode_normalized == "direto":
        merged.update({
            "max_chars": 300,
            "qualification_depth": "low",
            "cta_every_turn": True,
        })

    # Injetar contexto de qualificação enriquecido (qualification_fields sobrescreve se presente)
    qual_context = _build_qualification_context(ai_profile)
    if qual_context:
        merged.update(qual_context)

    return merged


class ContextBundle(BaseModel):
    user_id: int
    entitlements: Dict[str, Any] = Field(default_factory=dict)
    ai_profile: Dict[str, Any] | None = None
    playbook: Dict[str, Any]
    lead: Dict[str, Any]
    history: List[Dict[str, Any]]
    next_action: str = "reply"
    metadata: Dict[str, Any]
    conversation_goal: str | None = None
    qualification_state: Optional[Dict[str, Any]] = None
    knowledge_items: Optional[Dict[str, str]] = None
    knowledge_media: Optional[Dict[str, List]] = None
    training_examples: Optional[Dict[str, Any]] = None
    # Estrutura: { "qualification": { "good": [...], "bad": [...] }, "apresentation": {...}, ... }
    generated_prompt_parts: Optional[Dict[str, Any]] = None
    lead_detected_language: Optional[str] = None
    calendar_busy_slots: Optional[List[Dict[str, Any]]] = None


def _classify_lead_origin(origin_raw: Optional[str]) -> tuple[bool, str, str]:
    """
    Direção da conversa a partir de lead.origin. Único valor que sinaliza prospecção
    fria é o literal "outbound" (gravado via PATCH /api/leads/{id} pelo
    ProspectConfirmModal ou por agent-local/log_outbound). Qualquer outro valor —
    'whatsapp_inbound', 'Formulário Website', 'Manual', 'Planilha', canais de
    marketing livres — é inbound por default seguro.
    """
    is_outbound = (origin_raw or "").strip().lower() == "outbound"
    lead_origin = "outbound" if is_outbound else "inbound"
    lead_origin_label = (
        "OUTBOUND (lead foi abordado — não te conhecia)"
        if is_outbound
        else "INBOUND (lead veio te procurar)"
    )
    return is_outbound, lead_origin, lead_origin_label


def build_context_bundle(
    current_user: CurrentUser,
    lead_id: int,
    inbound_message_text: str,
    channel: str = "whatsapp",
) -> ContextBundle:
    """Legacy builder for authenticated flows (still used by manual script)."""

    if not current_user.token:
        raise HTTPException(status_code=401, detail="Token ausente para consultar o core")

    entitlements = current_user.entitlements or {}
    ai_profile = fetch_core_ai_profile(current_user.token)
    template_key = ai_profile.get("template_key") if ai_profile else None
    normalized_mode = _normalize_agent_mode_for_bundle(ai_profile, template_key)
    if ai_profile is not None:
        ai_profile["agent_mode"] = normalized_mode
    presentation_contract = _resolve_presentation_contract(ai_profile=ai_profile, agent_mode_normalized=normalized_mode)
    if ai_profile is not None:
        ai_profile["presentation_variant"] = presentation_contract["presentation_variant"]
        ai_profile["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
        ai_profile["offer_pack"] = presentation_contract["offer_pack"]
    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"
    playbook = apply_mode_overrides(playbook, normalized_mode, ai_profile=ai_profile)
    playbook["presentation_variant"] = presentation_contract["presentation_variant"]
    playbook["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    playbook["offer_pack"] = presentation_contract["offer_pack"]

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads WHERE id = ? AND user_id = ?", (lead_id, current_user.id))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    lead_data = {key: row[key] for key in row.keys()}

    if ai_profile:
        _resolve_profile_templates(ai_profile, lead_id, current_user.id)

    _is_outbound, _lead_origin, _lead_origin_label = _classify_lead_origin(lead_data.get("origin"))
    metadata = {
        "channel": channel,
        "inbound_message_text": inbound_message_text,
        "received_at": datetime.utcnow().isoformat(),
        "presentation_variant": presentation_contract["presentation_variant"],
        "presentation_variant_source": presentation_contract["presentation_variant_source"],
        "hybrid_flow_style": presentation_contract["hybrid_flow_style"],
        "lead_origin": _lead_origin,
        "lead_origin_label": _lead_origin_label,
    }

    history: List[Dict[str, Any]] = []

    return ContextBundle(
        user_id=current_user.id,
        entitlements=entitlements,
        ai_profile=ai_profile or {},
        playbook=playbook,
        lead=lead_data,
        history=history,
        next_action=playbook.get("default_next_action", "reply"),
        metadata=metadata,
        conversation_goal="qualify" if not history else "advance",
    )


def _load_lead(user_id: int, lead_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads WHERE id = ? AND user_id = ?", (lead_id, user_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return {key: row[key] for key in row.keys()}


def build_context_bundle_from_inbound(event: InboundEvent) -> ContextBundle:
    ai_profile: Dict[str, Any] | None = None
    ai_profile_status = "ok"
    try:
        ai_profile = fetch_core_ai_profile_resolve(event.user_id)
    except HTTPException as exc:  # fallback
        logger.warning("AI profile resolve failed: %s", exc)
        ai_profile_status = "unavailable"
    else:
        if ai_profile is None:
            ai_profile_status = "not_found"

    template_key = ai_profile.get("template_key") if ai_profile else None
    normalized_mode = _normalize_agent_mode_for_bundle(ai_profile, template_key)
    if ai_profile is not None:
        ai_profile["agent_mode"] = normalized_mode
    presentation_contract = _resolve_presentation_contract(ai_profile=ai_profile, agent_mode_normalized=normalized_mode)
    if ai_profile is not None:
        ai_profile["presentation_variant"] = presentation_contract["presentation_variant"]
        ai_profile["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
        ai_profile["offer_pack"] = presentation_contract["offer_pack"]
    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"
    playbook = apply_mode_overrides(playbook, normalized_mode, ai_profile=ai_profile)
    playbook["presentation_variant"] = presentation_contract["presentation_variant"]
    playbook["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    playbook["offer_pack"] = presentation_contract["offer_pack"]

    lead_data = _load_lead(user_id=event.user_id, lead_id=event.lead_id)

    if ai_profile:
        _resolve_profile_templates(ai_profile, event.lead_id, event.user_id)

    history = get_recent_history(event.lead_id)
    conversation_goal = "qualify" if len(history) <= 1 else "advance"

    _is_outbound, _lead_origin, _lead_origin_label = _classify_lead_origin(lead_data.get("origin"))
    metadata = {
        "channel": event.channel,
        "inbound_message_text": event.message_text,
        "received_at": event.received_at or datetime.utcnow().isoformat(),
        "message_id": event.message_id,
        "instance_id": event.instance_id,
        "provider": event.provider,
        "phone": event.phone,
        "ai_profile_status": ai_profile_status if ai_profile is None else "ok",
        "presentation_variant": presentation_contract["presentation_variant"],
        "presentation_variant_source": presentation_contract["presentation_variant_source"],
        "hybrid_flow_style": presentation_contract["hybrid_flow_style"],
        "lead_origin": _lead_origin,
        "lead_origin_label": _lead_origin_label,
    }

    return ContextBundle(
        user_id=event.user_id,
        entitlements={},
        ai_profile=ai_profile or {},
        playbook=playbook,
        lead=lead_data,
        history=history,
        next_action=playbook.get("default_next_action", "reply"),
        metadata=metadata,
        conversation_goal=conversation_goal,
    )


def _load_training_examples(user_id: int, ai_profile_id: int, agent_mode: str | None) -> Dict[str, Any]:
    """
    Carrega exemplos de treino do playground agrupados por fase.

    Retorna até 3 exemplos bons e 3 ruins por fase (priorizando os mais recentes),
    filtrados por user_id, ai_profile_id e agent_mode (quando disponível).
    """
    phases = ["qualification", "apresentation", "followup", "closing"]
    result: Dict[str, Any] = {}

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        for phase in phases:
            good_examples: List[Dict[str, Any]] = []
            bad_examples: List[Dict[str, Any]] = []

            params: tuple = (str(user_id), ai_profile_id, phase)
            mode_filter = ""
            if agent_mode:
                mode_filter = " AND (agent_mode IS NULL OR agent_mode = ?)"
                params = (str(user_id), ai_profile_id, phase, agent_mode)

            cur.execute(
                f"""
                SELECT lead_message, bot_message, rating, comment
                  FROM playground_training_items
                 WHERE user_id = ? AND ai_profile_id = ? AND phase = ?
                   {mode_filter}
                 ORDER BY created_at DESC
                 LIMIT 30
                """,
                params,
            )
            for row in cur.fetchall():
                item = {
                    "lead_message": row["lead_message"],
                    "bot_message": row["bot_message"],
                    "rating": row["rating"],
                    "comment": row["comment"],
                }
                if row["rating"] == "excelente" and len(good_examples) < 3:
                    good_examples.append(item)
                elif row["rating"] in ("boa",) and len(good_examples) < 3:
                    good_examples.append(item)
                elif row["rating"] in ("ruim", "regular") and len(bad_examples) < 3:
                    bad_examples.append(item)

            if good_examples or bad_examples:
                result[phase] = {"good": good_examples, "bad": bad_examples}

    return result


_MULTI_ITEM_CATEGORIES = {"service_pricing_table"}


def _render_service_pricing_block(title: str, content_text: str) -> str:
    """Renderiza um item de service_pricing_table como bloco de texto p/ o LLM.

    Itens novos guardam linhas estruturadas como JSON ({"format": "structured_v1",
    "rows": [...]}); itens legados guardam texto livre. Em qualquer um dos casos o
    resultado final é só texto, com o título da tabela como cabeçalho.
    """
    body = content_text
    try:
        parsed = json.loads(content_text)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict) and parsed.get("format") == "structured_v1" and isinstance(parsed.get("rows"), list):
        lines = []
        for row in parsed["rows"]:
            if not isinstance(row, dict):
                continue
            nome = str(row.get("nome") or "").strip()
            if not nome:
                continue
            duracao = row.get("duracaoMinutos")
            preco = str(row.get("preco") or "").strip()
            descricao = str(row.get("descricao") or "").strip()
            line = f"{nome} — {duracao}min" if duracao else nome
            if preco:
                line += f": {preco}"
            if descricao:
                line += f" ({descricao})"
            lines.append(f"- {line}")
        body = "\n".join(lines)
    if not body:
        return ""
    return f"## {title}\n{body}" if title else body


def _load_knowledge_items(user_id: int) -> Dict[str, str]:
    """Carrega knowledge items do utilizador agrupados por categoria.

    Para a maioria das categorias, só a entrada mais recente é usada (1 item por
    categoria). Categorias em _MULTI_ITEM_CATEGORIES agregam TODOS os itens activos
    (ex.: várias tabelas de serviços/preços, cada uma identificada pelo seu título)."""
    knowledge_by_category: Dict[str, str] = {}
    multi_blocks: Dict[str, list] = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT title, category, content_text FROM knowledge_items WHERE user_id = ? AND active_in_funnel = 1 ORDER BY updated_at DESC",
            (user_id,),
        )
        for row in cur.fetchall():
            cat = row["category"] or "uncategorized"
            if cat in _MULTI_ITEM_CATEGORIES:
                block = _render_service_pricing_block(row["title"] or "", row["content_text"] or "")
                if block:
                    multi_blocks.setdefault(cat, []).append(block)
            elif cat not in knowledge_by_category:
                knowledge_by_category[cat] = row["content_text"]
    for cat, blocks in multi_blocks.items():
        knowledge_by_category[cat] = "\n\n".join(blocks)
    return knowledge_by_category


def _load_knowledge_media(user_id: int) -> Dict[str, list]:
    """Carrega mídias do knowledge agrupadas por categoria (espelho do executor.py)."""
    knowledge_media: Dict[str, list] = {}
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ki.category, kim.media_url, kim.media_type, kim.language, kim.send_order
              FROM knowledge_item_media kim
              JOIN knowledge_items ki ON ki.id = kim.knowledge_item_id
             WHERE ki.user_id = ? AND ki.active_in_funnel = 1
             ORDER BY ki.category, ki.updated_at DESC, kim.send_order ASC, kim.id ASC
            """,
            (user_id,),
        )
        for row in cur.fetchall():
            cat = row["category"] or "uncategorized"
            knowledge_media.setdefault(cat, []).append({
                "media_url":  row["media_url"],
                "media_type": row["media_type"],
                "language":   row["language"],
                "send_order": row["send_order"],
            })
    return knowledge_media


def _format_hours_value(value: str) -> str:
    """Converte JSON estruturado de horários em texto legível para o prompt."""
    import json as _json
    try:
        days = _json.loads(value)
        if not isinstance(days, list):
            return value
    except Exception:
        return value

    DAY_ABBR = {"seg": "Seg", "ter": "Ter", "qua": "Qua", "qui": "Qui",
                "sex": "Sex", "sab": "Sáb", "dom": "Dom"}
    parts = []
    for d in days:
        abbr = DAY_ABBR.get(d.get("day", ""), d.get("label", d.get("day", "")))
        if d.get("closed"):
            parts.append(f"{abbr}: Fechado")
        else:
            open_t = (d.get("open") or "").replace(":", "h")
            close_t = (d.get("close") or "").replace(":", "h")
            parts.append(f"{abbr}: {open_t}-{close_t}")
    return " | ".join(parts) if parts else value


def _load_business_info(user_id: int) -> Optional[str]:
    """Carrega business_info — espelho de executor.py para garantir paridade de contexto."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT field_key, label, value FROM business_info
             WHERE user_id = ? AND enabled = 1
               AND value IS NOT NULL AND trim(coalesce(value,'')) != ''
             ORDER BY sort_order ASC, id ASC
            """,
            (user_id,),
        )
        biz_lines = []
        for row in cur.fetchall():
            v = row["value"]
            if row["field_key"] == "horario":
                v = _format_hours_value(v)
            biz_lines.append(f"• {row['label']}: {v}")
    return "\n".join(biz_lines) if biz_lines else None


_CALENDAR_BUSY_SLOTS_WINDOW_DAYS = 30


def _load_calendar_busy_slots(user_id: int, window_days: int = _CALENDAR_BUSY_SLOTS_WINDOW_DAYS) -> List[Dict[str, Any]]:
    """Carrega compromissos reais do profissional para a IA não inventar disponibilidade.

    Mesma cláusula de scoping de routes/appointments.py::list_appointments —
    cobre tanto appointments criados pelo CRM (lead_id IS NOT NULL, herdam
    user_id do lead) quanto importados do Google Calendar (lead_id IS NULL,
    user_id próprio). Manter sincronizado se aquela query mudar.
    """
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=window_days)
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.id, a.lead_id, a.start_at, a.end_at
              FROM appointments a LEFT JOIN leads l ON a.lead_id = l.id
             WHERE (a.lead_id IS NOT NULL AND l.user_id = ? OR a.lead_id IS NULL AND a.user_id = ?)
               AND a.status = 'pending'
               AND a.end_at >= ?
               AND a.start_at <= ?
            """,
            (user_id, user_id, now.isoformat(), window_end.isoformat()),
        )
        return [
            {"id": row["id"], "lead_id": row["lead_id"], "start_at": row["start_at"], "end_at": row["end_at"]}
            for row in cur.fetchall()
        ]


def enrich_context_bundle(bundle: ContextBundle, user_id: int) -> ContextBundle:
    """
    Enriquece o ContextBundle com todos os campos extras necessários para o decision_engine.

    É a ÚNICA fonte de enriquecimento — chamada pelo playground E pelo executor.
    Adicionar qualquer campo novo aqui garante paridade automática entre os dois caminhos.
    """
    updates: Dict[str, Any] = {}

    # B2 — business_info (injetado como categoria especial em knowledge_items)
    business_info_text = _load_business_info(user_id)
    if business_info_text:
        knowledge_items = dict(bundle.knowledge_items or {})
        knowledge_items["business_info"] = business_info_text
        updates["knowledge_items"] = knowledge_items

    # B3 — generated_prompt_parts (sobe do ai_profile para o nível raiz do contexto)
    if bundle.generated_prompt_parts is None:
        gpp = (bundle.ai_profile or {}).get("generated_prompt_parts") or {}
        if gpp:
            updates["generated_prompt_parts"] = gpp

    # B4 — lead_detected_language (para filtro de knowledge_media por idioma)
    if bundle.lead_detected_language is None:
        lang = (bundle.lead or {}).get("detected_language") or "all"
        updates["lead_detected_language"] = lang

    # B5 — calendar_busy_slots (agentes de agenda não devem inventar disponibilidade)
    if bundle.calendar_busy_slots is None and (bundle.ai_profile or {}).get("agent_mode") == "agenda":
        updates["calendar_busy_slots"] = _load_calendar_busy_slots(user_id)

    # B6 — bot_disabled_reason="meeting_scheduled" (paridade Playground ↔ executor real)
    # routes/executor.py também seta isto para o fluxo real do WhatsApp, mas só para ESTE motivo
    # específico (decide() em decision_engine.py trata-o como gestão pós-confirmação, não como
    # silêncio total). Replicado aqui para que o Playground também exercite esse caminho — outros
    # motivos de bot_disabled (ex.: handoff_requested) continuam não propagados no Playground,
    # propositalmente (ver docs/architecture/agenda.md).
    lead = bundle.lead or {}
    if lead.get("bot_disabled") and lead.get("bot_disabled_reason") == "meeting_scheduled":
        _meeting_management_enabled = bool((bundle.ai_profile or {}).get("meeting_management_enabled", True))
        bundle.metadata["bot_disabled"] = True
        bundle.metadata["bot_disabled_reason"] = "meeting_scheduled" if _meeting_management_enabled else None

    # B7 — Resolver {{}} nos campos de template do AI Profile e nos blocos do
    # Fluxo de Venda (orientacao/mensagem). Corre aqui — não nos builders —
    # pela mesma razão do resto desta função: é o único ponto que garante
    # paridade Playground ↔ executor real automaticamente. Antes desta linha,
    # o Playground nunca resolvia {{}} nos 7 campos de template (só o
    # caminho real do WhatsApp chamava _resolve_profile_templates
    # diretamente) — ver docs/implementations/nome-whatsapp-lead-variaveis-fluxo-venda.md.
    _lead_id_for_vars = lead.get("id")
    if _lead_id_for_vars and bundle.ai_profile:
        _resolve_profile_templates(bundle.ai_profile, _lead_id_for_vars, user_id)
        _resolve_sales_flow_variables(bundle.ai_profile, _lead_id_for_vars, user_id)

    if updates:
        bundle = bundle.model_copy(update=updates)
    return bundle


def _resolve_sales_flow_variables(
    ai_profile: Dict[str, Any],
    lead_id: int,
    user_id: int,
) -> None:
    """
    Resolve variáveis dinâmicas ({{lead.nome}}, {{lead.nome_whatsapp}}, etc.)
    no conteúdo dos blocos `orientacao`/`mensagem` do Fluxo de Venda
    (ai_profile["sales_flow"]), alterando o dict in-place. Blocos `mensagem`
    são enviados literalmente ao lead (system_actions[send_message]) e blocos
    `orientacao` são injetados como instrução no prompt filho — ambos
    chegavam com `{{}}` literal antes desta função.
    Não lança exceção — em caso de erro, os blocos permanecem com o texto
    original.
    """
    sales_flow = ai_profile.get("sales_flow")
    if not isinstance(sales_flow, dict):
        return
    phases = sales_flow.get("phases")
    if not isinstance(phases, list):
        return

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            ctx = build_resolution_context_from_db(
                conn=conn,
                lead_id=lead_id,
                user_id=user_id,
                ai_profile=ai_profile,
            )
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            blocks = phase.get("blocks")
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if not isinstance(block, dict) or block.get("typeId") not in ("orientacao", "mensagem"):
                    continue
                raw = block.get("content")
                if raw:
                    block["content"] = resolve_template(raw, ctx)
    except Exception:
        logger.exception("_resolve_sales_flow_variables failed — using raw block text")


def build_context_bundle_for_playground(
    user_id: int,
    ai_profile: Dict[str, Any],
    lead_id: int,
    message_text: str,
    scenario_type: str = "inbound",
    followup_context: Optional[Dict[str, Any]] = None,
) -> ContextBundle:
    """
    Constrói um ContextBundle para o playground, sem InboundEvent nem WhatsApp.
    Reutiliza toda a lógica de normalização de agent_mode, playbook e histórico.
    """
    template_key = ai_profile.get("template_key") or None
    normalized_mode = _normalize_agent_mode_for_bundle(ai_profile, template_key)

    ai_profile = dict(ai_profile)
    ai_profile["agent_mode"] = normalized_mode

    presentation_contract = _resolve_presentation_contract(
        ai_profile=ai_profile,
        agent_mode_normalized=normalized_mode,
    )
    ai_profile["presentation_variant"] = presentation_contract["presentation_variant"]
    ai_profile["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    ai_profile["offer_pack"] = presentation_contract["offer_pack"]

    playbook = get_playbook(template_key)
    playbook["template_key"] = template_key or "sdr_padrao"
    playbook = apply_mode_overrides(playbook, normalized_mode, ai_profile=ai_profile)
    playbook["presentation_variant"] = presentation_contract["presentation_variant"]
    playbook["hybrid_flow_style"] = presentation_contract["hybrid_flow_style"]
    playbook["offer_pack"] = presentation_contract["offer_pack"]

    lead = _load_lead(user_id, lead_id)
    history = get_recent_history(lead_id)
    conversation_goal = "qualify" if len(history) <= 1 else "advance"

    qualification_state = get_qualification_state(lead_id)
    knowledge_items = _load_knowledge_items(user_id)
    knowledge_media = _load_knowledge_media(user_id)
    training_examples = _load_training_examples(
        user_id=user_id,
        ai_profile_id=ai_profile.get("id", 0),
        agent_mode=normalized_mode,
    )

    _lead_origin_label = (
        "OUTBOUND (bot abordou o lead ativamente) — PLAYGROUND"
        if scenario_type == "outbound"
        else "FOLLOW-UP (simulação de tick automático) — PLAYGROUND"
        if scenario_type == "followup"
        else "INBOUND (lead veio te procurar) — PLAYGROUND"
    )
    metadata: Dict[str, Any] = {
        "channel": "playground",
        "inbound_message_text": message_text,
        "received_at": datetime.utcnow().isoformat(),
        "presentation_variant": presentation_contract["presentation_variant"],
        "presentation_variant_source": presentation_contract["presentation_variant_source"],
        "hybrid_flow_style": presentation_contract["hybrid_flow_style"],
        "lead_origin": scenario_type,
        "lead_origin_label": _lead_origin_label,
    }

    # Quando scenario_type=followup, injeta followup_context sintético e força categoria
    if followup_context and scenario_type == "followup":
        metadata["followup_context"] = followup_context
        if lead:
            lead = dict(lead)
            lead["category"] = "follow-up"

    bundle = ContextBundle(
        user_id=user_id,
        entitlements={},
        ai_profile=ai_profile,
        playbook=playbook,
        lead=lead,
        history=history,
        next_action=playbook.get("default_next_action", "reply"),
        metadata=metadata,
        conversation_goal=conversation_goal,
        qualification_state=qualification_state,
        knowledge_items=knowledge_items,
        knowledge_media=knowledge_media or None,
        training_examples=training_examples if training_examples else None,
    )
    return enrich_context_bundle(bundle, user_id)


def decide_next_action(bundle: ContextBundle) -> Dict[str, Any]:
    text = (bundle.metadata.get("inbound_message_text") or "").strip()
    if not text:
        return {"next_action": "ignore", "reason": "empty_message", "questions": []}

    lowered = text.lower()
    for keyword in ("humano", "atendente", "ligar"):
        if keyword in lowered:
            return {"next_action": "handoff", "reason": f"keyword:{keyword}", "questions": []}

    history = bundle.history or []
    qualification_questions = bundle.playbook.get("qualification_questions") or []
    outbound_present = any((msg.get("model") or "").lower() == "outbound" for msg in history)

    if (len(history) <= 1 or not outbound_present) and qualification_questions:
        return {
            "next_action": "ask_qualification",
            "reason": "qualification_needed",
            "questions": qualification_questions[:2],
        }

    return {"next_action": "reply", "reason": "default_reply", "questions": []}


def log_ai_decision(
    *,
    lead_id: int,
    user_id: int,
    decision: Dict[str, Any],
    template_key: str,
    received_at: str | None,
    message_id: str | None,
) -> None:
    notes = {
        "next_action": decision.get("next_action"),
        "reason": decision.get("reason"),
        "template_key": template_key,
        "questions": decision.get("questions") or [],
        "received_at": received_at,
        "message_id": message_id,
    }

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
            VALUES (?, 'whatsapp', NULL, 'ai_decided', ?, ?)
            """,
            (lead_id, json.dumps(notes, ensure_ascii=False), user_id),
        )
        conn.commit()
