"""Serviço de dossiê/briefing pré-reunião para o operador."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core_client import fetch_core_ai_profile_resolve
from database import get_connection
from services.jobs_service import TYPE_WHATSAPP_APPOINTMENT_BRIEFING, TYPE_WHATSAPP_SEND, create_job
from services.qualification_state import get_qualification_state

logger = logging.getLogger(__name__)

_SCORE_LABEL = {0: "❌ Ausente", 1: "⚠️ Fraco", 2: "🔶 Médio", 3: "✅ Forte"}

_SCORE_FIELD_LABELS = {
    "power_score": "Poder de decisão",
    "priority_score": "Urgência / prioridade",
    "price_score": "Orçamento disponível",
    "timing_score": "Prazo definido",
}


def _fetch_lead(conn, lead_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def _fetch_recent_messages(lead_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT channel, body, model, createdAt
            FROM messages
            WHERE lead_id = ?
            ORDER BY createdAt DESC
            LIMIT ?
            """,
            (lead_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def _fetch_appointment(conn, appointment_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def _format_score_bar(score: int, max_score: int = 3) -> str:
    filled = "█" * score
    empty = "░" * (max_score - score)
    return f"{filled}{empty} {score}/{max_score}"


def _build_briefing_message(
    lead: Dict[str, Any],
    qual_state: Dict[str, Any],
    messages: List[Dict[str, Any]],
    appointment: Optional[Dict[str, Any]],
) -> str:
    lines: List[str] = []

    lines.append("📋 *DOSSIÊ PRÉ-REUNIÃO*")
    lines.append("─" * 30)

    # Dados do lead
    name = lead.get("contactName") or lead.get("companyName") or "Sem nome"
    company = lead.get("companyName") or ""
    phone = lead.get("phone") or "Não informado"
    email = lead.get("email") or "Não informado"
    origin = lead.get("origin") or "inbound"
    origin_label = "Inbound (veio te procurar)" if origin in ("inbound", "WhatsApp", None) else "Outbound (foi abordado)"
    category = lead.get("category") or "—"

    lines.append(f"👤 *Lead:* {name}")
    if company and company != name:
        lines.append(f"🏢 *Empresa:* {company}")
    lines.append(f"📱 *Telefone:* {phone}")
    lines.append(f"✉️ *Email:* {email}")
    lines.append(f"🔀 *Origem:* {origin_label}")
    lines.append(f"📂 *Estágio:* {category}")

    # Appointment
    if appointment:
        start_at = str(appointment.get("start_at") or "").replace("T", " ")[:16]
        apt_title = appointment.get("title") or "Reunião"
        lines.append("")
        lines.append(f"📅 *Reunião:* {apt_title}")
        lines.append(f"🕐 *Horário:* {start_at}")
        if appointment.get("location"):
            lines.append(f"📍 *Local:* {appointment['location']}")

    # Score dos 4Ps
    data_json = qual_state.get("data_json") or {}
    total_score = qual_state.get("qualification_total_score") or 0
    has_scores = any(k in qual_state for k in _SCORE_FIELD_LABELS)
    if has_scores or total_score:
        lines.append("")
        lines.append(f"🎯 *Score de Qualificação: {total_score}/12*")
        for field, label in _SCORE_FIELD_LABELS.items():
            score = qual_state.get(field) or 0
            lines.append(f"  • {label}: {_format_score_bar(score)} {_SCORE_LABEL.get(score, '')}")

    # Dados de qualificação coletados
    qual_fields = {
        "urgency": "Urgência",
        "budget_or_price_acceptance": "Orçamento",
        "decision_role": "Papel de decisão",
        "availability_window": "Disponibilidade",
        "main_pain": "Dor principal",
        "current_solution": "Solução atual",
        "team_size": "Tamanho da equipe",
        "revenue_range": "Faixa de receita",
    }
    filled_qual = {label: data_json[key] for key, label in qual_fields.items() if data_json.get(key)}
    if filled_qual:
        lines.append("")
        lines.append("📊 *Qualificação coletada:*")
        for label, value in filled_qual.items():
            lines.append(f"  • {label}: {value}")

    # Observações do operador
    observations = lead.get("observations") or lead.get("customMessage")
    if observations:
        lines.append("")
        lines.append(f"📝 *Nota do operador:*\n{observations}")

    # Resumo da conversa (últimas mensagens)
    if messages:
        lines.append("")
        lines.append(f"💬 *Últimas {len(messages)} mensagens:*")
        for msg in messages[-5:]:
            role = "🤖" if msg.get("model") else "👤"
            body = str(msg.get("body") or "").strip()
            if len(body) > 120:
                body = body[:120] + "…"
            lines.append(f"  {role} {body}")

    lines.append("")
    lines.append("─" * 30)
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M") + " UTC"
    lines.append(f"⏱️ Gerado em: {now_str}")

    return "\n".join(lines)


def generate_and_send_briefing(
    *,
    lead_id: int,
    user_id: int,
    appointment_id: Optional[int] = None,
) -> None:
    """Gera o dossiê do lead e envia para o operador via WhatsApp ou notificação interna."""
    try:
        ai_profile = fetch_core_ai_profile_resolve(user_id) or {}
    except Exception:
        ai_profile = {}

    briefing_enabled = ai_profile.get("briefing_enabled")
    # None interpreta como True (default ativo)
    if briefing_enabled is False:
        logger.info("briefing_disabled user_id=%s lead_id=%s", user_id, lead_id)
        return

    briefing_channel = ai_profile.get("briefing_channel") or "whatsapp"
    operator_whatsapp = ai_profile.get("operator_whatsapp")

    with get_connection() as conn:
        lead = _fetch_lead(conn, lead_id)
        appointment = _fetch_appointment(conn, appointment_id) if appointment_id else None

    if not lead:
        logger.warning("briefing_lead_not_found lead_id=%s", lead_id)
        return

    qual_state = get_qualification_state(lead_id) or {}
    messages = _fetch_recent_messages(lead_id, limit=10)

    briefing_text = _build_briefing_message(lead, qual_state, messages, appointment)

    if briefing_channel == "whatsapp":
        if not operator_whatsapp:
            logger.warning(
                "briefing_no_operator_whatsapp user_id=%s lead_id=%s — briefing não enviado",
                user_id,
                lead_id,
            )
            _save_internal_notification(lead_id=lead_id, user_id=user_id, text=briefing_text)
            return

        try:
            create_job(
                job_type=TYPE_WHATSAPP_SEND,
                payload={
                    "lead_id": lead_id,
                    "user_id": user_id,
                    "appointment_id": appointment_id,
                    "phone": operator_whatsapp,
                    "message_text": briefing_text,
                    "briefing": True,
                },
                user_id=user_id,
            )
            logger.info(
                "briefing_job_enqueued lead_id=%s user_id=%s operator=%s",
                lead_id,
                user_id,
                operator_whatsapp,
            )
        except Exception as exc:
            logger.error("briefing_send_failed lead_id=%s error=%s", lead_id, exc)
    else:
        _save_internal_notification(lead_id=lead_id, user_id=user_id, text=briefing_text)


def _save_internal_notification(*, lead_id: int, user_id: int, text: str) -> None:
    """Salva o briefing como notificação interna na tabela notifications (se existir)."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO notifications (user_id, lead_id, type, body, created_at)
                VALUES (?, ?, 'appointment_briefing', ?, CURRENT_TIMESTAMP)
                """,
                (user_id, lead_id, text),
            )
            conn.commit()
        logger.info("briefing_internal_notification_saved lead_id=%s user_id=%s", lead_id, user_id)
    except Exception as exc:
        logger.warning("briefing_internal_notification_failed lead_id=%s error=%s", lead_id, exc)


def schedule_briefing_job(
    *,
    lead_id: int,
    user_id: int,
    appointment_id: int,
    appointment_start_at: datetime,
    lead_time_minutes: int = 120,
) -> None:
    """Agenda o job de briefing para `lead_time_minutes` antes da reunião."""
    from datetime import timedelta

    send_at = appointment_start_at - timedelta(minutes=lead_time_minutes)
    if send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)
    if send_at <= now_utc:
        logger.info(
            "briefing_job_skipped lead_id=%s appointment_id=%s send_at=%s (already past)",
            lead_id,
            appointment_id,
            send_at.isoformat(),
        )
        return

    try:
        create_job(
            job_type=TYPE_WHATSAPP_APPOINTMENT_BRIEFING,
            payload={
                "lead_id": lead_id,
                "user_id": user_id,
                "appointment_id": appointment_id,
                "appointment_start_at": appointment_start_at.isoformat(),
            },
            scheduled_at=send_at,
            user_id=user_id,
        )
        logger.info(
            "briefing_job_scheduled lead_id=%s appointment_id=%s send_at=%s",
            lead_id,
            appointment_id,
            send_at.isoformat(),
        )
    except Exception as exc:
        logger.warning(
            "briefing_job_schedule_failed lead_id=%s appointment_id=%s error=%s",
            lead_id,
            appointment_id,
            exc,
        )


def schedule_briefing_job_for_appointment(
    *,
    lead_id: int,
    user_id: int,
    appointment_id: int,
    appointment_start_at: datetime,
) -> None:
    """Resolve briefing_enabled/briefing_lead_time do AI Profile e agenda o job.

    Compartilhado por routes/appointments.py e routes/leads.py — os dois pontos de
    entrada para criar/editar um compromisso.
    """
    try:
        ai_profile = fetch_core_ai_profile_resolve(user_id) or {}
    except Exception:
        ai_profile = {}

    if ai_profile.get("briefing_enabled") is False:
        return

    lead_time = ai_profile.get("briefing_lead_time") or 120
    schedule_briefing_job(
        lead_id=lead_id,
        user_id=user_id,
        appointment_id=appointment_id,
        appointment_start_at=appointment_start_at,
        lead_time_minutes=int(lead_time),
    )
