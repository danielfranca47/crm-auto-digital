# automations/assistente_ia/variable_resolver.py
"""
Resolve variáveis dinâmicas em campos de template de mensagem do AI Profile.

Variáveis suportadas (sintaxe {{chave}}):
  {{lead.nome}}         — contactName do lead
  {{lead.empresa}}      — companyName do lead
  {{agente.nome}}       — name do ai_profile
  {{negocio.nome}}      — brand_name do ai_profile
  {{negocio.local}}     — business_info field_key='endereco'
  {{negocio.horario}}   — business_info field_key='horario'
  {{negocio.telefone}}  — business_info field_key='telefone'
  {{reuniao.horario}}   — próximo appointment pendente do lead (formatado)
  {{reuniao.titulo}}    — título do próximo appointment pendente
  {{saudacao}}          — "Bom dia" / "Boa tarde" / "Boa noite" pelo timezone

Variáveis personalizadas: qualquer chave em ai_profile["custom_variables"] dict.

Fallback: token não resolvido → placeholder removido + cleanup de pontuação/espaços.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ── Regex ─────────────────────────────────────────────────────────────────────
_VAR_RE = re.compile(r"\{\{([\w.]+)\}\}")


class ResolutionContext:
    """Contexto completo para resolução de variáveis em um template."""

    def __init__(
        self,
        *,
        lead: Dict[str, Any],
        ai_profile: Dict[str, Any],
        business_info: Dict[str, str],
        appointment: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._lead = lead or {}
        self._profile = ai_profile or {}
        self._biz = business_info or {}
        self._appt = appointment

    def resolve(self, key: str) -> Optional[str]:
        """Retorna o valor string para a chave, ou None se não disponível/vazio."""
        lead = self._lead
        profile = self._profile
        tz_str = str(profile.get("timezone") or "America/Sao_Paulo")

        # ── Variáveis de lead ──────────────────────────────────────────────────
        if key == "lead.nome":
            return _nonempty(lead.get("contactName"))

        if key == "lead.empresa":
            return _nonempty(lead.get("companyName"))

        # ── Variáveis do agente / negócio ──────────────────────────────────────
        if key == "agente.nome":
            return _nonempty(profile.get("name"))

        if key == "negocio.nome":
            return _nonempty(profile.get("brand_name"))

        if key == "negocio.local":
            return _nonempty(self._biz.get("endereco"))

        if key == "negocio.horario":
            return _nonempty(self._biz.get("horario"))

        if key == "negocio.telefone":
            return _nonempty(self._biz.get("telefone"))

        # ── Saudação temporal ──────────────────────────────────────────────────
        if key == "saudacao":
            return _compute_saudacao(tz_str)

        # ── Reunião / agendamento ──────────────────────────────────────────────
        if key == "reuniao.horario":
            if self._appt:
                start = self._appt.get("start_at")
                if start:
                    return _format_appointment_time(start, tz_str)
            return None

        if key == "reuniao.titulo":
            if self._appt:
                return _nonempty(self._appt.get("title"))
            return None

        # ── Variáveis personalizadas ───────────────────────────────────────────
        custom = profile.get("custom_variables")
        if isinstance(custom, dict) and key in custom:
            return _nonempty(custom[key])

        return None  # desconhecida → fallback remove


def resolve_template(text: str, ctx: ResolutionContext) -> str:
    """
    Substitui todas as ocorrências de {{chave}} no texto.
    Tokens não resolvidos são removidos e a pontuação/espaços são limpos.
    """
    if not text:
        return text

    def _replacer(m: re.Match) -> str:
        return ctx.resolve(m.group(1)) or ""

    result = _VAR_RE.sub(_replacer, text)
    return _cleanup(result)


def build_resolution_context_from_db(
    *,
    conn: sqlite3.Connection,
    lead_id: int,
    user_id: int,
    ai_profile: Dict[str, Any],
) -> ResolutionContext:
    """
    Constrói o ResolutionContext consultando o SQLite do backend-crm.
    Usar dentro de um bloco com conn já aberto via get_connection().
    """
    conn.row_factory = sqlite3.Row

    # Lead
    row = conn.execute(
        "SELECT * FROM leads WHERE id = ? AND user_id = ?",
        (lead_id, user_id),
    ).fetchone()
    lead: Dict[str, Any] = dict(row) if row else {}

    # Business info (apenas campos com valor preenchido)
    biz_rows = conn.execute(
        "SELECT field_key, value FROM business_info WHERE user_id = ? AND enabled = 1",
        (user_id,),
    ).fetchall()
    business_info: Dict[str, str] = {
        r["field_key"]: r["value"]
        for r in biz_rows
        if r["value"]
    }

    # Próximo appointment pendente do lead
    appt_row = conn.execute(
        """
        SELECT * FROM appointments
         WHERE lead_id = ? AND status = 'pending'
         ORDER BY start_at ASC
         LIMIT 1
        """,
        (lead_id,),
    ).fetchone()
    appointment: Optional[Dict[str, Any]] = dict(appt_row) if appt_row else None

    return ResolutionContext(
        lead=lead,
        ai_profile=ai_profile,
        business_info=business_info,
        appointment=appointment,
    )


# ── Helpers privados ──────────────────────────────────────────────────────────

def _nonempty(val: Any) -> Optional[str]:
    s = str(val or "").strip()
    return s if s else None


def _compute_saudacao(timezone_str: str) -> str:
    try:
        tz = ZoneInfo(timezone_str)
    except (ZoneInfoNotFoundError, Exception):
        tz = ZoneInfo("America/Sao_Paulo")
    hour = datetime.now(tz).hour
    if hour < 12:
        return "Bom dia"
    if hour < 18:
        return "Boa tarde"
    return "Boa noite"


def _format_appointment_time(start_at_iso: str, timezone_str: str) -> str:
    try:
        tz = ZoneInfo(timezone_str)
    except (ZoneInfoNotFoundError, Exception):
        tz = ZoneInfo("America/Sao_Paulo")
    try:
        dt = datetime.fromisoformat(start_at_iso.replace("Z", "+00:00"))
        dt_local = dt.astimezone(tz)
        return dt_local.strftime("%d/%m às %H:%M")
    except (ValueError, AttributeError):
        return "em breve"


def _cleanup(text: str) -> str:
    """Remove artefatos deixados após a remoção de variáveis vazias."""
    # espaços duplos
    text = re.sub(r"[ \t]{2,}", " ", text)
    # espaços antes de quebras de linha
    text = re.sub(r"[ \t]+\n", "\n", text)
    # quebras de linha excessivas
    text = re.sub(r"\n{3,}", "\n\n", text)
    # vírgula/ponto-e-vírgula imediatamente antes de pontuação terminal
    text = re.sub(r"[,;]\s*([!?.;:])", r"\1", text)
    # vírgula/ponto-e-vírgula no início de frase/linha
    text = re.sub(r"(?m)^[,;]\s*", "", text)
    # espaço antes de pontuação terminal
    text = re.sub(r" ([!?.;:,])", r"\1", text)
    return text.strip()
