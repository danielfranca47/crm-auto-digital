"""Public-facing endpoints for website integrations."""
from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from typing import Dict, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from database import get_connection

router = APIRouter(prefix="/public", tags=["Public"])


class PublicLeadPayload(BaseModel):
    """Payload accepted by the public lead creation endpoint."""

    fullName: str = Field(..., min_length=1)
    email: EmailStr
    phone: Optional[str] = None
    message: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None


class EmailSettings(BaseModel):
    host: str
    port: int
    user: Optional[str]
    password: Optional[str]
    sender: EmailStr


def _get_form_token() -> str:
    token = os.getenv("FORM_TOKEN")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FORM_TOKEN não configurado no servidor.",
        )
    return token


def _load_email_settings() -> EmailSettings:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("EMAIL_FROM")

    if not host or not sender:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configurações de SMTP ausentes.",
        )

    return EmailSettings(host=host, port=port, user=user, password=password, sender=sender)  # type: ignore[arg-type]


def _build_email(subject: str, body: str, *, sender: str, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    return msg


def _send_email(msg: EmailMessage, settings: EmailSettings) -> None:
    try:
        with smtplib.SMTP(settings.host, settings.port, timeout=30) as server:
            try:
                server.starttls()
            except smtplib.SMTPException:
                # Alguns servidores podem não suportar STARTTLS no porto configurado.
                pass

            if settings.user and settings.password:
                server.login(settings.user, settings.password)

            server.send_message(msg)
    except Exception as exc:  # pragma: no cover - apenas log/propagação
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível enviar os e-mails de notificação.",
        ) from exc


def _prepare_custom_message(utm_data: Dict[str, Optional[str]]) -> Optional[str]:
    utm_clean = {k: v for k, v in utm_data.items() if v}
    if not utm_clean:
        return None
    return json.dumps({"utm": utm_clean}, ensure_ascii=False)


@router.post("/leads", status_code=status.HTTP_201_CREATED)
def create_public_lead(
    payload: PublicLeadPayload,
    x_form_token: str = Header(alias="x-form-token"),
):
    expected_token = _get_form_token()
    if x_form_token != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou ausente.")

    utm_payload = {
        "utm_source": payload.utm_source,
        "utm_medium": payload.utm_medium,
        "utm_campaign": payload.utm_campaign,
        "utm_term": payload.utm_term,
        "utm_content": payload.utm_content,
    }
    custom_message = _prepare_custom_message(utm_payload)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO leads (
                companyName,
                contactName,
                phone,
                email,
                origin,
                category,
                customMessage,
                observations,
                priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.fullName,
                payload.fullName,
                payload.phone,
                payload.email,
                "Formulário Website",
                "to-prospect",
                custom_message,
                payload.message,
                1,
            ),
        )

        lead_id = cursor.lastrowid

        email_settings = _load_email_settings()
        admin_recipient = os.getenv("EMAIL_TO")
        if not admin_recipient:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="EMAIL_TO não configurado.",
            )

        admin_body_lines = [
            "Nova lead criada pelo formulário do site:",
            f"Nome: {payload.fullName}",
            f"Email: {payload.email}",
            f"Telefone: {payload.phone or '-'}",
            f"Mensagem: {payload.message or '-'}",
        ]
        if custom_message:
            admin_body_lines.append(f"UTMs: {custom_message}")

        admin_msg = _build_email(
            subject="Nova lead capturada pelo site",
            body="\n".join(admin_body_lines),
            sender=email_settings.sender,
            to=admin_recipient,
        )

        lead_msg = _build_email(
            subject="Recebemos sua mensagem",
            body=(
                "Olá, {name}!\n\nRecebemos o seu contato e entraremos em contato em breve.\n"
                "Se precisar falar conosco com urgência, responda a este e-mail.\n\nAbraços,\nDaniel França"
            ).format(name=payload.fullName),
            sender=email_settings.sender,
            to=payload.email,
        )

        _send_email(admin_msg, email_settings)
        _send_email(lead_msg, email_settings)

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao criar lead.") from exc
    finally:
        conn.close()

    return {"id": lead_id, "status": "created"}
