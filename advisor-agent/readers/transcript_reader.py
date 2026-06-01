import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

TRANSCRIPTS_DIR = Path(os.getenv(
    "TRANSCRIPTS_DIR",
    r"C:\Users\Daniel França\.claude\projects\c--crm-auto-digital",
))


def get_recent_sessions(days: int = 7) -> List[Dict[str, Any]]:
    """Return sessions from the last N days, sorted ascending by start time."""
    cutoff = datetime.now() - timedelta(days=days)
    sessions = []

    if not TRANSCRIPTS_DIR.exists():
        return sessions

    for jsonl_file in TRANSCRIPTS_DIR.glob("*.jsonl"):
        mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
        if mtime < cutoff:
            continue

        session = _parse_session(jsonl_file)
        if session:
            sessions.append(session)

    sessions.sort(key=lambda s: s.get("started_at", ""))
    return sessions


def _parse_session(path: Path) -> Optional[Dict[str, Any]]:
    messages: List[Dict] = []
    metadata: Dict[str, Any] = {}

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") == "queue-operation":
                    continue

                if not metadata and entry.get("timestamp"):
                    metadata = {
                        "session_id": entry.get("sessionId", path.stem),
                        "started_at": entry.get("timestamp", ""),
                        "branch": entry.get("gitBranch", ""),
                    }

                msg_type = entry.get("type")
                if msg_type in ("user", "assistant"):
                    messages.append(entry)
    except Exception:
        return None

    if not messages:
        return None

    return {**metadata, "messages": messages}
