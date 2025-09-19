# automations/assistente_ia/text_renderer.py
import re
from typing import Dict, Optional

PLACEHOLDER_RE = re.compile(r"\[(?:seu|sua|nome|empresa|email|e-mail|telefone|contato|contato\)|.*?)\]", re.IGNORECASE)

def _safe(val: Optional[str]) -> str:
    return str(val or "").strip()

def interpolate(text: str, lead: Dict, profile: Dict) -> str:
    """
    Substitui variáveis de remetente e prospect:
      {{prospect.company}}, {{sender.name}}, {{sender.company}}, {{sender.email}}, {{sender.phone}}, {{sender.signature}}
    Remove colchetes remanescentes.
    """
    out = text or ""

    # dicionários básicos
    prospect = {
        "company": _safe(lead.get("companyName")) or _safe(lead.get("company")) or "sua empresa",
    }
    sender = {
        "name": _safe(profile.get("sender_name")),
        "company": _safe(profile.get("sender_company")),
        "email": _safe(profile.get("sender_email")),
        "phone": _safe(profile.get("sender_phone")),
        "signature": _safe(profile.get("sender_signature")),
    }

    # substituições
    out = out.replace("{{prospect.company}}", prospect["company"])
    out = out.replace("{{sender.name}}", sender["name"])
    out = out.replace("{{sender.company}}", sender["company"])
    out = out.replace("{{sender.email}}", sender["email"])
    out = out.replace("{{sender.phone}}", sender["phone"])
    out = out.replace("{{sender.signature}}", sender["signature"])

    # limpeza de colchetes: se sobrar qualquer placeholder com [ ... ]
    out = PLACEHOLDER_RE.sub("", out)
    # normaliza espaços múltiplos
    out = re.sub(r"[ \t]{2,}", " ", out)
    # remove espaços antes de quebras
    out = re.sub(r"[ \t]+\n", "\n", out)

    return out.strip()

def format_email(body: str) -> str:
    """
    Garante parágrafos com linhas em branco entre eles.
    Se vier tudo colado, cria quebras sensatas.
    """
    if not body:
        return body
    # normaliza \r\n
    b = body.replace("\r\n", "\n")
    # se já tem linhas em branco, mantém; senão, tenta quebrar por sentenças maiores
    if "\n\n" not in b:
        b = re.sub(r"([.!?])\s+", r"\1\n\n", b)
    # compacta excesso de linhas em branco
    b = re.sub(r"\n{3,}", "\n\n", b).strip()
    return b

def format_whatsapp_or_dm(body: str) -> str:
    """
    Tenta quebrar em blocos curtos (2–4 linhas).
    """
    if not body:
        return body
    b = body.replace("\r\n", "\n").strip()
    # se está tudo em um parágrafo, cria quebras leves por pontuação
    if "\n" not in b:
        b = re.sub(r"([.!?])\s+", r"\1\n", b)
    # evita mais de 2 linhas em branco
    b = re.sub(r"\n{3,}", "\n\n", b).strip()
    return b
