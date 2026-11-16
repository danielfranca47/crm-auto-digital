"""
Versão (commit) de cada serviço em produção, sem acesso ao Railway.

O Railway põe o commit do deploy em `RAILWAY_GIT_COMMIT_SHA`. O CRM junta o seu com o do core
(`/version`) e o do executors (`/health`) para quem publica código confirmar que o deploy chegou —
por exemplo a skill de configuração de agentes no PC de um colaborador.
"""
from __future__ import annotations

import os
from typing import Dict, Optional

import httpx

from core_client import _get_core_base


def commit_atual() -> Optional[str]:
    return os.getenv("RAILWAY_GIT_COMMIT_SHA") or None


def _commit_de(url: str) -> Optional[str]:
    try:
        r = httpx.get(url, timeout=5)
        return r.json().get("commit") if r.status_code == 200 else None
    except Exception:
        return None


def versoes() -> Dict[str, Optional[str]]:
    executors = os.getenv("EXECUTORS_BASE_URL", "").rstrip("/")
    return {
        "crm": commit_atual(),
        "core": _commit_de(f"{_get_core_base()}/version"),
        "executors": _commit_de(f"{executors}/health") if executors else None,
    }
