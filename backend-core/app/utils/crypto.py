"""Utility helpers for encrypting/decrypting provider secrets at rest."""
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class SecretEncryptionError(RuntimeError):
    """Raised when encryption configuration is missing or decryption fails."""


_DEF_ERROR = "WHATSAPP_TOKEN_ENC_KEY is not configured"


def _get_fernet() -> Fernet:
    key = settings.WHATSAPP_TOKEN_ENC_KEY
    if not key:
        raise SecretEncryptionError(_DEF_ERROR)
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    if plain is None:
        raise ValueError("Secret value cannot be None")
    fernet = _get_fernet()
    return fernet.encrypt(plain.encode()).decode()


def decrypt_secret(enc: str) -> str:
    fernet = _get_fernet()
    try:
        return fernet.decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        raise SecretEncryptionError("Failed to decrypt secret") from exc
