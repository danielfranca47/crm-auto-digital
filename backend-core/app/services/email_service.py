import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings

_FOOTER = '<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0"><p style="color:#94a3b8;font-size:0.75em">Lara by Digital Pro — A tua IA de vendas via WhatsApp</p>'
_FOOTER_TEXT = "\n\n---\nLara by Digital Pro — A tua IA de vendas via WhatsApp"


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
  <h2 style="color:#0284c7">Bem-vindo à Digital Pro</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>A tua conta foi criada. A <strong>Lara</strong> — a tua IA de vendas via WhatsApp — está pronta para trabalhar para ti.</p>
  <p>Usa as credenciais abaixo para entrar:</p>
  <div style="background:#f1f5f9;border-radius:8px;padding:16px 20px;margin:16px 0">
    <p style="margin:4px 0"><strong>Senha temporária:</strong> <code style="font-size:1.1em">{temp_password}</code></p>
  </div>
  <p style="margin:24px 0">
    <a href="{login_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Começar com a Lara →
    </a>
  </p>
  <p style="color:#64748b;font-size:0.875em">Podes alterar a senha depois de entrar.</p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"Bem-vindo à Digital Pro\n\n"
        f"Olá, {display}.\n\n"
        f"A tua conta foi criada. A Lara — a tua IA de vendas via WhatsApp — está pronta para trabalhar para ti.\n\n"
        f"Senha temporária: {temp_password}\n\n"
        f"Entra em: {login_url}\n\n"
        f"Podes alterar a senha depois de entrar."
        f"{_FOOTER_TEXT}"
    )
    return html, text


def render_reset_email(reset_url: str) -> tuple[str, str]:
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#0284c7">Recuperação de senha — Digital Pro</h2>
  <p>Recebemos um pedido de recuperação de senha para a tua conta.</p>
  <p>Clica no botão abaixo para definir uma nova senha. O link expira em <strong>2 horas</strong>.</p>
  <p style="margin:24px 0">
    <a href="{reset_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Redefinir senha
    </a>
  </p>
  <p style="color:#64748b;font-size:0.875em">Se não foste tu a pedir, ignora este email — a tua senha não será alterada.</p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"Recuperação de senha — Digital Pro\n\n"
        f"Recebemos um pedido de recuperação de senha.\n\n"
        f"Acede ao link abaixo para definir uma nova senha (expira em 2 horas):\n"
        f"{reset_url}\n\n"
        f"Se não foste tu, ignora este email."
        f"{_FOOTER_TEXT}"
    )
    return html, text


def render_register_welcome_email(name: Optional[str], login_url: str) -> tuple[str, str]:
    display = name or "Cliente"
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#0284c7">A Lara está pronta para ti</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>A tua conta na <strong>Digital Pro</strong> foi criada com sucesso.</p>
  <p>A <strong>Lara</strong> é a tua nova IA de vendas via WhatsApp — ela atende, qualifica leads e faz follow-up para ti, 24/7.</p>
  <p style="margin:24px 0">
    <a href="{login_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Começar com a Lara →
    </a>
  </p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"A Lara está pronta para ti\n\n"
        f"Olá, {display}.\n\n"
        f"A tua conta na Digital Pro foi criada com sucesso.\n"
        f"A Lara — a tua IA de vendas via WhatsApp — está pronta para trabalhar para ti 24/7.\n\n"
        f"Começa em: {login_url}"
        f"{_FOOTER_TEXT}"
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
  <h2 style="color:#16a34a">A Lara está activa!</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> foi activado. A <strong>Lara</strong> está pronta para atender, qualificar e fazer follow-up dos teus leads pelo WhatsApp.</p>
  <div style="background:#f0fdf4;border-radius:8px;padding:16px 20px;margin:16px 0;border-left:4px solid #16a34a">
    <p style="margin:4px 0"><strong>Plano:</strong> {plan_name}</p>
    <p style="margin:4px 0"><strong>Acesso até:</strong> {end_str}</p>
  </div>
  <p style="margin:24px 0">
    <a href="{login_url}"
       style="background:#16a34a;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Activar a Lara agora →
    </a>
  </p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"A Lara está activa!\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} foi activado.\n"
        f"A Lara está pronta para atender, qualificar e fazer follow-up dos teus leads pelo WhatsApp.\n\n"
        f"Acesso até: {end_str}\n\n"
        f"Entra em: {login_url}"
        f"{_FOOTER_TEXT}"
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
  <h2 style="color:#7c3aed">O teu trial da Lara começou!</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu período de experimentação do plano <strong>{plan_name}</strong> foi iniciado. Tens acesso completo à <strong>Lara</strong> — a tua IA de vendas via WhatsApp.</p>
  <div style="background:#faf5ff;border-radius:8px;padding:16px 20px;margin:16px 0;border-left:4px solid #7c3aed">
    <p style="margin:4px 0"><strong>Plano:</strong> {plan_name}</p>
    <p style="margin:4px 0"><strong>Trial termina em:</strong> {end_str}</p>
  </div>
  <p>Aproveita para configurar a Lara com o teu negócio e ver ela trabalhar para ti. Antes de o trial terminar, activa o plano para continuar.</p>
  <p style="margin:24px 0">
    <a href="{login_url}"
       style="background:#7c3aed;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Conhecer a Lara →
    </a>
  </p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"O teu trial da Lara começou!\n\n"
        f"Olá, {display}.\n\n"
        f"O teu período de experimentação do plano {plan_name} foi iniciado.\n"
        f"Tens acesso completo à Lara — a tua IA de vendas via WhatsApp.\n\n"
        f"Trial termina em: {end_str}\n\n"
        f"Começa em: {login_url}"
        f"{_FOOTER_TEXT}"
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
  <h2 style="color:#16a34a">A Lara continua activa!</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> foi renovado com sucesso. A <strong>Lara</strong> continua a trabalhar para ti.</p>
  <div style="background:#f0fdf4;border-radius:8px;padding:16px 20px;margin:16px 0;border-left:4px solid #16a34a">
    <p style="margin:4px 0"><strong>Plano:</strong> {plan_name}</p>
    <p style="margin:4px 0"><strong>Próxima renovação:</strong> {end_str}</p>
  </div>
  <p style="color:#64748b;font-size:0.875em">Obrigado por continuares com a Lara.</p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"A Lara continua activa!\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} foi renovado. A Lara continua a trabalhar para ti.\n"
        f"Próxima renovação: {end_str}\n\n"
        f"Obrigado por continuares com a Lara."
        f"{_FOOTER_TEXT}"
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
  <h2 style="color:#dc2626">Subscrição cancelada</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>A tua subscrição do plano <strong>{plan_name}</strong> foi cancelada.</p>
  <p>O acesso à <strong>Lara</strong> ficará limitado no final do período actual.</p>
  <p style="color:#64748b;font-size:0.875em">Se cancelaste por engano ou mudaste de ideias, podes reactivar a Lara a qualquer momento.</p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"Subscrição cancelada\n\n"
        f"Olá, {display}.\n\n"
        f"A tua subscrição do plano {plan_name} foi cancelada.\n"
        f"O acesso à Lara ficará limitado no final do período actual."
        f"{_FOOTER_TEXT}"
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
  <h2 style="color:#d97706">A Lara para em breve ⚠️</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> expira em <strong>{end_str}</strong>. Renova agora para a <strong>Lara</strong> continuar a trabalhar para ti sem interrupções.</p>
  <p style="margin:24px 0">
    <a href="{checkout_url}"
       style="background:#d97706;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Renovar a Lara →
    </a>
  </p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"A Lara para em breve\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} expira em {end_str}.\n"
        f"Renova agora para a Lara continuar a trabalhar para ti.\n\n"
        f"Renova em: {checkout_url}"
        f"{_FOOTER_TEXT}"
    )
    return html, text


def render_password_changed_email(name: Optional[str]) -> tuple[str, str]:
    display = name or "Cliente"
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;color:#1e293b;max-width:520px;margin:0 auto;padding:24px">
  <h2 style="color:#0284c7">Senha alterada com sucesso</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>A tua senha na <strong>Digital Pro</strong> foi alterada com sucesso.</p>
  <p style="color:#64748b;font-size:0.875em">Se não foste tu a fazer esta alteração, contacta-nos imediatamente respondendo a este email.</p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"Senha alterada com sucesso\n\n"
        f"Olá, {display}.\n\n"
        f"A tua senha na Digital Pro foi alterada com sucesso.\n\n"
        f"Se não foste tu, contacta-nos imediatamente."
        f"{_FOOTER_TEXT}"
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
  <h2 style="color:#dc2626">A Lara está pausada</h2>
  <p>Olá, <strong>{display}</strong>.</p>
  <p>O teu plano <strong>{plan_name}</strong> expirou e o acesso à <strong>Lara</strong> foi suspenso.</p>
  <p>Reactiva agora para a Lara retomar o atendimento automático dos teus leads.</p>
  <p style="margin:24px 0">
    <a href="{checkout_url}"
       style="background:#0284c7;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Reactivar a Lara →
    </a>
  </p>
  {_FOOTER}
</body>
</html>
"""
    text = (
        f"A Lara está pausada\n\n"
        f"Olá, {display}.\n\n"
        f"O teu plano {plan_name} expirou e o acesso à Lara foi suspenso.\n\n"
        f"Reactiva em: {checkout_url}"
        f"{_FOOTER_TEXT}"
    )
    return html, text
