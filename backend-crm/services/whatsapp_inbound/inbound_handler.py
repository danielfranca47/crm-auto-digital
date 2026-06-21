"""Funções auxiliares para lidar com webhooks WhatsApp inbound (ETAPA 3)."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core_client import fetch_core_ai_profile_resolve, fetch_core_whatsapp_connection_resolve, fetch_core_whatsapp_token, send_whatsapp_direct
from database import get_connection
from services.audio_transcription import is_audio_type, transcribe_audio_from_url, download_audio_url_from_uazapi
from services.jobs_service import (
    TYPE_WHATSAPP_INBOUND,
    create_job,
    find_pending_inbound_job,
    update_inbound_job_accumulation,
)
from services.humanization import compute_reply_delay, compute_scheduled_at, scheduled_at_from_delay
from services.ai_orchestrator import (
    InboundEvent,
    build_context_bundle_from_inbound,
    decide_next_action,
    log_ai_decision,
)
from services.whatsapp_inbound.conversations import (
    get_conversations_count_for_month,
    get_month_key,
    try_register_conversation,
)
from services.whatsapp_inbound.phone import normalize_phone
from services.whatsapp_inbound.guardrail import (
    find_or_create_lead_by_phone,
    maybe_promote_lead_on_inbound,
)
from services.followup_state import stop_followup_on_inbound_reply


logger = logging.getLogger(__name__)


def _env_flag(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _disable_local_orchestrator() -> bool:
    raw = os.getenv("CRM_DISABLE_LOCAL_ORCHESTRATOR")
    if raw is None:
        return True
    return _env_flag(raw)


def _resolve_stub_user_id(phone_norm: str) -> int:
    stub_user = os.getenv("CRM_STUB_USER_ID")
    if stub_user:
        try:
            return int(stub_user)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail="CRM_STUB_USER_ID inválido") from exc

    with get_connection() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT user_id FROM leads WHERE phone = ? LIMIT 1",
            (phone_norm,),
        ).fetchone()
    if row and row["user_id"] is not None:
        return int(row["user_id"])

    raise HTTPException(
        status_code=400,
        detail="CRM_STUB_USER_ID não configurado e nenhum lead encontrado para o telefone",
    )


class InboundWebhookPayload(BaseModel):
    instance_id: str
    sender: str = Field(..., alias="from")
    message_text: Optional[str] = Field(None, alias="message_text")
    message: Optional[str] = Field(None, alias="message")
    body: Optional[str] = Field(None, alias="body")
    text: Optional[str] = Field(None, alias="text")
    message_id: Optional[str] = Field(None, alias="message_id")
    event_id: Optional[str] = Field(None, alias="event_id")
    timestamp: Optional[Any] = Field(None, alias="timestamp")
    provider: Optional[str] = None
    message_type: Optional[str] = None
    media_url: Optional[str] = None

    model_config = ConfigDict(extra="allow")

    def resolved_message_text(self) -> str:
        for candidate in (self.message_text, self.message, self.body, self.text):
            if candidate:
                return str(candidate)
        return ""

    def resolved_event_id(self) -> str:
        return str(self.message_id or self.event_id or "").strip()


def _mask_duplicate_error(exc: sqlite3.IntegrityError) -> bool:
    return "UNIQUE" in str(exc).upper()


def insert_inbound_event(
    conn: sqlite3.Connection,
    *,
    provider: str,
    instance_id: str,
    external_event_id: str,
    user_id: int,
) -> bool:
    """
    Tenta registrar o evento inbound. Retorna True se inseriu, False se já existia.
    """

    try:
        conn.execute(
            """
            INSERT INTO inbound_events (provider, instance_id, external_event_id, user_id)
            VALUES (?, ?, ?, ?)
            """,
            (provider, instance_id, external_event_id, user_id),
        )
        return True
    except sqlite3.IntegrityError as exc:  # idempotência
        if _mask_duplicate_error(exc):
            conn.rollback()
            return False
        raise


def save_inbound_message(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    body: str,
    user_id: int,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO messages (lead_id, channel, subject, body, model)
        VALUES (?, 'whatsapp', NULL, ?, 'inbound')
        """,
        (lead_id, body),
    )
    message_id = int(cur.lastrowid)
    cur.execute(
        """
        INSERT INTO prospection_logs (lead_id, channel, message_id, action, notes, user_id)
        VALUES (?, 'whatsapp', ?, 'inbound_received', NULL, ?)
        """,
        (lead_id, message_id, user_id),
    )
    return message_id


def build_job_payload(
    *,
    lead_id: int,
    user_id: int,
    instance_id: str,
    provider: str,
    phone: str,
    message_text: str,
    external_event_id: str,
    received_at: str,
) -> Dict[str, Any]:
    return {
        "lead_id": lead_id,
        "user_id": user_id,
        "instance_id": instance_id,
        "provider": provider,
        "phone": phone,
        "message_text": message_text,
        "message_id": external_event_id,
        "received_at": received_at,
    }


def _apply_media_fallback(
    user_id: int,
    instance_id: str,
    ai_profile: Dict[str, Any],
    phone: str,
    external_event_id: str,
) -> Dict[str, Any]:
    """
    Aplica o comportamento configurado em offer_pack.media_fallback quando o lead
    envia uma mídia não processável (áudio sem transcrição, vídeo, figurinha, etc.).
    """
    offer_pack = ai_profile.get("offer_pack") or {}
    if isinstance(offer_pack, str):
        import json as _json
        try:
            offer_pack = _json.loads(offer_pack) or {}
        except Exception:
            offer_pack = {}

    behavior = (offer_pack.get("media_fallback") or "ignorar").lower()
    msg = offer_pack.get("media_fallback_msg") or ""

    logger.info(
        "[media_fallback] user_id=%s behavior=%s instance=%s",
        user_id, behavior, instance_id,
    )

    if behavior == "ignorar":
        return {"status": "ignored", "reason": "media_fallback_ignore"}

    # "continuar" ou "pausar": enviar mensagem ao lead directamente (sem job queue)
    # whatsapp.send.local é processado pelo agent-local, não pelo executor — usar envio directo
    if msg:
        try:
            sent = send_whatsapp_direct(instance_id, phone, msg)
            if not sent:
                logger.warning("[media_fallback] falha no envio directo user_id=%s phone=%s", user_id, phone)
        except Exception as _exc:
            logger.error("[media_fallback] excepção no envio directo: %s", _exc)

    if behavior == "pausar":
        with get_connection() as _conn:
            _conn.execute(
                "UPDATE leads SET bot_disabled = 1 WHERE phone = ? AND user_id = ?",
                (phone, user_id),
            )
            _conn.commit()

    return {"status": "ok", "reason": f"media_fallback_{behavior}"}


def handle_inbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("is_group", False):
        return {"status": "ignored", "reason": "group_message"}

    parsed = InboundWebhookPayload(**payload)
    message_text = parsed.resolved_message_text()
    incoming_audio = is_audio_type(parsed.message_type)

    # Texto vazio é permitido para áudio (transcrição) e mídia inválida (vídeo, imagem, sticker)
    _incoming_invalid_media = (parsed.message_type or "").lower() in {
        "video", "image", "sticker", "reaction", "document",
        "videomessage", "imagemessage", "stickermessage",
    }
    if not message_text and not incoming_audio and not _incoming_invalid_media:
        raise HTTPException(status_code=400, detail="message_text obrigatório")

    external_event_id = parsed.resolved_event_id()
    if not external_event_id:
        raise HTTPException(status_code=400, detail="message_id/event_id obrigatório")

    phone_norm = normalize_phone(parsed.sender)
    if not phone_norm:
        raise HTTPException(status_code=400, detail="Telefone inválido")

    stub_enabled = _env_flag(os.getenv("CRM_WHATSAPP_STUB"))
    logger.info("whatsapp inbound stub=%s", stub_enabled)

    if stub_enabled:
        user_id = _resolve_stub_user_id(phone_norm)
        provider = parsed.provider or "uazapi"
        connection = {
            "user_id": user_id,
            "provider": provider,
            "connection_status": "active",
            "allow_orion": True,
            "max_ia_conversas_monthly": None,
        }
    else:
        connection = fetch_core_whatsapp_connection_resolve(parsed.instance_id)
        status = (connection.get("connection_status") or "").lower()
        if status and status != "active":
            raise HTTPException(status_code=403, detail="Conexão inativa")

        if connection.get("allow_orion") is False:
            raise HTTPException(status_code=403, detail="Plano não habilitado para Orion")

        provider = connection.get("provider") or parsed.provider or "uazapi"
        user_id = int(connection["user_id"])

    # ── Tratamento de áudio e mídia não-texto ──────────────────────────────────
    _AUDIO_TYPES = {"audio", "ptt", "myaudio", "audiomessage", "pttmessage"}
    _INVALID_MEDIA_TYPES = {"video", "image", "sticker", "reaction", "document"}

    if incoming_audio or (parsed.message_type and parsed.message_type.lower() in _INVALID_MEDIA_TYPES):
        _media_type = (parsed.message_type or "").lower()
        _is_audio = _media_type in _AUDIO_TYPES or incoming_audio

        if _is_audio:
            # Buscar AI Profile para verificar flag de transcrição
            _ai_profile_media: Dict[str, Any] = {}
            try:
                _ai_profile_media = fetch_core_ai_profile_resolve(user_id) or {}
            except Exception as _exc:
                logger.warning("[inbound_audio] falha ao buscar ai_profile user_id=%s: %s", user_id, _exc)

            if _ai_profile_media.get("audio_transcription_enabled"):
                # mmg.whatsapp.net (URL do webhook) requer autenticação da sessão WhatsApp.
                # Sempre usar UazAPI /message/download para obter URL pública acessível pelo Whisper.
                _audio_url = ""
                if external_event_id:
                    logger.info(
                        "[inbound_audio] obtendo URL pública via UazAPI download message_id=%s",
                        external_event_id,
                    )
                    _instance_token = fetch_core_whatsapp_token(parsed.instance_id)
                    if _instance_token:
                        _audio_url = download_audio_url_from_uazapi(_instance_token, external_event_id) or ""
                # Fallback: usar media_url do webhook (pode falhar se mmg.whatsapp.net exigir auth)
                if not _audio_url:
                    _audio_url = parsed.media_url or ""
                    if _audio_url:
                        logger.warning(
                            "[inbound_audio] usando media_url direto (download UazAPI falhou) message_id=%s",
                            external_event_id,
                        )

                # Transcrever áudio e usar como message_text
                _transcription = transcribe_audio_from_url(_audio_url)
                if _transcription:
                    message_text = f"[Áudio]: {_transcription}"
                    logger.info(
                        "[inbound_audio] transcrição concluída user_id=%s chars=%s",
                        user_id, len(_transcription),
                    )
                else:
                    logger.warning(
                        "[inbound_audio] transcrição falhou user_id=%s audio_url=%s — aplicando media_fallback",
                        user_id, _audio_url,
                    )
                    return _apply_media_fallback(user_id, parsed.instance_id, _ai_profile_media, phone_norm, external_event_id)
            else:
                return _apply_media_fallback(user_id, parsed.instance_id, _ai_profile_media, phone_norm, external_event_id)
        else:
            # Vídeo, figurinha, reação, documento
            _ai_profile_media = {}
            try:
                _ai_profile_media = fetch_core_ai_profile_resolve(user_id) or {}
            except Exception as _exc:
                logger.warning("[inbound_media] falha ao buscar ai_profile user_id=%s: %s", user_id, _exc)
            return _apply_media_fallback(user_id, parsed.instance_id, _ai_profile_media, phone_norm, external_event_id)

    if not message_text:
        raise HTTPException(status_code=400, detail="message_text vazio após processamento de mídia")
    # ──────────────────────────────────────────────────────────────────────────

    received_at = parsed.timestamp or datetime.utcnow().isoformat()
    received_iso = str(received_at).replace(" ", "T")
    month_key = get_month_key(received_iso)

    with get_connection() as conn:
        inserted = insert_inbound_event(
            conn,
            provider=provider,
            instance_id=parsed.instance_id,
            external_event_id=external_event_id,
            user_id=user_id,
        )
        if not inserted:
            return {"status": "duplicate", "lead_id": None, "job_id": None}

        consumed_conversation = try_register_conversation(
            conn,
            user_id=user_id,
            phone_e164=phone_norm,
            month_key=month_key,
            lead_id=None,
        )

        if consumed_conversation:
            limit = connection.get("max_ia_conversas_monthly")
            if limit is not None:
                total = get_conversations_count_for_month(
                    conn, user_id=user_id, month_key=month_key
                )
                if total > int(limit):
                    conn.rollback()
                    raise HTTPException(
                        status_code=403, detail="Limite de conversas Orion excedido"
                    )

        lead_id, created = find_or_create_lead_by_phone(
            conn,
            user_id=user_id,
            phone_norm=phone_norm,
            payload=payload,
        )
        if not created:
            maybe_promote_lead_on_inbound(conn, lead_id=lead_id, user_id=user_id)

        conn.execute(
            """
            UPDATE orion_conversations
            SET lead_id = COALESCE(lead_id, ?)
            WHERE user_id = ? AND phone_e164 = ? AND month_key = ?
            """,
            (lead_id, user_id, phone_norm, month_key),
        )
        save_inbound_message(conn, lead_id=lead_id, body=message_text, user_id=user_id)

        # Detetar e persistir idioma do lead (first-detect wins)
        try:
            from services.language_detector import detect_language as _detect_lang
            _detected = _detect_lang(message_text)
            if _detected:
                conn.execute(
                    "UPDATE leads SET detected_language = ? WHERE id = ? AND (detected_language IS NULL OR detected_language = '')",
                    (_detected, lead_id),
                )
        except Exception as _lang_exc:
            logger.debug("language_detector erro: %s", _lang_exc)

        followup_stopped = stop_followup_on_inbound_reply(
            conn,
            lead_id=lead_id,
            user_id=user_id,
            inbound_message_id=external_event_id,
        )
        if followup_stopped:
            conn.execute(
                "INSERT INTO notifications (user_id, lead_id, type) VALUES (?, ?, ?)",
                (user_id, lead_id, "followup_paused_by_reply"),
            )
        conn.commit()

    _ai_profile_for_delay: Optional[Dict[str, Any]] = None
    try:
        event = InboundEvent(
            user_id=user_id,
            lead_id=lead_id,
            channel="whatsapp",
            message_text=message_text,
            received_at=received_iso,
            phone=phone_norm,
            message_id=external_event_id,
            instance_id=parsed.instance_id,
            provider=provider,
        )
        bundle = build_context_bundle_from_inbound(event)
        _ai_profile_for_delay = bundle.ai_profile
        if _disable_local_orchestrator():
            logger.info(
                "crm_inbound delegated_to_executor lead_id=%s user_id=%s message_id=%s",
                lead_id,
                user_id,
                external_event_id,
            )
        else:
            decision = decide_next_action(bundle)
            ai_profile_status = bundle.metadata.get("ai_profile_status", "ok")
            if ai_profile_status != "ok":
                decision = {
                    **decision,
                    "reason": f"{decision.get('reason')}|ai_profile_{ai_profile_status}_fallback",
                }
            template_key = (
                bundle.ai_profile.get("template_key")
                if bundle.ai_profile
                else bundle.playbook.get("template_key")
            ) or "sdr_padrao"
            log_ai_decision(
                lead_id=lead_id,
                user_id=user_id,
                decision=decision,
                template_key=template_key,
                received_at=received_iso,
                message_id=external_event_id,
            )
    except HTTPException:
        raise
    except Exception as exc:  # fail-safe: não bloquear webhook
        logger.exception("Falha ao orquestrar decisão de IA", exc_info=exc)

    with get_connection() as _conn_check:
        _bot_row = _conn_check.execute(
            "SELECT bot_disabled, bot_disabled_reason FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
        _bot_disabled_reason = _bot_row["bot_disabled_reason"] if _bot_row else None
        _meeting_management_enabled = bool((_ai_profile_for_delay or {}).get("meeting_management_enabled", True))
        _meeting_management_open = (
            _bot_disabled_reason == "meeting_scheduled" and _meeting_management_enabled
        )
        if (
            _bot_row
            and int(_bot_row["bot_disabled"] or 0) == 1
            and not _meeting_management_open
        ):
            logger.info(
                "inbound_bot_disabled_skip lead_id=%s user_id=%s reason=bot_disabled",
                lead_id,
                user_id,
            )
            return {"status": "skipped", "lead_id": lead_id, "job_id": None, "reason": "bot_disabled"}

    with get_connection() as _conn_delay:
        _msg_row = _conn_delay.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        _msg_count = int(_msg_row["cnt"]) if _msg_row else 0
    _is_first_message = _msg_count <= 1

    _buffer_secs = int((_ai_profile_for_delay or {}).get("multi_message_buffer_seconds") or 0)

    if _buffer_secs > 0:
        with get_connection() as _conn_buf:
            existing_job = find_pending_inbound_job(_conn_buf, lead_id, user_id)
            if existing_job:
                import json as _json
                old_payload = _json.loads(existing_job["payload"])
                accumulated_text = old_payload.get("message_text", "") + "\n" + message_text
                new_scheduled_at = datetime.utcnow() + timedelta(seconds=_buffer_secs)
                update_inbound_job_accumulation(_conn_buf, existing_job["id"], accumulated_text, new_scheduled_at)
                _conn_buf.commit()
                logger.info(
                    "inbound_buffered lead_id=%s user_id=%s job_id=%s buffer_secs=%s",
                    lead_id, user_id, existing_job["id"], _buffer_secs,
                )
                return {"status": "buffered", "lead_id": lead_id, "job_id": existing_job["id"]}

        _scheduled_at = datetime.utcnow() + timedelta(seconds=_buffer_secs)
    else:
        _scheduled_at = None
        if _ai_profile_for_delay:
            try:
                _scheduled_at = compute_scheduled_at(_ai_profile_for_delay, _is_first_message)
            except Exception as _delay_exc:
                logger.debug("humanization scheduled_at error (fallback None): %s", _delay_exc)

    job_payload = build_job_payload(
        lead_id=lead_id,
        user_id=user_id,
        instance_id=parsed.instance_id,
        provider=provider,
        phone=phone_norm,
        message_text=message_text,
        external_event_id=external_event_id,
        received_at=received_iso,
    )
    job = create_job(
        job_type=TYPE_WHATSAPP_INBOUND,
        payload=job_payload,
        user_id=user_id,
        scheduled_at=_scheduled_at,
    )
    return {"status": "accepted", "lead_id": lead_id, "job_id": job.get("id")}
