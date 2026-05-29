"""
audio_transcription.py — Transcrição de áudio via OpenAI Whisper para o pipeline inbound.

Extraído de spy_agent/media_processor.py para uso no fluxo principal de inbound
quando audio_transcription_enabled está ativo no AI Profile do usuário.
"""
from __future__ import annotations

import logging
import os
import tempfile

import httpx

logger = logging.getLogger(__name__)

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_UAZAPI_BASE_URL = os.getenv("UAZAPI_BASE_URL", "https://free.uazapi.com").rstrip("/")

_CONTENT_TYPE_EXT = {
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/x-m4a": ".m4a",
}

_AUDIO_MESSAGE_TYPES = {"audio", "ptt", "myaudio", "audiomessage", "pttmessage"}


def is_audio_type(message_type: str | None) -> bool:
    return (message_type or "").lower().strip() in _AUDIO_MESSAGE_TYPES


def download_audio_url_from_uazapi(instance_token: str, message_id: str) -> str | None:
    """Chama POST {uazapi}/message/download para obter a URL pública do áudio de um PTT recebido.
    A UazAPI não inclui fileURL no webhook de PTT — esta chamada é necessária antes da transcrição.
    Retorna a fileURL ou None em caso de falha.
    """
    if not instance_token or not message_id:
        logger.warning("[uazapi_download] token ou message_id ausente")
        return None

    url = f"{_UAZAPI_BASE_URL}/message/download"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                headers={"token": instance_token},
                json={"id": message_id, "return_link": True, "generate_mp3": True},
            )
            resp.raise_for_status()
            data = resp.json()
            file_url = data.get("fileURL") or data.get("url")
            if file_url:
                logger.info("[uazapi_download] fileURL obtido message_id=%s", message_id)
                return file_url
            logger.warning("[uazapi_download] resposta sem fileURL message_id=%s data=%s", message_id, str(data)[:200])
            return None
    except Exception as exc:
        logger.error("[uazapi_download] falha message_id=%s: %s", message_id, exc)
        return None


def transcribe_audio_from_path(file_path: str, language: str = "pt") -> str | None:
    """
    Transcreve áudio a partir de um caminho local via OpenAI Whisper.
    Usado pelo playground (evita round-trip HTTP ao contrário de transcribe_audio_from_url).
    Retorna o texto transcrito ou None em caso de falha.
    """
    if not _OPENAI_API_KEY:
        logger.warning("[audio_transcription] OPENAI_API_KEY não configurada — transcrição impossível")
        return None

    if not file_path or not os.path.exists(file_path):
        logger.warning("[audio_transcription] file_path inválido ou não encontrado: %s", file_path)
        return None

    ext = os.path.splitext(file_path)[1].lstrip(".") or "ogg"
    content_type = f"audio/{ext}"

    try:
        with open(file_path, "rb") as audio_file:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {_OPENAI_API_KEY}"},
                    data={"model": "whisper-1", "language": language},
                    files={"file": (f"audio.{ext}", audio_file, content_type)},
                )
                resp.raise_for_status()
                result = resp.json()
                text = result.get("text", "").strip()
                if not text:
                    logger.warning("[audio_transcription] Whisper retornou texto vazio path=%s", file_path)
                    return None
                logger.info("[audio_transcription] transcrição concluída chars=%s", len(text))
                return text
    except Exception as exc:
        logger.error("[audio_transcription] erro na transcrição Whisper path=%s: %s", file_path, exc)
        return None


def transcribe_audio_from_url(media_url: str, language: str = "pt") -> str | None:
    """
    Baixa o áudio de media_url e transcreve via OpenAI Whisper.
    Retorna o texto transcrito ou None em caso de falha.
    """
    if not _OPENAI_API_KEY:
        logger.warning("[audio_transcription] OPENAI_API_KEY não configurada — transcrição impossível")
        return None

    if not media_url:
        logger.warning("[audio_transcription] media_url vazia — transcrição impossível")
        return None

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.get(media_url)
            resp.raise_for_status()
            audio_bytes = resp.content
            content_type = resp.headers.get("content-type", "audio/ogg").split(";")[0].strip()
    except Exception as exc:
        logger.error("[audio_transcription] falha ao baixar áudio url=%s: %s", media_url, exc)
        return None

    ext = _CONTENT_TYPE_EXT.get(content_type, ".ogg")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {_OPENAI_API_KEY}"},
                    data={"model": "whisper-1", "language": language},
                    files={"file": (f"audio{ext}", audio_file, content_type)},
                )
                resp.raise_for_status()
                result = resp.json()
                text = result.get("text", "").strip()
                if not text:
                    logger.warning("[audio_transcription] Whisper retornou texto vazio url=%s", media_url)
                    return None
                logger.info("[audio_transcription] transcrição concluída chars=%s", len(text))
                return text
    except Exception as exc:
        logger.error("[audio_transcription] erro na transcrição Whisper: %s", exc)
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
