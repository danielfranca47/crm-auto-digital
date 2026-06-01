"""
Arquivo histórico de análises. Cada análise bem-sucedida é guardada em
data/history/ com timestamp no nome. Usado para dar contexto transversal
ao próximo ciclo de análise.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

HISTORY_DIR = Path(__file__).parent.parent / "data" / "history"


def save(report: Dict[str, Any]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = HISTORY_DIR / f"{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def load_recent(n: int = 4) -> List[Dict[str, Any]]:
    """Return the last N analyses, oldest first, condensed for context."""
    if not HISTORY_DIR.exists():
        return []

    files = sorted(HISTORY_DIR.glob("*.json"))[-n:]
    result = []
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            result.append(_condense(raw))
        except Exception:
            continue
    return result


def load_latest() -> Dict[str, Any] | None:
    """Return the most recent full analysis from history."""
    if not HISTORY_DIR.exists():
        return None
    files = sorted(HISTORY_DIR.glob("*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _condense(report: Dict[str, Any]) -> Dict[str, Any]:
    """Strip heavy fields to keep token usage low when passing history as context."""
    improvements = report.get("improvements", [])
    return {
        "period": report.get("period", ""),
        "cached_at": report.get("cached_at", "")[:10],
        "assessment_summary": report.get("assessment", "")[:400],
        "high_priority_issues": [
            i.get("issue", "") for i in improvements if i.get("priority") == "high"
        ],
        "next_priorities": [
            p.get("description", "") for p in report.get("next_priorities", [])
        ],
    }
