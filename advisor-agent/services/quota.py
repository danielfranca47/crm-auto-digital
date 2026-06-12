"""
Controlo de quota semanal de chamadas ao Claude.
Rastreia chamadas feitas pelo advisor e bloqueia quando o limite é atingido.
A semana começa à segunda-feira às 00:00.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple

SETTINGS_PATH = Path(__file__).parent.parent / "data" / "settings.json"
USAGE_PATH    = Path(__file__).parent.parent / "data" / "usage.json"

DEFAULT_MAX_CALLS = 3  # padrão conservador (~30% de uso típico)


# --- Definições ---

def get_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {"max_calls_per_week": DEFAULT_MAX_CALLS}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"max_calls_per_week": DEFAULT_MAX_CALLS}


def save_settings(max_calls: int) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "max_calls_per_week": max(1, min(20, int(max_calls))),
        "updated_at": datetime.now().isoformat(),
    }
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# --- Registo de chamadas ---

def record_call(call_type: str = "analysis") -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8")) if USAGE_PATH.exists() else {"calls": []}
    except Exception:
        data = {"calls": []}

    data["calls"].append({"timestamp": datetime.now().isoformat(), "type": call_type})

    # Guarda apenas os últimos 90 dias
    cutoff = datetime.now() - timedelta(days=90)
    data["calls"] = [
        c for c in data["calls"]
        if datetime.fromisoformat(c["timestamp"]) > cutoff
    ]
    USAGE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_calls_this_week() -> List[Dict]:
    if not USAGE_PATH.exists():
        return []
    try:
        all_calls = json.loads(USAGE_PATH.read_text(encoding="utf-8")).get("calls", [])
    except Exception:
        return []

    start = _week_start()
    end   = start + timedelta(days=7)
    return [
        c for c in all_calls
        if start <= datetime.fromisoformat(c["timestamp"]) < end
    ]


# --- Verificação de permissão ---

def can_run() -> Tuple[bool, str]:
    settings  = get_settings()
    max_calls = settings.get("max_calls_per_week", DEFAULT_MAX_CALLS)
    used      = len(get_calls_this_week())
    if used >= max_calls:
        reset = (_week_start() + timedelta(days=7)).strftime("%d/%m")
        return False, (
            f"Limite semanal atingido ({used}/{max_calls} chamadas). "
            f"Repõe a {reset} ou aumenta o limite nas Definições."
        )
    return True, f"{used}/{max_calls} chamadas usadas esta semana."


# --- Info para o dashboard ---

def get_quota_info() -> Dict[str, Any]:
    settings  = get_settings()
    max_calls = settings.get("max_calls_per_week", DEFAULT_MAX_CALLS)
    calls     = get_calls_this_week()
    used      = len(calls)
    remaining = max(0, max_calls - used)
    pct       = round(used / max_calls * 100) if max_calls > 0 else 0
    reset_dt  = _week_start() + timedelta(days=7)

    return {
        "max_calls_per_week": max_calls,
        "used_this_week":     used,
        "remaining":          remaining,
        "percent_used":       pct,
        "week_reset_date":    reset_dt.strftime("%d/%m"),
        "at_limit":           used >= max_calls,
        "calls_this_week":    calls,
    }


def _week_start() -> datetime:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=today.weekday())  # segunda-feira
