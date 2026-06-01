"""
Métricas objectivas calculadas directamente dos dados de sessão e git log.
Não chama o Claude — execução instantânea.
"""
import subprocess
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List
import os

PROJECT_DIR = Path(os.getenv("PROJECT_DIR", r"c:\crm-auto-digital"))

_AREA_PREFIXES = {
    "backend-crm": "Backend CRM",
    "backend-core": "Backend Core",
    "backend-executors": "Backend Executors",
    "frontend-crm": "Frontend CRM",
    "frontend-admin": "Frontend Admin",
    "website": "Website",
    "agent-local": "Agent Local",
    "advisor-agent": "Advisor Agent",
    "docs/": "Documentação",
}

_FILE_TOOLS = {"Edit", "Write", "MultiEdit"}


def compute(sessions_raw: List[Dict]) -> Dict[str, Any]:
    if not sessions_raw:
        return _empty()

    files_counter: Counter = Counter()
    area_counter: Counter = Counter()
    total_messages = 0

    for session in sessions_raw:
        messages = session.get("messages", [])
        total_messages += len(messages)
        for msg in messages:
            content = msg.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("name") not in _FILE_TOOLS:
                    continue
                path = block.get("input", {}).get("file_path", "")
                if not path:
                    continue
                short = _shorten(path)
                files_counter[short] += 1
                area = _area_for(path)
                area_counter[area] += 1

    commits = _count_commits(days=7)
    avg_msgs = round(total_messages / len(sessions_raw)) if sessions_raw else 0

    return {
        "total_sessions": len(sessions_raw),
        "avg_messages_per_session": avg_msgs,
        "commits_this_week": commits,
        "files_by_area": dict(area_counter.most_common()),
        "most_modified_files": files_counter.most_common(7),
        "unique_branches": sorted({s.get("branch", "") for s in sessions_raw if s.get("branch")}),
    }


def _shorten(path: str) -> str:
    for prefix in (r"c:\crm-auto-digital\\", r"c:\crm-auto-digital/",
                   "c:/crm-auto-digital/", "c:/crm-auto-digital\\"):
        if path.lower().startswith(prefix.lower()):
            return path[len(prefix):]
    return path


def _area_for(path: str) -> str:
    p = path.replace("\\", "/").lower()
    for key, label in _AREA_PREFIXES.items():
        if key in p:
            return label
    return "Outro"


def _count_commits(days: int = 7) -> int:
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "log",
             f"--since={days} days ago", "--oneline", "--no-merges"],
            capture_output=True, text=True, timeout=10,
        )
        lines = [l for l in result.stdout.strip().splitlines() if l]
        return len(lines)
    except Exception:
        return 0


def _empty() -> Dict[str, Any]:
    return {
        "total_sessions": 0,
        "avg_messages_per_session": 0,
        "commits_this_week": 0,
        "files_by_area": {},
        "most_modified_files": [],
        "unique_branches": [],
    }
