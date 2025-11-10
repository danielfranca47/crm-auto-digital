"""Configurações do agente local."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv


load_dotenv()


@dataclass
class AgentSettings:
    backend_url: str = field(default="http://localhost:8000")
    agent_id: str = field(default="local-agent")
    agent_token: str = field(default="changeme")
    accepted_job_types: List[str] = field(default_factory=lambda: ["whatsapp_send"])
    poll_interval: int = field(default=5)
    chrome_profile_path: Path | None = field(default=None)
    headless: bool = field(default=False)

    @classmethod
    def from_env(cls) -> "AgentSettings":
        backend = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
        agent_id = os.getenv("AGENT_ID", "local-agent")
        token = os.getenv("AGENT_TOKEN", "changeme")
        accepted = os.getenv("JOB_TYPES", "whatsapp_send")
        poll_seconds = int(os.getenv("POLL_INTERVAL", "5"))
        profile = os.getenv("CHROME_PROFILE_PATH")
        headless = os.getenv("HEADLESS", "false").lower() == "true"

        accepted_types = [t.strip() for t in accepted.split(",") if t.strip()]
        profile_path = Path(profile).expanduser() if profile else None

        return cls(
            backend_url=backend,
            agent_id=agent_id,
            agent_token=token,
            accepted_job_types=accepted_types or ["whatsapp_send"],
            poll_interval=poll_seconds,
            chrome_profile_path=profile_path,
            headless=headless,
        )


settings = AgentSettings.from_env()
