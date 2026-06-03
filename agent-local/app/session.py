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
