"""Cliente HTTP para comunicação com o backend."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

import requests

from .config import settings

logger = logging.getLogger(__name__)


class JobsClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.backend_url).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Agent-Id": settings.agent_id,
                "X-Agent-Token": settings.agent_token,
                "Content-Type": "application/json",
            }
        )

    def register(self) -> Dict[str, Any]:
        payload = {
            "agent_id": settings.agent_id,
            "name": settings.agent_id,
            "token": settings.agent_token,
        }
        resp = self.session.post(f"{self.base_url}/api/agents/register", json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Agente registrado: %s", data.get("agent", {}).get("id"))
        return data

    def next_job(self, accepted_types: Optional[Iterable[str]] = None) -> Optional[Dict[str, Any]]:
        params = []
        if accepted_types:
            params = [("types", t) for t in accepted_types]
        resp = self.session.get(f"{self.base_url}/api/agents/next-job", params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json() or {}
        return data.get("job")

    def report(self, job_id: int, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "job_id": job_id,
            "status": status,
            "result": result or {},
            "error": error,
        }
        resp = self.session.post(f"{self.base_url}/api/agents/report", json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def overview(self) -> Dict[str, Any]:
        resp = self.session.get(f"{self.base_url}/api/agents/overview", timeout=15)
        resp.raise_for_status()
        return resp.json()


client = JobsClient()
