from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    env: str = "dev"
    log_level: str = "INFO"
    crm_api_base: str = "http://localhost:8000"
    core_api_base: str = "http://localhost:8001"
    crm_service_token: Optional[str] = None
    core_service_token: Optional[str] = None
    llm_api_base: str = "http://localhost:8002"
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 20
    qualification_heuristic_fallback: int = 1
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
