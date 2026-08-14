from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict

from database import get_connection


def _json_loads(value: Any, default: dict) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return dict(default)
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return dict(default)


def _json_loads_list(value: Any, default: list) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return list(default)
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return list(default)


def _normalize_row(row: sqlite3.Row | None) -> Dict[str, Any]:
    if not row:
        return {
            "exists": False,
            "data_json": {},
            "confidence_json": {},
            "attempts_json": {},
            "asked_questions_json": [],
            "last_question_text": "",
            "last_questioned_field": None,
            "stage": "qualification",
        }
    payload = dict(row)
    payload["exists"] = True
    payload["data_json"] = _json_loads(payload.get("data_json"), {})
    payload["confidence_json"] = _json_loads(payload.get("confidence_json"), {})
    payload["attempts_json"] = _json_loads(payload.get("attempts_json"), {})
    payload["asked_questions_json"] = _json_loads_list(payload.get("asked_questions_json"), [])
    payload["asked_questions_json"] = [item for item in payload["asked_questions_json"] if isinstance(item, dict)]
    payload["last_question_text"] = str(payload.get("last_question_text") or "")
    return payload


def _score_field(value: Any, positive_keywords: tuple, negative_keywords: tuple = ()) -> int:
    """Retorna score 0-3 para um campo com base em keywords.

    3 = sinal positivo forte
    2 = campo preenchido, sinal neutro
    1 = sinal negativo/fraco
    0 = campo ausente ou vazio
    """
    if value is None:
        return 0
    text = str(value).strip().lower()
    if not text:
        return 0
    if any(k in text for k in positive_keywords):
        return 3
    if any(k in text for k in negative_keywords):
        return 1
    return 2


def compute_4p_scores(data: Dict[str, Any]) -> Dict[str, int]:
    """Extrai scores 0-3 dos 4Ps (Power, Priority, Price, Timing) a partir dos campos de qualificação."""
    d = data or {}

    # Power: quem decide (decision_role)
    power_score = _score_field(
        d.get("decision_role"),
        positive_keywords=("eu decido", "sou eu", "decisor", "eu mesmo", "posso decidir", "só eu", "sou o", "sim"),
        negative_keywords=("consultar", "perguntar", "marido", "esposa", "sócio", "chefe", "não decido", "preciso ver", "meu pai", "minha mãe"),
    )

    # Priority: urgência do problema (urgency)
    priority_score = _score_field(
        d.get("urgency"),
        positive_keywords=("urgente", "agora", "hoje", "imediato", "quanto antes", "semana", "essa semana", "nessa semana", "o mais rápido"),
        negative_keywords=("sem urgência", "no futuro", "talvez", "futuramente", "algum dia", "não sei quando", "não tenho pressa"),
    )

    # Price: verba disponível (budget_or_price_acceptance)
    price_score = _score_field(
        d.get("budget_or_price_acceptance"),
        positive_keywords=("sim", "ok", "aceito", "concordo", "tá bem", "beleza", "ótimo", "tenho", "cabe", "consigo", "tranquilo", "dentro do orçamento"),
        negative_keywords=("caro", "não tenho", "sem verba", "muito caro", "não posso", "acima", "fora do orçamento", "não cabe", "apertado"),
    )

    # Timing: prazo definido (availability_window)
    timing_score = _score_field(
        d.get("availability_window"),
        positive_keywords=("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "manhã", "tarde", "noite", "às ", "horas", "amanhã", "semana que vem"),
        negative_keywords=("qualquer hora", "tanto faz", "não sei", "qualquer dia", "sem preferência"),
    )

    total = power_score + priority_score + price_score + timing_score
    return {
        "power_score": power_score,
        "priority_score": priority_score,
        "price_score": price_score,
        "timing_score": timing_score,
        "qualification_total_score": total,
    }


def get_qualification_state(lead_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute(
            "SELECT * FROM lead_qualification_state WHERE lead_id = ?",
            (lead_id,),
        ).fetchone()
    return _normalize_row(row)


def merge_data(existing: Dict[str, Any], extracted: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing or {})
    for key, value in (extracted or {}).items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        merged[key] = value
    return merged


def merge_asked_questions(existing: list[dict], new_items: list[dict]) -> list[dict]:
    merged = [item for item in (existing or []) if isinstance(item, dict)]
    by_field_count: Dict[str, int] = {}
    for item in merged:
        field = str(item.get("field") or "")
        by_field_count[field] = by_field_count.get(field, 0) + 1

    for item in (new_items or []):
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "")
        if not field:
            continue
        question_text = str(item.get("question_text") or "").strip()
        if not question_text:
            continue
        attempt = by_field_count.get(field, 0) + 1
        by_field_count[field] = attempt
        merged.append(
            {
                "field": field,
                "question_text": question_text,
                "created_at": item.get("created_at") or "",
                "job_id": item.get("job_id"),
                "attempt": attempt,
            }
        )

    # manter últimos 20 no total
    merged = merged[-20:]
    # manter no máximo 3 por campo
    pruned: list[dict] = []
    field_buckets: Dict[str, list[dict]] = {}
    for item in merged:
        field = str(item.get("field") or "")
        field_buckets.setdefault(field, []).append(item)
    for _field, items in field_buckets.items():
        pruned.extend(items[-3:])
    pruned = sorted(pruned, key=lambda x: str(x.get("created_at") or ""))[-20:]
    return pruned


def upsert_qualification_state(lead_id: int, user_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Lê o estado atual e grava o merge dentro da MESMA transação (BEGIN IMMEDIATE),
    mesmo padrão de jobs_service.py::fetch_next_job(). Antes, a leitura (get_qualification_state)
    acontecia numa conexão separada da escrita, com o merge feito em Python no meio — duas
    chamadas próximas no tempo para o mesmo lead_id (ex.: duas mensagens do lead processadas
    em sequência, ou uma edição manual do card coincidindo com uma extração do bot em
    andamento) podiam ler o mesmo estado "antigo" e a gravação mais recente sobrescrevia a
    anterior, perdendo um campo de qualificação já capturado. BEGIN IMMEDIATE bloqueia
    outras escritas no SQLite até o commit, fechando essa janela.
    """
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        existing = _normalize_row(
            cur.execute(
                "SELECT * FROM lead_qualification_state WHERE lead_id = ?", (lead_id,)
            ).fetchone()
        )

        merged_data = merge_data(existing.get("data_json") or {}, patch.get("data_json") or {})
        merged_confidence = merge_data(existing.get("confidence_json") or {}, patch.get("confidence_json") or {})
        merged_attempts = merge_data(existing.get("attempts_json") or {}, patch.get("attempts_json") or {})
        merged_asked_questions = merge_asked_questions(
            existing.get("asked_questions_json") or [],
            patch.get("asked_questions_json") if isinstance(patch.get("asked_questions_json"), list) else [],
        )

        stage = patch.get("stage") or existing.get("stage") or "qualification"
        agent_mode_normalized = patch.get("agent_mode_normalized") or existing.get("agent_mode_normalized")
        playbook_key = patch.get("playbook_key") or existing.get("playbook_key")
        playbook_version = patch.get("playbook_version") or existing.get("playbook_version")
        last_questioned_field = patch.get("last_questioned_field")
        if last_questioned_field is None:
            last_questioned_field = existing.get("last_questioned_field")
        last_question_text = patch.get("last_question_text")
        if last_question_text is None:
            last_question_text = existing.get("last_question_text") or ""

        scores = compute_4p_scores(merged_data)

        cur.execute(
            """
            INSERT INTO lead_qualification_state (
                lead_id, user_id, stage, agent_mode_normalized, playbook_key, playbook_version,
                data_json, confidence_json, last_questioned_field, attempts_json, asked_questions_json, last_question_text,
                power_score, priority_score, price_score, timing_score, qualification_total_score,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(lead_id) DO UPDATE SET
                user_id=excluded.user_id,
                stage=excluded.stage,
                agent_mode_normalized=excluded.agent_mode_normalized,
                playbook_key=excluded.playbook_key,
                playbook_version=excluded.playbook_version,
                data_json=excluded.data_json,
                confidence_json=excluded.confidence_json,
                last_questioned_field=excluded.last_questioned_field,
                attempts_json=excluded.attempts_json,
                asked_questions_json=excluded.asked_questions_json,
                last_question_text=excluded.last_question_text,
                power_score=excluded.power_score,
                priority_score=excluded.priority_score,
                price_score=excluded.price_score,
                timing_score=excluded.timing_score,
                qualification_total_score=excluded.qualification_total_score,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                lead_id,
                user_id,
                stage,
                agent_mode_normalized,
                playbook_key,
                playbook_version,
                json.dumps(merged_data, ensure_ascii=False),
                json.dumps(merged_confidence, ensure_ascii=False),
                last_questioned_field,
                json.dumps(merged_attempts, ensure_ascii=False),
                json.dumps(merged_asked_questions, ensure_ascii=False),
                str(last_question_text or ""),
                scores["power_score"],
                scores["priority_score"],
                scores["price_score"],
                scores["timing_score"],
                scores["qualification_total_score"],
            ),
        )
        conn.commit()

    return get_qualification_state(lead_id)


def increment_attempt(lead_id: int, user_id: int, field: str) -> Dict[str, Any]:
    current = get_qualification_state(lead_id)
    attempts = dict(current.get("attempts_json") or {})
    attempts[field] = int(attempts.get(field) or 0) + 1
    return upsert_qualification_state(
        lead_id=lead_id,
        user_id=user_id,
        patch={
            "attempts_json": attempts,
            "last_questioned_field": field,
        },
    )
