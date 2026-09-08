"""
image_description.py — Descrição de imagem via visão do GPT-4o-mini.

Extraído de spy_agent/media_processor.py para reuso fora do Agente Espião
(mesmo precedente de audio_transcription.py, extraído do mesmo arquivo para
uso no fluxo principal de inbound).
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_VISION_MODEL = "gpt-4o-mini"


def describe_image_from_url(media_url: str) -> str | None:
    """Envia a imagem ao gpt-4o-mini (visão) e retorna uma descrição."""
    if not _OPENAI_API_KEY:
        logger.warning("[image_description] OPENAI_API_KEY não configurada — análise de imagem impossível")
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
        logger.error("[image_description] erro na análise de imagem: %s", exc)
        return None
