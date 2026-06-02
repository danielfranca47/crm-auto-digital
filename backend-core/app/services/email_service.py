import smtplib
from datetime import datetime
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
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
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
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
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


def render_register_welcome_email(name: Optional[str], login_url: str) -> tuple[str, str]:
    display = name or "Cliente"
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#0284c7">Bem-vindo ao Digital Pro</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>A tua conta foi criada com sucesso. Podes entrar agora e começar a usar o CRM com IA.</p>
  <p style="margin:24px 0">
    <a href="{login_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Entrar no Digital Pro
    </a>
  </p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"Bem-vindo ao Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"A tua conta foi criada com sucesso.\n\n"
        f"Entra em: {login_url}"
    )
    return html, text


def render_subscription_activated_email(
    name: Optional[str], plan_name: str, period_end: datetime, login_url: str
) -> tuple[str, str]:
    display = name or "Cliente"
    end_str = period_end.strftime("%d/%m/%Y")
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#16a34a">Plano activado — Digital Pro</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> foi activado com sucesso.</p>
  <div style="background:#f0fdf4;border-radius:8px;padding:16px 20px;margin:16px 0;border-left:4px solid #16a34a">
    <p style="margin:4px 0"><strong>Plano:</strong> {plan_name}</p>
    <p style="margin:4px 0"><strong>Acesso até:</strong> {end_str}</p>
  </div>
  <p style="margin:24px 0">
    <a href="{login_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Entrar no Digital Pro
    </a>
  </p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"Plano activado — Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} foi activado.\n"
        f"Acesso até: {end_str}\n\n"
        f"Entra em: {login_url}"
    )
    return html, text


def render_trial_started_email(
    name: Optional[str], plan_name: str, trial_end: datetime, login_url: str
) -> tuple[str, str]:
    display = name or "Cliente"
    end_str = trial_end.strftime("%d/%m/%Y")
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#7c3aed">Trial iniciado — Digital Pro</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu período de experimentação do plano <strong>{plan_name}</strong> foi iniciado.</p>
  <div style="background:#faf5ff;border-radius:8px;padding:16px 20px;margin:16px 0;border-left:4px solid #7c3aed">
    <p style="margin:4px 0"><strong>Plano:</strong> {plan_name}</p>
    <p style="margin:4px 0"><strong>Trial termina em:</strong> {end_str}</p>
  </div>
  <p>Aproveita para explorar todas as funcionalidades do CRM. Antes de o trial terminar, activa o teu plano para continuar.</p>
  <p style="margin:24px 0">
    <a href="{login_url}"
       style="background:#7c3aed;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Começar agora
    </a>
  </p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"Trial iniciado — Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"O teu período de experimentação do plano {plan_name} foi iniciado.\n"
        f"Trial termina em: {end_str}\n\n"
        f"Começa agora em: {login_url}"
    )
    return html, text


def render_subscription_renewed_email(
    name: Optional[str], plan_name: str, new_end: datetime
) -> tuple[str, str]:
    display = name or "Cliente"
    end_str = new_end.strftime("%d/%m/%Y")
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#16a34a">Plano renovado — Digital Pro</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> foi renovado com sucesso.</p>
  <div style="background:#f0fdf4;border-radius:8px;padding:16px 20px;margin:16px 0;border-left:4px solid #16a34a">
    <p style="margin:4px 0"><strong>Plano:</strong> {plan_name}</p>
    <p style="margin:4px 0"><strong>Próxima renovação:</strong> {end_str}</p>
  </div>
  <p style="color:#64748b;font-size:0.875em">Obrigado por continuares connosco.</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"Plano renovado — Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} foi renovado.\n"
        f"Próxima renovação: {end_str}\n\n"
        f"Obrigado por continuares connosco."
    )
    return html, text


def render_subscription_cancelled_email(
    name: Optional[str], plan_name: str
) -> tuple[str, str]:
    display = name or "Cliente"
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#dc2626">Subscrição cancelada — Digital Pro</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>A tua subscrição do plano <strong>{plan_name}</strong> foi cancelada.</p>
  <p>O acesso ao Digital Pro ficará limitado no final do período actual.</p>
  <p style="color:#64748b;font-size:0.875em">Se cancelaste por engano ou mudaste de ideia, podes reactivar o teu plano a qualquer momento.</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"Subscrição cancelada — Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"A tua subscrição do plano {plan_name} foi cancelada.\n"
        f"O acesso ficará limitado no final do período actual."
    )
    return html, text


def render_subscription_expiring_email(
    name: Optional[str], plan_name: str, period_end: datetime, checkout_url: str
) -> tuple[str, str]:
    display = name or "Cliente"
    end_str = period_end.strftime("%d/%m/%Y")
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#d97706">O teu plano expira em breve</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> expira em <strong>{end_str}</strong>.</p>
  <p>Renova agora para garantir que o acesso não é interrompido.</p>
  <p style="margin:24px 0">
    <a href="{checkout_url}"
       style="background:#d97706;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Renovar plano
    </a>
  </p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"O teu plano expira em breve — Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} expira em {end_str}.\n\n"
        f"Renova em: {checkout_url}"
    )
    return html, text


def render_subscription_expired_email(
    name: Optional[str], plan_name: str, checkout_url: str
) -> tuple[str, str]:
    display = name or "Cliente"
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#dc2626">O teu plano expirou</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> expirou e o acesso ao Digital Pro foi suspenso.</p>
  <p>Reactiva o teu plano para recuperar o acesso completo.</p>
  <p style="margin:24px 0">
    <a href="{checkout_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Reactivar plano
    </a>
  </p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="color:#94a3b8;font-size:0.75em">Digital Pro — CRM com IA para vendas via WhatsApp</p>
</body>
</html>
"""
    text = (
        f"O teu plano expirou — Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} expirou.\n\n"
        f"Reactiva em: {checkout_url}"
    )
    return html, text
