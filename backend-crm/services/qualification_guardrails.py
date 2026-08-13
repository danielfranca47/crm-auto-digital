from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Categorias-alvo cuja transição a partir de "qualification" exige completude
# (campos obrigatórios + score). Usado tanto pelo caminho manual (operador
# arrastando o card, routes/leads.py) quanto pelo automático (bot, jobs_service.py
# e routes/playground.py) — mantém os dois em paridade.
QUALIFICATION_GATED_CATEGORIES = {"apresentation", "follow-up", "closing"}


def required_fields_for_mode(
    agent_mode_normalized: str,
    required_fields_override: List[str] | None = None,
) -> List[str]:
    if required_fields_override is not None:
        return list(required_fields_override)
    return []  # Sem configuração no AI Profile = sem campos obrigatórios


def compute_missing_fields(
    agent_mode_normalized: str,
    extracted: Dict[str, Any],
    required_fields_override: List[str] | None = None,
) -> List[str]:
    required = required_fields_for_mode(agent_mode_normalized, required_fields_override=required_fields_override)
    missing: List[str] = []
    has_next_step_with_time = bool((extracted or {}).get("next_step_with_time"))
    for field in required:
        if field == "availability_window" and agent_mode_normalized == "consultivo" and has_next_step_with_time:
            continue
        value = (extracted or {}).get(field)
        if isinstance(value, str):
            if value.strip():
                continue
        elif isinstance(value, (list, dict)):
            if value:
                continue
        elif value is not None:
            continue
        missing.append(field)
    return missing


def _agent_type_to_mode(agent_type: str | None) -> str:
    normalized = str(agent_type or "").strip().lower()
    if normalized == "agent_3":
        return "consultivo"
    if normalized == "agent_1":
        return "agenda"
    return "agenda"


def _fetch_ai_profile(user_id: int) -> Dict[str, Any]:
    """Retorna o ai_profile completo do usuário via service token. Em caso de erro, retorna {}."""
    try:
        from core_client import fetch_core_ai_profile_resolve
        return fetch_core_ai_profile_resolve(user_id) or {}
    except Exception as exc:
        logger.warning("can_advance_from_qualification: falha ao buscar ai_profile user_id=%s: %s", user_id, exc)
        return {}


def _fetch_ai_profile_threshold(user_id: int) -> Tuple[int, str]:
    """Retorna (qualification_score_threshold, nurture_vs_discard_rule) do ai_profile do usuário."""
    profile = _fetch_ai_profile(user_id)
    threshold = profile.get("qualification_score_threshold")
    rule = profile.get("nurture_vs_discard_rule") or "discard"
    return (int(threshold) if threshold is not None else 6, str(rule))


# Chaves hardcoded que compute_4p_scores() (backend-crm/services/qualification_state.py)
# sabe pontuar. Perfis 100% custom (sem nenhuma destas chaves em qualification_fields)
# nunca acumulam score real — aplicar o gate de score nesse caso bloquearia para sempre,
# então ambos os checks de score abaixo pulam quando nenhuma chave configurada bate aqui.
_4P_SCORABLE_KEYS = {"decision_role", "urgency", "budget_or_price_acceptance", "availability_window"}


def _load_lead_mode_and_score(conn, lead_id: int, user_id: int) -> Tuple[bool, str, int]:
    """Lê agent_mode_normalized e qualification_total_score do lead. Retorna (found, mode, score)."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    lead_row = cur.execute(
        "SELECT agent_type FROM leads WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    ).fetchone()
    if not lead_row:
        return False, "", 0

    state_row = cur.execute(
        "SELECT agent_mode_normalized, qualification_total_score FROM lead_qualification_state WHERE lead_id = ?",
        (lead_id,),
    ).fetchone()

    mode = _agent_type_to_mode(lead_row["agent_type"])
    total_score = 0
    if state_row:
        mode = str(state_row["agent_mode_normalized"] or "").strip().lower() or mode
        total_score = int(state_row["qualification_total_score"] or 0)
    return True, mode, total_score


def _score_below_threshold(ai_profile: Dict[str, Any], total_score: int) -> Tuple[bool, List[str]]:
    """Só a checagem de score dos 4Ps — sem campos obrigatórios. Usada tanto pelo guardrail
    manual completo quanto pelo gate do caminho automático (ver can_advance_score_gate)."""
    _qfields = ai_profile.get("qualification_fields") or []
    _configured_keys = {f["key"] for f in _qfields if isinstance(f, dict) and "key" in f}
    if not _configured_keys or not (_configured_keys & _4P_SCORABLE_KEYS):
        return True, []

    threshold = ai_profile.get("qualification_score_threshold")
    threshold_int = int(threshold) if threshold is not None else 6
    if total_score < threshold_int:
        return False, [f"score_{total_score}_of_12_below_threshold_{threshold_int}"]
    return True, []


def can_advance_from_qualification(conn, lead_id: int, user_id: int) -> Tuple[bool, List[str]]:
    """Guardrail completo (campos obrigatórios + score) — só para rotas manuais
    (routes/leads.py, drag do Kanban pelo operador). NÃO chamar do pipeline automático
    da IA: campos obrigatórios já são aplicados lá via decision_engine.py
    (_enforce_qualification_route_when_missing), checar de novo aqui seria redundante
    (decisão de "audit: Fase 5 — isolar guardrail de qualificação", commit 511d9c9).
    Para o gate de score no caminho automático, usar can_advance_score_gate().
    """
    found, mode, total_score = _load_lead_mode_and_score(conn, lead_id, user_id)
    if not found:
        return False, ["lead_not_found"]

    conn.row_factory = sqlite3.Row
    state_row = conn.execute(
        "SELECT data_json FROM lead_qualification_state WHERE lead_id = ?", (lead_id,)
    ).fetchone()
    extracted: Dict[str, Any] = {}
    if state_row and state_row["data_json"]:
        raw_data = state_row["data_json"]
        if isinstance(raw_data, dict):
            extracted = raw_data
        elif isinstance(raw_data, str) and raw_data.strip():
            try:
                import json

                parsed = json.loads(raw_data)
                if isinstance(parsed, dict):
                    extracted = parsed
            except Exception:
                extracted = {}

    # Lê override de campos do ai_profile (None = usar defaults do modo)
    ai_profile = _fetch_ai_profile(user_id)
    override = ai_profile.get("qualification_required_fields")
    required_fields_override: List[str] | None = None
    if isinstance(override, list):
        required_fields_override = [str(f) for f in override if isinstance(f, str)]

    # Verificação 1: campos obrigatórios completos
    missing_fields = compute_missing_fields(mode, extracted, required_fields_override=required_fields_override)
    if missing_fields:
        return False, missing_fields

    # Verificação 2: score mínimo dos 4Ps (ignorado se não houver campos obrigatórios
    # explicitamente configurados — mesma leitura histórica do guardrail manual)
    if required_fields_override is not None and len(required_fields_override) == 0:
        # Lista vazia configurada explicitamente — sem qualificação obrigatória, avança sempre
        return True, []

    return _score_below_threshold(ai_profile, total_score)


def can_advance_score_gate(conn, lead_id: int, user_id: int) -> Tuple[bool, List[str]]:
    """Gate de score, isolado dos campos obrigatórios — para o caminho automático da IA
    (jobs_service.apply_suggested_category, routes/playground.py).

    Não repete a Verificação 1 de can_advance_from_qualification (campos obrigatórios):
    isso já é aplicado por decision_engine.py antes de a IA decidir avançar, e checar de
    novo aqui seria a redundância que "audit: Fase 5" removeu de propósito. Também não
    herda o atalho "required_fields=[] → pula score também": qualification_score_threshold
    é uma configuração independente de campos obrigatórios — o usuário pode querer o score
    como único critério, sem nenhum campo marcado "obrigatório".
    """
    found, _mode, total_score = _load_lead_mode_and_score(conn, lead_id, user_id)
    if not found:
        return False, ["lead_not_found"]
    ai_profile = _fetch_ai_profile(user_id)
    return _score_below_threshold(ai_profile, total_score)
