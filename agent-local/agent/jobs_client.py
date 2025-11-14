"""Cliente HTTP para comunicação com o backend."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

import requests

from .config import AgentConfig

logger = logging.getLogger(__name__)


class JobsClient:
    """Cliente que encapsula as chamadas HTTP para o backend."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.base_url = config.backend_url.rstrip("/")

    # --------- helpers HTTP ---------

    def _post(self, path: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, json=json_data, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("POST %s -> %s", path, data)
        return data

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("GET %s -> %s", path, data)
        return data

    # --------- chamadas públicas ---------

    def register_agent(self, *, capabilities: Iterable[str], version: str) -> Dict[str, Any]:
        payload = {
            "agent_id": self.config.agent_id,
            "token": self.config.token,
            "name": self.config.agent_id,
            "capabilities": list(capabilities),
            "version": version,
        }
        return self._post("/api/agents/register", payload)

    def fetch_next_job(self, job_types: Iterable[str]) -> Optional[Dict[str, Any]]:
        params = {
            "agent_id": self.config.agent_id,
            "token": self.config.token,
            "types": ",".join(job_types),
        }
        data = self._get("/api/agents/next-job", params=params)
        return data.get("job")

    def report_job(
        self,
        *,
        job_id: int,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "agent_id": self.config.agent_id,
            "token": self.config.token,
            "job_id": job_id,
            "status": status,
            "result": result,
            "error": error,
        }
        return self._post("/api/agents/report", payload)


__all__ = ["JobsClient"]
