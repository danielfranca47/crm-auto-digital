from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "dev"
    log_level: str = "INFO"
    crm_api_base: str = "http://localhost:8000"
    core_api_base: str = "http://localhost:8001"
    crm_service_token: Optional[str] = None
    core_service_token: Optional[str] = None
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
BASE_DIR = Path(__file__).resolve().parents[2]
