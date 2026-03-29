from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = "sqlite:///./core.db"
    WHATSAPP_TOKEN_ENC_KEY: Optional[str] = None
    CORE_SERVICE_TOKEN: Optional[str] = None
    core_whatsapp_stub: bool = Field(False, env="CORE_WHATSAPP_STUB")
    UAZAPI_BASE_URL: Optional[str] = None
    UAZAPI_ADMIN_TOKEN: Optional[str] = None
    CRM_PUBLIC_BASE_URL: Optional[str] = None
    EXECUTORS_BASE_URL: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
BASE_DIR = Path(__file__).resolve().parent
