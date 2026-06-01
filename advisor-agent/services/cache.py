import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

CACHE_PATH = Path(__file__).parent.parent / "data" / "analysis_cache.json"
STALE_HOURS = 18  # consider cache stale after this many hours


def load() -> Optional[Dict[str, Any]]:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save(report: Dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    report["cached_at"] = datetime.now().isoformat()
    CACHE_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def is_stale() -> bool:
    data = load()
    if not data:
        return True
    cached_at_str = data.get("cached_at", "")
    if not cached_at_str:
        return True
    try:
        cached_at = datetime.fromisoformat(cached_at_str)
        return datetime.now() - cached_at > timedelta(hours=STALE_HOURS)
    except Exception:
        return True
