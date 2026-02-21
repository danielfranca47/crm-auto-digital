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


def _normalize_row(row: sqlite3.Row | None) -> Dict[str, Any]:
    if not row:
        return {
            "exists": False,
            "data_json": {},
            "confidence_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
            "stage": "qualification",
        }
    payload = dict(row)
    payload["exists"] = True
    payload["data_json"] = _json_loads(payload.get("data_json"), {})
    payload["confidence_json"] = _json_loads(payload.get("confidence_json"), {})
    payload["attempts_json"] = _json_loads(payload.get("attempts_json"), {})
    return payload


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


def upsert_qualification_state(lead_id: int, user_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    existing = get_qualification_state(lead_id)

    merged_data = merge_data(existing.get("data_json") or {}, patch.get("data_json") or {})
    merged_confidence = merge_data(existing.get("confidence_json") or {}, patch.get("confidence_json") or {})
    merged_attempts = merge_data(existing.get("attempts_json") or {}, patch.get("attempts_json") or {})

    stage = patch.get("stage") or existing.get("stage") or "qualification"
    agent_mode_normalized = patch.get("agent_mode_normalized") or existing.get("agent_mode_normalized")
    playbook_key = patch.get("playbook_key") or existing.get("playbook_key")
    playbook_version = patch.get("playbook_version") or existing.get("playbook_version")
    last_questioned_field = patch.get("last_questioned_field")
    if last_questioned_field is None:
        last_questioned_field = existing.get("last_questioned_field")

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO lead_qualification_state (
                lead_id, user_id, stage, agent_mode_normalized, playbook_key, playbook_version,
                data_json, confidence_json, last_questioned_field, attempts_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
