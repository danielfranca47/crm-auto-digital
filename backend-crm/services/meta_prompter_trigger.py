"""
meta_prompter_trigger.py — Gatilho compartilhado de regeneração de prompt.

Usado por routes/knowledge.py (edição manual de objections_faq) e por
services/knowledge_ingest/ingest_worker.py (ingestão que cobre objections_faq).
"""
from __future__ import annotations

import logging
import os

import httpx

from core_client import fetch_core_ai_profile_resolve

logger = logging.getLogger(__name__)


def trigger_meta_prompter_for_knowledge(user_id: int) -> None:
    """Fire-and-forget: regenera os blocos de prompt após mudança em objections_faq."""
    base = os.getenv("EXECUTORS_BASE_URL", "").rstrip("/")
    token = os.getenv("CORE_SERVICE_TOKEN")
    if not base or not token:
        logger.debug("meta_prompter knowledge trigger ignorado: EXECUTORS_BASE_URL ou CORE_SERVICE_TOKEN ausente")
        return
    try:
        ai_profile = fetch_core_ai_profile_resolve(user_id)
    except Exception as exc:
        logger.warning("meta_prompter knowledge trigger: falha ao resolver ai_profile user_id=%s: %s", user_id, exc)
        return
    if not ai_profile:
        return
    url = f"{base}/api/meta-prompter/generate/{user_id}"
    headers = {"X-Service-Token": token, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, headers=headers, json={"ai_profile": ai_profile})
        if not resp.is_success:
            logger.warning("meta_prompter knowledge trigger falhou user_id=%s status=%s", user_id, resp.status_code)
    except Exception as exc:
        logger.warning("meta_prompter knowledge trigger erro user_id=%s: %s", user_id, exc)
