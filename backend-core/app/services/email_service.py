import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings


def send_email(to: str, subject: str, html: str, text: str) -> None:
    """Send email via SMTP. Raises RuntimeError if SMTP is not configured."""
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASS:
        raise RuntimeError("SMTP não configurado — defina SMTP_HOST, SMTP_USER e SMTP_PASS no .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    smtp_cls = smtplib.SMTP if not settings.SMTP_TLS else smtplib.SMTP
    with smtp_cls(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_TLS:
            server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.sendmail(msg["From"], [to], msg.as_string())


def render_welcome_email(name: Optional[str], temp_password: str, login_url: str) -> tuple[str, str]:
    display = name or "Cliente"
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#0284c7">Bem-vindo ao Digital Pro</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>A sua conta foi criada. Use as credenciais abaixo para entrar:</p>
  <div style="background:#f1f5f9;border-radius:8px;padding:16px 20px;margin:16px 0">
    <p style="margin:4px 0"><strong>Senha temporária:</strong> <code style="font-size:1.1em">{temp_password}</code></p>
  </div>
  <p>Aceda em: <a href="{login_url}" style="color:#0284c7">{login_url}</a></p>
  <p style="color:#64748b;font-size:0.875em">Pode alterar a senha depois de entrar.</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">AutoDigital — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"Bem-vindo ao Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"A sua conta foi criada.\n"
        f"Senha temporária: {temp_password}\n\n"
        f"Aceda em: {login_url}\n\n"
        f"Pode alterar a senha depois de entrar."
    )
    return html, text


def render_reset_email(reset_url: str) -> tuple[str, str]:
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#0284c7">Recuperação de senha — Digital Pro</h2>
  <p>Recebemos um pedido de recuperação de senha para a sua conta.</p>
  <p>Clique no botão abaixo para definir uma nova senha. O link expira em <strong>2 horas</strong>.</p>
  <p style="margin:24px 0">
    <a href="{reset_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Redefinir senha
    </a>
  </p>
  <p style="color:#64748b;font-size:0.875em">Se não foi você a pedir, ignore este email — a sua senha não será alterada.</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">AutoDigital — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"Recuperação de senha — Digital Pro\n\n"
        f"Recebemos um pedido de recuperação de senha.\n\n"
        f"Aceda ao link abaixo para definir uma nova senha (expira em 2 horas):\n"
        f"{reset_url}\n\n"
        f"Se não foi você, ignore este email."
    )
    return html, text
