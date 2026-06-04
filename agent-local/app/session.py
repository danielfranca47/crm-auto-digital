"""Persistência de sessão local em ~/.agent-local/session.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_SESSION_DIR = Path.home() / ".agent-local"
_SESSION_FILE = _SESSION_DIR / "session.json"


def load_session() -> Optional[dict]:
    if not _SESSION_FILE.exists():
        return None
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        if not data.get("access_token"):
            return None
        return data
    except Exception:
        return None


def save_session(data: dict) -> None:
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_session() -> None:
    if _SESSION_FILE.exists():
        _SESSION_FILE.unlink()


def is_subscriber(session: dict) -> bool:
    return (session or {}).get("subscription_status") == "active"


# ── Templates de mensagem ─────────────────────────────────────────────────────

def get_templates(session: dict) -> list:
    """Retorna lista de templates: [{'name': str, 'text': str}, ...]"""
    return list(session.get("message_templates") or [])


def save_template(session: dict, name: str, text: str) -> None:
    """Adiciona ou actualiza template pelo nome. Persiste em session.json."""
    templates = get_templates(session)
    for t in templates:
        if t.get("name") == name:
            t["text"] = text
            session["message_templates"] = templates
            save_session(session)
            return
    templates.append({"name": name, "text": text})
    session["message_templates"] = templates
    save_session(session)


def delete_template(session: dict, name: str) -> None:
    """Remove template pelo nome. Persiste em session.json."""
    templates = [t for t in get_templates(session) if t.get("name") != name]
    session["message_templates"] = templates
    save_session(session)
