"""
media_processor.py — Processamento assíncrono de mídia para o Agente Espião.

Executado via job spy.media.process:
- Áudio  → transcrição via OpenAI Whisper (audio/transcriptions)
- Imagem → descrição via gpt-4o-mini com visão
"""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_VISION_MODEL = "gpt-4o-mini"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _transcribe_audio(media_url: str) -> str | None:
    """Baixa o áudio e envia para o Whisper. Retorna o texto transcrito."""
    if not _OPENAI_API_KEY:
        logger.warning("[spy:media] OPENAI_API_KEY não configurada — transcrição impossível")
        return None

    try:
        # Baixa o arquivo de mídia
        with httpx.Client(timeout=60) as client:
            resp = client.get(media_url)
            resp.raise_for_status()
            audio_bytes = resp.content
            content_type = resp.headers.get("content-type", "audio/ogg")
    except Exception as exc:
        logger.error("[spy:media] falha ao baixar áudio url=%s: %s", media_url, exc)
        return None

    # Determina extensão pelo content-type
    ext_map = {
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/webm": ".webm",
    }
    ext = next((v for k, v in ext_map.items() if k in content_type), ".ogg")

    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {_OPENAI_API_KEY}"},
                    data={"model": "whisper-1", "language": "pt"},
                    files={"file": (f"audio{ext}", audio_file, content_type)},
                )
                resp.raise_for_status()
                result = resp.json()
                return result.get("text", "").strip() or None
    except Exception as exc:
        logger.error("[spy:media] erro na transcrição Whisper: %s", exc)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _describe_image(media_url: str) -> str | None:
    """Envia a imagem ao gpt-4o-mini (visão) e retorna uma descrição."""
    if not _OPENAI_API_KEY:
        logger.warning("[spy:media] OPENAI_API_KEY não configurada — análise de imagem impossível")
        return None

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {_OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _VISION_MODEL,
                    "max_tokens": 300,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Descreva esta imagem no contexto de uma conversa comercial de vendas. "
                                        "Seja objetivo e conciso. Se houver texto na imagem, transcreva-o."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": media_url, "detail": "low"},
                                },
                            ],
                        }
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip() or None
    except Exception as exc:
        logger.error("[spy:media] erro na análise de imagem: %s", exc)
        return None


def process_spy_media_job(payload: Dict[str, Any]) -> None:
    """
    Processa um job spy.media.process.

    Payload esperado:
      spy_msg_id (int), user_id (int), message_type (str), media_url (str)
    """
    from database import get_connection

    spy_msg_id: int = int(payload.get("spy_msg_id", 0))
    message_type: str = payload.get("message_type", "")
    media_url: str = payload.get("media_url", "")

    if not spy_msg_id or not media_url:
        logger.warning("[spy:media] payload inválido: %s", payload)
        return

    transcription: str | None = None

    if message_type == "audio":
        transcription = _transcribe_audio(media_url)
        logger.info("[spy:media] transcrição áudio spy_msg_id=%s: %s chars", spy_msg_id, len(transcription or ""))
    elif message_type == "image":
        transcription = _describe_image(media_url)
        logger.info("[spy:media] descrição imagem spy_msg_id=%s: %s chars", spy_msg_id, len(transcription or ""))
    else:
        logger.warning("[spy:media] tipo não suportado: %s", message_type)
        return

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE spy_agent_messages SET transcription = ?, processed_at = ? WHERE id = ?",
            (transcription, _now_utc_iso(), spy_msg_id),
        )
        conn.commit()
    finally:
        conn.close()
