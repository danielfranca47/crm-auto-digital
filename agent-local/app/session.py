"""Persistência de sessão local em ~/.agent-local/session.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_SESSION_DIR = Path.home() / ".agent-local"
_SESSION_FILE = _SESSION_DIR / "session.json"
_PROSPECT_LOG = _SESSION_DIR / "prospect_log.jsonl"


def load_session() -> Optional[dict]:
    if not _SESSION_FILE.exists():
        return None
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        if not data.get("access_token"):
            return None
        return data
    except Exception:
        return None


def save_session(data: dict) -> None:
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_session() -> None:
    if _SESSION_FILE.exists():
        _SESSION_FILE.unlink()


def is_subscriber(session: dict) -> bool:
    return (session or {}).get("subscription_status") == "active"


# ── Templates de mensagem ─────────────────────────────────────────────────────

def get_templates(session: dict) -> list:
    """Retorna lista de templates: [{'name': str, 'text': str}, ...]"""
    return list(session.get("message_templates") or [])


def save_template(session: dict, name: str, text: str) -> None:
    """Adiciona ou actualiza template pelo nome. Persiste em session.json."""
    templates = get_templates(session)
    for t in templates:
        if t.get("name") == name:
            t["text"] = text
            session["message_templates"] = templates
            save_session(session)
            return
    templates.append({"name": name, "text": text})
    session["message_templates"] = templates
    save_session(session)


def delete_template(session: dict, name: str) -> None:
    """Remove template pelo nome. Persiste em session.json."""
    templates = [t for t in get_templates(session) if t.get("name") != name]
    session["message_templates"] = templates
    save_session(session)


# ── Kanban local de prospecção (modo gratuito) ───────────────────────────────
# Espelha o Kanban de assinante (categorias "to-prospect"/"in-progress"/
# "qualification") usando os mesmos nomes de campo (companyName/phone/category/
# id/origin) para que os renderers possam tratar leads locais e remotos da
# mesma forma. Persistido em session["local_leads"].

def get_local_leads(session: dict) -> list:
    """Retorna lista de leads locais: [{'id', 'companyName', 'phone', 'category', ...}]"""
    return list(session.get("local_leads") or [])


def upsert_local_lead(
    session: dict,
    *,
    phone: str,
    name: str,
    category: str,
    website: str = "",
    address: str = "",
    **extra,
) -> dict:
    """Cria ou actualiza um lead local pelo telefone (idempotente). Persiste em session.json."""
    leads = get_local_leads(session)
    for lead in leads:
        if lead.get("phone") == phone:
            lead["companyName"] = name or lead.get("companyName")
            lead["category"] = category
            if website:
                lead["website"] = website
            if address:
                lead["address"] = address
            for key, value in extra.items():
                if value not in (None, ""):
                    lead[key] = value
            session["local_leads"] = leads
            save_session(session)
            return lead

    seq = int(session.get("_local_lead_seq") or 0) + 1
    session["_local_lead_seq"] = seq
    lead = {
        "id": f"local-{seq}",
        "companyName": name or phone,
        "phone": phone,
        "category": category,
        "origin": "Local",
        "customMessage": "",
        "website": website,
        "address": address,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    lead.update({k: v for k, v in extra.items() if v not in (None, "")})
    leads.append(lead)
    session["local_leads"] = leads
    save_session(session)
    return lead


def move_local_lead(session: dict, lead_id: str, category: str) -> None:
    """Move um lead local para outra categoria. Persiste em session.json."""
    leads = get_local_leads(session)
    for lead in leads:
        if lead.get("id") == lead_id:
            lead["category"] = category
            session["local_leads"] = leads
            save_session(session)
            return


def update_local_lead(session: dict, lead_id: str, **fields) -> None:
    """Actualiza campos arbitrários de um lead local (ex.: customMessage). Persiste em session.json."""
    leads = get_local_leads(session)
    for lead in leads:
        if lead.get("id") == lead_id:
            lead.update(fields)
            session["local_leads"] = leads
            save_session(session)
            return


# ── Log local de prospecções ──────────────────────────────────────────────────

def append_prospect_log(entry: dict) -> None:
    """Adiciona linha JSONL ao log local: {ts, name, phone, status, reason}."""
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    try:
        with _PROSPECT_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_prospect_log(limit: int = 100) -> list:
    """Lê as últimas N linhas do log local (mais recentes primeiro)."""
    if not _PROSPECT_LOG.exists():
        return []
    try:
        lines = _PROSPECT_LOG.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in reversed(lines[-limit * 2:]):
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
            if len(entries) >= limit:
                break
        return entries
    except Exception:
        return []
