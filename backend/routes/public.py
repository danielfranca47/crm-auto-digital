"""Public-facing endpoints for website integrations."""
from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Dict, Optional

from fastapi import APIRouter, Header, HTTPException, status, BackgroundTasks
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

def _notify_admin_and_autoreply(payload: PublicLeadPayload, lead_id: int, settings: EmailSettings, admin_recipient: str) -> None:
    # monta os corpos
    admin_body_lines = [
        "Nova lead criada pelo formulário do site:",
        f"Nome: {payload.fullName}",
        f"Email: {payload.email}",
        f"Telefone: {payload.phone or '-'}",
        f"Mensagem: {payload.message or '-'}",
        f"Lead ID: {lead_id}",
    ]
    utm_payload = {
        "utm_source": payload.utm_source,
        "utm_medium": payload.utm_medium,
        "utm_campaign": payload.utm_campaign,
        "utm_term": payload.utm_term,
        "utm_content": payload.utm_content,
    }
    utm_clean = {k: v for k, v in utm_payload.items() if v}
    if utm_clean:
        admin_body_lines.append(f"UTMs: {json.dumps(utm_clean, ensure_ascii=False)}")

    admin_msg = _build_email(
        subject="Nova lead capturada pelo site",
        body="\n".join(admin_body_lines),
        sender=settings.sender,
        to=admin_recipient,
    )

    lead_msg = _build_email(
        subject="Obrigado pelo seu contacto | Thank you for your message",
        body=(
            f"Olá {payload.fullName},\n\n"
            "Agradeço pelo seu contacto.\n"
            "Recebi a sua mensagem e entrarei em breve em contacto para entender melhor o seu projeto.\n\n"
            "------------------------------\n"
            "Hello,\n"
            "Thank you for getting in touch!\n"
            "I received your message and will be in touch soon to better understand your project.\n\n"
            "Best regards,\n"
            "Daniel França\n"
            "Digital PRO"
        ),
        sender=settings.sender,
        to=payload.email,
    )

    # envia com try/except individuais e LOGA erro
    try:
        _send_email(admin_msg, settings)
        print("INFO: e-mail admin enviado para", admin_recipient)
    except Exception as e:
        print("ERRO admin:", repr(e))

    try:
        _send_email(lead_msg, settings)
        print("INFO: auto-reply enviado para", payload.email)
    except Exception as e:
        print("ERRO auto-reply:", repr(e))


def _send_email(msg: EmailMessage, settings: EmailSettings) -> None:
    host, port = settings.host, settings.port
    user, password = settings.user, settings.password

    if port == 465:
        # SSL direto
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    else:
        # STARTTLS (587 por padrão)
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            try:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            except smtplib.SMTPException:
                # Alguns servidores podem não oferecer STARTTLS — segue sem TLS (raro)
                pass
            if user and password:
                server.login(user, password)
            server.send_message(msg)



def _prepare_custom_message(utm_data: Dict[str, Optional[str]]) -> Optional[str]:
    utm_clean = {k: v for k, v in utm_data.items() if v}
    if not utm_clean:
        return None
    return json.dumps({"utm": utm_clean}, ensure_ascii=False)


@router.post("/leads", status_code=status.HTTP_201_CREATED)
def create_public_lead(
    payload: PublicLeadPayload,
    x_form_token: str = Header(alias="x-form-token"),
    bg: BackgroundTasks = None,  # ← novo
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
                companyName, contactName, phone, email, origin, category, customMessage, observations, priority
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
        conn.commit()  # ← COMMIT antes dos e-mails

        # prepara e agenda envio em background (não bloqueia a resposta)
        email_settings = _load_email_settings()
        admin_recipient = os.getenv("EMAIL_TO")
        if not admin_recipient:
            print("WARN: EMAIL_TO não configurado — notificações por e-mail desabilitadas.")
        else:
            try:
                if bg is not None:
                    bg.add_task(_notify_admin_and_autoreply, payload, lead_id, email_settings, admin_recipient)
                else:
                    # fallback (em casos de teste sem BackgroundTasks)
                    _notify_admin_and_autoreply(payload, lead_id, email_settings, admin_recipient)
            except Exception as e:
                print("WARN: falha ao agendar envio de e-mails:", repr(e))

    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao criar lead.") from exc
    finally:
        conn.close()

    return {"id": lead_id, "status": "created"}
