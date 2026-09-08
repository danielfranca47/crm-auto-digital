"""
media_worker.py — Worker interno para processar jobs collab_monitor.media.process.

Executado como loop em background no backend-crm (app.py), mesmo padrão de
services/spy_agent/spy_media_worker.py. Transcreve áudio (Whisper) ou
descreve imagem (visão) de mensagens de leads monitorados, atualiza
messages.body e, se a mensagem for do próprio lead (from_me=False), enfileira
a reclassificação de estágio — só agora existe texto real para classificar.

Nunca chama orchestrator/decision_engine/guardrail do pipeline real — mesmo
princípio de isolamento de monitor_inbound_handler.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core_client import fetch_core_ai_profile_resolve, fetch_core_whatsapp_token
from database import get_connection
from services.audio_transcription import download_audio_url_from_uazapi, transcribe_audio_from_url
from services.image_description import describe_image_from_url
from services.jobs_service import TYPE_COLLAB_MONITOR_CLASSIFY, TYPE_COLLAB_MONITOR_MEDIA, create_job

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5

_AUDIO_TRANSCRIPTION_DISABLED_PLACEHOLDER = "[Áudio] (transcrição desativada nas configurações da conta)"
_AUDIO_TRANSCRIPTION_FAILED_PLACEHOLDER = "[Áudio] (transcrição indisponível)"
_IMAGE_DESCRIPTION_FAILED_PLACEHOLDER = "[Imagem] (descrição indisponível)"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _process_audio(*, instance_id: str, user_id: int, media_url: str, external_message_id: str) -> tuple[str, Optional[str]]:
    """Transcreve áudio via Whisper — gate pelo mesmo toggle de conta do pipeline real.

    Retorna (body, media_url_resolvido_ou_None) — a URL resolvida via UazAPI é
    mais confiável para uso futuro (ex.: tocar o áudio numa tela dedicada) do
    que a URL crua do webhook, que pode exigir autenticação da sessão.
    """
    ai_profile: Dict[str, Any] = {}
    try:
        ai_profile = fetch_core_ai_profile_resolve(user_id) or {}
    except Exception as exc:
        logger.warning("[collab_monitor:media_worker] falha ao buscar ai_profile user_id=%s: %s", user_id, exc)

    if not ai_profile.get("audio_transcription_enabled"):
        return _AUDIO_TRANSCRIPTION_DISABLED_PLACEHOLDER, None

    # mmg.whatsapp.net (URL do webhook) costuma exigir autenticação da sessão —
    # sempre tenta resolver a URL pública via UazAPI /message/download primeiro
    # (mesmo caminho do pipeline real, services/whatsapp_inbound/inbound_handler.py).
    resolved_url = ""
    if external_message_id:
        instance_token = fetch_core_whatsapp_token(instance_id)
        if instance_token:
            resolved_url = download_audio_url_from_uazapi(instance_token, external_message_id) or ""

    audio_url = resolved_url or media_url
    transcription = transcribe_audio_from_url(audio_url) if audio_url else None
    if not transcription:
        return _AUDIO_TRANSCRIPTION_FAILED_PLACEHOLDER, (resolved_url or None)
    return f"[Áudio]: {transcription}", (resolved_url or None)


def _process_image(media_url: str) -> str:
    description = describe_image_from_url(media_url) if media_url else None
    if not description:
        return _IMAGE_DESCRIPTION_FAILED_PLACEHOLDER
    return f"[Imagem]: {description}"


def process_collab_monitor_media_job(payload: Dict[str, Any]) -> None:
    """
    Processa um job collab_monitor.media.process.

    Payload esperado:
      message_id (int), lead_id (int), instance_id (str), user_id (int),
      message_type (audio|image), media_url (str), external_message_id (str),
      from_me (bool)
    """
    message_id = int(payload.get("message_id", 0))
    lead_id = int(payload.get("lead_id", 0))
    instance_id = payload.get("instance_id") or ""
    user_id = int(payload.get("user_id", 0))
    message_type = (payload.get("message_type") or "").lower()
    media_url = payload.get("media_url") or ""
    external_message_id = payload.get("external_message_id") or ""
    from_me = bool(payload.get("from_me", False))

    if not message_id or not lead_id:
        logger.warning("[collab_monitor:media_worker] payload inválido: %s", payload)
        return

    resolved_media_url: Optional[str] = None
    if message_type == "audio":
        body, resolved_media_url = _process_audio(
            instance_id=instance_id,
            user_id=user_id,
            media_url=media_url,
            external_message_id=external_message_id,
        )
    elif message_type == "image":
        body = _process_image(media_url)
    else:
        logger.warning("[collab_monitor:media_worker] tipo não suportado: %s", message_type)
        return

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE messages SET body = ?, media_url = COALESCE(?, media_url) WHERE id = ?",
            (body, resolved_media_url, message_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info(
        "[collab_monitor:media_worker] mensagem processada message_id=%s type=%s chars=%s",
        message_id,
        message_type,
        len(body or ""),
    )

    if not from_me:
        create_job(
            job_type=TYPE_COLLAB_MONITOR_CLASSIFY,
            payload={"lead_id": lead_id, "user_id": user_id},
            user_id=user_id,
        )


def process_pending_collab_monitor_media_jobs(batch_size: int = _BATCH_SIZE) -> Dict[str, int]:
    """
    Processa até `batch_size` jobs collab_monitor.media.process pendentes.
    Retorna contadores: processed, failed.
    """
    now = _now_utc_iso()
    processed = 0
    failed = 0

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, payload
              FROM jobs
             WHERE type = ?
               AND status = 'pending'
               AND attempts < 3
               AND (scheduled_at IS NULL OR scheduled_at <= ?)
             ORDER BY created_at ASC
             LIMIT ?
            """,
            (TYPE_COLLAB_MONITOR_MEDIA, now, batch_size),
        ).fetchall()

        for row in rows:
            job_id = int(row["id"])

            # Tenta adquirir o job (CAS: muda de pending → in_progress só se ainda pending)
            updated = conn.execute(
                """
                UPDATE jobs
                   SET status = 'in_progress',
                       started_at = ?,
                       attempts = attempts + 1,
                       updated_at = ?
                 WHERE id = ? AND status = 'pending'
                """,
                (now, now, job_id),
            ).rowcount
            conn.commit()

            if not updated:
                continue

            payload: Dict[str, Any] = {}
            try:
                payload = json.loads(row["payload"] or "{}")
                process_collab_monitor_media_job(payload)
                conn.execute(
                    """
                    UPDATE jobs
                       SET status = 'completed',
                           completed_at = ?,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (now, now, job_id),
                )
                processed += 1
                logger.info("[collab_monitor:media_worker] job concluído job_id=%d", job_id)
            except Exception as exc:
                logger.error("[collab_monitor:media_worker] falha job_id=%d: %s", job_id, exc)
                attempts_row = conn.execute(
                    "SELECT attempts FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
                attempts = int(attempts_row["attempts"]) if attempts_row else 3
                new_status = "failed" if attempts >= 3 else "pending"
                conn.execute(
                    """
                    UPDATE jobs
                       SET status = ?,
                           error = ?,
                           completed_at = CASE WHEN ? = 'failed' THEN ? ELSE NULL END,
                           started_at = CASE WHEN ? = 'pending' THEN NULL ELSE started_at END,
                           updated_at = ?
                     WHERE id = ?
                    """,
                    (new_status, str(exc)[:500], new_status, now, new_status, now, job_id),
                )
                failed += 1
            conn.commit()
    finally:
        conn.close()

    return {"processed": processed, "failed": failed}
