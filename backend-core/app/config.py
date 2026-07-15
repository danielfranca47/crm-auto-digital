from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    SECRET_KEY: str
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
    ADMIN_SECRET: Optional[str] = None
    # Email SMTP
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_TLS: bool = True
    # URL público do frontend-crm (usado em links de email — reset de senha, boas-vindas)
    CRM_FRONTEND_URL: Optional[str] = None
    # Google Maps API (used by agent-local proxy endpoint)
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    # Google Calendar OAuth2
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
BASE_DIR = Path(__file__).resolve().parent
