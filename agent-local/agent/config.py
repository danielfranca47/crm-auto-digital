"""Configurações do agente local."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


@dataclass
class AgentConfig:
    backend_url: str
    agent_id: str
    token: str
    poll_interval: float = 5.0
    idle_interval: float = 15.0
    job_types: List[str] = field(default_factory=lambda: ["whatsapp_send"])
    user_data_dir: Path = field(default_factory=lambda: Path.home() / ".agent-local" / "chrome-profile")
    chrome_binary: str | None = None
    headless: bool = False
    log_path: Path = field(default_factory=lambda: Path.cwd() / "agent.log")

    @classmethod
    def load(cls) -> "AgentConfig":
        backend_url = os.getenv("BACKEND_URL") or "http://localhost:8000"
        agent_id = os.getenv("AGENT_ID") or "local-agent"
        token = os.getenv("AGENT_TOKEN") or "change-me"
        poll_interval = float(os.getenv("POLL_INTERVAL", "5"))
        idle_interval = float(os.getenv("IDLE_INTERVAL", "15"))
        job_types = [t.strip() for t in os.getenv("JOB_TYPES", "whatsapp_send").split(",") if t.strip()]
        user_data_dir = Path(os.getenv("CHROME_USER_DATA", str(Path.home() / ".agent-local" / "chrome-profile")))
        chrome_binary = os.getenv("CHROME_BINARY") or None
        headless = os.getenv("CHROME_HEADLESS", "0").lower() in {"1", "true", "yes"}
        log_path = Path(os.getenv("AGENT_LOG", str(Path.cwd() / "agent.log")))
        return cls(
            backend_url=backend_url.rstrip("/"),
            agent_id=agent_id,
            token=token,
            poll_interval=poll_interval,
            idle_interval=idle_interval,
            job_types=job_types or ["whatsapp_send"],
            user_data_dir=user_data_dir,
            chrome_binary=chrome_binary,
            headless=headless,
            log_path=log_path,
        )


__all__ = ["AgentConfig"]
