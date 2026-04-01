from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# NOTE: manter em sincronia com backend-executors/app/contracts/qualification_contract.py
_MIN_REQUIRED_FIELDS = {
    "consultivo": [
        "service_interest",
        "urgency",
        "decision_role",
        "constraints",
        "availability_window",
        "budget_or_price_acceptance",
    ],
    "agenda": [
        "service_interest",
        "availability_window",
        "price_acceptance",
    ],
    "direto": [
        "service_interest",
        "availability_window",
        "price_acceptance",
    ],
}


def required_fields_for_mode(
    agent_mode_normalized: str,
    required_fields_override: List[str] | None = None,
) -> List[str]:
    if required_fields_override is not None:
        return list(required_fields_override)
    return list(_MIN_REQUIRED_FIELDS.get(agent_mode_normalized, _MIN_REQUIRED_FIELDS["agenda"]))


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


def can_advance_from_qualification(conn, lead_id: int, user_id: int) -> Tuple[bool, List[str]]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    lead_row = cur.execute(
        "SELECT agent_type FROM leads WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    ).fetchone()
    if not lead_row:
        return False, ["lead_not_found"]

    state_row = cur.execute(
        """
        SELECT agent_mode_normalized, data_json,
               qualification_total_score
          FROM lead_qualification_state
         WHERE lead_id = ?
        """,
        (lead_id,),
    ).fetchone()

    mode = _agent_type_to_mode(lead_row["agent_type"])
    extracted: Dict[str, Any] = {}
    total_score = 0
    if state_row:
        mode = str(state_row["agent_mode_normalized"] or "").strip().lower() or mode
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
        total_score = int(state_row["qualification_total_score"] or 0)

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

    # Verificação 2: score mínimo dos 4Ps (ignorado se não houver campos obrigatórios)
    threshold = ai_profile.get("qualification_score_threshold")
    threshold_int = int(threshold) if threshold is not None else 6
    if required_fields_override is not None and len(required_fields_override) == 0:
        # Lista vazia configurada explicitamente — sem qualificação obrigatória, avança sempre
        return True, []
    if total_score < threshold_int:
        return False, [f"score_{total_score}_of_12_below_threshold_{threshold_int}"]

    return True, []
