from __future__ import annotations

import json
import logging
import unicodedata
from datetime import datetime, timedelta, timezone as _dt_timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

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


def _resolve_lead_name(lead: Dict[str, Any]) -> Optional[str]:
    """
    Nome do lead para saudação/prompt. `contactName` recebe o próprio telefone
    como placeholder quando nenhum nome é conhecido na criação do lead (ver
    find_or_create_lead_by_phone) — esse valor não é um nome real e é ignorado
    aqui, caindo para o próximo candidato (ex.: wa_display_name, o nome de
    exibição do WhatsApp). Só retorna None quando nenhum candidato sobra —
    nesse caso o prompt não deve inventar/adivinhar um nome.
    """
    phone = str(lead.get("phone") or "").strip()
    for key in ("contactName", "companyName", "wa_display_name", "name"):
        value = lead.get(key)
        if value is None:
            continue
        value_str = str(value).strip()
        if not value_str or (phone and value_str == phone):
            continue
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
    "\nNOME DO LEAD: Se lead.name for null, NÃO invente nem adivinhe o nome do lead. "
    "Nunca chame o lead pelo nome se ele não o forneceu na conversa.\n"
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
    "pre-agendamento",
    "agendamento",
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


def _evaluate_sales_flow(
    context: Dict[str, Any],
    current_phase: str,
    signals_structured: Optional[dict],
) -> Optional[dict]:
    """Avalia os nodes do sales_flow configurado e retorna o primeiro match ativo.

    Retorna dict com {action_instruction, action_media_category, matched_node_id, matched_node_label}
    ou None se nenhum node fizer match (ou fluxo estiver desabilitado).
    """
    ai_profile = context.get("ai_profile") or {}
    sales_flow = ai_profile.get("sales_flow")
    if not isinstance(sales_flow, dict) or not sales_flow.get("enabled"):
        return None

    nodes = sales_flow.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return None

    signals = _sanitize_signals_structured(signals_structured) if isinstance(signals_structured, dict) else {}
    qual_state = _qualification_state_from_context(context)
    qual_data = qual_state.get("data_json") or {}
    message_text = _extract_message_text(context)
    normalized_msg = _normalize_str(message_text)

    sorted_nodes = sorted(
        [n for n in nodes if isinstance(n, dict) and n.get("enabled", True)],
        key=lambda n: int(n.get("priority") or 0),
    )

    for node in sorted_nodes:
        trigger_phases = node.get("trigger_phases") or []
        if trigger_phases and current_phase not in trigger_phases:
            continue

        trigger_type = (node.get("trigger_type") or "").strip().lower()
        matched = False

        if trigger_type == "phase_entered":
            matched = True
        elif trigger_type == "signal":
            sig_key = (node.get("trigger_signal") or "").strip()
            sig_val = (node.get("trigger_value") or "").strip().lower()
            if sig_key and sig_key in signals:
                actual = str(signals.get(sig_key) or "").strip().lower()
                matched = (actual == sig_val) if sig_val else bool(actual)
        elif trigger_type == "keyword":
            keywords = [
                _normalize_str(kw.strip())
                for kw in (node.get("trigger_keywords") or [])
                if kw and kw.strip()
            ]
            matched = any(kw in normalized_msg for kw in keywords)
        elif trigger_type == "qualification_field":
            field_key = (node.get("trigger_field_key") or "").strip()
            field_val = (node.get("trigger_field_value") or "").strip().lower()
            if field_key and field_key in qual_data:
                actual = str(qual_data.get(field_key) or "").strip().lower()
                matched = (actual == field_val) if field_val else bool(actual)

        if matched:
            instruction = (node.get("action_instruction") or "").strip()
            if not instruction:
                continue
            return {
                "action_instruction": instruction,
                "action_media_category": (node.get("action_media_category") or "").strip() or None,
                "matched_node_id": node.get("id", ""),
                "matched_node_label": node.get("label", ""),
            }

    return None


def _build_sales_flow_block(sf_match: Optional[dict]) -> str:
    """Gera o bloco de instrução de Fluxo de Venda para injeção no prompt da filha."""
    if not sf_match:
        return ""
    instruction = sf_match.get("action_instruction", "").strip()
    if not instruction:
        return ""
    label = sf_match.get("matched_node_label", "")
    header = "\nINSTRUÇÃO DE FLUXO DE VENDA"
    if label:
        header += f" [{label}]"
    media_hint = sf_match.get("action_media_category")
    media_line = f"\nsales_flow_media_hint: {media_hint}" if media_hint else ""
    return (
        f"{header} (prioridade alta — aplicar antes de responder):\n"
        f"{instruction}\n"
        f"{media_line}\n"
    )


_ROUTE_TO_PHASE_ID: Dict[str, str] = {
    "recepcao":         "p0",
    "qualification":    "p1",
    "apresentation":    "p2",
    "pre-agendamento":  "p3a",
    "pre_agendamento":  "p3a",
    "agendamento":      "p3b",
    "followup":         "p4",
    "follow-up":        "p4",
    "closing":          "p5",
}


def _parse_json_id_set(raw: Any) -> set:
    """Parseia um campo JSON (string ou já-lista) de IDs num set. Usado para
    leads.triggers_fired e leads.phases_triggered — JSON inválido vira set vazio."""
    try:
        import json as _json
        return set(
            _json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, list) else [])
        )
    except (ValueError, TypeError):
        return set()


def _load_triggers_fired_set(context: Dict[str, Any]) -> set:
    return _parse_json_id_set((context.get("lead") or {}).get("triggers_fired") or "[]")


def _load_triggered_phases_set(context: Dict[str, Any]) -> set:
    return _parse_json_id_set((context.get("lead") or {}).get("phases_triggered") or "[]")


def _load_branches_selected_map(context: Dict[str, Any]) -> Dict[str, str]:
    """Ramos de nós `condicao` (lógica de ramificação) já escolhidos e persistidos —
    leads.branches_selected, JSON {block_id: branch_id}. Só nós com sticky=True gravam
    aqui (ver mark_branch_selected em compose_decision_output). Chave: id do bloco
    `condicao`. Valor: id do ramo (branch) escolhido nesse nó."""
    raw = (context.get("lead") or {}).get("branches_selected") or "{}"
    try:
        import json as _json
        parsed = _json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
        return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _load_sales_flow_wait(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pausa persistida do bloco `espera` (Smart Delay) — leads.sales_flow_wait, JSON
    {until, block_id, phase_id, suppress_llm}. None se não houver pausa configurada ou o
    JSON estiver corrompido (falha aberto — nunca trava o fluxo por dado inválido)."""
    raw = (context.get("lead") or {}).get("sales_flow_wait")
    if not raw:
        return None
    try:
        import json as _json
        parsed = _json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else None)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) and parsed.get("until") else None


def _sales_flow_wait_timedelta(wait_value: str, wait_unit: str) -> Optional[timedelta]:
    """Converte wait_value/wait_unit (bloco `espera`) num timedelta. None se inválido."""
    try:
        amount = float(wait_value)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    unit = (wait_unit or "hours").strip().lower()
    if unit == "minutes":
        return timedelta(minutes=amount)
    if unit == "days":
        return timedelta(days=amount)
    return timedelta(hours=amount)


def _is_sequential_trigger_block(block: Dict[str, Any]) -> bool:
    """Um gatilho é "sequencial" quando tem um registo persistido de satisfação que
    permite usá-lo como checkpoint: phase_trigger (sempre único por fase), block_trigger
    (sempre — dispara uma única vez assim que a dependência configurada for satisfeita,
    sem condição de conteúdo) ou kw_trigger/intent_trigger com o campo `sequential=True`.

    `sequential` é independente de `fire_once` — controla só se o gatilho participa do
    encadeamento (espera os anteriores, trava os seguintes, conta como pendência no
    guardrail de transição de fase); `fire_once` controla só se ele pode disparar mais
    de uma vez. Um bloco sem o campo `sequential` (blocos salvos antes desta feature)
    usa `fire_once` como fallback — preserva exatamente o comportamento anterior, em que
    os dois conceitos eram o mesmo campo. Ver docs/architecture/sales-flow.md."""
    type_id = (block.get("typeId") or "").strip()
    if type_id in ("phase_trigger", "block_trigger"):
        return True
    if type_id in ("kw_trigger", "intent_trigger"):
        if "sequential" in block:
            return bool(block.get("sequential"))
        return bool(block.get("fire_once"))
    return False


def _phase_pending_sequential_triggers(
    phase_id: str,
    ai_profile: Dict[str, Any],
    triggers_fired: set,
) -> List[str]:
    """block_ids de kw_trigger/intent_trigger sequenciais (sequential=True, com fallback para
    fire_once=True) ou block_trigger (sempre sequencial) configurados na fase `phase_id` que
    ainda não dispararam (não estão em triggers_fired). Lista vazia = sem gate: sales_flow
    desligado, fase inexistente no
    profile, ou nenhum gatilho sequencial configurado nela (ou todos já dispararam) —
    nesses casos o guardrail que consome este helper não deve interferir. Opt-in: só
    retorna pendências quando o utilizador configurou explicitamente pelo menos um gatilho
    sequencial nessa fase.

    Extraído do scan que já existia hardcoded para "p2" dentro de
    _enforce_apresentation_sales_flow_pending — usado agora por qualquer guardrail de
    "gatilhos pendentes bloqueiam avanço de fase" (ver docs/architecture/sales-flow.md)."""
    sales_flow = ai_profile.get("sales_flow")
    if not isinstance(sales_flow, dict) or not sales_flow.get("enabled"):
        return []
    phases = sales_flow.get("phases")
    if not isinstance(phases, list):
        return []
    phase = next((p for p in phases if isinstance(p, dict) and p.get("id") == phase_id), None)
    if not phase:
        return []
    pending: List[str] = []
    for block in (phase.get("blocks") or []):
        if not isinstance(block, dict):
            continue
        type_id = (block.get("typeId") or "").strip()
        if type_id not in ("kw_trigger", "intent_trigger", "block_trigger"):
            continue
        if not _is_sequential_trigger_block(block):
            continue
        block_id = (block.get("id") or "").strip()
        if block_id and block_id not in triggers_fired:
            pending.append(block_id)
    return pending


def _build_block_lookup(phases: List[Dict[str, Any]]) -> Dict[str, Tuple[Dict[str, Any], str]]:
    """Mapa block_id -> (block, phase_id) construído a partir de TODAS as fases do profile
    (não só a fase corrente) — usado para resolver `requires_block_id`. Cobre referência
    cross-fase defensivamente; na prática o builder só oferece blocos da MESMA fase no
    dropdown (ver CamadaFluxoVenda.tsx). Construído uma vez por chamada de
    _evaluate_sales_flow_phases(); custo desprezível (poucas dezenas de blocos no total)."""
    lookup: Dict[str, Tuple[Dict[str, Any], str]] = {}
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        p_id = (phase.get("id") or "").strip()
        for blk in (phase.get("blocks") or []):
            if not isinstance(blk, dict):
                continue
            b_id = (blk.get("id") or "").strip()
            if b_id and b_id not in lookup:
                lookup[b_id] = (blk, p_id)
    return lookup


def _requires_block_satisfied(
    block: Dict[str, Any],
    block_lookup: Dict[str, Tuple[Dict[str, Any], str]],
    triggers_fired: set,
    triggered_phases: set,
) -> bool:
    """True se a dependência explícita `requires_block_id` (kw_trigger/intent_trigger) está
    satisfeita — ou se não há referência configurada, ou se a referência é inválida por
    qualquer motivo (bloco apagado OU bloco ainda existe mas deixou de ser elegível, ex.:
    "Ordem" mudada para "Pode ser acionado a qualquer momento" depois — ou, em blocos sem o
    campo novo, fire_once desmarcado): FAIL-OPEN em ambos os casos, nunca bloqueia
    permanentemente (ver docs/architecture/sales-flow.md, "Dependência explícita
    requires_block_id").

    Ao contrário do gating posicional (_prereqs_satisfied_by_scope), que aceita satisfação
    no MESMO turno (fired), esta checagem só olha para estado PERSISTIDO (triggers_fired /
    triggered_phases, carregados uma vez no topo da função — sempre anterior a este turno) —
    nunca inclui `fired` deste turno. É intencional: o requisito é "já disparou num turno
    ANTERIOR", nunca "está a disparar também agora"."""
    ref_id = (block.get("requires_block_id") or "").strip()
    if not ref_id:
        return True
    entry = block_lookup.get(ref_id)
    if entry is None:
        return True  # bloco referenciado foi apagado — fail-open
    ref_block, ref_phase_id = entry
    if not _is_sequential_trigger_block(ref_block):
        return True  # existe mas já não é elegível (ex.: fire_once desmarcado) — fail-open
    ref_type = (ref_block.get("typeId") or "").strip()
    if ref_type == "phase_trigger":
        return ref_phase_id in triggered_phases
    ref_bid = (ref_block.get("id") or "").strip()
    return bool(ref_bid) and ref_bid in triggers_fired


_LEAD_CAT_TO_ROUTE: Dict[str, str] = {
    "qualification":    "qualification",
    "apresentation":    "apresentation",
    "pre-agendamento":  "pre-agendamento",
    "pre_agendamento":  "pre-agendamento",
    "agendamento":      "agendamento",
    "follow-up":        "followup",
    "follow_up":        "followup",
    "closing":          "closing",
    "recepcao":         "recepcao",
}


def _compute_is_phase_entry(context: Dict[str, Any], effective_route_to: str) -> bool:
    """True quando o lead está a transitar para esta fase neste turno: a categoria
    atual do lead é diferente da rota efetiva E a fase ainda não disparou antes
    (leads.phases_triggered). Reutilizado tanto para decidir o que injectar no prompt
    filho (_build_child_prompt_*) quanto para o despacho real de system_actions
    (compose_decision_output) — antes da Fase 3, só o despacho usava este cálculo; o
    prompt filho recebia sempre o default is_phase_entry=True, reapresentando conteúdo
    de entrada como se fosse novo em todo turno (ver
    docs/implementations/fix-fluxo-vendas-sequencial.md, Fase 3)."""
    lead_cat_raw = ((context.get("lead") or {}).get("category") or "").strip().lower()
    lead_current_route = _LEAD_CAT_TO_ROUTE.get(lead_cat_raw, lead_cat_raw)
    effective_phase_id = _ROUTE_TO_PHASE_ID.get(effective_route_to)
    triggered_phases = _load_triggered_phases_set(context)
    return (
        lead_current_route != effective_route_to
        and (not effective_phase_id or effective_phase_id not in triggered_phases)
    )


def _evaluate_sales_flow_phases(
    context: Dict[str, Any],
    effective_route_to: str,
    message_text: str,
    detected_intents: Optional[List[str]] = None,
    is_phase_entry: bool = True,
    branch_selections: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Avalia os blocos tipados do novo sistema de fases do Fluxo de Venda.

    Retorna:
      prompt_injections  — strings para injetar no prompt LLM (orientacao, intent_trigger)
      pre_send_media     — mídias a enviar diretamente (blocos midia com media_url explícito)
      system_actions     — ações a executar pelo executor (mensagem, avancar_fase, webhook, espera)

    Nós `condicao` (lógica de ramificação) escolhem, por turno, qual `branch_id` está activo
    (via `branch_selections`, populado pela Mãe, ou já persistido se o nó for `sticky`) — só
    os blocos com `branch_group_id`/`branch_id` correspondentes ao ramo activo são avaliados;
    os blocos dos ramos irmãos são ignorados por completo (não entram em prompt_injections
    nem em system_actions). Ver docs/architecture/sales-flow.md, "Lógica de Ramificação".
    """
    result: Dict[str, Any] = {"prompt_injections": [], "pre_send_media": [], "system_actions": [], "suppress_llm_response": False}

    ai_profile = context.get("ai_profile") or {}
    sales_flow = ai_profile.get("sales_flow")
    if not isinstance(sales_flow, dict) or not sales_flow.get("enabled"):
        return result

    phases = sales_flow.get("phases")
    if not isinstance(phases, list) or not phases:
        return result

    phase_id = _ROUTE_TO_PHASE_ID.get(effective_route_to)
    if not phase_id:
        return result

    phase_data = next((p for p in phases if isinstance(p, dict) and p.get("id") == phase_id), None)
    if not phase_data:
        return result

    blocks = phase_data.get("blocks") or []
    normalized_msg = _normalize_str(message_text)

    # Blocos que já dispararam com fire_once=True — lidos do lead para impedir re-disparo
    _triggers_fired = _load_triggers_fired_set(context)
    # Fases já disparadas (phase_trigger) — mesma finalidade de _triggers_fired, para o
    # gating sequencial e para a persistência de orientações críticas entre turnos.
    _triggered_phases = _load_triggered_phases_set(context)
    # Ramos de nós `condicao` (sticky) já resolvidos em turnos anteriores.
    _branches_persisted = _load_branches_selected_map(context)
    # Mapa block_id -> (block, phase_id) de TODAS as fases — usado para resolver a
    # dependência explícita `requires_block_id`. Ver _requires_block_satisfied().
    _block_lookup = _build_block_lookup(phases)

    # Pausa persistida do bloco `espera` (Smart Delay) — só relevante se pertence à fase
    # sendo avaliada agora. Se existir mas já tiver expirado, limpa o estado persistido
    # (higiene — o gate abaixo já vira no-op sozinho, mas evita lixo acumulado no lead).
    _sales_flow_wait = _load_sales_flow_wait(context)
    _active_wait: Optional[Dict[str, Any]] = None
    if _sales_flow_wait and _sales_flow_wait.get("phase_id") == phase_id:
        try:
            _wait_until_dt = datetime.fromisoformat(str(_sales_flow_wait.get("until")))
        except (TypeError, ValueError):
            _wait_until_dt = None
        if _wait_until_dt and _wait_until_dt > datetime.utcnow():
            _active_wait = _sales_flow_wait
        else:
            result["system_actions"].append({"type": "sales_flow_pause_clear"})
    if _active_wait and _active_wait.get("suppress_llm"):
        result["suppress_llm_response"] = True
    _wait_gate_block_id = (_active_wait or {}).get("block_id")
    # Escopo(s) que já entraram em pausa durante esta avaliação — "root" ou
    # "{branch_group_id}:{branch_id}", mesma chave usada por _prereqs_satisfied_by_scope.
    # Uma vez marcado, todo bloco seguinte do MESMO escopo é ignorado por completo (nem
    # gatilho é avaliado, nem ação executa) até o próximo turno em que a pausa já não
    # estiver mais ativa.
    _scope_paused: Dict[str, bool] = {}
    _wait_paused_block_ids: set = set()

    def _trigger_persisted_satisfied(_blk: Dict[str, Any], _type: str) -> bool:
        """True se este gatilho já disparou ANTES deste turno (estado persistido no lead).

        Só chamada para gatilhos já confirmados "sequenciais" por
        _is_sequential_trigger_block() (kw_trigger/intent_trigger com sequential=True,
        ou fallback fire_once=True se o bloco não tiver o campo novo) — os demais nunca
        chegam aqui, o que é intencional: não participam do encadeamento sequencial (ver
        docs/architecture/sales-flow.md, "Modelo sequencial de trigger").
        """
        if _type == "phase_trigger":
            return phase_id in _triggered_phases
        if _type in ("block_trigger", "kw_trigger", "intent_trigger"):
            _bid = (_blk.get("id") or "").strip()
            return bool(_bid) and _bid in _triggers_fired
        return False

    # Modelo sequencial: o último gatilho disparado governa os blocos de ação seguintes.
    # Por defeito True — ações sem gatilho antes delas disparam automaticamente ao entrar na fase.
    _TRIGGER_TYPES = {"phase_trigger", "kw_trigger", "intent_trigger", "no_reply_trigger", "block_trigger"}
    last_trigger_active = True
    # Pré-requisitos sequenciais, agora por ESCOPO — "root" para blocos fora de qualquer
    # ramo, ou "{branch_group_id}:{branch_id}" dentro de um. Cada escopo começa desbloqueado
    # de forma independente: um gatilho fire_once dentro do Caminho A nunca é bloqueado por
    # (nem bloqueia) nada do Caminho B — são caminhos mutuamente exclusivos do mesmo nó.
    _prereqs_satisfied_by_scope: Dict[str, bool] = {}
    # Ramo activo por nó de ramificação nesta avaliação — {branch_group_id: branch_id}.
    _active_branches: Dict[str, str] = {}
    # IDs de blocos `orientacao` já injectados na passagem principal — evita duplicar na
    # segunda passagem (guarda permanente de orientações críticas), abaixo.
    _injected_block_ids: set = set()
    # Blocos midia/mensagem que disparam FORA de phase_trigger são despachados DEPOIS
    # da resposta da LLM (ver whatsapp.py:1210 e a ordem documentada em sales-flow.md).
    # Coleta aqui para avisar a LLM filha que ainda não foram enviados.
    _deferred_media_notes: List[str] = []

    for block in blocks:
        if not isinstance(block, dict):
            continue
        type_id = (block.get("typeId") or "").strip()

        # Escopo de ramo: um bloco marcado com branch_group_id só é avaliado se pertence ao
        # ramo actualmente activo desse nó de ramificação — senão é ignorado por completo
        # (nem prompt_injections, nem system_actions, nem gating sequencial). É aqui que a
        # redução de poluição de tokens dos ramos irmãos não escolhidos acontece de facto.
        _branch_group = (block.get("branch_group_id") or "").strip()
        _own_branch_id = (block.get("branch_id") or "").strip()
        if _branch_group and _active_branches.get(_branch_group) != _own_branch_id:
            continue
        _scope_key = f"{_branch_group}:{_own_branch_id}" if _branch_group else "root"

        # Gate de pausa do bloco `espera`: se este escopo já entrou em pausa (por um
        # `espera` anterior na mesma passagem, ou por uma pausa persistida de um turno
        # anterior cujo gatilho já foi alcançado abaixo), ignora este bloco por completo —
        # nem gatilho é avaliado, nem ação executa. Ver docs/architecture/sales-flow.md,
        # secção do bloco `espera`.
        if _scope_paused.get(_scope_key):
            _wait_paused_block_ids.add((block.get("id") or "").strip())
            continue
        if _wait_gate_block_id and (block.get("id") or "").strip() == _wait_gate_block_id:
            _scope_paused[_scope_key] = True
            _wait_paused_block_ids.add(_wait_gate_block_id)
            continue

        if type_id == "condicao":
            # Nó de lógica de ramificação: resolve qual ramo está activo e regista em
            # _active_branches para os blocos filhos seguintes. Respeita o mesmo gate de
            # "last_trigger_active" que qualquer outro bloco de ação/lógica.
            if not last_trigger_active:
                continue
            _node_id = (block.get("id") or "").strip()
            _branches = block.get("branches")
            if not _node_id or not isinstance(_branches, list) or not _branches:
                continue
            _valid_branch_ids = {
                (br.get("id") or "").strip()
                for br in _branches
                if isinstance(br, dict) and (br.get("id") or "").strip()
            }
            _chosen: Optional[str] = None
            _already_persisted = _node_id in _branches_persisted
            if block.get("sticky") and _already_persisted:
                _persisted_choice = _branches_persisted.get(_node_id)
                if _persisted_choice in _valid_branch_ids:
                    _chosen = _persisted_choice
            elif branch_selections:
                _mother_choice = branch_selections.get(_node_id)
                if _mother_choice in _valid_branch_ids:
                    _chosen = _mother_choice
            if _chosen:
                _active_branches[_node_id] = _chosen
                if block.get("sticky") and not _already_persisted:
                    result["system_actions"].append({
                        "type": "mark_branch_selected",
                        "block_id": _node_id,
                        "branch_id": _chosen,
                    })
            continue

        if type_id in _TRIGGER_TYPES:
            # Gating sequencial: só gatilhos "sequenciais" (sequential=True, com fallback
            # para fire_once=True em blocos sem o campo novo — ver _is_sequential_trigger_block)
            # participam — um gatilho não-sequencial não tem registo persistido de satisfação,
            # então nem bloqueia nem é bloqueado por este mecanismo. O pré-requisito é isolado
            # por escopo (root ou ramo) — ver comentário acima.
            _is_sequential = _is_sequential_trigger_block(block)
            _scope_satisfied = _prereqs_satisfied_by_scope.setdefault(_scope_key, True)
            # Dependência explícita (requires_block_id): trava ADITIVA à posicional acima —
            # só olha estado persistido de ANTES deste turno, nunca satisfação no mesmo turno
            # (ver _requires_block_satisfied). Independente de _is_sequential/_scope_key.
            _requires_satisfied = _requires_block_satisfied(block, _block_lookup, _triggers_fired, _triggered_phases)
            _locked = (_is_sequential and not _scope_satisfied) or not _requires_satisfied

            # Avaliar e atualizar o flag de trigger ativo
            fired = False
            if _locked:
                fired = False  # um gatilho anterior da sequência ainda não foi satisfeito
            elif type_id == "phase_trigger":
                fired = is_phase_entry
            elif type_id == "kw_trigger":
                _block_id = (block.get("id") or "").strip()
                _fire_once = bool(block.get("fire_once"))
                if _fire_once and _block_id and _block_id in _triggers_fired:
                    fired = False
                else:
                    keywords = [
                        _normalize_str(kw.strip())
                        for kw in (block.get("keywords") or "").split(",")
                        if kw.strip()
                    ]
                    if keywords:
                        match_mode = (block.get("match") or "contains").strip().lower()
                        if match_mode == "exact":
                            fired = any(kw == normalized_msg for kw in keywords)
                        elif match_mode == "starts_with":
                            fired = any(normalized_msg.startswith(kw) for kw in keywords)
                        else:
                            fired = any(kw in normalized_msg for kw in keywords)
                # Marca a 1ª ocorrência sempre, independente de fire_once — é o registo que
                # _is_sequential_trigger_block()/_trigger_persisted_satisfied() consultam quando
                # sequential=True. fire_once continua a única coisa que suprime disparos
                # seguintes (checagem acima); um gatilho sequencial mas repetível continua
                # disparando nos turnos seguintes mesmo já estando marcado aqui.
                if fired and _block_id and _block_id not in _triggers_fired:
                    result["system_actions"].append({"type": "mark_trigger_fired", "block_id": _block_id})
            elif type_id == "intent_trigger":
                _block_id = (block.get("id") or "").strip()
                _fire_once = bool(block.get("fire_once"))
                if _fire_once and _block_id and _block_id in _triggers_fired:
                    fired = False
                else:
                    intent_label = (block.get("intent") or "").strip()
                    if detected_intents is not None and intent_label:
                        fired = intent_label in detected_intents
                    else:
                        fired = True  # fallback: mãe não classificou, comportamento legado
                # Mesmo padrão do kw_trigger acima: marca a 1ª ocorrência independente de
                # fire_once, para servir de registo ao gating sequencial quando sequential=True.
                if fired and _block_id and _block_id not in _triggers_fired:
                    result["system_actions"].append({"type": "mark_trigger_fired", "block_id": _block_id})
            elif type_id == "block_trigger":
                # Sem condição de conteúdo — dispara assim que a dependência (requires_block_id,
                # já verificada acima em _requires_satisfied/_locked) estiver satisfeita. Diferente
                # de phase_trigger (auto-limitado por is_phase_entry) e de kw/intent_trigger
                # (auto-limitados pelo checkbox fire_once), este tipo não tem nenhum outro
                # mecanismo de "uma vez só" — a checagem de _triggers_fired abaixo é obrigatória,
                # senão dispararia (e reenviaria mensagem/mídia) em todo turno seguinte.
                _block_id = (block.get("id") or "").strip()
                if _block_id and _block_id in _triggers_fired:
                    fired = False
                else:
                    fired = True
                if fired and _block_id:
                    result["system_actions"].append({"type": "mark_trigger_fired", "block_id": _block_id})
            # no_reply_trigger é gerido pelo followup_state — não avaliado aqui

            if fired and block.get("suppress_llm_response"):
                result["suppress_llm_response"] = True

            last_trigger_active = fired

            if _is_sequential:
                _persisted_satisfied = _trigger_persisted_satisfied(block, type_id)
                _prereqs_satisfied_by_scope[_scope_key] = _scope_satisfied and (_persisted_satisfied or fired)

            # Injeções de prompt para blocos de gatilho que dispararam
            if fired:
                if type_id == "phase_trigger":
                    result["phase_trigger_fired"] = True
                    result["prompt_injections"].append(
                        "ATENÇÃO: As mensagens listadas abaixo foram enviadas AUTOMATICAMENTE ao lead "
                        "antes da sua resposta. Complemente-as — não as repita."
                    )
                    content = (block.get("content") or "").strip()
                    if content:
                        priority = (block.get("priority") or "normal").strip().lower()
                        label = "INSTRUÇÃO CRÍTICA DE FLUXO DE VENDA" if priority == "critical" else "INSTRUÇÃO DE FLUXO DE VENDA"
                        result["prompt_injections"].append(f"{label}:\n{content}")
                elif type_id == "intent_trigger":
                    intent = (block.get("intent") or "").strip()
                    if intent:
                        inj = f"FLUXO DE VENDA — Detetar intenção: {intent}"
                        note = (block.get("note") or "").strip()
                        if note:
                            inj += f"\n{note}"
                        result["prompt_injections"].append(inj)

        else:
            # Bloco de ação/lógica: executa apenas se o último gatilho disparou
            if not last_trigger_active:
                continue

            if type_id == "orientacao":
                content = (block.get("content") or "").strip()
                if content:
                    priority = (block.get("priority") or "normal").strip().lower()
                    label = "INSTRUÇÃO CRÍTICA DE FLUXO DE VENDA" if priority == "critical" else "INSTRUÇÃO DE FLUXO DE VENDA"
                    result["prompt_injections"].append(f"{label}:\n{content}")
                    _oid = (block.get("id") or "").strip()
                    if _oid:
                        _injected_block_ids.add(_oid)
            elif type_id == "midia":
                media_url = (block.get("media_url") or "").strip()
                if media_url:
                    result["system_actions"].append({
                        "type": "send_media",
                        "media_url": media_url,
                        "media_type": block.get("media_type") or "image",
                        "caption": (block.get("caption") or "").strip() or None,
                    })
                    _mtype = block.get("media_type") or "image"
                    if result.get("phase_trigger_fired"):
                        result["prompt_injections"].append(
                            f"[Mídia enviada automaticamente ao lead: {_mtype}]"
                        )
                    else:
                        _deferred_media_notes.append(_mtype)
            elif type_id == "mensagem":
                content = (block.get("content") or "").strip()
                if content:
                    result["system_actions"].append({
                        "type": "send_message",
                        "content": content,
                        "channel": block.get("channel") or "whatsapp",
                    })
                    if result.get("phase_trigger_fired"):
                        result["prompt_injections"].append(
                            f"[Mensagem automática enviada ao lead antes desta resposta: \"{content}\"]"
                        )
                    else:
                        _deferred_media_notes.append(f'mensagem: "{content}"')
            elif type_id == "avancar_fase":
                target = (block.get("target_phase") or "").strip()
                if target:
                    result["system_actions"].append({
                        "type": "advance_phase",
                        "target_phase": target,
                    })
            elif type_id == "webhook":
                url = (block.get("url") or "").strip()
                if url:
                    result["system_actions"].append({
                        "type": "webhook",
                        "url": url,
                        "method": block.get("method") or "POST",
                        "note": block.get("note") or "",
                        "block_id": (block.get("id") or "").strip(),
                        "phase_id": phase_id,
                    })
            elif type_id == "espera":
                _wait_delta = _sales_flow_wait_timedelta(
                    str(block.get("wait_value") or "").strip(), block.get("wait_unit") or "hours"
                )
                if _wait_delta:
                    _eid = (block.get("id") or "").strip()
                    # allow_llm_during_wait=True (default) mantém a LLM respondendo dúvidas
                    # durante a pausa — só as ações do Fluxo de Venda abaixo deste bloco
                    # ficam paradas. False = pausa total (suprime também a resposta da LLM).
                    _allow_llm = block.get("allow_llm_during_wait")
                    _suppress = not bool(True if _allow_llm is None else _allow_llm)
                    result["system_actions"].append({
                        "type": "sales_flow_pause_set",
                        "wait_until": (datetime.utcnow() + _wait_delta).isoformat(),
                        "block_id": _eid,
                        "phase_id": phase_id,
                        "suppress_llm": _suppress,
                    })
                    if _suppress:
                        result["suppress_llm_response"] = True
                    # Pausa vale já a partir deste turno — o resto da fase (mesmo escopo)
                    # não é avaliado nem agora nem nos turnos seguintes, até expirar.
                    if _eid:
                        _scope_paused[_scope_key] = True
            # `condicao` (nó de ramificação) é resolvido no topo do loop, antes da
            # distinção trigger/ação — ver bloco `if type_id == "condicao":` acima.

    # Segunda passagem: orientações críticas ficam como guarda permanente — reinjectadas
    # em todo turno desta fase enquanto o próximo gatilho sequencial da sequência ainda
    # não estiver satisfeito (persistido). Sem isto, uma regra como "não pergunte X ainda"
    # só valia no turno em que foi originalmente disparada (ver diagnóstico do bug em
    # docs/implementations/fix-fluxo-vendas-sequencial.md).
    for _idx, _block in enumerate(blocks):
        if not isinstance(_block, dict):
            continue
        if (_block.get("typeId") or "").strip() != "orientacao":
            continue
        if (_block.get("priority") or "").strip().lower() != "critical":
            continue
        _my_branch_group = (_block.get("branch_group_id") or "").strip()
        _my_branch_id = (_block.get("branch_id") or "").strip()
        if _my_branch_group and _active_branches.get(_my_branch_group) != _my_branch_id:
            continue  # orientação pertence a um ramo não escolhido — não relevante agora
        _cid = (_block.get("id") or "").strip()
        if _cid and _cid in _injected_block_ids:
            continue  # já injectada na passagem principal deste turno
        if _cid and _cid in _wait_paused_block_ids:
            continue  # dentro da janela de pausa de um bloco `espera` — não reinjectar
        _content = (_block.get("content") or "").strip()
        if not _content:
            continue
        _superseded = False
        for _later in blocks[_idx + 1:]:
            if not isinstance(_later, dict):
                continue
            if (_later.get("branch_group_id") or "").strip() != _my_branch_group or (_later.get("branch_id") or "").strip() != _my_branch_id:
                continue  # só o próximo gatilho sequencial do MESMO escopo importa
            _later_type = (_later.get("typeId") or "").strip()
            if not _is_sequential_trigger_block(_later):
                continue
            _superseded = _trigger_persisted_satisfied(_later, _later_type)
            break  # só o próximo gatilho sequencial da sequência importa
        if not _superseded:
            result["prompt_injections"].append(
                f"INSTRUÇÃO CRÍTICA DE FLUXO DE VENDA (em vigor nesta etapa):\n{_content}"
            )

    if _deferred_media_notes:
        _items = ", ".join(_deferred_media_notes)
        result["prompt_injections"].append(
            f"[FLUXO DE VENDA — envio automático pendente: {_items}. Isto será enviado "
            "AUTOMATICAMENTE logo APÓS a tua resposta — ainda NÃO foi enviado.\n"
            "NÃO digas 'aqui está'/'segue' nem peças para o lead já ver/escolher agora;\n"
            "usa fraseado no futuro (ex.: 'vou te mandar já', 'te envio agora') e evita\n"
            "perguntas que dependam do lead já ter visto o conteúdo nesta mesma mensagem.]"
        )

    return result


def _build_sales_flow_phases_block(phases_result: Dict[str, Any]) -> str:
    """Converte as prompt_injections do sistema de fases num bloco de texto para o prompt LLM."""
    injections = phases_result.get("prompt_injections") or []
    if not injections:
        return ""
    return "\n" + "\n".join(injections) + "\n"


# Categorias de knowledge_items consideradas "narrativas" — informação para contar
# proativamente 1x (prova social, roteiro de pitch, detalhes do produto), não uma
# resposta sob demanda. Categorias reativas/FAQ (objections_faq, service_faq,
# guarantee_policy, service_pricing_table, commercial_objections, service_differentials,
# active_promotion, payment_policy, pre_commitment_faq) ficam de fora de propósito — já
# são condicionadas a "usar apenas se o lead perguntar X" e o lead pode perguntar a
# qualquer momento, então devem continuar sempre disponíveis no prompt.
_NARRATIVE_KNOWLEDGE_CATEGORIES_BY_PHASE: Dict[str, tuple] = {
    "apresentation": ("social_proof", "pitch_script", "product_details"),
    "follow-up": ("social_proof",),
    "followup": ("social_proof",),
}


def _evaluate_narrative_knowledge_dedup(
    context: Dict[str, Any],
    phase: str,
    knowledge_items: Dict[str, Any],
) -> Dict[str, Any]:
    """Filtra categorias narrativas do knowledge base para injeção no máximo 1x por lead —
    evita repetir a mesma prova social/pitch/detalhes do produto em turnos consecutivos da
    mesma fase (bug relatado: social_proof repetindo em 3 turnos seguidos da apresentação).

    Função pura: não depende de MotherDecision, ChildResult nem do prompt montado — só de
    context["lead"]["knowledge_categories_shown"] (JSON array já persistido) e do dict
    knowledge_items. Chamada 2x por turno (mesmo padrão já usado por
    _evaluate_sales_flow_phases): uma vez dentro do prompt builder para decidir o que
    incluir/omitir, outra dentro de compose_decision_output para emitir o system_action que
    persiste o novo estado.

    Retorna:
      content                — {categoria: texto_ou_None}; None quando não há conteúdo
                                configurado OU quando a categoria já foi mostrada antes.
      new_categories          — categorias com conteúdo que aparecem pela 1ª vez neste turno.
      suppressed_categories   — categorias com conteúdo configurado mas já mostradas antes
                                (distinção necessária para callers que têm um fallback
                                próprio quando "não configurado" — não devem cair nesse
                                fallback quando o motivo real é "já mostrado").
    """
    candidates = _NARRATIVE_KNOWLEDGE_CATEGORIES_BY_PHASE.get(phase, ())
    if not candidates:
        return {"content": {}, "new_categories": [], "suppressed_categories": []}

    lead = context.get("lead") or {}
    raw_shown = lead.get("knowledge_categories_shown") or "[]"
    try:
        already_shown: set = set(
            json.loads(raw_shown) if isinstance(raw_shown, str)
            else (raw_shown if isinstance(raw_shown, list) else [])
        )
    except (ValueError, TypeError):
        already_shown = set()

    content: Dict[str, Optional[str]] = {}
    new_categories: List[str] = []
    suppressed_categories: List[str] = []
    for category in candidates:
        text = str((knowledge_items or {}).get(category) or "").strip()
        if not text:
            content[category] = None
            continue
        if category in already_shown:
            content[category] = None
            suppressed_categories.append(category)
        else:
            content[category] = text
            new_categories.append(category)

    return {
        "content": content,
        "new_categories": new_categories,
        "suppressed_categories": suppressed_categories,
    }


# Sequência de fases ativas do Fluxo de Venda por agent_mode normalizado — espelha
# SALES_FLOW_PHASES_BY_AGENT_MODE (frontend-crm/src/types/agente.ts) e a tabela em
# docs/architecture/sales-flow.md. Usada para saber qual é "a fase seguinte" a partir
# da fase atual do lead, sem depender de route_to (que só a mãe decide neste turno).
_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE: Dict[str, List[str]] = {
    "consultivo": ["p0", "p1", "p2", "p4", "p5"],
    "direto": ["p0", "p1", "p2", "p5"],
    "agenda": ["p0", "p1", "p2", "p3a", "p3b", "p4", "p5"],
}


def _collect_intent_triggers_for_lead_phase(
    context: Dict[str, Any], agent_mode_normalized: str
) -> List[dict]:
    """Coleta blocos intent_trigger da fase atual do lead e da fase seguinte (dado o
    pipeline do agent_mode) para injeção no prompt da mãe.

    Incluir a fase seguinte é necessário porque a transição de fase só é decidida
    pela própria mãe NESTE turno — se olhássemos só a fase já salva em lead.category,
    um intent_trigger configurado como o próprio sinal de entrada numa fase (ex.:
    "cliente aceitou a oferta") nunca teria como disparar na mensagem que o causa.
    """
    ai_profile = context.get("ai_profile") or {}
    sales_flow = ai_profile.get("sales_flow")
    if not isinstance(sales_flow, dict) or not sales_flow.get("enabled"):
        return []
    phases = sales_flow.get("phases")
    if not isinstance(phases, list):
        return []
    lead = context.get("lead") or {}
    raw_category = (lead.get("category") or "").strip().lower().replace("-", "_")
    _CATEGORY_TO_PHASE_ID: Dict[str, str] = {
        "recepcao": "p0",
        "qualification": "p1",
        "apresentation": "p2",
        "pre_agendamento": "p3a",
        "agendamento": "p3b",
        "follow_up": "p4",
        "followup": "p4",
        "closing": "p5",
    }
    current_phase_id = _CATEGORY_TO_PHASE_ID.get(raw_category, "p0")

    candidate_phase_ids = {current_phase_id}
    sequence = _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE.get(agent_mode_normalized)
    if sequence and current_phase_id in sequence:
        idx = sequence.index(current_phase_id)
        if idx + 1 < len(sequence):
            candidate_phase_ids.add(sequence[idx + 1])

    blocks: List[dict] = []
    for phase_data in phases:
        if isinstance(phase_data, dict) and phase_data.get("id") in candidate_phase_ids:
            blocks.extend(
                b for b in (phase_data.get("blocks") or [])
                if isinstance(b, dict) and b.get("typeId") == "intent_trigger" and (b.get("intent") or "").strip()
            )
    return blocks


def _collect_branch_nodes_for_lead_phase(context: Dict[str, Any], agent_mode_normalized: str) -> List[dict]:
    """Coleta blocos `condicao` (nós de lógica de ramificação) com ramos configurados, da
    fase ATUAL do lead e da fase seguinte (dado o pipeline do agent_mode) — usados para o
    bloco [LÓGICA DE RAMIFICAÇÃO] no prompt da mãe.

    Inclui a fase seguinte pelo mesmo motivo de _collect_intent_triggers_for_lead_phase:
    uma transição de fase (ex.: qualification → apresentation via auto-promoção de
    qualificação vazia) é decidida NESTE turno — se olhássemos só `leads.category` (que só
    reflecte turnos anteriores), um nó configurado na fase de destino nunca seria visto pela
    mãe no turno exacto em que o lead chega lá (confirmado ao vivo: um nó em p2 nunca
    aparecia no prompt da mãe no turno em que qualification promovia para apresentation).

    Nós `sticky` já resolvidos (leads.branches_selected) não são listados de novo — a mãe
    não precisa reavaliar o que já foi decidido num turno anterior (economiza tokens).
    """
    ai_profile = context.get("ai_profile") or {}
    sales_flow = ai_profile.get("sales_flow")
    if not isinstance(sales_flow, dict) or not sales_flow.get("enabled"):
        return []
    phases = sales_flow.get("phases")
    if not isinstance(phases, list):
        return []
    lead = context.get("lead") or {}
    lead_cat_raw = (lead.get("category") or "").strip().lower()
    current_phase_id = _ROUTE_TO_PHASE_ID.get(_LEAD_CAT_TO_ROUTE.get(lead_cat_raw, lead_cat_raw)) or "p0"

    candidate_phase_ids = {current_phase_id}
    sequence = _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE.get(agent_mode_normalized)
    if sequence and current_phase_id in sequence:
        idx = sequence.index(current_phase_id)
        if idx + 1 < len(sequence):
            candidate_phase_ids.add(sequence[idx + 1])

    _resolved = _load_branches_selected_map(context)
    nodes: List[dict] = []
    for phase_data in phases:
        if not isinstance(phase_data, dict) or phase_data.get("id") not in candidate_phase_ids:
            continue
        for b in (phase_data.get("blocks") or []):
            if not isinstance(b, dict) or b.get("typeId") != "condicao":
                continue
            branches = b.get("branches")
            if not isinstance(branches, list) or not branches:
                continue
            _bid = (b.get("id") or "").strip()
            if b.get("sticky") and _bid and _bid in _resolved:
                continue
            nodes.append(b)
    return nodes


def _build_custom_instructions_block(ai_profile: Dict[str, Any]) -> str:
    """Gera bloco de instruções personalizadas do operador com prioridade máxima."""
    ci = (ai_profile.get("custom_instructions") or "").strip()
    if not ci:
        return ""
    return (
        "\nINSTRUÇÕES PERSONALIZADAS DO OPERADOR (prioridade máxima — seguir à risca):\n"
        f"{ci}\n"
    )


def _build_business_info_block(context: Dict[str, Any]) -> str:
    """Injeta informações gerais do negócio disponíveis em qualquer fase do funil."""
    biz = (context.get("knowledge_items") or {}).get("business_info", "").strip()
    if not biz:
        return ""
    return f"\nINFORMAÇÕES DO NEGÓCIO (disponíveis em qualquer fase):\n{biz}\n"


def _build_training_examples_block(context: Dict[str, Any], phase: str) -> str:
    """
    Gera bloco de exemplos de treino classificados pelo operador para a fase atual.

    Esses exemplos são classificações reais de respostas do bot feitas pelo utilizador
    no playground e servem como few-shot de referência para reduzir aleatoriedade.
    """
    training = context.get("training_examples") or {}
    phase_data = training.get(phase) or {}
    good = phase_data.get("good") or []
    bad = phase_data.get("bad") or []
    if not good and not bad:
        return ""

    lines = ["\nEXEMPLOS DE TREINO DO OPERADOR (baseados em classificações reais — usar como referência):"]

    for item in good:
        lead_msg = (item.get("lead_message") or "").strip()
        bot_msg = (item.get("bot_message") or "").strip()
        if not bot_msg:
            continue
        lines.append("\n✅ RESPOSTA APROVADA:")
        if lead_msg:
            lines.append(f'Lead: "{lead_msg}"')
        lines.append(f'Bot: "{bot_msg}"')

    for item in bad:
        lead_msg = (item.get("lead_message") or "").strip()
        bot_msg = (item.get("bot_message") or "").strip()
        comment = (item.get("comment") or "").strip()
        if not bot_msg:
            continue
        lines.append("\n❌ RESPOSTA REJEITADA:")
        if lead_msg:
            lines.append(f'Lead: "{lead_msg}"')
        lines.append(f'Bot: "{bot_msg}"')
        if comment:
            lines.append(f'Motivo do operador: "{comment}"')

    lines.append("")
    return "\n".join(lines)


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
                qualify_if = f.get("qualify_if", "")
                disqualify_if = f.get("disqualify_if", "")
                line = f"- {label} (key: {f.get('key', '')})"
                if question:
                    line += f': pergunta → "{question}"'
                if hint:
                    line += f' | inferir: "{hint}"'
                if qualify_if:
                    line += f' | qualificar se: "{qualify_if}"'
                if disqualify_if:
                    line += f' | não qualificar se: "{disqualify_if}"'
                block += line + "\n"
        if optional_fields:
            block += "DESEJÁVEIS — capturar se surgir oportunidade natural:\n"
            for f in optional_fields:
                label = f.get("label") or f.get("key", "")
                question = f.get("question", "")
                hint = f.get("passive_hint", "")
                qualify_if = f.get("qualify_if", "")
                disqualify_if = f.get("disqualify_if", "")
                line = f"- {label} (key: {f.get('key', '')})"
                if question:
                    line += f': pergunta → "{question}"'
                if hint:
                    line += f' | inferir: "{hint}"'
                if qualify_if:
                    line += f' | qualificar se: "{qualify_if}"'
                if disqualify_if:
                    line += f' | não qualificar se: "{disqualify_if}"'
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
    agent_mode = str(ai_profile.get("agent_mode") or "").strip().lower()

    block = (
        f"\nTOM DE VOZ — REGRAS WHATSAPP:\n"
        f"- Tom configurado: {tone_of_voice}\n"
        f"- Comprimento máximo: {max_chars} caracteres\n"
        f"- Formato: 1 parágrafo curto ou 2–3 linhas. Sem bullet points. Sem formatação markdown.\n"
        f"- Linguagem: conversacional, como se escrevesse a um colega. Sem jargão corporativo.\n"
        f"- Abertura: nunca comece com 'Olá, tudo bem?' genérico se já houve conversa anterior. "
        f"Use o contexto: referir algo que o lead disse antes, ou o campo recém-coletado.\n"
        f"- Variação obrigatória: nunca inicie 2 mensagens consecutivas com a mesma palavra ou expressão. "
        f"Consulte o history para garantir variedade. Proibido repetir 'Ótimo!', 'Perfeito!', 'Claro!' consecutivamente.\n"
        f"- Encerramento: sempre feche com UMA pergunta ou UM próximo passo claro. Nunca dois.\n"
        f"- PROIBIDO: emojis excessivos (máx 1 por mensagem), CAPS LOCK, exclamações consecutivas (!!), "
        f"linguagem de vendas agressiva ('IMPERDÍVEL', 'CORRA', 'NÃO PERCA').\n"
    )
    if agent_mode in ("direto", "closer"):
        block += (
            f"- Comprimento adaptativo (modo direto): mensagens curtas e objetivas. "
            f"Se a resposta cabe em 1 frase, use 1 frase. "
            f"Não expanda para preencher o limite de {max_chars} caracteres.\n"
        )
    elif agent_mode in ("consultivo",):
        block += (
            f"- Comprimento adaptativo (modo consultivo): pode usar até {max_chars} chars "
            f"quando o lead faz uma pergunta complexa ou levanta uma objeção. "
            f"Para perguntas simples, responda de forma objetiva mesmo abaixo do limite.\n"
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


def _build_followup_tone_extensions() -> str:
    """Diretivas de tom específicas para Follow-up e Closing — fases de reengajamento."""
    return (
        "\nTOM — EXTENSÕES PARA REENGAJAMENTO:\n"
        "- Contexto do histórico: abra fazendo referência a algo concreto da última troca "
        "(ex.: 'Como conversamos na semana passada...', 'Você mencionou que...', 'Desde a nossa última conversa...').\n"
        "- Nunca abra como se fosse o primeiro contato — o lead já te conhece.\n"
        "- Anti-repetição de perguntas: antes de fazer qualquer pergunta, verifique no history se ela já foi feita. "
        "Se a resposta já consta no histórico, não repita a pergunta.\n"
    )


def _build_agent_role_block(agent_mode: str, phase: str, ai_profile: Dict[str, Any]) -> str:
    """Gera parágrafo de identidade comercial diferenciado por agent_mode e fase."""
    tone  = str(ai_profile.get("tone_of_voice") or "profissional").strip()
    niche = str(ai_profile.get("niche") or "do negócio").strip()
    brand = str(ai_profile.get("brand_name") or "da empresa").strip()
    rs    = (ai_profile.get("response_style") or "passive").strip().lower()
    qual_style = (
        "passivamente, por inferência silenciosa da conversa"
        if rs == "passive"
        else "ativamente, com perguntas diretas e naturais"
    )

    roles: Dict[str, Dict[str, str]] = {
        "consultivo": {
            "qualification": (
                f"Você é um SDR consultivo especializado em {niche}. "
                f"Tom: {tone}. "
                f"Qualifique o lead {qual_style}. "
                "Cada informação coletada prepara uma reunião de alto valor — nunca force a venda."
            ),
            "apresentation": (
                f"Você é um especialista em agendamento de diagnóstico para {niche} da {brand}. "
                "Objetivo único: confirmar data e horário para sessão com o especialista. "
                "Gere confiança e credibilidade antes de mencionar valor."
            ),
            "follow-up": (
                f"Você é o responsável pelo relacionamento pós-contato da {brand}. "
                f"Tom: {tone}. "
                "Nutra o lead com empatia, trate objeções sem pressão e prepare o caminho "
                "para o fechamento pelo especialista humano."
            ),
            "closing": (
                f"Você prepara o handoff para o especialista humano da {brand}. "
                "Contextualize o interesse e o estágio do lead. "
                "Seu papel é garantir que o especialista receba o contexto completo — não vender."
            ),
        },
        "agenda": {
            "qualification": (
                f"Você é um profissional de atendimento {tone} da {brand}, especializado em {niche}. "
                f"Qualifique o lead {qual_style}. "
                "Objetivo final: conduzir o lead qualificado para uma agenda confirmada."
            ),
            "apresentation": (
                f"Você é um agendador de alta conversão da {brand}. "
                f"Tom: {tone}. "
                "Cada mensagem deve ter um próximo passo claro. "
                "Confirme horário, reforce o benefício da reunião e garanta compromisso de presença."
            ),
            "follow-up": (
                f"Você reengaja leads da {brand} que não compareceram ou precisam remarcar. "
                f"Tom: {tone}, abordagem direta e amigável. "
                "Ofereça 2 a 3 horários concretos para facilitar a decisão — não pergunte 'quando pode'."
            ),
            "closing": (
                f"Você confirma a agenda e coleta dados operacionais da {brand}. "
                "Horário confirmado, link enviado, presença garantida. "
                "Resposta objetiva — não expanda além do necessário."
            ),
        },
        "direto": {
            "qualification": (
                f"Você é um qualificador para venda direta de {niche}. "
                f"Tom: {tone}. "
                f"Qualifique {qual_style}. "
                "Se houver sinal claro de intenção de compra — avance imediatamente para a oferta."
            ),
            "apresentation": (
                f"Você apresenta a oferta da {brand} e conduz ao fechamento direto. "
                f"Tom: {tone}. "
                "Mostre valor em 1 a 2 frases, trate objeção com objetividade, envie link de checkout. "
                "Sem rodeios — cada mensagem empurra ao próximo passo."
            ),
            "follow-up": (
                f"Você recupera vendas da {brand} não concluídas. "
                f"Tom: {tone}. "
                "Mensagem curta: 1 benefício claro + 1 CTA direto. "
                "Não explique — converta."
            ),
            "closing": (
                f"Você conduz o pagamento para {brand}. "
                "Confirmação de interesse → link de checkout → CTA final. "
                "Máximo 2 frases. Nenhuma pergunta aberta nesta fase."
            ),
        },
    }

    role_text = roles.get(agent_mode, {}).get(phase)
    if not role_text:
        return ""
    return f"\nIDENTIDADE COMERCIAL:\n{role_text}\n"


def _build_daughter_identity_block(context: Dict[str, Any], phase: str) -> str:
    """Gera bloco de identidade da profissional para as filhas, análogo ao da mãe.

    Para hybrid_scheduler o bot fala COMO a própria profissional (ex.: Cristina, massagista).
    Para os demais templates, fala como assistente do negócio.
    Inclui tom, nicho, público-alvo e instruções personalizadas do operador com prioridade máxima.
    """
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}

    name = (ai_profile.get("name") or "").strip()
    brand = (ai_profile.get("brand_name") or "").strip()
    niche = (ai_profile.get("niche") or "").strip()
    audience = (ai_profile.get("target_audience") or "").strip()
    tone = (ai_profile.get("tone_of_voice") or "").strip()
    custom = (ai_profile.get("custom_instructions") or "").strip()
    template_key = str(ai_profile.get("template_key") or playbook.get("template_key") or "").strip().lower()

    phase_labels = {
        "qualification": "qualificação",
        "apresentation": "apresentação",
        "follow-up": "follow-up",
        "closing": "fechamento",
        "pre-agendamento": "pré-agendamento",
        "agendamento": "agendamento",
        "recepcao": "recepção",
    }
    phase_label = phase_labels.get(phase, phase)

    if template_key == "hybrid_scheduler":
        # Identidade direta: o bot é a própria profissional
        who = name if name else (f"profissional de {niche}" if niche else "a profissional")
        niche_label = f" especializada em {niche}" if niche else ""
        brand_label = f" ({brand})" if brand else ""
        intro = f"Você é {who}{niche_label}{brand_label}, falando diretamente com o cliente pelo WhatsApp."
    elif template_key in {"consultor_especialista"}:
        business_label = f"da {brand}" if brand else "do negócio"
        niche_label = f" no nicho de {niche}" if niche else ""
        who = name if name else "consultor(a) especialista"
        intro = f"Você é {who}, {business_label}{niche_label}."
    elif template_key in {"closer_agressivo", "closer_agressivo_cart_recovery"}:
        business_label = f"da {brand}" if brand else "do negócio"
        niche_label = f" ({niche})" if niche else ""
        intro = f"Você é vendedor(a) direto(a) {business_label}{niche_label}."
    else:
        # sdr_padrao e outros
        business_label = f"da {brand}" if brand else "do negócio"
        niche_label = f" no nicho de {niche}" if niche else ""
        who = name if name else "assistente de vendas"
        intro = f"Você é {who}, {business_label}{niche_label}."

    lines = [intro]
    if audience:
        lines.append(f"Público-alvo: {audience}.")
    if tone:
        lines.append(f"Tom de comunicação: {tone}.")
    lines.append(f"Fase atual: {phase_label}.")
    lines.append("Papel nesta fase: gerar a resposta para o WhatsApp — conversacional, adaptada ao negócio e ao contexto.")

    identity = "\n".join(lines)
    block = f"\nIDENTIDADE DA PROFISSIONAL:\n{identity}\n"

    if custom:
        block += (
            "\nINSTRUÇÕES DO NEGÓCIO (prioridade máxima — seguir à risca, acima de qualquer padrão genérico):\n"
            f"{custom}\n"
        )

    block += (
        "\nREGRA ANTI-REPETIÇÃO (obrigatória):\n"
        "- Leia o histórico antes de responder.\n"
        "- NUNCA repita frases, conteúdo ou informações já enviados nesta conversa.\n"
        "- NUNCA envie tabelas de preços ou imagens de forma repetida — se já foram enviadas, não mencione nem instrua o cliente a 'ver as informações'.\n"
        "- NUNCA repita saudações (Bom dia/Boa tarde/Boa noite/Olá/Oi): se o histórico já\n"
        "  contém UMA mensagem tua nesta troca, não cumprimente de novo — vai direto ao\n"
        "  conteúdo. Cumprimenta uma vez por conversa, não uma vez por resposta.\n"
        "- Cada resposta deve avançar a conversa, não repetir o turno anterior.\n"
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


_WEEKDAY_NAMES_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def _calendar_lookup_table_pt(days_ahead: int = 14) -> str:
    """Tabela com hoje + próximos `days_ahead` dias, cada um com data e dia da semana.

    Só dar à LLM a data de hoje + nome do dia da semana ("2026-06-21
    (domingo)") não bastou: em teste real, ela ainda errou a contagem ao
    resolver "quinta-feira" (calculou 2026-06-23, uma terça, em vez de
    2026-06-25). Com a tabela completa pronta, ela só precisa localizar a
    linha cujo dia da semana bate com o que o lead disse — sem fazer
    nenhuma conta de calendário por conta própria.
    """
    now = datetime.utcnow()
    lines = []
    for offset in range(days_ahead + 1):
        day = now + timedelta(days=offset)
        marker = " [hoje]" if offset == 0 else ""
        lines.append(f"{day.strftime('%Y-%m-%d')} ({_WEEKDAY_NAMES_PT[day.weekday()]}){marker}")
    return "\n".join(lines)


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
    ) or (
        effective_route_to == "agendamento"
        and (agent_mode == "agenda" or template_key in _SCHEDULING_AGENT_TEMPLATES)
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
    """Lê campos obrigatórios do ai_profile. None = usar defaults do modo."""
    ai_profile = context.get("ai_profile") or {}
    # qualification_fields (UI rica) tem prioridade: contém exatamente o que o usuário configurou.
    # Se presente, usar apenas esses — ignora a lista legada para evitar campos inesperados.
    qual_fields = ai_profile.get("qualification_fields")
    if isinstance(qual_fields, list) and len(qual_fields) > 0:
        return [
            str(f["key"])
            for f in qual_fields
            if isinstance(f, dict) and f.get("mode") == "required" and isinstance(f.get("key"), str)
        ]
    # Backward compat: perfis sem qualification_fields usam a lista plana legada
    override = ai_profile.get("qualification_required_fields")
    if isinstance(override, list):
        return [str(f) for f in override if isinstance(f, str)]
    return None


def _get_active_fields_for_extraction(context: Dict[str, Any]) -> List[str]:
    """Keys de todos os campos ativos (mode required|optional) de
    ai_profile.qualification_fields — usado para ampliar o que o extractor
    de campos (field_extractor.extract_fields_llm) pode capturar, além dos
    required_fields. [] se qualification_fields não estiver configurado
    (perfis legados continuam usando só required_fields + must_collect)."""
    ai_profile = context.get("ai_profile") or {}
    qual_fields = ai_profile.get("qualification_fields")
    if not isinstance(qual_fields, list) or not qual_fields:
        return []
    return [
        str(f["key"])
        for f in qual_fields
        if isinstance(f, dict) and f.get("mode") in ("required", "optional") and isinstance(f.get("key"), str)
    ]


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
        "name": _resolve_lead_name(lead),
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


def _build_mother_identity_block(ai_profile: dict) -> str:
    brand = (ai_profile.get("brand_name") or "").strip()
    niche = (ai_profile.get("niche") or "").strip()
    audience = (ai_profile.get("target_audience") or "").strip()
    tone = (ai_profile.get("tone_of_voice") or "").strip()
    mode = (ai_profile.get("agent_mode") or "").strip()
    offer = (ai_profile.get("offer_description") or "").strip()

    business_label = f"da {brand}" if brand else "do negócio"
    niche_label = f"no nicho de {niche}" if niche else "de vendas"
    audience_label = f"Seu público-alvo: {audience}." if audience else ""
    tone_label = f"Tom de comunicação: {tone}." if tone else ""
    offer_label = f"O que é vendido: {offer}." if offer else ""

    mode_descriptions = {
        "agenda": "foco em conduzir o cliente até o agendamento",
        "consultivo": "foco em qualificar e preparar handoff consultivo",
        "direto": "foco em fechamento direto e objetivo",
        "closer": "foco em fechamento, sem etapas de agendamento",
        "sdr_scheduler": "foco em agendamento via SDR",
    }
    mode_label = mode_descriptions.get(mode, f"modo {mode}") if mode else "modo de vendas"

    lines = [
        f"Você é supervisora de vendas {business_label}, um negócio {niche_label}.",
        f"Seu papel: avaliar em qual fase do processo de compra cada cliente está e decidir o próximo passo ideal para avançar a venda. Você opera com {mode_label}.",
    ]
    if audience_label:
        lines.append(audience_label)
    if tone_label:
        lines.append(tone_label)
    if offer_label:
        lines.append(offer_label)
    lines.append("Você NÃO gera mensagens para o cliente — apenas diagnostica o estado e decide a rota.")
    return "\n".join(lines)


_SCHEDULING_AGENT_TEMPLATES_SET = {"sdr_padrao", "hybrid_scheduler"}


def _build_mother_pipeline_block(template_key: str, ai_profile: dict) -> str:
    tkey = (template_key or "").strip().lower()
    niche = (ai_profile.get("niche") or "serviço").strip()

    if tkey in _SCHEDULING_AGENT_TEMPLATES_SET:
        return (
            f"FASES DA VENDA — pipeline deste agente (nesta sequência):\n\n"
            f"1. QUALIFICAÇÃO — entender o cliente antes de avançar.\n"
            f"   Quando usar: ainda há campos obrigatórios não coletados (missing_fields não vazio).\n"
            f"   Próximo passo: coletar o que falta com naturalidade, sem interrogar.\n\n"
            f"2. APRESENTAÇÃO — apresentar o {niche} e responder dúvidas.\n"
            f"   Quando usar: cliente pergunta sobre serviços, preços, como funciona, localização,\n"
            f"   ou demonstra curiosidade sem ainda ter feito uma escolha concreta.\n"
            f"   Próximo passo: gerar valor, responder, criar interesse.\n\n"
            f"3. PRÉ-AGENDAMENTO — cliente mostrou que quer, mas ainda não disse quando.\n"
            f"   Quando usar: cliente fez uma escolha concreta de serviço/produto ou confirmou\n"
            f"   interesse real (ex.: 'quero o serviço X', 'quero experimentar', 'vou com essa opção',\n"
            f"   'tenho interesse', 'quero marcar') — mas NÃO mencionou data ou horário.\n"
            f"   Não confundir com dúvida: dúvida vai para apresentação. Escolha feita vai aqui.\n"
            f"   Próximo passo: perguntar quando o cliente quer vir.\n\n"
            f"4. AGENDAMENTO — fechar o horário.\n"
            f"   Quando usar: cliente mencionou dia, turno ou hora específica\n"
            f"   (ex.: 'amanhã', 'sexta à tarde', 'às 15h', 'pode ser segunda de manhã?').\n"
            f"   Próximo passo: confirmar e registrar.\n\n"
            f"5. FOLLOW-UP — nutrição pós-apresentação.\n"
            f"   Quando usar: SOMENTE após apresentação realizada, com sinais de adiamento\n"
            f"   (ex.: 'vou pensar', 'me chama mês que vem', 'preciso falar com alguém').\n"
            f"   NUNCA use se não houver evidência de apresentação prévia.\n\n"
            f"6. CLOSING — venda confirmada ou encerrada."
        )
    elif tkey == "closer_agressivo":
        return (
            f"FASES DA VENDA — pipeline deste agente (nesta sequência):\n\n"
            f"1. QUALIFICAÇÃO — validar fit e urgência rapidamente.\n"
            f"   Quando usar: missing_fields não vazio.\n\n"
            f"2. APRESENTAÇÃO — pitch direto da oferta de {niche}.\n"
            f"   Quando usar: cliente demonstra interesse ou faz perguntas sobre o serviço.\n\n"
            f"3. CLOSING — fechar ou tratar objeção.\n"
            f"   Quando usar: cliente sinalizou intenção de compra ('quero fechar', 'posso assinar',\n"
            f"   'manda contrato') ou após apresentação com sinal de decisão.\n"
            f"   NÃO há etapas de pré-agendamento ou agendamento neste agente.\n\n"
            f"4. FOLLOW-UP — SOMENTE após apresentação com adiamento explícito."
        )
    else:
        return (
            f"FASES DA VENDA:\n"
            f"1. QUALIFICAÇÃO → 2. APRESENTAÇÃO → 3. FOLLOW-UP → 4. CLOSING\n"
            f"Use cada fase conforme o estado atual do cliente na conversa."
        )


def _build_mother_prompt(context: Dict[str, Any], message_text: str) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _resolve_lead_name(lead),
        "segment": lead.get("segment"),
        "status": lead.get("status"),
        "category": lead.get("category"),
    }
    ai_summary = {
        "id": ai_profile.get("id"),
        "name": ai_profile.get("name"),
        "brand_name": ai_profile.get("brand_name"),
        "template_key": ai_profile.get("template_key"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "target_audience": ai_profile.get("target_audience"),
        "agent_mode": ai_profile.get("agent_mode"),
        "offer_description": ai_profile.get("offer_description"),
        "goals": ai_profile.get("goals"),
        "custom_instructions": ai_profile.get("custom_instructions"),
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
    _mother_outbound_count = sum(1 for h in history if str(h.get("model") or "").lower() == "outbound")
    mode_contract = _build_mode_contract_context(context)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    template_key = playbook_summary["template_key"] or ""
    custom_instructions = (ai_profile.get("custom_instructions") or "").strip()

    identity_block = _build_mother_identity_block(ai_profile)
    pipeline_block = _build_mother_pipeline_block(template_key, ai_profile)

    custom_block = (
        f"\nINSTRUÇÕES ESPECÍFICAS DO NEGÓCIO:\n{custom_instructions}\n"
        if custom_instructions else ""
    )

    _active_intent_triggers = _collect_intent_triggers_for_lead_phase(context, agent_mode_normalized)
    _intent_detection_block = ""
    if _active_intent_triggers:
        _intent_lines = "\n".join(
            f'- "{b["intent"]}"' + (f": {(b.get('note') or '').strip()}" if (b.get("note") or "").strip() else "")
            for b in _active_intent_triggers
        )
        _intent_detection_block = (
            "\n[DETECÇÃO DE INTENÇÃO]\n"
            "A mensagem do lead pode conter intenções específicas que ativam ações automáticas.\n"
            "Avalie a última mensagem e indique quais das intenções abaixo foram detectadas:\n\n"
            f"{_intent_lines}\n\n"
            "Preencha o campo `detected_intents` com os labels detectados (pode ser lista vazia []).\n"
            "Seja conservador: só marque se houver sinal claro na mensagem. Dúvida = não marcar.\n"
            "OBRIGATÓRIO: se o seu campo \"reason\" menciona que o lead fez/disse algo que\n"
            "corresponde a uma das intenções acima, essa intenção DEVE também aparecer em\n"
            "\"detected_intents\", copiada exatamente entre aspas como está listada acima.\n"
            "Uma resposta onde \"reason\" reconhece a intenção mas \"detected_intents\" fica\n"
            "vazio é INCONSISTENTE — não faça isso.\n"
        )

    _active_branch_nodes = _collect_branch_nodes_for_lead_phase(context, agent_mode_normalized)
    _branch_logic_block = ""
    if _active_branch_nodes:
        _branch_sections = []
        for _node in _active_branch_nodes:
            _node_id = (_node.get("id") or "").strip()
            _node_label = (_node.get("label") or _node.get("condition") or "Lógica sem nome").strip()
            _paths = "\n".join(
                f'  - id="{(br.get("id") or "").strip()}" ({(br.get("label") or "Caminho").strip()}): '
                f'{(br.get("criteria") or "").strip()}'
                for br in (_node.get("branches") or [])
                if isinstance(br, dict) and (br.get("id") or "").strip()
            )
            _branch_sections.append(f'- Lógica "{_node_label}" (id="{_node_id}"), caminhos:\n{_paths}')
        _branch_logic_block = (
            "\n[LÓGICA DE RAMIFICAÇÃO]\n"
            "Cada lógica abaixo tem caminhos nomeados com um critério — avalie a conversa e\n"
            "escolha, para cada lógica, qual caminho o lead deve seguir.\n\n"
            f"{chr(10).join(_branch_sections)}\n\n"
            "Preencha o campo `branch_selections` como um objeto {id_da_logica: id_do_caminho},\n"
            "um par por lógica listada acima. Se nenhum caminho tiver evidência clara na\n"
            "conversa ainda, OMITA essa lógica do objeto (não invente escolha sem sinal).\n"
        )

    return (
        f"{identity_block}\n\n"
        f"{pipeline_block}\n"
        f"{custom_block}\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {template_key}. Missing fields: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}.\n"
        "RECUSAS: Nunca retorne route_to=\"follow-up\" sem evidência textual de apresentação realizada. agent_mode DEVE ser null (vem do sistema).\n\n"
        "PRINCÍPIO FUNDAMENTAL — LEIA ANTES DE QUALQUER REGRA:\n"
        "Antes de verificar missing_fields ou aplicar qualquer prioridade, identifique\n"
        "a INTENÇÃO do lead nesta mensagem. Existem três categorias:\n\n"
        "  1. PRESENÇA SOCIAL: o lead chegou e está se apresentando — saudação, cumprimento,\n"
        "     sem nenhum pedido ou dúvida comercial.\n"
        "     → Não há intenção comercial ainda. NÃO qualifique. Acolha.\n"
        "     → PRIORIDADE 0 abaixo se aplica. Esta categoria SEMPRE prevalece sobre missing_fields.\n\n"
        "  2. INTENÇÃO COMERCIAL: o lead está buscando algo — preço, serviço, disponibilidade,\n"
        "     como funciona, comparando opções.\n"
        "     → Verifique missing_fields e responda ou qualifique conforme as prioridades.\n\n"
        "  3. INTENÇÃO DE AVANÇAR: o lead demonstrou escolha concreta ou confirmação.\n"
        "     → Avance no pipeline (pre-agendamento, agendamento, closing).\n\n"
        "Antes de decidir o route_to, raciocine como uma supervisora experiente:\n"
        "1. É PRESENÇA SOCIAL pura (saudação sem intenção) + outbound_count=0? → recepcao (PRIORIDADE 0)\n"
        "2. Ainda há campos obrigatórios não coletados? (missing_fields não vazio) → qualificação\n"
        "3. O cliente está fazendo perguntas sobre o serviço/produto? → apresentação\n"
        "4. O cliente fez uma escolha concreta de serviço mas não disse quando quer vir? → pré-agendamento\n"
        "5. O cliente mencionou dia, hora ou turno específico? → agendamento\n"
        "6. Apresentação já aconteceu e o cliente pediu tempo? → follow-up\n"
        "7. Sinal claro de fechamento/compra? → closing\n\n"
        "Use o campo \"reason\" para documentar o raciocínio em 1-2 frases curtas.\n\n"
        "Retorne SOMENTE JSON válido no schema MotherDecision:\n"
        "{\n"
        '  "route_to": "qualification|apresentation|pre-agendamento|agendamento|follow-up|closing",\n'
        '  "perceived_category": "qualification|apresentation|pre-agendamento|agendamento|follow-up|closing|null",\n'
        '  "confidence": 0.0,\n'
        '  "reason": "curto",\n'
        '  "agent_mode": null (opcional; deixe null, o modo vem do perfil/sistema),\n'
        '  "signals": {"meeting_scheduled": true|false, "intent_level": "low|medium|high", "urgency_level": "low|medium|high", "price_acceptance": "no|unsure|yes"} (opcional),\n'
        '  "objective": "string curta opcional",\n'
        '  "next_action_hint": "reply|ask_qualification|handoff|ignore|greet|null (opcional)",\n'
        '  "detected_intents": [] (lista de intent labels detectados — ver [DETECÇÃO DE INTENÇÃO] se presente; caso contrário [])\n'
        '  "branch_selections": {} (objeto {id_da_lógica: id_do_caminho} — ver [LÓGICA DE RAMIFICAÇÃO] se presente; caso contrário {})\n'
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
        "  EXCEÇÃO ABSOLUTA: se outbound_count = 0 E a mensagem for exclusivamente saudação social\n"
        "  sem intenção comercial → PRIORIDADE 0 vence; não aplique esta regra.\n"
        "  Se o lead fez uma pergunta direta (sobre serviços, preços, como funciona, etc.) E missing_fields não\n"
        "  estiver vazio → use route_to=\"qualification\" + next_action_hint=\"reply\" (filha responde primeiro,\n"
        "  qualificação continua nos turnos seguintes). NUNCA force qualification sem next_action_hint=\"reply\"\n"
        "  quando o lead fizer uma pergunta direta.\n"
        "  EXCEÇÃO FECHO: sinal explícito de confirmação/booking em agent_mode=agenda/sdr_scheduler permite\n"
        "  route_to=\"apresentation\" — ver PRIORIDADE 1 EXCEÇÃO FECHO abaixo.\n"
        "- Enquanto houver missing_fields E sem sinal de fecho E sem pergunta direta, NÃO sugerir avanço para apresentation, follow-up ou closing.\n"
        "- perceived_category pode refletir o estágio atual do lead, mas route_to deve permanecer qualification até completar o contrato.\n"
        "\n"
        "REGRAS DE ROUTING — AVALIAR NESTA ORDEM (a primeira que coincidir vence):\n\n"
        "PRIORIDADE 0 — PRIMEIRO CONTATO: SAUDAÇÃO PURA (REGRA ABSOLUTA):\n"
        "Quando greeting_responded = false (bot nunca respondeu este lead) E a mensagem do lead\n"
        "é exclusivamente uma saudação social, sem nenhuma intenção comercial embutida\n"
        "(sem pedido de serviço, preço, disponibilidade, produto ou qualquer dúvida):\n"
        "→ route_to = \"recepcao\", confidence = 0.9\n\n"
        "IMPORTANTE: o sistema vai forçar route_to=\"recepcao\" via guardrail de código quando\n"
        "greeting_responded = false, independente do que você decidir. Esta regra existe para\n"
        "você entender o porquê e tomar a decisão conscientemente.\n\n"
        "Por que esta regra existe e por que ela vence sobre todas as outras:\n"
        "Um cliente que chega e apenas diz \"olá\" ainda não expressou o que quer.\n"
        "Qualquer profissional de vendas experiente sabe que o primeiro passo é acolher,\n"
        "não qualificar. Forçar qualificação sobre um cumprimento puro seria antinatural\n"
        "e afastaria o cliente — é como um vendedor em loja que ignora o \"bom dia\" do\n"
        "cliente e já pergunta \"qual o seu orçamento?\". Esta regra VENCE sobre PRIORIDADE 1A\n"
        "mesmo que missing_fields não esteja vazio, porque a ausência de qualificação é\n"
        "irrelevante quando o lead ainda não expressou absolutamente nada além de presença.\n\n"
        "Exemplos de quando aplicar (qualquer idioma, qualquer nicho — raciocine pela intenção):\n"
        "- Apenas cumprimento temporal ou social, sem pergunta = PRIORIDADE 0\n"
        "- Múltiplos cumprimentos encadeados sem pergunta = PRIORIDADE 0\n"
        "- Cumprimento em qualquer idioma, sem pedido = PRIORIDADE 0\n\n"
        "SAUDAÇÃO COMPOSTA (saudação + pergunta ou pedido comercial embutido):\n"
        "→ route_to = \"recepcao\" também vence aqui (mesma regra do guardrail de código acima).\n"
        "Não tente rotear a parte comercial você mesma — a Filha Recepção é responsável por\n"
        "extrair esse pedido e o sistema o reencaminha automaticamente num próximo turno.\n\n"
        "PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):\n"
        "- PRIORIDADE 1A: missing_fields NÃO vazio + mensagem SEM pergunta direta → route_to = \"qualification\"\n"
        "  EXCEÇÃO ABSOLUTA: se greeting_responded = false → PRIORIDADE 0 vence; não aplique esta regra.\n"
        "  O guardrail de código também irá forçar recepcao neste caso.\n"
        "- PRIORIDADE 1B: missing_fields NÃO vazio + mensagem COM pergunta direta (serviços, preço, como\n"
        "  funciona, horários, etc.) → route_to = \"qualification\", next_action_hint = \"reply\"\n"
        "  (filha responde à pergunta antes de qualificar — NUNCA ignore uma pergunta direta do lead)\n"
        "  EXCEÇÃO FECHO (agent_mode=agenda/sdr_scheduler): se a mensagem contiver sinal EXPLÍCITO de\n"
        "  confirmação/booking (\"fica combinado\", \"perfeito\", \"pode ser\", \"fechado\", \"aceito\",\n"
        "  \"tá bom\", \"ok então\", \"combinado\", \"confirmado\", \"então fica assim\" ou equivalentes),\n"
        "  interprete price_acceptance='yes' e meeting_scheduled=true\n"
        "  → route_to = \"apresentation\" mesmo com missing_fields. Documentar no reason.\n\n"
        "PRIORIDADE 2 (sinais fortes de intenção — raciocine pelo contexto, não por palavras específicas):\n"
        "- Cliente fez escolha concreta de serviço/produto sem mencionar data → route_to = \"pre-agendamento\"\n"
        "  (só para templates com fases de agendamento: sdr_padrao, hybrid_scheduler)\n"
        "- Cliente mencionou dia, hora ou turno → route_to = \"agendamento\"\n"
        "  (só para templates com fases de agendamento)\n"
        "- Cliente disse que quer comprar/assinar/fechar com intenção clara → route_to = \"closing\"\n"
        "- Cliente mencionou sessão/reunião passada + dúvida/objeção/feedback → route_to = \"follow-up\"\n\n"
        "PRIORIDADE 3 (sinais médios — usar confidence para desambiguar):\n"
        "- Cliente mostrou interesse mas ainda explora dúvidas → route_to = \"apresentation\", confidence < 0.7\n"
        "- Cliente pediu \"para pensar\" sem evidência de apresentação prévia → MANTER rota atual, não avançar\n\n"
        "PRIORIDADE 4 (sinais fracos — contexto decide):\n"
        "- Mensagem genérica sem intenção clara em conversa já iniciada (outbound_count >= 1)\n"
        "  → manter rota anterior, confidence baixa\n"
        "- Mensagem fora de contexto → route_to = rota atual, next_action_hint = \"reply\"\n\n"
        "SE EM DÚVIDA: mantenha a rota atual com confidence < 0.6.\n"
        "NUNCA retorne route_to=\"follow-up\" se não houver evidência textual de apresentação/sessão realizada.\n\n"
        # ETAPA 4 (roadmap): o marcador "meeting_scheduled" em reason é provisório.
        # Nesta etapa usamos sinal textual simples para orientar o executor, mas a Etapa 4
        # deve migrar isso para um sinal estruturado (ex.: fields JSON/signals) e o CRM
        # será responsável por criar appointment e setar bot_disabled.
        "POLÍTICA POR MODO (agent_mode):\n"
        "- consultivo: não fechar sozinho; qualificar, preparar handoff e agendar quando aplicável.\n"
        "- agenda: foco em conduzir até booking e confirmar presença.\n"
        "- direto: foco em fechamento objetivo e comercial.\n"
        "- sdr_scheduler: compatível com agenda/consultivo.\n"
        "  - Se confirmação de horário/link fechado (ex.: \"Fechou amanhã 17h\", \"pode confirmar\", \"manda o link\"),\n"
        '    prefira signals.meeting_scheduled=true e mantenha substring "meeting_scheduled" no reason por compatibilidade.\n'
        "- closer: foco em avançar até fechamento.\n"
        "  - Agendamento NÃO é objetivo final; meeting_scheduled deve ficar false, salvo agendamento real com necessidade operacional.\n"
        "  - Se inbound for claramente de fechamento, route_to=closing.\n"
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
        f"- outbound_count: {_mother_outbound_count}\n"
        f"- greeting_responded: {'true' if _mother_outbound_count >= 1 else 'false'} "
        f"({'saudação já feita — pipeline normal' if _mother_outbound_count >= 1 else 'PRIMEIRO CONTATO — bot nunca respondeu este lead'})\n"
        f"- lead_origin: {lead_origin_label}\n"
        f"- origin_opener: {origin_opener}\n"
        f"- inbound_message_text: {message_text}\n"
        + (
            "\nMODO PASSIVO (response_style=passive): "
            "Se a mensagem do cliente for uma pergunta directa (sobre serviços, preços, localização, "
            "horários, catálogo de opções, o que oferecem, quais são os valores, etc.) "
            "E missing_fields NÃO ESTIVER VAZIO, "
            "usa next_action_hint='reply' para sinalizar à filha que deve responder a pergunta primeiro. "
            "O route_to continua 'qualification' (os campos ainda precisam de ser coletados), "
            "mas a filha terá prioridade para responder antes de perguntar.\n"
            if (ai_profile.get("response_style") or "passive") == "passive"
            else ""
        )
        + _intent_detection_block
        + _branch_logic_block
    )


def _build_child_prompt_recepcao(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
    is_phase_entry: bool = True,
) -> str:
    """Filha Recepcionista: prompt enxuto para saudações. Sem acesso a mídia, preços ou catálogo."""
    ai_profile = context.get("ai_profile") or {}
    lead = context.get("lead") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []
    playbook = context.get("playbook") or {}

    lead_name = (_resolve_lead_name(lead) or "").strip()
    _is_outbound_lead = (metadata.get("lead_origin") or "inbound") == "outbound"
    origin_opener = (
        ai_profile.get("origin_outbound_opener") if _is_outbound_lead else ai_profile.get("origin_inbound_opener")
    ) or ""

    outbound_count = sum(1 for h in history if str(h.get("model") or "").lower() == "outbound")
    is_new_lead = outbound_count == 0

    identity_block = _build_daughter_identity_block(context, "recepcao")
    tone_block = _build_tone_block(ai_profile, playbook)

    if is_new_lead and origin_opener.strip():
        greeting_instruction = (
            "ABERTURA CONFIGURADA — PRIMEIRO CONTATO:\n"
            f"Use o texto abaixo como BASE da sua resposta de boas-vindas.\n"
            f"Adapte ao WhatsApp e ao tom de voz, mas preserve a essência:\n"
            f"{origin_opener}\n"
        )
    elif is_new_lead:
        greeting_instruction = (
            "INSTRUÇÃO: Dê boas-vindas ao lead de forma calorosa e natural.\n"
            "Exemplo de tom (adapte): 'Olá! Seja bem-vindo(a)! Como posso ajudar?'\n"
        )
    else:
        lead_name_part = f", {lead_name}" if lead_name else ""
        greeting_instruction = (
            f"INSTRUÇÃO: O lead retornou. Cumprimente de volta de forma calorosa e breve "
            f"(ex.: 'Olá{lead_name_part}! Que bom ter você de volta.').\n"
            "Convide-o a continuar com uma frase natural (ex.: 'Como posso te ajudar hoje?').\n"
        )

    lead_name_ctx = f"Nome do lead: {lead_name}." if lead_name else "Nome do lead: desconhecido."
    brand_name = (ai_profile.get("brand_name") or "").strip() or "o negócio"

    _recepcao_prompt = f"""{identity_block}
{tone_block}FASE: recepção (saudação).

{lead_name_ctx}
Mensagem recebida: {message_text}

IDENTIDADE:
Você é a Recepção de {brand_name} — a primeira pessoa que o lead encontra ao
entrar em contato. Seu papel dura só este turno: dar as boas-vindas e passar a
conversa adiante para quem trata o assunto de verdade.

O QUE VOCÊ FAZ:
1. Cumprimenta o lead de forma calorosa, breve e natural.
2. Lê a mensagem inteira — ela pode ter VÁRIAS LINHAS, porque o sistema agrupa
   mensagens que o lead mandou em sequência rápida no WhatsApp (dentro de poucos
   segundos) num único texto, uma por linha.
3. Se, além da saudação/cortesia, houver QUALQUER pedido, pergunta ou intenção
   comercial (agendar, preço, horário de funcionamento, disponibilidade,
   serviço, catálogo, etc.) — mesmo fundida na MESMA linha da saudação —
   extrai esse trecho, literal, para o campo "pending_commercial_text".

COMO VOCÊ FAZ:
{greeting_instruction}
Extração: releia linha a linha antes de responder. Copie o trecho comercial
LITERAL (não resuma, não reescreva, não responda a ele) para
"pending_commercial_text". Se a mensagem for saudação/social pura, sem nenhum
pedido embutido, retorne "pending_commercial_text": null.

EXEMPLOS DO QUE FAZER (✅):
1. Mensagem: "Oi"
   → message_text: "Oi! Seja bem-vindo(a)! Como posso ajudar?" | pending_commercial_text: null
2. Mensagem: "Boa tarde, gostaria de agendar para hoje às 17:30"
   → message_text: "Boa tarde! Obrigado pelo contato." | pending_commercial_text: "gostaria de agendar para hoje às 17:30"
3. Mensagem: "oi\\nboa tarde\\ntudo bem?\\nqual o preço da massagem e horários disponíveis?"
   → message_text: "Boa tarde! Agradeço o contato, estou aqui para ajudar." | pending_commercial_text: "qual o preço da massagem e horários disponíveis?"

O QUE VOCÊ NÃO FAZ:
- Não responde, não promete verificar, não qualifica o pedido comercial —
  isso é trabalho de outro turno do sistema, não seu.
- Não menciona preços, tabelas, serviços, imagens, links ou catálogo.
- Não faz perguntas de qualificação neste turno.
- Máximo 2-3 linhas, sempre.

EXEMPLOS DE ERRO (❌) — NÃO FAÇA ISTO:
1. Mensagem: "Boa tarde, gostaria de agendar para hoje às 17:30"
   ❌ message_text: "Vamos agendar seu horário. Você gostaria de agendar para hoje às 17:30?"
   (respondeu ao pedido em vez de só cumprimentar e reportar em pending_commercial_text)
2. Mensagem: "Olá, qual o horário de funcionamento de vocês?"
   ❌ message_text: "Nós funcionamos de segunda a sábado, das 9h às 18h."
   (deu a informação diretamente em vez de extrair o pedido para outro turno tratar)
3. Mensagem: "Oi, gostaria de saber o preço"
   ❌ message_text: "Olá! Vou verificar o preço para você e já te retorno."
   (promessa vazia sem nenhum estado registrado — o pedido tem que ir para
   pending_commercial_text, nunca virar uma promessa solta que ninguém cumpre)

Retorne SOMENTE JSON válido:
{{
  "message_text": "<cumprimento caloroso — máximo 2-3 linhas>",
  "should_ask": false,
  "question_text": "",
  "field": null,
  "did_complete_phase": false,
  "confidence": 0.95,
  "signals": [],
  "pending_commercial_text": "<trecho literal do pedido comercial, ou null se só houve saudação>"
}}
"""
    _recepcao_prompt += _build_sales_flow_phases_block(_evaluate_sales_flow_phases(context, "recepcao", message_text, detected_intents=mother_decision.detected_intents, is_phase_entry=is_phase_entry, branch_selections=mother_decision.branch_selections))
    return _recepcao_prompt


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
        "name": _resolve_lead_name(lead),
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
        "RECUSAS: Nunca invente informação. Nunca prometa condições não presentes no contexto. Nunca dê conselhos médicos, jurídicos ou financeiros.\n"
        "NOME DO LEAD: Se lead.name for null, NÃO invente nem adivinhe o nome do lead. Nunca chame o lead pelo nome se ele não o forneceu na conversa.\n\n"
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
    is_phase_entry: bool = True,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _resolve_lead_name(lead),
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
    is_first_contact = len(history) <= 1

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

    _mother_hint = (mother_decision.next_action_hint or "").strip().lower()
    _passive_reply_now = response_style == "passive" and _mother_hint == "reply"

    _has_active_qual_fields = any(
        isinstance(f, dict) and f.get("mode") in ("required", "optional")
        for f in (ai_profile.get("qualification_fields") or [])
    )
    _natural_reaction_block = (
        "\nREAÇÃO NATURAL (obrigatória entre respostas e perguntas):\n"
        "Quando o histórico mostra que o lead acabou de responder a uma pergunta de qualificação, "
        "ANTES de fazer a próxima pergunta inclui um breve comentário contextual (1-2 frases curtas):\n"
        "- Resposta corresponde ao critério 'qualificar se' do campo → usa tom de conexão "
        "(ex: 'Perfeito.', 'Faz sentido!', 'Ótimo, faz todo o sentido.').\n"
        "- Resposta não corresponde ao critério 'não qualificar se' → usa compreensão breve "
        "(ex: 'Entendi.', 'Certo.', 'Obrigado por partilhar.').\n"
        "- Sem critério definido para o campo → reage naturalmente ao que o lead disse.\n"
        "Nunca pula de pergunta para pergunta sem reconhecer o que o lead disse primeiro.\n"
        if response_style == "active" and _has_active_qual_fields
        else ""
    )

    # Detectar bloco de abertura de qualificação (qual_opener) na fase p1 do sales_flow
    _asked_questions_all = mode_contract.get("asked_questions_json") or []
    _qual_opener_content: Optional[str] = None
    if response_style == "active" and _has_active_qual_fields and not _asked_questions_all:
        _sales_flow = ai_profile.get("sales_flow") or {}
        _p1_phase = next(
            (p for p in (_sales_flow.get("phases") or []) if isinstance(p, dict) and p.get("id") == "p1"),
            None,
        )
        if _p1_phase:
            _opener_block = next(
                (b for b in (_p1_phase.get("blocks") or []) if isinstance(b, dict) and b.get("qual_opener")),
                None,
            )
            if _opener_block:
                _qual_opener_content = str(_opener_block.get("content") or "").strip() or None

    _qual_opener_injection = (
        f"\nINSTRUÇÃO DE ABERTURA OBRIGATÓRIA (somente neste turno — é a primeira pergunta desta sessão):\n"
        f"{_qual_opener_content}\n"
        f"IMPORTANTE: em message_text coloca a abertura + a primeira pergunta de qualificação juntos (numa resposta fluida). "
        f"Não comeces directamente pela pergunta sem a abertura.\n"
        if _qual_opener_content
        else ""
    )

    _media_intro_note = ""  # qualificação nunca envia knowledge_media

    # ESCOPO e RECUSAS condicionais ao response_style.
    # O bloco passivo aparece ANTES do PAPEL para ter precedência sobre qualquer instrução posterior.
    _escopo_line = (
        "Responder perguntas directas do cliente PRIMEIRO, usando custom_instructions. "
        "Se a mensagem do lead for uma saudação social (boa tarde, oi, olá, tudo bem, bom dia, etc.), "
        "responde à saudação de forma calorosa. "
        "NÃO agenda reunião nesta fase. "
        "MODO PASSIVO — REGRA ABSOLUTA DE PERGUNTAS: ZERO perguntas abertas. "
        "should_ask=false na esmagadora maioria dos casos. "
        "A qualificação é feita por INFERÊNCIA SILENCIOSA — lê o que o lead diz e preenche os campos internamente. "
        "A única exceção permitida: pergunta de fechamento binária no contexto de marcação de hora "
        "(ex.: 'Tenho segunda às 15h ou 17h — qual prefere?'). Mesmo assim, only 1 pergunta, nunca aberta."
        if response_style == "passive"
        else (
            "Responde SEMPRE à mensagem do cliente antes de qualificar. Se o cliente fez uma pergunta, "
            "responde usando custom_instructions. "
            "Se a mensagem do lead for uma saudação social (boa tarde, oi, olá, tudo bem, bom dia, etc.), "
            "responde à saudação de forma calorosa antes de qualificar. "
            "Depois, se houver campos obrigatórios em falta, adicione UMA única pergunta de qualificação natural ao final. "
            "Nunca respondas APENAS com uma pergunta de qualificação. Não agenda reuniões nesta fase."
        )
    )
    _recusas_line = (
        "Nunca invente informação. Nunca agende reunião nesta fase. "
        "Se a resposta não estiver em custom_instructions, diz que vais verificar (→ handoff). "
        "Em modo passivo: NUNCA faças perguntas para coletar dados — infere silenciosamente da conversa."
        if response_style == "passive"
        else (
            "Nunca invente informação. Nunca agende reunião nesta fase. "
            "Se não souber responder, diz que vais verificar (→ handoff)."
        )
    )
    _passive_header = (
        (
            "MODO PASSIVO ACTIVADO — RESPOSTA IMEDIATA OBRIGATÓRIA.\n"
            "A mãe sinalizou next_action_hint='reply': o cliente fez uma pergunta directa.\n"
            "INSTRUÇÃO CRÍTICA: coloca TODA a resposta em message_text. NÃO perguntes nada neste turno.\n"
            "should_ask=false. question_text DEVE ficar vazio (\"\").\n"
            "Responde à pergunta do cliente usando apenas custom_instructions. "
            "NÃO menciones preços, tabelas de valores, promoções ou oferta comercial — "
            "essas informações são exclusivas da fase de apresentação.\n"
            "A qualificação continua nos próximos turnos — NÃO neste.\n\n"
        )
        if _passive_reply_now
        else (
            "MODO PASSIVO ACTIVADO — ZERO PERGUNTAS ABERTAS.\n"
            "PRIORIDADE ABSOLUTA: se a mensagem do cliente for uma pergunta directa (sobre\n"
            "localização, horários, funcionamento, etc.), RESPONDE-A PRIMEIRO usando custom_instructions.\n"
            "Para perguntas sobre preços ou oferta: informa que essas informações serão apresentadas em breve.\n"
            "NÃO faças perguntas de qualificação. Infere os campos silenciosamente da conversa.\n"
            "should_ask=false na esmagadora maioria dos casos.\n"
            "NUNCA ignores uma pergunta directa para fazer uma pergunta de qualificação.\n\n"
            if response_style == "passive"
            else ""
        )
    )

    _first_contact_opener_header = (
        f"ABERTURA OBRIGATÓRIA — PRIMEIRO CONTATO:\n"
        f"Este é o PRIMEIRO contacto do lead. Use o texto abaixo como BASE da tua resposta.\n"
        f"Adapte ao WhatsApp e ao tom de voz, mas preserve a essência:\n"
        f"{origin_opener}\n\n"
        if (is_first_contact and origin_opener.strip())
        else ""
    )

    _qual_prompt = f"""{_first_contact_opener_header}{_passive_header}{_build_daughter_identity_block(context, "qualification")}
{_build_agent_role_block(agent_mode_normalized, "qualification", ai_profile)}
PAPEL: Coletar campos de qualificação do lead, um por vez, através de perguntas naturais e contextuais.
ESCOPO: {_escopo_line}{_media_intro_note}
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
  "recommended_next_category": "apresentation|pre-agendamento|null",
  "outcome": null,
  "kanban_highlight": null,
  "signals": ["..."],
  "signals_structured": {{"missing_fields": ["..."], "handoff_requested": false}} (opcional),
  "confidence": 0.0
}}
Regras:
- LIMITE CRÍTICO DE PERGUNTAS: máximo 1 (UMA) pergunta por mensagem, sem exceção.
  Nunca coloque 2 ou mais perguntas numa mesma resposta (nem com "e também", "além disso", listas, etc.).
  Se precisar de múltiplos campos, pergunte UM por vez, em rodadas separadas.
  Puxe gancho da última resposta do lead para formular a próxima pergunta de forma natural.
{_natural_reaction_block}- Quando should_ask=true, field deve ser EXATAMENTE o current_field.
- Quando should_ask=true, question_text não pode ser vazio.
- Evite repetir frases de asked_questions_for_current_field; reformule.
- Se current_field já tiver sido preenchido, retorne should_ask=false, field=null, question_text="".
- NÃO agendar reunião aqui (só na rota apresentation, salvo pedido explícito do inbound).
- recommended_next_category pode ser null, 'apresentation' ou 'pre-agendamento'.
- outcome e kanban_highlight devem ser null.
- RECONHECIMENTO DE INTENÇÃO DE AGENDAMENTO: Se o lead demonstrou interesse concreto num serviço específico
  ("quero [serviço]", "quero experimentar", "quero marcar", "vou querer") OU perguntou sobre
  disponibilidade/horários ("que horas", "que dia", "tem horário", "posso marcar"), mesmo que ainda haja
  campos em falta, sinalize: should_ask=false, did_complete_phase=true,
  recommended_next_category="pre-agendamento". Em message_text: reconheça o interesse com naturalidade
  e pergunte quando o cliente pode vir (dia e horário). Não continue o fluxo de qualificação neste turno.

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
{_qual_opener_injection}
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
{_build_qualification_fields_block(ai_profile, response_style)}{_build_custom_instructions_block(ai_profile)}{_build_business_info_block(context)}{_build_training_examples_block(context, "qualification")}"""
    _qual_prompt += _build_sales_flow_block(_evaluate_sales_flow(context, "qualification", mother_decision.signals))
    _qual_prompt += _build_sales_flow_phases_block(_evaluate_sales_flow_phases(context, "qualification", message_text, detected_intents=mother_decision.detected_intents, is_phase_entry=is_phase_entry, branch_selections=mother_decision.branch_selections))
    return _inject_generated_parts(_qual_prompt, context, "qualification")

def _build_child_prompt_apresentation(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
    is_phase_entry: bool = True,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _resolve_lead_name(lead),
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
    dates_table = _calendar_lookup_table_pt()

    # Fix P9: passive reply antes do agendamento quando a qualificação foi auto-promovida
    # neste mesmo turno e o lead tinha uma pergunta aberta de serviço na mensagem.
    # Inclui route_to=="recepcao": numa saudação composta (1ª mensagem do lead já
    # qualificada + com pedido de serviço), o _enforce_greeting_first força route_to
    # para "recepcao" mesmo quando o compound follow-through já promoveu o turno para
    # apresentation — sem isto, esse caso nunca era reconhecido como "qualificação
    # recém-concluída" (bug: bloco MODO COMERCIAL não disparava na 1ª mensagem rica).
    _response_style_apres = (ai_profile.get("response_style") or "passive").strip().lower()
    _auto_promoted_from_qual = (
        mother_decision.route_to in ("qualification", "recepcao")
        and not mode_contract.get("missing_fields")
    )
    _inbound_text_apres = str(metadata.get("inbound_message_text") or "").lower()
    _apres_inbound_has_question = "?" in _inbound_text_apres or any(
        m in _inbound_text_apres for m in [
            "gostaria de saber", "como faço", "como funciona", "o que é",
            "queria entender", "pode me dizer", "me explica", "preciso entender",
        ]
    )
    _passive_apres_header = ""
    if _auto_promoted_from_qual and _response_style_apres == "passive" and _apres_inbound_has_question:
        _passive_apres_header = (
            "ATENÇÃO — PERGUNTA ABERTA DO LEAD: O lead fez uma pergunta sobre o serviço neste turno "
            "(ver inbound_message_text). A qualificação foi concluída neste mesmo turno.\n"
            "INSTRUÇÃO CRÍTICA: ANTES de propor o agendamento, RESPONDE à pergunta do lead "
            "usando offer_description e custom_instructions.\n"
            "Integra a resposta e a proposta de agendamento numa única mensagem fluida e natural. "
            "NUNCA ignores a pergunta do lead.\n\n"
        )

    # Greeting awareness — quando a mãe sinaliza next_action_hint='greet', o lead abriu com uma
    # saudação social. O prompt de apresentação deve responder à saudação antes de executar o
    # objetivo do estágio (agendamento, aquecimento ou pitch). Sem alterar roteamento.
    _mother_hint_apres = (mother_decision.next_action_hint or "").strip().lower()
    _is_greeting_apres = _mother_hint_apres == "greet"
    _greeting_apres_header = (
        "ATENÇÃO — SAUDAÇÃO DO LEAD: O lead enviou uma saudação como primeira mensagem.\n"
        "INSTRUÇÃO OBRIGATÓRIA: A tua resposta DEVE começar com um cumprimento caloroso e natural "
        "(ex.: 'Boa noite!', 'Olá, boa noite!', 'Oi, boa noite! Tudo bem?'). "
        "O cumprimento deve ser breve e proporcional à saudação recebida.\n"
        "DEPOIS do cumprimento, de forma fluida e natural na MESMA mensagem, "
        "executa o objetivo do estágio atual (agendamento, aquecimento ou apresentação).\n"
        "NUNCA ignores a saudação e vás directamente para o pitch ou para o agendamento.\n\n"
        if _is_greeting_apres
        else ""
    )

    # Opener de primeiro contato para apresentation
    _is_outbound_lead_apres = (metadata.get("lead_origin") or "inbound") == "outbound"
    origin_opener_apres = (
        ai_profile.get("origin_outbound_opener") if _is_outbound_lead_apres
        else ai_profile.get("origin_inbound_opener")
    ) or ""
    is_first_contact_apres = len(history) <= 1
    _apres_first_contact_opener = (
        f"ABERTURA OBRIGATÓRIA — PRIMEIRO CONTATO:\n"
        f"Este é o PRIMEIRO contacto do lead. Use o texto abaixo como BASE da tua resposta.\n"
        f"Adapte ao WhatsApp e ao tom de voz, mas preserve a essência:\n"
        f"{origin_opener_apres}\n\n"
        if (is_first_contact_apres and origin_opener_apres.strip())
        else ""
    )

    # Estágio de aquecimento (Tarefa 3.8) — Agent 3 (hybrid_scheduler) pós-qualificação.
    # Trigger: _auto_promoted_from_qual (route_to "qualification" OU "recepcao" com
    # missing_fields vazio — qualificação recém-aprovada/auto-promovida para apresentation,
    # incluindo a saudação composta da 1ª mensagem).
    # Defaults context-aware: usam o niche do ai_profile para evitar linguagem B2B genérica
    # ("profissional com o seu perfil", "mapear situação", "plano de ação") em nichos B2C.
    _niche_for_defaults = str(ai_profile.get("niche") or "").strip()
    _DEFAULT_SOCIAL_PROOF = (
        f"Já trabalhei com vários clientes na área de {_niche_for_defaults} e os resultados têm sido muito positivos. "
        "Posso te contar mais na nossa conversa."
        if _niche_for_defaults else
        "Vários clientes já utilizaram o serviço e tiveram ótimos resultados. "
        "Posso te contar mais na nossa conversa."
    )
    _DEFAULT_SESSION_PREVIEW = (
        f"Na nossa sessão, vou perceber melhor o que precisas na área de {_niche_for_defaults} "
        "e encontraremos juntos a melhor abordagem para ti."
        if _niche_for_defaults else
        "Na nossa sessão, vamos entender o que você precisa e encontrar a melhor forma de te ajudar."
    )
    template_key_for_warming = str(ai_profile.get("template_key") or "").strip().lower()
    appointment_mode = str(ai_profile.get("appointment_mode") or "exploratory").strip().lower()
    knowledge_items = context.get("knowledge_items") or {}
    # Categorias do knowledge que têm mídia configurada — usadas para suprimir texto
    # quando a mídia é preferencial (evita que o LLM descreva o conteúdo em texto).
    _km_categories = set((context.get("knowledge_media") or {}).keys())
    # Dedup de knowledge narrativo (social_proof/pitch_script/product_details): calculado
    # uma única vez e reutilizado tanto pelo caminho commercial_injection (abaixo) quanto
    # pelo caminho on-demand (_apres_knowledge_parts, mais adiante) — os dois são
    # mutuamente exclusivos no MESMO turno, mas cobrem o mesmo estado "já mostrado" entre
    # turnos diferentes da mesma conversa (_auto_promoted_from_qual pode ficar True em
    # mais de um turno).
    _narrative_dedup_apres = _evaluate_narrative_knowledge_dedup(context, "apresentation", knowledge_items)
    warming_injection = ""
    commercial_injection = ""
    if (
        template_key_for_warming == "hybrid_scheduler"
        and _auto_promoted_from_qual
    ):
        if appointment_mode == "commercial":
            # Modo comercial: apresentar serviços/preços, tratar objeções, fechar compromisso, DEPOIS agendar.
            # Pagamento sempre presencial — nunca enviar link de checkout.
            _social_kb_apres = str(knowledge_items.get("social_proof") or "").strip()
            _social_proof_suppressed_apres = "social_proof" in _narrative_dedup_apres["suppressed_categories"]
            if _social_kb_apres and not _social_proof_suppressed_apres:
                social = _social_kb_apres
            elif not _social_kb_apres:
                # Nunca configurado no knowledge base — mantém o fallback do AI Profile.
                social = str(ai_profile.get("warming_social_proof") or "").strip()
            else:
                # Configurado, mas já mostrado nesta conversa — suprime sem cair no
                # fallback (evitaria repetir com outras palavras a mesma narrativa).
                social = ""
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
                    (
                        ""  # já mostrada antes nesta conversa — omite o parágrafo inteiro
                        if _social_proof_suppressed_apres
                        else "  PROVA SOCIAL: (não configurada — use tom acolhedor e destaque o diferencial do profissional)\n"
                    )
                )
                + (
                    f"  TABELA DE SERVIÇOS/PREÇOS (apresentar para contextualizar a oferta — pode haver mais "
                    f"de uma tabela, cada uma com um título próprio, ex. por profissional ou especialidade):\n"
                    f"  {pricing}\n"
                    f"  INSTRUÇÃO: Apresente com clareza. Se houver mais de uma tabela, identifique qual é "
                    f"relevante para o lead antes de apresentar valores. Nunca invente preços ou condições "
                    f"não listadas.\n"
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

    # Nota de mídia: quando há mídia configurada no knowledge, instrui o LLM a escrever texto curto.
    # Suprimido em greeting e quando a mídia já foi enviada antes (deduplicação).
    _has_knowledge_media_apres = bool(context.get("knowledge_media"))
    _apres_outbound_count = sum(1 for h in history if str(h.get("model") or "").lower() == "outbound")
    _apres_media_already_sent = _apres_outbound_count >= 1
    _media_intro_note_apres = (
        "\nMÍDIA DISPONÍVEL: Imagens/arquivos serão enviados automaticamente após esta mensagem.\n"
        "Escreva APENAS uma frase curta de introdução (ex.: 'Aqui estão os detalhes:', "
        "'Veja as informações abaixo:'). NÃO descreva o conteúdo da mídia no texto — a mídia tem prioridade.\n"
        if (_has_knowledge_media_apres and not _is_greeting_apres and not _apres_media_already_sent)
        else ""
    )

    # Tarefa 1.3 — knowledge_items com directivas de uso para sdr_padrao / closer_agressivo
    # (e qualquer path que não use commercial_injection, onde knowledge não é injectado inline)
    _apres_knowledge_parts: list[str] = []
    if not commercial_injection:
        _social_proof_apres = _narrative_dedup_apres["content"].get("social_proof") or ""
        _pitch_script_apres = _narrative_dedup_apres["content"].get("pitch_script") or ""
        _product_details_apres = _narrative_dedup_apres["content"].get("product_details") or ""
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
            if "pitch_script" in _km_categories:
                _apres_knowledge_parts.append(
                    "SCRIPT DE PITCH: Conteúdo disponível em mídia visual (enviada automaticamente).\n"
                    "INSTRUÇÃO CRÍTICA: Escreva APENAS uma frase curta de introdução. "
                    "NÃO descreva o conteúdo — a mídia tem prioridade absoluta.\n"
                )
            else:
                _apres_knowledge_parts.append(
                    f"SCRIPT DE PITCH (usar como guia estrutural da apresentação, não copiar literalmente):\n"
                    f"{_pitch_script_apres}\n"
                    f"INSTRUÇÃO: Adapte ao contexto da conversa e ao tom de voz configurado. "
                    f"Nunca copie o script palavra por palavra.\n"
                )
        if _product_details_apres:
            if "product_details" in _km_categories:
                _apres_knowledge_parts.append(
                    "DETALHES DO PRODUTO/SERVIÇO: Conteúdo disponível em mídia visual (enviada automaticamente).\n"
                    "INSTRUÇÃO CRÍTICA: Escreva APENAS uma frase curta de introdução. "
                    "NÃO descreva features nem condições — a mídia tem prioridade absoluta.\n"
                )
            else:
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
            if "service_faq" in _km_categories:
                _apres_knowledge_parts.append(
                    "FAQ DO SERVIÇO: Informação completa disponível em arquivo de mídia (enviado automaticamente).\n"
                    "INSTRUÇÃO CRÍTICA: Escreva APENAS uma frase curta de introdução "
                    "(ex.: 'Aqui estão os valores:', 'Veja os detalhes abaixo:'). "
                    "NÃO liste preços, serviços nem detalhes — a mídia tem prioridade absoluta sobre o texto.\n"
                )
            else:
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
        # Categorias comerciais do hybrid_scheduler (modo commercial) fora do turno único
        # de warming (commercial_injection vazio aqui): o aquecimento proativo não repete,
        # mas o conteúdo (preço, objeções, etc.) continua disponível sob demanda — mesmo
        # padrão "usar APENAS se pedido" já aplicado acima a objections_faq/service_faq.
        if template_key_for_warming == "hybrid_scheduler" and appointment_mode == "commercial":
            _pricing_ondemand = knowledge_items.get("service_pricing_table") or ""
            _objections_ondemand = knowledge_items.get("commercial_objections") or ""
            _differentials_ondemand = knowledge_items.get("service_differentials") or ""
            _promotion_ondemand = knowledge_items.get("active_promotion") or ""
            _payment_ondemand = knowledge_items.get("payment_policy") or ""
            _faq_commit_ondemand = knowledge_items.get("pre_commitment_faq") or ""
            if _pricing_ondemand:
                if "service_pricing_table" in _km_categories:
                    _apres_knowledge_parts.append(
                        "TABELA DE SERVIÇOS/PREÇOS: conteúdo disponível em mídia visual "
                        "(enviada automaticamente quando pedida).\n"
                        "INSTRUÇÃO CRÍTICA: escreva APENAS uma frase curta de introdução SE o lead "
                        "pedir preço, valores ou pacotes explicitamente neste turno. Caso contrário, "
                        "não mencione — a mídia tem prioridade absoluta sobre o texto.\n"
                    )
                else:
                    _apres_knowledge_parts.append(
                        f"TABELA DE SERVIÇOS/PREÇOS (usar APENAS se o lead pedir preço, valores ou "
                        f"pacotes explicitamente neste turno):\n"
                        f"{_pricing_ondemand}\n"
                        f"INSTRUÇÃO: Se houver pedido explícito, apresente com clareza os valores "
                        f"exatos. Nunca invente preços ou condições não listadas. Sem pedido explícito, "
                        f"não mencione.\n"
                    )
            if _objections_ondemand:
                _apres_knowledge_parts.append(
                    f"OBJEÇÕES COMERCIAIS E RESPOSTAS (usar APENAS quando o lead levantar uma "
                    f"objeção de preço ou comprometimento):\n"
                    f"{_objections_ondemand}\n"
                    f"INSTRUÇÃO: Use a resposta configurada como base, adapte ao tom de voz. "
                    f"Nunca copie literalmente.\n"
                )
            if _differentials_ondemand:
                _apres_knowledge_parts.append(
                    f"DIFERENCIAIS DO SERVIÇO (usar APENAS quando o lead comparar com concorrência "
                    f"ou pedir o diferencial):\n"
                    f"{_differentials_ondemand}\n"
                    f"INSTRUÇÃO: Integre naturalmente, não liste como bullet points.\n"
                )
            if _promotion_ondemand:
                _apres_knowledge_parts.append(
                    f"CONDIÇÃO ESPECIAL VIGENTE (citar apenas se relevante para o lead fechar agora):\n"
                    f"{_promotion_ondemand}\n"
                    f"INSTRUÇÃO: Cite apenas se vigente. Nunca crie urgência artificial.\n"
                )
            if _payment_ondemand:
                _apres_knowledge_parts.append(
                    f"POLÍTICA DE PAGAMENTO PRESENCIAL (usar APENAS se o lead perguntar sobre "
                    f"formas de pagamento):\n"
                    f"{_payment_ondemand}\n"
                    f"INSTRUÇÃO: Reforce que o pagamento é presencial. Nunca envie link de checkout.\n"
                )
            if _faq_commit_ondemand:
                _apres_knowledge_parts.append(
                    f"FAQ PRÉ-COMPROMISSO (usar APENAS quando o lead fizer uma pergunta diretamente "
                    f"coberta):\n"
                    f"{_faq_commit_ondemand}\n"
                    f"INSTRUÇÃO: Responda com base no FAQ. Se a pergunta não estiver coberta, diga "
                    f"que vai confirmar com a equipa.\n"
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

    # Bloco de seleção contextual de mídias — a filha declara explicitamente quais
    # mídias do knowledge devem ser anexadas neste turno. O decision_engine usa essa
    # lista para filtrar o envio (substitui a anexação determinística que enviava tudo).
    _CATEGORY_LABELS_APRES = {
        "service_pricing_table": "Tabela de preços e serviços",
        "commercial_objections": "Respostas a objeções comerciais",
        "payment_policy": "Política de pagamento",
        "service_differentials": "Diferenciais do serviço",
        "active_promotion": "Condição/promoção vigente",
        "pre_commitment_faq": "FAQ pré-compromisso",
        "social_proof": "Prova social",
        "pitch_script": "Script de pitch",
        "product_details": "Detalhes do produto/serviço",
        "service_faq": "FAQ do serviço",
        "guarantee_policy": "Política de garantia",
    }
    _media_catalog_lines = []
    for _cat, _entries in (context.get("knowledge_media") or {}).items():
        _n = len(_entries) if isinstance(_entries, list) else 1
        _label = _CATEGORY_LABELS_APRES.get(_cat, _cat)
        _media_catalog_lines.append(
            f"  - {_cat}: {_label} ({_n} {'mídia' if _n == 1 else 'mídias'})"
        )
    _media_selection_block = (
        "\nSELEÇÃO CONTEXTUAL DE MÍDIA (campo media_keys_to_send do JSON):\n"
        "O sistema enviará automaticamente APENAS as mídias cujas chaves você listar em media_keys_to_send.\n"
        "MÍDIAS DISPONÍVEIS:\n"
        + "\n".join(_media_catalog_lines) + "\n"
        "REGRA CRÍTICA — mídia NUNCA é enviada proativamente:\n"
        "- Default: media_keys_to_send=[]. Em dúvida, deixe vazio.\n"
        "- Inclua service_pricing_table APENAS se o lead pediu explicitamente preços, valores, "
        "tabela, pacotes, condições ou informações diretas sobre o serviço "
        "(ex.: 'quanto custa?', 'quais os pacotes?', 'me manda a tabela').\n"
        "- NÃO envie service_pricing_table no primeiro turno pós-qualificação se o lead não pediu — "
        "apresente em texto via o bloco COMERCIAL do prompt, não por anexo.\n"
        "- NÃO envie nenhuma mídia quando o lead só cumprimentou, perguntou horário/dia, "
        "endereço/localização, formas de pagamento (texto), ou pediu contato humano.\n"
        "- Inclua payment_policy APENAS se o lead perguntou sobre pagamento/forma de pagar.\n"
        "- Inclua commercial_objections APENAS se o lead levantou objeção explícita "
        "(preço alto, já tem fornecedor, desconfiança, etc.).\n"
        "- Inclua service_differentials / active_promotion / guarantee_policy / service_faq / "
        "product_details / pitch_script / social_proof APENAS quando o lead fizer pergunta "
        "diretamente coberta pela categoria.\n"
        "- Para categorias custom (não listadas acima): mesma regra — só se o conteúdo for diretamente "
        "relevante ao que o lead pediu no turno atual.\n"
        "- Se media_already_sent=true e o lead NÃO está repetindo o pedido do conteúdo, mantenha [].\n"
    ) if _media_catalog_lines else ""

    # "Reconhecimento de interesse de agendamento" — migrado de texto hardcoded para um
    # bloco editável/removível do Fluxo de Venda (booking_signal_opener), só para o grupo
    # agenda (agent_1/SDR e agent_3/Híbrido — os únicos com fases de agendamento no
    # pipeline). Para direto (Closer), a instrução nunca é injectada — "perguntar
    # disponibilidade" contradiz o objectivo do variant sales (CONFIRMAR/ENVIAR LINK); ver
    # docs/implementations/fix-instrucao-agendamento-closer.md. Para consultivo,
    # mantém-se o texto hardcoded (fora de escopo — ver
    # docs/plans/fluxo-vendas-melhorias-futuras.md, item M1).
    _booking_signal_block = (
        "- RECONHECIMENTO DE INTERESSE DE AGENDAMENTO: Se o lead já escolheu um serviço específico ou perguntou\n"
        "  sobre horários/disponibilidade ('que horas', 'que dia', 'tem horário'), sinalize:\n"
        "  did_complete_phase=true, recommended_next_category='pre-agendamento'. Em message_text: reconheça\n"
        "  o interesse e pergunte sobre dia/horário preferencial de forma direta e natural.\n"
        "  Não envie warming script neste caso — o lead já está pronto para marcar.\n"
    )
    if agent_mode_normalized == "agenda":
        _sales_flow_bs = ai_profile.get("sales_flow")
        _p2_phase_bs = None
        if isinstance(_sales_flow_bs, dict) and _sales_flow_bs.get("enabled"):
            _p2_phase_bs = next(
                (p for p in (_sales_flow_bs.get("phases") or []) if isinstance(p, dict) and p.get("id") == "p2"),
                None,
            )
        if _p2_phase_bs is not None and (_p2_phase_bs.get("blocks") or []):
            # Fase p2 configurada pelo utilizador — usar só o que ele definiu, nunca o
            # fallback hardcoded (se removeu o bloco, é deliberado).
            _opener_bs = next(
                (
                    b for b in (_p2_phase_bs.get("blocks") or [])
                    if isinstance(b, dict) and b.get("booking_signal_opener")
                ),
                None,
            )
            if _opener_bs:
                _content_bs = str(_opener_bs.get("content") or "").strip()
                _booking_signal_block = f"- RECONHECIMENTO DE INTERESSE DE AGENDAMENTO: {_content_bs}\n" if _content_bs else ""
            else:
                _booking_signal_block = ""
    elif agent_mode_normalized == "direto":
        # Closer: nunca "pergunta disponibilidade" — sem bloco editável equivalente em p2
        # (decisão de escopo: instruções de fechamento do Closer vivem em p5, não aqui).
        _booking_signal_block = ""

    _apres_prompt = (
        _greeting_apres_header
        + _apres_first_contact_opener
        + _passive_apres_header
        + _build_daughter_identity_block(context, "apresentation")
        + _build_agent_role_block(agent_mode_normalized, "apresentation", ai_profile)
        + "\n"
        + f"PAPEL: Conduzir a fase de apresentação — agendamento (scheduler) ou oferta+fechamento (sales).\n"
        f"ESCOPO: Variant {presentation_variant}. Gera a mensagem de apresentação e preenche signals_structured.{_media_intro_note_apres}\n"
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
        '  "media_keys_to_send": ["..."],\n'
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
        "  * Para datas relativas (amanhã, depois de amanhã, etc.) ou nomes de dia da semana (sábado, "
        "quinta-feira, etc.), procure a linha correspondente na tabela_de_dias abaixo e use a data dessa linha — "
        "NUNCA calcule a data ou o dia da semana por conta própria, esse cálculo não é confiável.\n"
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
        f"{_booking_signal_block}"
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
        + _media_selection_block
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
        f"- media_already_sent: {bool(_apres_media_already_sent)}\n"
        f"- extracted_fields: {json.dumps(mode_contract.get('extracted_fields') or {}, ensure_ascii=False)}\n"
        "- tabela_de_dias (hoje + próximos 14 dias; use para resolver QUALQUER data relativa ou nome de dia "
        f"da semana, SEM calcular por conta própria):\n{dates_table}\n"
        f"- inbound_message_text: {message_text}\n"
        + _build_custom_instructions_block(ai_profile)
        + _build_business_info_block(context)
        + _build_training_examples_block(context, "apresentation")
    )
    _apres_prompt += _build_sales_flow_block(_evaluate_sales_flow(context, "apresentation", mother_decision.signals))
    _apres_prompt += _build_sales_flow_phases_block(_evaluate_sales_flow_phases(context, "apresentation", message_text, detected_intents=mother_decision.detected_intents, is_phase_entry=is_phase_entry, branch_selections=mother_decision.branch_selections))
    return _inject_generated_parts(_apres_prompt, context, "apresentation")



def _build_child_prompt_follow_up(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
    is_phase_entry: bool = True,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []
    followup_ctx = metadata.get("followup_context") if isinstance(metadata.get("followup_context"), dict) else {}

    lead_summary = {
        "id": lead.get("id"),
        "name": _resolve_lead_name(lead),
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
        # Fase 6 — instrução por followup_goal configurada pelo operador
        _active_goal = str(followup_summary.get("followup_goal") or "").strip().lower()
        _goal_instrs = ai_profile.get("followup_goal_instructions") or {}
        _goal_custom = ((_goal_instrs.get(_active_goal) or "") if isinstance(_goal_instrs, dict) else "").strip()
        _goal_rule = (
            f"- Instrução para goal '{_active_goal}' (personalização do operador): {_goal_custom}\n"
            if _goal_custom else ""
        )
        variant_rule = (
            "- ABERTURA OBRIGATÓRIA: começa sempre com uma saudação breve e calorosa, contextual à conversa anterior "
            "(ex: 'Oi [nome]!' ou referência ao que foi discutido). NUNCA abre directamente com pitch ou proposta — "
            "a saudação vem PRIMEIRO, numa frase curta separada.\n"
            "- Variante sdr_scheduler: follow-up consultivo pós-reunião; "
            "reforçar valor, síntese do contexto e próximo passo comercial.\n"
            + _goal_rule
        )
    elif followup_variant == "cart_recovery":
        attempts_done = int(followup_summary.get("attempts") or 0)
        next_attempt = attempts_done + 1
        # Fase 7 — instrução por tentativa configurada pelo operador (sobrescreve default)
        _cart_custom_list = ai_profile.get("cart_recovery_attempt_instructions")
        _cart_custom = ""
        if isinstance(_cart_custom_list, list) and len(_cart_custom_list) >= next_attempt:
            _cart_custom = (_cart_custom_list[next_attempt - 1] or "").strip()
        if _cart_custom:
            attempt_instruction = _cart_custom
        elif next_attempt <= 1:
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
        cart_opening = (
            "- ABERTURA OBRIGATÓRIA: começa com uma saudação breve e amigável antes do conteúdo "
            "(ex: 'Oi [nome]! Passando para dar um retorno'). NUNCA abre directamente com pitch.\n"
            if next_attempt <= 1 else
            "- Tom directo sem saudação extensa — a mensagem pode abrir directamente no contexto.\n"
        )
        variant_rule = (
            f"{cart_opening}"
            "- Variante cart_recovery (carrinho abandonado, Agent 2): "
            "recuperar pagamento pendente após link enviado. Mensagens curtas (máx 280 chars).\n"
            f"- Instrução para tentativa {next_attempt}/3: {attempt_instruction}\n"
        )
    elif followup_variant == "hybrid_scheduler":
        outcome = str(followup_summary.get("outcome") or "").strip().lower()
        # Fase 8 — instrução por outcome configurada pelo operador (sobrescreve default)
        _outcome_instrs = ai_profile.get("followup_outcome_instructions") or {}
        _outcome_custom = ((_outcome_instrs.get(outcome) or "") if isinstance(_outcome_instrs, dict) else "").strip()
        if _outcome_custom:
            outcome_instruction = _outcome_custom
        elif outcome == "interested_not_closed":
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
            "- ABERTURA OBRIGATÓRIA: começa sempre com uma saudação pessoal e calorosa, como assistente "
            "do próprio profissional (ex: 'Oi [nome]! Tudo bem?'). A saudação vem PRIMEIRO, "
            "numa frase curta separada, antes de qualquer conteúdo sobre a sessão.\n"
            "- Variante hybrid_scheduler (coaches/terapeutas/consultores solo): "
            "tom pessoal e próximo, como assistente do próprio profissional — nunca SDR agressivo.\n"
            f"- Regra por outcome ({outcome or 'indefinido'}): {outcome_instruction}\n"
        )
    elif followup_variant == "client_checkin":
        variant_rule = (
            "- ABERTURA OBRIGATÓRIA: começa com uma saudação calorosa de quem já é cliente "
            "(ex: 'Oi [nome]! Tudo bem? Faz um tempo que não nos falamos.'). A saudação vem "
            "PRIMEIRO, numa frase curta separada.\n"
            "- Variante client_checkin (cliente já convertido, em client-list): este é um "
            "check-in de relacionamento pós-venda, NÃO uma tentativa de venda nova. "
            "Objetivo único: perguntar como está, e se quer agendar a próxima sessão/compra.\n"
            "- Tom sem pressão: agradeça por ser cliente, demonstre cuidado genuíno. "
            "Nunca use urgência, desconto ou escassez artificial.\n"
            "- Se o cliente topar agendar, proponha 2-3 horários directamente na mensagem "
            "(sem mudar de categoria — a confirmação final fica para o operador/agenda); "
            "se recusar ou ficar em silêncio, apenas registre e encerre educadamente.\n"
            "- NUNCA reabra qualificação antiga nem trate como lead novo.\n"
        )

    # Instrução específica do operador para esta variante (personalização de negócio)
    _followup_variant_instr_key = {
        "sdr_scheduler":    "followup_sdr_instructions",
        "cart_recovery":    "followup_recovery_instructions",
        "hybrid_scheduler": "followup_postsession_instructions",
        "client_checkin":   "followup_checkin_instructions",
    }.get(followup_variant)
    _variant_operator_block = ""
    if _followup_variant_instr_key:
        _instr = (ai_profile.get(_followup_variant_instr_key) or "").strip()
        if _instr:
            _variant_operator_block = (
                "INSTRUÇÕES DO OPERADOR PARA ESTE FOLLOW-UP"
                " (personalização do negócio — respeitar acima das regras genéricas):\n"
                f"{_instr}\n"
            )

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    presentation_variant, presentation_variant_source = _resolve_presentation_variant(context, agent_mode_normalized)
    hybrid_flow_style = _resolve_hybrid_flow_style(context)
    is_followup_tick = _is_followup_tick_context(context)

    # Tarefa 1.3 — knowledge_items com directivas de uso
    knowledge_items = context.get("knowledge_items") or {}
    _km_categories_fu = set((context.get("knowledge_media") or {}).keys())
    _followup_knowledge_parts: list[str] = []
    _narrative_dedup_fu = _evaluate_narrative_knowledge_dedup(context, "follow-up", knowledge_items)
    _social_proof_ki = _narrative_dedup_fu["content"].get("social_proof") or ""
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
        if "service_faq" in _km_categories_fu:
            _followup_knowledge_parts.append(
                "FAQ DO SERVIÇO: Informação completa disponível em arquivo de mídia (enviado automaticamente).\n"
                "INSTRUÇÃO CRÍTICA: Escreva APENAS uma frase curta de introdução "
                "(ex.: 'Aqui estão os valores:', 'Veja os detalhes abaixo:'). "
                "NÃO liste preços, serviços nem detalhes — a mídia tem prioridade absoluta sobre o texto.\n"
            )
        else:
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

    # Greeting awareness — quando o lead em follow-up abre com uma saudação, o bot responde
    # ao cumprimento antes de continuar o objetivo do follow-up. Sem alterar roteamento.
    _mother_hint_fu = (mother_decision.next_action_hint or "").strip().lower()
    _is_greeting_fu = _mother_hint_fu == "greet"
    _greeting_fu_header = (
        "ATENÇÃO — SAUDAÇÃO DO LEAD: O lead enviou uma saudação.\n"
        "INSTRUÇÃO OBRIGATÓRIA: Começa com um cumprimento natural e breve antes de continuar o follow-up.\n"
        "DEPOIS, de forma fluida na MESMA mensagem, executa o objetivo do estágio de follow-up.\n\n"
        if _is_greeting_fu
        else ""
    )

    _followup_prompt = (
        _greeting_fu_header
        + _build_daughter_identity_block(context, "follow-up")
        + f"Você é a FILHA FOLLOW-UP de um CRM de vendas WhatsApp.\n"
        + _build_agent_role_block(agent_mode_normalized, "follow-up", ai_profile)
        + "\n"
        + f"PAPEL: Re-engajar o lead pós-apresentação. Variante: {followup_variant or 'padrão'}.\n"
        f"ESCOPO: Nutrir, tratar objeções, reagendar. Nunca reabrir campos de qualificação antigos em ticks automáticos.\n"
        f"TOM: {ai_summary.get('tone_of_voice') or 'profissional'} — empático e orientado a ação. Máx {playbook_summary.get('max_chars') or 'N/D'} caracteres.\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary.get('template_key')}. is_followup_tick: {is_followup_tick}.\n"
        "RECUSAS: Nunca invente informação. Nunca use urgência artificial sem urgency_offer. Nunca reabra qualificação em follow-up tick.\n"
        + tone_block_followup
        + _build_followup_tone_extensions()
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
        f"{_variant_operator_block}"
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
        + _build_training_examples_block(context, "followup")
        + _build_custom_instructions_block(ai_profile)
        + _build_business_info_block(context)
    )
    _followup_prompt += _build_sales_flow_block(_evaluate_sales_flow(context, "follow-up", mother_decision.signals))
    _followup_prompt += _build_sales_flow_phases_block(_evaluate_sales_flow_phases(context, "followup", message_text, detected_intents=mother_decision.detected_intents, is_phase_entry=is_phase_entry, branch_selections=mother_decision.branch_selections))
    return _inject_generated_parts(_followup_prompt, context, "followup")


def _build_child_prompt_closing(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
    is_phase_entry: bool = True,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    metadata = context.get("metadata") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _resolve_lead_name(lead),
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

    # Greeting awareness — quando o lead retoma uma conversa com saudação em estágio de closing,
    # o bot responde ao cumprimento antes de continuar o fechamento. Sem alterar roteamento.
    _mother_hint_closing = (mother_decision.next_action_hint or "").strip().lower()
    _is_greeting_closing = _mother_hint_closing == "greet"
    _greeting_closing_header = (
        "ATENÇÃO — SAUDAÇÃO DO LEAD: O lead enviou uma saudação.\n"
        "INSTRUÇÃO OBRIGATÓRIA: Começa com um cumprimento natural e breve antes de continuar o fechamento.\n"
        "DEPOIS, de forma fluida na MESMA mensagem, executa o objetivo do estágio de closing.\n\n"
        if _is_greeting_closing
        else ""
    )

    _closing_prompt = (
        _greeting_closing_header
        + _build_daughter_identity_block(context, "closing")
        + f"Você é a FILHA CLOSING de um CRM de vendas WhatsApp.\n"
        + _build_agent_role_block(agent_mode_normalized, "closing", ai_profile)
        + "\n"
        + f"PAPEL: Finalizar o fechamento conforme o modo do agente.\n"
        f"ESCOPO: Modo {agent_mode_normalized}. Consultivo: handoff para humano. Agenda: confirmar horário+pagamento. Direto: conduzir pagamento.\n"
        f"TOM: {ai_summary.get('tone_of_voice') or 'profissional'} — confiante e claro. Máx {playbook_summary.get('max_chars') or 'N/D'} caracteres.\n"
        f"FRAMEWORK: Template {playbook_summary.get('template_key')}. Campos verificados: {json.dumps(mode_contract['required_fields'], ensure_ascii=False)}. Missing: {json.dumps(mode_contract['missing_fields'], ensure_ascii=False)}.\n"
        "RECUSAS: Nunca feche sozinho em modo consultivo (handoff obrigatório). Nunca emita outcome/kanban_highlight fora da categoria closing.\n"
        + tone_block_closing
        + _build_followup_tone_extensions()
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
        + _build_training_examples_block(context, "closing")
        + _build_custom_instructions_block(ai_profile)
        + _build_business_info_block(context)
    )
    # _inject_generated_parts não é chamado aqui para evitar duplicação do tone_rules
    # (já injectado via _build_tone_block). training_examples e custom_instructions são
    # adicionados directamente ao prompt.
    _closing_prompt += _build_sales_flow_phases_block(_evaluate_sales_flow_phases(context, "closing", message_text, detected_intents=mother_decision.detected_intents, is_phase_entry=is_phase_entry, branch_selections=mother_decision.branch_selections))
    return _closing_prompt

def _build_child_prompt_pre_agendamento(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    history = context.get("history") or []

    lead_name = _resolve_lead_name(lead) or ""
    lead_summary = {
        "id": lead.get("id"),
        "name": lead_name,
        "category": lead.get("category"),
    }
    ai_summary = {
        "name": ai_profile.get("name"),
        "brand_name": ai_profile.get("brand_name"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "agent_mode": ai_profile.get("agent_mode"),
        "custom_instructions": ai_profile.get("custom_instructions"),
    }
    playbook_summary = {
        "template_key": playbook.get("template_key") or playbook.get("name"),
        "max_chars": playbook.get("max_chars"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    dates_table = _calendar_lookup_table_pt()

    # Detecta se é o trigger de check-in agendado (mensagem gerada pelo job)
    is_checkin_trigger = message_text.strip() == "preagendamento_checkin_trigger"

    if is_checkin_trigger:
        greeting_name = f" {lead_name.split()[0]}" if lead_name else ""
        _pre_prompt = (
            "Você é o assistente de um CRM de WhatsApp.\n\n"
            "TAREFA: Gerar a mensagem de check-in de confirmação de sessão combinada anteriormente.\n\n"
            "REGRAS:\n"
            "- Seja breve e cordial (1-2 frases).\n"
            "- Relembre o combinado e pergunte se o lead confirma a sessão de amanhã.\n"
            "- NÃO mencione preços, não faça pitch de venda.\n"
            "- NÃO recomende transição de categoria (recommended_next_category deve ser null).\n"
            "- NÃO preencha signals_structured.\n\n"
            f"Exemplo de tom: 'Oi{greeting_name}! 👋 Como combinamos, estou passando para confirmar "
            "a sessão de amanhã. Você confirma?'\n\n"
            + _build_tone_block(ai_profile, playbook)
            + "\nRetorne SOMENTE JSON válido no schema ChildResult:\n"
            "{\n"
            '  "message_text": "mensagem de confirmação",\n'
            '  "did_complete_phase": false,\n'
            '  "recommended_next_category": null,\n'
            '  "outcome": null,\n'
            '  "kanban_highlight": null,\n'
            '  "signals": [],\n'
            '  "signals_structured": null,\n'
            '  "confidence": 0.9\n'
            "}\n\n"
            f"Contexto:\n"
            f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
            f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
            f"- history: {history_text}\n"
        )
        return _pre_prompt

    _pre_prompt = (
        _build_daughter_identity_block(context, "pre-agendamento")
        + "Você é o assistente de um CRM de WhatsApp na fase de PRÉ-AGENDAMENTO.\n\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary['template_key']}.\n\n"
        "SITUAÇÃO: O lead demonstrou interesse tentativo em marcar uma sessão, mas SEM data confirmada.\n"
        "Ex.: 'quero ir sim, vou tentar semana que vem', 'vou ver pra próxima semana'.\n\n"
        "ATENÇÃO — VERIFICAR ISTO ANTES DE QUALQUER OUTRA REGRA DESTA FASE:\n"
        "Se a mensagem do lead já contém um dia E uma hora específicos e objetivos (ex.: 'amanhã\n"
        "às 14h', 'sexta de manhã às 9h'), esta fase de pré-agendamento NÃO se aplica — não\n"
        "pergunte mais nada, não peça permissão de check-in, NÃO siga o FLUXO DE CONVERSA abaixo.\n"
        "Responda confirmando que vai verificar esse horário (1 frase) e devolva:\n"
        "recommended_next_category='agendamento', did_complete_phase=true.\n"
        "Só continue com o resto desta fase quando o lead NÃO tiver dado dia+hora específicos.\n\n"
        "OBJETIVO (quando dia+hora específicos NÃO foram dados): Capturar um dia estimado e\n"
        "solicitar permissão para enviar uma mensagem de check-in um dia antes da sessão para\n"
        "confirmar o compromisso.\n\n"
        "FLUXO DE CONVERSA (siga esta progressão — só quando o caso de dia+hora específicos acima\n"
        "não se aplicar):\n"
        "1. Se ainda NÃO souber o dia estimado do lead:\n"
        "   → Responda acolhedoramente e pergunte: 'Que dia funcionaria melhor pra você?'\n"
        "2. Se souber o dia estimado MAS ainda não pediu permissão para o check-in:\n"
        "   → Confirme o dia e peça permissão: 'Posso te mandar uma mensagem [dia anterior] de manhã\n"
        "     para confirmar a sessão?'\n"
        "3. Se o lead JÁ confirmou o dia E confirmou permissão para o check-in:\n"
        "   → Responda positivamente e sinalize o check-in no campo signals_structured:\n"
        "     Calcule checkin_at_iso = data do dia ANTERIOR à sessão às 09:00 (procure a sessão na "
        "tabela_de_dias abaixo, NUNCA calcule a data por conta própria)\n"
        "     Emita: signals_structured = {\"checkin_at_iso\": \"YYYY-MM-DDTHH:MM:SS\"}\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "- Máximo 2-3 frases por resposta.\n"
        "- NÃO repita preços nem faça pitch de venda.\n"
        "- checkin_at_iso SOMENTE quando lead confirmar permissão E um dia estiver claro.\n"
        "- Para resolver dias estimados ditos pelo lead (ex.: 'sábado', 'sexta que vem'), procure a linha "
        "correspondente na tabela_de_dias abaixo e use a data dessa linha — NUNCA calcule a data ou o dia da "
        "semana por conta própria.\n"
        "- Se lead disser 'não' ao check-in → apenas confirme o interesse e encerre educadamente.\n\n"
        + _build_tone_block(ai_profile, playbook)
        + _build_agent_role_block(agent_mode_normalized, "pre-agendamento", ai_profile)
        + "\nRetorne SOMENTE JSON válido no schema ChildResult:\n"
        "{\n"
        '  "message_text": "resposta ao lead",\n'
        '  "did_complete_phase": false|true,\n'
        '  "recommended_next_category": "agendamento"|null,\n'
        '  "outcome": null,\n'
        '  "kanban_highlight": null,\n'
        '  "signals": [],\n'
        '  "signals_structured": {"checkin_at_iso": "YYYY-MM-DDTHH:MM:SS"} | null,\n'
        '  "confidence": 0.0\n'
        "}\n\n"
        f"Contexto:\n"
        "- tabela_de_dias (hoje + próximos 14 dias; use para resolver QUALQUER data relativa ou nome de dia "
        f"da semana, SEM calcular por conta própria):\n{dates_table}\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- inbound_message_text: {message_text}\n"
        + _build_custom_instructions_block(ai_profile)
        + _build_business_info_block(context)
    )
    return _pre_prompt


def _format_busy_slots_block(busy_slots: Optional[List[Dict[str, Any]]], tz_name: Optional[str]) -> str:
    """Formata calendar_busy_slots (UTC) em texto humano, na timezone do perfil.

    Dados reais (tabela appointments) — usados para a IA não inventar
    disponibilidade. Em caso de erro de parsing de um item, ele é ignorado
    silenciosamente (não deve quebrar o prompt por um dado malformado).
    """
    if not busy_slots:
        return ""
    try:
        tz = ZoneInfo(str(tz_name)) if tz_name else _dt_timezone.utc
    except Exception:
        tz = _dt_timezone.utc

    parsed: list[tuple[datetime, str]] = []
    for slot in busy_slots:
        try:
            start_raw = str(slot.get("start_at") or "")
            end_raw = str(slot.get("end_at") or "")
            start_dt = datetime.fromisoformat(start_raw)
            end_dt = datetime.fromisoformat(end_raw)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=_dt_timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=_dt_timezone.utc)
            start_local = start_dt.astimezone(tz)
            end_local = end_dt.astimezone(tz)
            line = f"- {start_local.strftime('%d/%m %H:%M')} até {end_local.strftime('%H:%M')}"
            parsed.append((start_local, line))
        except (ValueError, TypeError):
            continue

    if not parsed:
        return ""
    parsed.sort(key=lambda item: item[0])
    return "\n".join(line for _, line in parsed)


def _build_child_prompt_agendamento(
    context: Dict[str, Any],
    message_text: str,
    mother_decision: MotherDecision,
) -> str:
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    playbook = context.get("playbook") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _resolve_lead_name(lead),
        "category": lead.get("category"),
    }
    availability_schedule = str(ai_profile.get("availability_schedule") or "").strip()
    ai_summary = {
        "name": ai_profile.get("name"),
        "brand_name": ai_profile.get("brand_name"),
        "tone_of_voice": ai_profile.get("tone_of_voice"),
        "niche": ai_profile.get("niche"),
        "agent_mode": ai_profile.get("agent_mode"),
        "timezone": ai_profile.get("timezone"),
        "availability_schedule": availability_schedule or None,
        "custom_instructions": ai_profile.get("custom_instructions"),
    }
    playbook_summary = {
        "template_key": playbook.get("template_key") or playbook.get("name"),
        "max_chars": playbook.get("max_chars"),
    }

    history_text = _format_history(history)
    mode_contract = _build_mode_contract_context(context, mother_decision)
    agent_mode_normalized = mode_contract["agent_mode_normalized"]
    dates_table = _calendar_lookup_table_pt()

    _busy_lines = _format_busy_slots_block(context.get("calendar_busy_slots"), ai_profile.get("timezone"))
    _busy_block = (
        f"HORÁRIOS JÁ OCUPADOS (compromissos reais já marcados — NÃO proponha nem confirme "
        f"horário que sobreponha estes intervalos):\n{_busy_lines}\n\n"
        if _busy_lines
        else "HORÁRIOS JÁ OCUPADOS: nenhum compromisso encontrado — a agenda está livre no "
        "período consultado.\n\n"
    )

    scheduling_offer_style = str(ai_profile.get("scheduling_offer_style") or "offer_alternatives").strip().lower()

    _avail_block = ""
    if availability_schedule:
        if scheduling_offer_style == "confirm_exact":
            _offer_instruction = (
                "REGRA CRÍTICA — CONFIRMAÇÃO DIRETA (obrigatória, máxima prioridade nesta fase):\n"
                "Antes de responder, verifique o horário exacto pedido pelo lead contra HORÁRIOS JÁ "
                "OCUPADOS acima e contra a disponibilidade. NÃO INVENTE conflito que não está "
                "listado — se o horário pedido não aparece em HORÁRIOS JÁ OCUPADOS e está dentro da "
                "disponibilidade, ELE ESTÁ LIVRE, mesmo que pareça um horário popular ou que você "
                "tenha dúvida.\n"
                "- Horário livre → confirme-o directamente nesta resposta. Não pergunte se quer "
                "outro horário, não ofereça alternativas, não diga que vai verificar.\n"
                "- Horário ocupado (aparece em HORÁRIOS JÁ OCUPADOS) ou fora da disponibilidade → "
                "só então proponha 2-3 alternativas.\n"
                "Exemplo (horário livre, sem nada em HORÁRIOS JÁ OCUPADOS para esse dia/hora): lead "
                "pede 'amanhã às 14h' → responda algo como 'Perfeito, fica confirmado amanhã às 14h.' "
                "— NUNCA 'não temos disponibilidade' ou 'já está ocupado' quando o horário não consta "
                "na lista de ocupados.\n\n"
            )
        else:
            _offer_instruction = (
                "Com base na disponibilidade acima, proponha 2-3 horários concretos que se encaixem "
                "no que o lead solicitou. Use linguagem natural e fluida.\n\n"
            )
        _avail_block = (
            f"DISPONIBILIDADE DO PROFISSIONAL:\n{availability_schedule}\n\n"
            + _offer_instruction
        )
    else:
        _avail_block = (
            "DISPONIBILIDADE: não configurada.\n"
            "Pergunte ao lead qual horário prefere e confirme que vai verificar a agenda.\n\n"
        )

    _pricing_table = str((context.get("knowledge_items") or {}).get("service_pricing_table") or "").strip()
    _services_block = ""
    if _pricing_table:
        _services_block = (
            f"SERVIÇOS E DURAÇÕES DISPONÍVEIS (cadastrado pelo profissional — pode haver mais de uma tabela, "
            f"cada uma com um título próprio, e cada linha pode ter uma duração diferente):\n{_pricing_table}\n\n"
            "INSTRUÇÃO: se houver mais de uma tabela (títulos diferentes, ex. por profissional ou "
            "especialidade), identifique primeiro a qual tabela o lead se refere; depois, identifique a que "
            "serviço/duração ele se refere dentro dela (pelo que ele pediu ou pelo histórico da conversa) e "
            "preencha signals_structured.meeting_duration_minutes com a duração (em minutos) dessa linha ao "
            "confirmar o horário. Se houver mais de uma opção (tabela ou linha) e não for possível saber qual "
            "o lead quer, PERGUNTE antes de confirmar — nunca assuma uma duração quando há ambiguidade real.\n\n"
        )

    _sched_prompt = (
        _build_daughter_identity_block(context, "agendamento")
        + "Você é o assistente de um CRM de WhatsApp na fase de AGENDAMENTO.\n\n"
        f"FRAMEWORK: Modo {agent_mode_normalized}. Template {playbook_summary['template_key']}.\n\n"
        "OBJETIVO: Confirmar data e horário para o serviço solicitado pelo lead.\n\n"
        + _busy_block
        + _avail_block
        + _services_block
        + "REGRAS OBRIGATÓRIAS:\n"
        "- Foco total em confirmar o horário. NÃO reintroduza temas de venda ou preços.\n"
        "- Seja conciso e direto: máximo 2-3 frases.\n"
        "- Ao confirmar o agendamento, recomende a transição para 'client-list' ou 'follow-up' "
        "via recommended_next_category.\n"
        "- Se o lead quiser reagendar ou cancelar, lide com isso naturalmente.\n\n"
        + _build_tone_block(ai_profile, playbook)
        + _build_agent_role_block(agent_mode_normalized, "agendamento", ai_profile)
        + "\nRetorne SOMENTE JSON válido no schema ChildResult:\n"
        "{\n"
        '  "message_text": "proposta de horário ou confirmação",\n'
        '  "did_complete_phase": false|true,\n'
        '  "recommended_next_category": "client-list"|"follow-up"|null,\n'
        '  "outcome": null,\n'
        '  "kanban_highlight": null,\n'
        '  "signals": [],\n'
        '  "signals_structured": {"meeting_proposed": false, "meeting_datetime_candidate": null, "meeting_duration_minutes": null} (opcional),\n'
        '  "confidence": 0.0\n'
        "}\n\n"
        "REGRAS DE SINALIZAÇÃO ESTRUTURADA (obrigatório):\n"
        "- SEMPRE preencha signals_structured.meeting_proposed (bool) e meeting_datetime_candidate (ISO ou null).\n"
        "  * Se houver proposta/confirmação com horário definido: meeting_proposed=true e meeting_datetime_candidate preenchido.\n"
        "  * Se estiver pedindo disponibilidade sem horário definido: meeting_proposed=true e meeting_datetime_candidate=null.\n"
        "  * Combine informação de turnos anteriores do history (ex.: dia mencionado antes + hora mencionada agora).\n"
        "  * Preferência: ISO naive no horário local de ai_profile.timezone (ex: 2026-03-05T17:00:00); também aceito offset/Z.\n"
        "  * Nunca assumir timezone fixa; sempre respeitar ai_profile.timezone.\n"
        "  * Para datas relativas (amanhã, depois de amanhã, etc.) ou nomes de dia da semana (sábado, "
        "quinta-feira, etc.), procure a linha correspondente na tabela_de_dias abaixo e use a data dessa linha — "
        "NUNCA calcule a data ou o dia da semana por conta própria, esse cálculo não é confiável.\n"
        "  * meeting_duration_minutes: preencha (inteiro, em minutos) só quando houver SERVIÇOS E DURAÇÕES "
        "DISPONÍVEIS configurado acima e você tiver identificado claramente a qual linha o lead se refere; "
        "deixe null se não houver essa tabela configurada ou se ainda não confirmou qual serviço o lead quer.\n\n"
        f"Contexto:\n"
        "- tabela_de_dias (hoje + próximos 14 dias; use para resolver QUALQUER data relativa ou nome de dia "
        f"da semana, SEM calcular por conta própria):\n{dates_table}\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- ai_profile: {json.dumps(ai_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- inbound_message_text: {message_text}\n"
        + _build_custom_instructions_block(ai_profile)
        + _build_business_info_block(context)
    )
    return _sched_prompt


def _build_child_prompt_meeting_management(context: Dict[str, Any], message_text: str) -> str:
    """Prompt dedicado para mensagens de um lead cujo bot foi desativado por meeting_scheduled.

    Não passa pela Mãe — o lead já tem uma reunião/sessão confirmada e o bot está
    silenciado para vendas; este prompt só decide se a mensagem pede cancelar/reagendar
    esse compromisso, ou se deve gerar uma resposta mínima sem reabrir negociação.
    """
    lead = context.get("lead") or {}
    ai_profile = context.get("ai_profile") or {}
    history = context.get("history") or []

    lead_summary = {
        "id": lead.get("id"),
        "name": _resolve_lead_name(lead),
    }
    history_text = _format_history(history)
    dates_table = _calendar_lookup_table_pt()

    busy_slots = context.get("calendar_busy_slots") or []
    same_lead_slots = [slot for slot in busy_slots if slot.get("lead_id") == lead.get("id")]
    _busy_lines = _format_busy_slots_block(same_lead_slots, ai_profile.get("timezone"))
    _meeting_block = (
        f"REUNIÃO/SESSÃO JÁ CONFIRMADA (este é o compromisso que o lead pode querer "
        f"cancelar ou reagendar):\n{_busy_lines}\n\n"
        if _busy_lines
        else "REUNIÃO/SESSÃO JÁ CONFIRMADA: não foi possível localizar o horário exato.\n\n"
    )

    return (
        _build_daughter_identity_block(context, "agendamento")
        + "\n\nCONTEXTO: este lead já tem uma reunião/sessão CONFIRMADA. O bot está em modo "
        "silencioso (não deve vender nem reabrir negociação) — só deve agir quando a mensagem "
        "for sobre cancelar ou reagendar esse compromisso.\n\n"
        + _meeting_block
        + "REGRAS OBRIGATÓRIAS:\n"
        "- Se a mensagem pedir CANCELAMENTO do compromisso: confirme o cancelamento de forma "
        "natural e empática, e preencha signals_structured.meeting_cancel_requested=true. "
        "NÃO diga que vai verificar ou confirmar depois — a ação é aplicada já neste turno.\n"
        "- Se a mensagem pedir REAGENDAMENTO para um NOVO DIA e JÁ incluir dia E horário (mesmo "
        "que tentativo, ex.: 'pode ser domingo às 11h?'): CONFIRME DIRETAMENTE neste turno — "
        "preencha signals_structured.meeting_reschedule_requested=true e meeting_datetime_candidate "
        "(ISO, use tabela_de_dias para resolver datas relativas — NUNCA calcule por conta própria). "
        "PROIBIDO responder de forma hesitante ('vou verificar', 'vou confirmar', 'um momento') "
        "quando dia e horário já foram informados — isso obriga outro turno e o lead fica sem "
        "resposta real; confirme já, como nas REGRAS acima para cancelamento.\n"
        "- Se a mensagem propuser SÓ UM HORÁRIO diferente do já confirmado, SEM mencionar um novo "
        "dia (ex.: 'pode ser às 16h em vez de 14h?', 'na verdade prefiro às 16h', 'dá pra adiantar "
        "pras 16h?'): trate como reagendamento para o MESMO DIA da reunião já confirmada (ver bloco "
        "acima) — preencha signals_structured.meeting_reschedule_requested=true e "
        "meeting_datetime_candidate combinando a DATA da reunião já confirmada com o NOVO horário "
        "mencionado. NÃO responda como se fosse uma nova confirmação nem peça o dia de novo — o dia "
        "já é conhecido (está no bloco acima).\n"
        "- Se o lead pedir para reagendar mas NÃO disser um horário novo (ex.: só 'posso "
        "remarcar?'): pergunte qual horário prefere e deixe meeting_reschedule_requested=false "
        "até ele responder com um horário.\n"
        "- Para qualquer outra mensagem (agradecimento, pergunta solta, etc.): responda de forma "
        "mínima e cordial (1 frase), SEM propor produtos/serviços, SEM reabrir qualificação ou "
        "venda, SEM perguntas de follow-up. Não preencha nenhum dos dois sinais acima.\n"
        "- Nunca mencione internamente termos como 'bot desativado' ou 'sinal estruturado' na "
        "mensagem ao lead.\n\n"
        "Retorne SOMENTE JSON válido no schema ChildResult:\n"
        "{\n"
        '  "message_text": "resposta para o lead",\n'
        '  "did_complete_phase": false,\n'
        '  "recommended_next_category": null,\n'
        '  "outcome": null,\n'
        '  "kanban_highlight": null,\n'
        '  "signals": [],\n'
        '  "signals_structured": {"meeting_cancel_requested": false, "meeting_reschedule_requested": false, "meeting_datetime_candidate": null},\n'
        '  "confidence": 0.0\n'
        "}\n\n"
        f"Contexto:\n"
        "- tabela_de_dias (hoje + próximos 14 dias; use para resolver QUALQUER data relativa ou "
        f"nome de dia da semana, SEM calcular por conta própria):\n{dates_table}\n"
        f"- lead: {json.dumps(lead_summary, ensure_ascii=False)}\n"
        f"- history: {history_text}\n"
        f"- inbound_message_text: {message_text}\n"
        + _build_custom_instructions_block(ai_profile)
    )


def _decide_post_meeting_management(
    context: Dict[str, Any], logger: Optional[logging.Logger] = None
) -> DecisionOutput:
    """Caminho dedicado para leads com bot_disabled_reason=meeting_scheduled.

    Curto-circuita antes da Mãe (mesmo padrão de fast_path) — não toca na pipeline de
    vendas. Só decide se a mensagem pede cancelar/reagendar a reunião já confirmada;
    caso contrário, produz uma resposta mínima sem reabrir negociação. Nunca sugere
    suggested_category (não move o Kanban).
    """
    message_text = _extract_message_text(context)
    prompt = _build_child_prompt_meeting_management(context, message_text)
    ai_profile = context.get("ai_profile") or {}

    child_result: Optional[ChildResult] = None
    try:
        child_text = llm_service.generate_child_result(
            "meeting_management", prompt, ai_profile=ai_profile
        )
        child_payload = _extract_json_payload(child_text)
        child_payload = _normalize_null_strings(child_payload)
        if child_payload is not None:
            child_result = ChildResult.model_validate(child_payload)
    except Exception as exc:
        if logger:
            logger.warning(
                "event=meeting_management_llm_failure exc_type=%s exc=%s",
                type(exc).__name__,
                exc,
            )

    if child_result is None:
        return DecisionOutput(
            next_action="ignore",
            message_text="",
            questions=[],
            reason="meeting_management_llm_failure",
        )

    return DecisionOutput(
        next_action="reply",
        message_text=child_result.message_text or "",
        questions=[],
        reason="post_meeting_management",
        signals=child_result.signals,
        confidence=child_result.confidence,
        decision_trace={
            "effective_route_to": "meeting_management",
            "is_phase_entry": False,
            "meeting_scheduled": False,
            "child_signals_structured": child_result.signals_structured or {},
        },
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


def _enforce_qualification_route_when_missing(
    mother_decision: MotherDecision,
    mode_contract: Dict[str, Any],
) -> MotherDecision:
    missing_fields = list(mode_contract.get("missing_fields") or [])
    if not missing_fields:
        return mother_decision
    if mother_decision.route_to in ("qualification", "recepcao"):
        return mother_decision
    mother_decision.route_to = "qualification"
    reason = str(mother_decision.reason or "").strip()
    forced_reason = "qualification_incomplete_forced_route"
    mother_decision.reason = f"{reason}|{forced_reason}" if reason else forced_reason
    return mother_decision


def _enforce_greeting_first(
    mother_decision: MotherDecision,
    context: Dict[str, Any],
) -> MotherDecision:
    """Garante que o primeiro contato seja sempre recepcao.

    Análogo ao _enforce_qualification_route_when_missing: baseado em estado
    (histórico), não em análise de texto. Se o bot nunca respondeu (outbound_count=0),
    a saudação ainda não foi feita — força recepcao antes de qualquer outra rota.
    """
    if mother_decision.route_to == "recepcao":
        return mother_decision
    history = context.get("history") or []
    outbound_count = sum(1 for h in history if str(h.get("model") or "").lower() == "outbound")
    if outbound_count == 0:
        reason = str(mother_decision.reason or "").strip()
        mother_decision.reason = f"{reason}|greeting_first_enforced" if reason else "greeting_first_enforced"
        mother_decision.route_to = "recepcao"
    return mother_decision


def _enforce_scheduling_agent_no_closing(
    mother_decision: MotherDecision,
    context: Dict[str, Any],
) -> MotherDecision:
    """Agentes de agendamento (sdr_padrao, hybrid_scheduler) não têm etapa

    comercial de "closing" — agendam sessões/reuniões, não fecham vendas.
    Confirmação de horário é interpretada pela Mãe como sinal de fechamento
    (heurística genérica), mas aqui não existe "venda fechada". Redireciona
    para a fase de agendamento atual (se já lá) ou apresentation.
    """
    ai_profile = context.get("ai_profile") or {}
    template_key = str(ai_profile.get("template_key") or "").strip().lower()
    if template_key not in _SCHEDULING_AGENT_TEMPLATES:
        return mother_decision

    route_is_closing = _normalize_category(mother_decision.route_to) == "closing"
    perceived_is_closing = _normalize_category(mother_decision.perceived_category) == "closing"
    if not route_is_closing and not perceived_is_closing:
        return mother_decision

    lead = context.get("lead") or {}
    current_category = _normalize_category(lead.get("category"))
    fallback = current_category if current_category in {"agendamento", "pre-agendamento"} else "apresentation"

    if route_is_closing:
        mother_decision.route_to = fallback
    if perceived_is_closing:
        mother_decision.perceived_category = fallback

    reason = str(mother_decision.reason or "").strip()
    tag = f"scheduling_agent_closing_disabled:{fallback}"
    mother_decision.reason = f"{reason}|{tag}" if reason else tag
    return mother_decision


_ALLOWED_ADVANCE = {
    "recepcao": {"qualification"},
    "qualification": {"apresentation"},
    "apresentation": {"closing", "follow-up", "pre-agendamento"},
    "pre-agendamento": {"agendamento", "follow-up"},
    "agendamento": {"follow-up", "client-list"},
    "follow-up": {"closing"},
}

_STAGE_ORDER = ["qualification", "apresentation", "pre-agendamento", "agendamento", "follow-up", "closing"]
_STAGE_INDEX = {stage: index for index, stage in enumerate(_STAGE_ORDER)}

# Templates que usam as fases de pré-agendamento e agendamento
_SCHEDULING_AGENT_TEMPLATES = {"sdr_padrao", "hybrid_scheduler"}


_MAX_RECEPCAO_ENFORCED_OUTBOUND_TURNS = 1
_PRE_QUALIFICATION_CATEGORIES = {"to-prospect", "in-progress", "qualification"}


def _enforce_recepcao_sales_flow_pending(
    mother_decision: MotherDecision,
    context: Dict[str, Any],
) -> MotherDecision:
    """Impede a Mãe de avançar a categoria para além de 'recepcao' enquanto houver gatilhos
    sequenciais (fire_once) configurados na fase p0 do Fluxo de Venda que ainda não dispararam
    para este lead.

    Espelha _enforce_apresentation_sales_flow_pending/_enforce_pre_agendamento_sales_flow_pending,
    trocando para p0, com 2 diferenças estruturais (ver
    docs/implementations/sales-flow-guardrail-p0-recepcao.md):

    1) "Engajado com recepção" não pode depender de current_category == "recepcao" (esse valor
       nunca é persistido em leads.category — só existe como route_to efémero) nem de
       phases_triggered conter "p0" sozinho (exigiria um bloco phase_trigger configurado). Usa
       o sinal oposto: o lead ainda não passou de "qualification" no pipeline
       (_PRE_QUALIFICATION_CATEGORIES cobre os valores reais pré-pipeline: to-prospect,
       in-progress, categoria ausente, ou já qualification mas ainda no turno de saudação).
    2) A Filha Recepção é desenhada para um único turno ("Seu papel dura só este turno" —
       _build_child_prompt_recepcao) — ao contrário das Filhas de apresentation/pré-agendamento
       (multi-turno por design). Sem teto, este guardrail forçaria route_to="recepcao"
       indefinidamente enquanto o gatilho de p0 não disparasse, repetindo a saudação em plena
       conversa real. _MAX_RECEPCAO_ENFORCED_OUTBOUND_TURNS limita a ação a, no máximo, 1 turno
       além do forçado por _enforce_greeting_first — depois disso, falha aberto.
    """
    route = _normalize_category(mother_decision.route_to)
    if route not in _ALLOWED_ADVANCE.get("recepcao", set()):
        return mother_decision

    history = context.get("history") or []
    outbound_count = sum(1 for h in history if str(h.get("model") or "").lower() == "outbound")
    if outbound_count > _MAX_RECEPCAO_ENFORCED_OUTBOUND_TURNS:
        return mother_decision

    current_category = _normalize_category((context.get("lead") or {}).get("category"))
    engaged_with_recepcao = current_category is None or current_category in _PRE_QUALIFICATION_CATEGORIES
    if not engaged_with_recepcao:
        return mother_decision

    ai_profile = context.get("ai_profile") or {}
    pending_ids = _phase_pending_sequential_triggers(
        "p0", ai_profile, _load_triggers_fired_set(context)
    )
    if not pending_ids:
        return mother_decision

    mother_decision.route_to = "recepcao"
    reason = str(mother_decision.reason or "").strip()
    tag = f"sales_flow_recepcao_pending_forced_route:{','.join(pending_ids)}"
    mother_decision.reason = f"{reason}|{tag}" if reason else tag
    return mother_decision


def _enforce_apresentation_sales_flow_pending(
    mother_decision: MotherDecision,
    context: Dict[str, Any],
) -> MotherDecision:
    """Impede a Mãe de avançar a categoria para além de 'apresentation' enquanto houver
    gatilhos sequenciais (fire_once) configurados na fase p2 do Fluxo de Venda que ainda
    não dispararam para este lead.

    Espelha _enforce_qualification_route_when_missing: guardrail determinístico baseado
    em estado persistido (leads.triggers_fired), não em julgamento da LLM. Necessário
    porque a Mãe pode decidir pular a fase inteira num único turno (ex.: "ok" interpretado
    como sinal suficiente para route_to="pre-agendamento") — nesse caso
    _evaluate_sales_flow_phases() nunca chega a avaliar os blocos de p2, e todo o
    encadeamento sequencial da fase (incluindo orientações críticas) é ignorado. Ver
    docs/implementations/fix-fluxo-vendas-sequencial.md, Fase 2.

    "Engajado com apresentation" é checado via `leads.phases_triggered` conter "p2"
    (o phase_trigger da fase já disparou para este lead) OU `lead.category` já ser
    "apresentation" — teste ao vivo mostrou que `lead.category` pode ficar defasado
    (a Mãe gera conteúdo de apresentation via `route_to` num turno sem a categoria
    persistida acompanhar, dependendo de `perceived_category`/guardrails de estágio),
    então `phases_triggered` é o sinal mais confiável de que a fase foi de facto
    iniciada.
    """
    triggered_phases = _load_triggered_phases_set(context)
    current_category = _normalize_category((context.get("lead") or {}).get("category"))
    engaged_with_apresentation = "p2" in triggered_phases or current_category == "apresentation"
    if not engaged_with_apresentation:
        return mother_decision

    route = _normalize_category(mother_decision.route_to)
    if route not in _ALLOWED_ADVANCE.get("apresentation", set()):
        return mother_decision

    ai_profile = context.get("ai_profile") or {}
    pending_ids = _phase_pending_sequential_triggers(
        "p2", ai_profile, _load_triggers_fired_set(context)
    )
    if not pending_ids:
        return mother_decision

    mother_decision.route_to = "apresentation"
    reason = str(mother_decision.reason or "").strip()
    tag = f"sales_flow_apresentation_pending_forced_route:{','.join(pending_ids)}"
    mother_decision.reason = f"{reason}|{tag}" if reason else tag
    return mother_decision


def _enforce_pre_agendamento_sales_flow_pending(
    mother_decision: MotherDecision,
    context: Dict[str, Any],
) -> MotherDecision:
    """Impede a Mãe de avançar a categoria para além de 'pre-agendamento' enquanto houver
    gatilhos sequenciais (fire_once) configurados na fase p3a do Fluxo de Venda que ainda
    não dispararam para este lead.

    Espelha _enforce_apresentation_sales_flow_pending, trocando p2→p3a — mesma classe de bug
    que p2 tinha antes de ser corrigido: a Mãe pode decidir pular a fase inteira num único
    turno, ignorando o encadeamento sequencial configurado nela. Só relevante para o modo
    `agenda` (único que visita p3a — ver docs/architecture/sales-flow.md); nos demais modos
    `_phase_pending_sequential_triggers` nunca encontra a fase "p3a" no profile e este
    guardrail é um no-op.
    """
    triggered_phases = _load_triggered_phases_set(context)
    current_category = _normalize_category((context.get("lead") or {}).get("category"))
    engaged_with_pre_agendamento = "p3a" in triggered_phases or current_category == "pre-agendamento"
    if not engaged_with_pre_agendamento:
        return mother_decision

    route = _normalize_category(mother_decision.route_to)
    if route not in _ALLOWED_ADVANCE.get("pre-agendamento", set()):
        return mother_decision

    ai_profile = context.get("ai_profile") or {}
    pending_ids = _phase_pending_sequential_triggers(
        "p3a", ai_profile, _load_triggers_fired_set(context)
    )
    if not pending_ids:
        return mother_decision

    mother_decision.route_to = "pre-agendamento"
    reason = str(mother_decision.reason or "").strip()
    tag = f"sales_flow_pre_agendamento_pending_forced_route:{','.join(pending_ids)}"
    mother_decision.reason = f"{reason}|{tag}" if reason else tag
    return mother_decision


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
    if template_key in _SCHEDULING_AGENT_TEMPLATES and suggested_category == "closing":
        suggested_category = "apresentation"
        reason_add = "guardrail_scheduling_agent_no_closing"
        category_reason = f"{category_reason}|{reason_add}" if category_reason else reason_add

    if suggested_category in {"pre-agendamento", "agendamento"} and template_key not in _SCHEDULING_AGENT_TEMPLATES:
        suggested_category = "apresentation"
        reason_add = "guardrail_scheduling_stage_non_scheduling_agent"
        category_reason = f"{category_reason}|{reason_add}" if category_reason else reason_add

    qualification_auto_promoted = False
    anti_loop_rule1_applied = False
    effective_route_to = effective_route_override or mother_decision.route_to
    # Snapshot da fase efetivamente usada para montar o prompt da filha (route_for_child em
    # decide()), antes de qualquer guardrail abaixo poder reatribuir effective_route_to (ex.:
    # apresentation_complete_auto_advance). Necessário para o dedup de knowledge narrativo: o
    # que marcamos como "mostrado" precisa corresponder ao que foi de fato injetado no prompt
    # desta LLM, não à fase pós-guardrail.
    _prompt_phase_for_narrative_dedup = effective_route_to
    missing_fields = list(mode_contract.get("missing_fields") or [])
    filled_fields = list(mode_contract.get("filled_fields") or [])
    current_field = _select_current_field(missing_fields, filled_fields)
    p1_pending_compose = _phase_pending_sequential_triggers(
        "p1", ai_profile, _load_triggers_fired_set(context)
    )
    if (
        mother_decision.route_to == "qualification"
        and not current_field
        and not p1_pending_compose
    ):
        qualification_auto_promoted = True
        anti_loop_rule1_applied = True
        effective_route_to = "apresentation"
        suggested_category = "apresentation"
        auto_promote_reason = "qualification_complete_auto_promote:apresentation"
        category_reason = (
            f"{category_reason}|{auto_promote_reason}" if category_reason else auto_promote_reason
        )

    # Guardrail: apresentation completa → avança para próxima fase (análogo ao de qualificação).
    # A Filha já sinaliza did_complete_phase + recommended_next_category — aqui apenas homologamos.
    # Restrito a agentes com fases de agendamento para não impactar closer_agressivo.
    # Gate de gatilhos pendentes: did_complete_phase é sinal da Filha (não determinístico) e
    # pode disparar antes de _enforce_apresentation_sales_flow_pending ter a chance de agir
    # sobre route_to — sem este gate, um gatilho sequencial pendente em p2 seria contornado
    # silenciosamente (ver docs/implementations/sales-flow-fase-pendente-guardrail.md, Fase 2).
    _apres_complete_next = str(child_result.recommended_next_category or "").strip().lower()
    p2_pending_compose = _phase_pending_sequential_triggers(
        "p2", ai_profile, _load_triggers_fired_set(context)
    )
    if (
        effective_route_to == "apresentation"
        and child_result.did_complete_phase
        and _apres_complete_next in {"pre-agendamento", "agendamento", "follow-up"}
        and template_key in _SCHEDULING_AGENT_TEMPLATES
        and not p2_pending_compose
    ):
        suggested_category = _apres_complete_next
        category_reason = (
            f"{category_reason}|apresentation_complete_auto_advance:{_apres_complete_next}"
            if category_reason else f"apresentation_complete_auto_advance:{_apres_complete_next}"
        )

    # Guardrail: pré-agendamento completo (dia/hora específicos já dados) → avança para
    # agendamento. Mesmo padrão do bloco de apresentation acima — a Filha já sinaliza
    # did_complete_phase + recommended_next_category="agendamento", aqui homologamos.
    # Mesmo gate de gatilhos pendentes do bloco de apresentation acima, aplicado a p3a.
    _pre_complete_next = str(child_result.recommended_next_category or "").strip().lower()
    p3a_pending_compose = _phase_pending_sequential_triggers(
        "p3a", ai_profile, _load_triggers_fired_set(context)
    )
    if (
        effective_route_to == "pre-agendamento"
        and child_result.did_complete_phase
        and _pre_complete_next == "agendamento"
        and template_key in _SCHEDULING_AGENT_TEMPLATES
        and not p3a_pending_compose
    ):
        suggested_category = _pre_complete_next
        category_reason = (
            f"{category_reason}|pre_agendamento_complete_auto_advance:{_pre_complete_next}"
            if category_reason else f"pre_agendamento_complete_auto_advance:{_pre_complete_next}"
        )

    # Guardrail: effective_route_to já é agendamento (mesmo sem ter passado por
    # pre-agendamento nesta conversa, ex.: saudação composta com dia/hora específicos já na
    # 1ª mensagem) → persiste agendamento como categoria. Sem isto, o clamp de salto único
    # (_ALLOWED_ADVANCE) mantém a categoria em apresentation indefinidamente, e o gate
    # is_phase_entry do M3 (meeting_scheduler) nunca reconhece turnos seguintes como "já na
    # fase" — bloqueando a criação real do appointment para sempre, não só no turno de
    # entrada.
    if (
        effective_route_to == "agendamento"
        and template_key in _SCHEDULING_AGENT_TEMPLATES
    ):
        suggested_category = "agendamento"
        category_reason = (
            f"{category_reason}|effective_route_agendamento_auto_advance"
            if category_reason else "effective_route_agendamento_auto_advance"
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
    _greeting_override = (
        effective_route_to == "qualification"
        and (mother_decision.next_action_hint or "").strip().lower() == "greet"
        and bool(child_result.message_text)
    )
    # Fix P10: passive question override — fallback para quando a mãe não emitiu hint='reply'
    # mas o lead fez uma pergunta directa de serviço/produto com response_style=passive.
    # A filha de qualificação já foi instruída a responder primeiro (via _passive_header),
    # mas o engine descartaria message_text em favor de question_text. Este override preserva
    # message_text (resposta + pergunta integradas) mantendo next_action=ask_qualification para tracking.
    _p10_inbound = str((context.get("metadata") or {}).get("inbound_message_text") or "").lower()
    _p10_inbound_has_question = "?" in _p10_inbound or any(
        m in _p10_inbound for m in [
            "gostaria de saber", "como faço", "como funciona", "o que é",
            "queria entender", "pode me dizer", "me explica", "preciso entender",
        ]
    )
    _passive_question_override = (
        effective_route_to == "qualification"
        and not _passive_reply_override
        and (mother_decision.next_action_hint or "").strip().lower() not in ("reply", "greet")
        and _response_style == "passive"
        and _p10_inbound_has_question
        and bool(child_result.message_text)
    )
    if _passive_reply_override:
        next_action = "reply"
        message_text = str(child_result.message_text).strip()
        message_field_used = None
    elif _passive_question_override:
        # Usa message_text do filho (resposta + pergunta integradas) mas mantém tracking de qualificação.
        next_action = "ask_qualification"
        message_text = str(child_result.message_text).strip()
        message_field_used = str(child_result.field or "").strip() or current_field
    elif _greeting_override:
        # Greet mode: message_text contém cumprimento + pergunta; question_text contém só a pergunta.
        # Usa message_text para o output final, mantém next_action=ask_qualification
        # para que o tracking de qualificação (field, asked_questions) continue normalmente.
        next_action = "ask_qualification"
        message_text = str(child_result.message_text).strip()
        message_field_used = str(child_result.field or "").strip() or current_field
    elif next_action == "ask_qualification":
        if not current_field and not p1_pending_compose:
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
            "child_media_keys_to_send": child_result.media_keys_to_send,
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
                decision.pre_send_media = [{
                    "media_url": str(media_url).strip(),
                    "media_type": str(raw_op.get("media_type") or "image").strip(),
                }]

    # Mídia de knowledge — anexação contextual guiada pela LLM filha.
    # A filha declara em child_result.media_keys_to_send quais categorias são
    # relevantes ao turno atual. Fallback estrito: se o campo vier None/vazio,
    # NÃO anexa nada — evita o bug histórico de enviar todas as mídias sempre
    # que effective_route_to=="apresentation".
    _should_send_knowledge_media = (effective_route_to == "apresentation")
    if _should_send_knowledge_media and not decision.pre_send_media:
        knowledge_media = context.get("knowledge_media") or {}
        lead_lang = str(context.get("lead_detected_language") or "all").lower()
        selected_keys = set(child_result.media_keys_to_send or [])
        _all_km_media: list[dict] = []
        for _cat, entries in knowledge_media.items():
            if _cat not in selected_keys:
                continue
            # Compatibilidade: se for string (formato legado), converter para lista
            if isinstance(entries, str):
                entries = [{"media_url": entries, "media_type": "image", "language": "all", "send_order": 0}]
            for e in entries:
                # Quando o idioma do lead é desconhecido ("all"), inclui todas as mídias
                # independentemente do idioma configurado (pt, en, es, all).
                if lead_lang == "all" or e.get("language") in ("all", lead_lang):
                    _all_km_media.append(e)
        if _all_km_media:
            _all_km_media.sort(key=lambda e: e.get("send_order", 0))
            decision.pre_send_media = _all_km_media

    # Mídia de Fluxo de Venda (legado) — resolve action_media_category para pre_send_media
    # independente da fase (o bloco acima só cobre "apresentation").
    if not decision.pre_send_media:
        _sf_match = _evaluate_sales_flow(context, effective_route_to, mother_decision.signals)
        if _sf_match:
            _sf_media_cat = _sf_match.get("action_media_category")
            if _sf_media_cat:
                _sf_knowledge_media = context.get("knowledge_media") or {}
                _sf_lead_lang = str(context.get("lead_detected_language") or "all").lower()
                _sf_entries = _sf_knowledge_media.get(_sf_media_cat, [])
                if isinstance(_sf_entries, str):
                    _sf_entries = [{"media_url": _sf_entries, "media_type": "image", "language": "all", "send_order": 0}]
                _sf_media: list[dict] = [
                    e for e in _sf_entries
                    if _sf_lead_lang == "all" or e.get("language") in ("all", _sf_lead_lang)
                ]
                if _sf_media:
                    _sf_media.sort(key=lambda e: e.get("send_order", 0))
                    decision.pre_send_media = _sf_media

    # Fluxo de Venda (novo sistema de fases) — mídia via system_actions e system_actions sequenciais
    _effective_phase_id = _ROUTE_TO_PHASE_ID.get(effective_route_to)
    _is_phase_entry = _compute_is_phase_entry(context, effective_route_to)
    # Exposto no decision_trace para o meeting_scheduler: gate de M3 (confirmação de
    # agendamento sem garantia) — só honra meeting_scheduled=true quando o lead já estava
    # nesta fase antes desta mensagem, agnóstico de qual route_to está em jogo.
    if decision.decision_trace is None:
        decision.decision_trace = {}
    decision.decision_trace["is_phase_entry"] = _is_phase_entry
    _phases_result = _evaluate_sales_flow_phases(
        context, effective_route_to, _extract_message_text(context),
        detected_intents=mother_decision.detected_intents,
        is_phase_entry=_is_phase_entry,
        branch_selections=mother_decision.branch_selections,
    )
    if _phases_result.get("pre_send_media") and not decision.pre_send_media:
        decision.pre_send_media = _phases_result["pre_send_media"]
    if _phases_result.get("system_actions"):
        decision.system_actions = _phases_result["system_actions"]
    # Se o phase_trigger disparou, adicionar ação para marcar fase como já disparada
    if _phases_result.get("phase_trigger_fired") and _effective_phase_id:
        _sys = list(decision.system_actions or [])
        _sys.append({"type": "mark_phase_triggered", "phase_id": _effective_phase_id})
        decision.system_actions = _sys
    # Se algum trigger activo tinha suppress_llm_response=True, suprimir a resposta da LLM filha
    if _phases_result.get("suppress_llm_response"):
        decision.suppress_llm_response = True
        decision.next_action = "ignore"
        decision.message_text = ""

    # Dedup de knowledge narrativo (social_proof/pitch_script/product_details) — reavalia a
    # MESMA função pura usada no prompt builder (_build_child_prompt_apresentation /
    # _build_child_prompt_follow_up). Como ela só depende de
    # context["lead"]["knowledge_categories_shown"] e de context["knowledge_items"]
    # (inalterados durante o turno), chamar de novo aqui produz o mesmo resultado — mesmo
    # padrão já usado acima para _evaluate_sales_flow_phases (chamada 1: dentro do prompt
    # builder, só para prompt_injections; chamada 2: aqui, só para system_actions). Usa o
    # snapshot _prompt_phase_for_narrative_dedup, não effective_route_to, para não marcar
    # categorias de uma fase diferente da que foi de facto usada para montar o prompt.
    _narrative_phase_for_dedup = {
        "apresentation": "apresentation",
        "follow-up": "follow-up",
        "followup": "follow-up",
    }.get(_prompt_phase_for_narrative_dedup)
    if _narrative_phase_for_dedup:
        _narrative_dedup_compose = _evaluate_narrative_knowledge_dedup(
            context, _narrative_phase_for_dedup, context.get("knowledge_items") or {}
        )
        if _narrative_dedup_compose["new_categories"]:
            _sys = list(decision.system_actions or [])
            _sys.append({
                "type": "mark_knowledge_shown",
                "categories": _narrative_dedup_compose["new_categories"],
            })
            decision.system_actions = _sys

    # Saudação com pedido comercial embutido: a Filha Recepção isolou o trecho não-social
    # em pending_commercial_text (extração determinística, feita por quem já lê a mensagem
    # crua — não mais uma decisão da Mãe). Reenfileira como novo job inbound em vez de tentar
    # tratar tudo no mesmo turno: o próximo ciclo do pipeline roda a Mãe de verdade, sem
    # overrides de rota. Ver "Saudação composta" em docs/architecture/llm-architecture.md.
    if effective_route_to == "recepcao":
        _pending_text = str(getattr(child_result, "pending_commercial_text", None) or "").strip()
        if _pending_text:
            _sys = list(decision.system_actions or [])
            _sys.append({"type": "requeue_pending_message", "message_text": _pending_text})
            decision.system_actions = _sys

    return decision


def decide(context: Dict[str, Any], logger: Optional[logging.Logger] = None) -> DecisionOutput:
    metadata = context.get("metadata") or {}
    ai_profile = context.get("ai_profile") or {}
    if metadata.get("bot_disabled"):
        if metadata.get("bot_disabled_reason") == "meeting_scheduled":
            if logger:
                logger.info("decision bot_disabled_reason=meeting_scheduled -> post_meeting_management")
            return _decide_post_meeting_management(context, logger=logger)
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
        mother_text = llm_service.generate_mother_route(mother_prompt, ai_profile=ai_profile)
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
        mother_decision = _enforce_greeting_first(mother_decision, context)
        mother_decision = _enforce_scheduling_agent_no_closing(mother_decision, context)
        mother_decision = _enforce_recepcao_sales_flow_pending(mother_decision, context)
        mother_decision = _enforce_apresentation_sales_flow_pending(mother_decision, context)
        mother_decision = _enforce_pre_agendamento_sales_flow_pending(mother_decision, context)
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

            is_upper_stage = normalized_current_category in {
                "apresentation", "pre-agendamento", "agendamento", "follow-up", "closing"
            }
            # Gatilhos sequenciais pendentes em p1 só bloqueiam o ramo "qualificação
            # completa, avança agora" (not missing_pre) — não o escape valve is_upper_stage,
            # que trata de um lead que já NÃO está em p1 (categoria persistida já é uma fase
            # posterior) e cuja Mãe, por engano, tentou rotear de volta para qualificação.
            p1_pending = _phase_pending_sequential_triggers("p1", ai_profile, _load_triggers_fired_set(context))
            if is_upper_stage or (not missing_pre and not p1_pending):
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

            active_fields = list(required_fields)
            for key in _get_active_fields_for_extraction(context):
                if key not in active_fields:
                    active_fields.append(key)

            fields_schema = {field: "string|number|object|null" for field in active_fields}
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
            new_extracted = {k: v for k, v in extracted.items() if k in active_fields and _is_filled_value(v)}
            if "price_acceptance" in active_fields and "budget_or_price_acceptance" in extracted and "price_acceptance" not in new_extracted:
                value = extracted.get("budget_or_price_acceptance")
                if _is_filled_value(value):
                    new_extracted["price_acceptance"] = value
                    if logger:
                        logger.info("event=qualification_price_field_mapped from=budget_or_price_acceptance to=price_acceptance")
            if "budget_or_price_acceptance" in active_fields and "price_acceptance" in extracted and "budget_or_price_acceptance" not in new_extracted:
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
            p1_pending_runtime = _phase_pending_sequential_triggers(
                "p1", ai_profile, _load_triggers_fired_set(context)
            )
            if not current_field and not p1_pending_runtime:
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
            # Restrito a required_fields (não active_fields): progresso num campo opcional/custom,
            # sem tocar o campo obrigatório pendente, não deve suprimir o contador de tentativas/anti-loop.
            has_progress = any(field in new_extracted for field in required_fields)

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
        # T4.1 — registrar qual função de prompt filha foi usada e o agent_mode resolvido.
        # T4.2 — ler prompt_variant do AI Profile para correlação A/B futura.
        _ai_profile_obs = context.get("ai_profile") or {}
        _agent_mode_resolved = _normalize_agent_mode(context, mother_decision)
        _prompt_variant = str(_ai_profile_obs.get("prompt_variant") or "v1").strip().lower()
        if _prompt_variant not in ("v1", "v2"):
            _prompt_variant = "v1"

        # Calculado uma única vez e passado ao builder do prompt filho — antes da Fase 3,
        # estas chamadas usavam sempre o default is_phase_entry=True, reapresentando
        # conteúdo de entrada (ex.: "ATENÇÃO: mensagens enviadas automaticamente") como
        # se fosse novo em todo turno. Ver docs/architecture/sales-flow.md.
        _is_phase_entry_for_prompt = _compute_is_phase_entry(context, route_for_child)

        if route_for_child == "recepcao":
            child_prompt = _build_child_prompt_recepcao(context, message_text, mother_decision, is_phase_entry=_is_phase_entry_for_prompt)
            _prompt_function_used = "_build_child_prompt_recepcao"
        elif route_for_child == "qualification":
            child_prompt = _build_child_prompt_qualification(context, message_text, mother_decision, is_phase_entry=_is_phase_entry_for_prompt)
            _prompt_function_used = "_build_child_prompt_qualification"
        elif route_for_child == "apresentation":
            child_prompt = _build_child_prompt_apresentation(context, message_text, mother_decision, is_phase_entry=_is_phase_entry_for_prompt)
            _prompt_function_used = "_build_child_prompt_apresentation"
        elif route_for_child == "pre-agendamento":
            try:
                child_prompt = _build_child_prompt_pre_agendamento(context, message_text, mother_decision)
                _prompt_function_used = "_build_child_prompt_pre_agendamento"
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
                _prompt_function_used = "_build_child_prompt(fallback)"
        elif route_for_child == "agendamento":
            try:
                child_prompt = _build_child_prompt_agendamento(context, message_text, mother_decision)
                _prompt_function_used = "_build_child_prompt_agendamento"
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
                _prompt_function_used = "_build_child_prompt(fallback)"
        elif route_for_child == "follow-up":
            try:
                child_prompt = _build_child_prompt_follow_up(context, message_text, mother_decision, is_phase_entry=_is_phase_entry_for_prompt)
                _prompt_function_used = "_build_child_prompt_follow_up"
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
                _prompt_function_used = "_build_child_prompt(fallback)"
        elif route_for_child == "closing":
            try:
                child_prompt = _build_child_prompt_closing(context, message_text, mother_decision, is_phase_entry=_is_phase_entry_for_prompt)
                _prompt_function_used = "_build_child_prompt_closing"
            except Exception:
                child_prompt = _build_child_prompt(context, message_text, mother_decision)
                _prompt_function_used = "_build_child_prompt(fallback)"
        else:
            child_prompt = _build_child_prompt(context, message_text, mother_decision)
            _prompt_function_used = "_build_child_prompt(generic)"
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
            child_text = llm_service.generate_child_result(
                route_for_child, prompt_to_use, ai_profile=ai_profile
            )
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
            decision.decision_trace["prompt_function_used"] = _prompt_function_used
            decision.decision_trace["agent_mode_resolved"] = _agent_mode_resolved
            decision.decision_trace["prompt_variant"] = _prompt_variant
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
            # T4.1 / T4.2 — observabilidade de qualidade de prompt
            logger.info(
                "event=prompt_observability job_id=%s lead_id=%s user_id=%s "
                "prompt_function=%s agent_mode_resolved=%s prompt_variant=%s route_for_child=%s",
                log_context["job_id"],
                log_context["lead_id"],
                log_context["user_id"],
                trace.get("prompt_function_used"),
                trace.get("agent_mode_resolved"),
                trace.get("prompt_variant"),
                route_for_child,
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
