"""Chamadas ao backend-crm autenticadas com JWT do utilizador (assinantes)."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests

from app.auth import refresh_access_token
from app.session import save_session

logger = logging.getLogger(__name__)


def _base() -> str:
    return os.getenv("BACKEND_URL", "https://backend-crm-production-a702.up.railway.app").rstrip("/")


def _auth(session: dict) -> Dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


def _request(method: str, url: str, session: dict, **kwargs) -> requests.Response:
    """HTTP request com refresh automático em 401 (access token expirado)."""
    resp = requests.request(method, url, headers=_auth(session), **kwargs)
    if resp.status_code != 401:
        return resp

    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return resp

    try:
        new_token = refresh_access_token(refresh_token)
        session["access_token"] = new_token
        save_session(session)
        logger.info("Access token renovado silenciosamente via refresh token")
        resp = requests.request(method, url, headers=_auth(session), **kwargs)
    except Exception as exc:
        logger.warning("Falha ao renovar token automaticamente: %s", exc)

    return resp


def create_lead(
    session: dict,
    *,
    name: str,
    phone: str,
    website: str = "",
    address: str = "",
) -> Dict[str, Any]:
    """
    Cria lead no CRM com o JWT do utilizador.
    Se o telefone já existir, o backend devolve o lead existente (sem duplicar).
    Retorna dict com 'id'.
    Levanta requests.HTTPError em falha de rede/auth.
    """
    observations = "\n".join(filter(None, [
        f"Website: {website}" if website else "",
        f"Endereço: {address}" if address else "",
    ]))
    payload: Dict[str, Any] = {
        "companyName": name,
        "phone": phone,
        "country_code": "BR",
        "origin": "Manual",
        "category": "to-prospect",
    }
    if observations:
        payload["observations"] = observations

    resp = _request("POST", f"{_base()}/api/leads", session, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def log_outbound(session: dict, lead_id: int, message: str) -> None:
    """
    Regista envio outbound no CRM: seta origin=outbound + prospection_context.
    Idempotente — se origin já for outbound, o backend mantém o valor.
    """
    resp = _request(
        "PATCH", f"{_base()}/api/leads/{lead_id}", session,
        json={"origin": "outbound", "prospection_context": message},
        timeout=15,
    )
    resp.raise_for_status()


def get_prospect_history(session: dict, limit: int = 100) -> list:
    """Histórico de prospecções do utilizador (assinantes). Retorna lista de dicts."""
    resp = _request(
        "GET", f"{_base()}/api/prospeccao/history", session,
        params={"limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def get_prospect_history_summary(session: dict, channel: str | None = None) -> dict:
    """Resumo agregado (sent/failed/queued) do histórico de prospecções (assinantes)."""
    params = {"channel": channel} if channel else {}
    resp = _request(
        "GET", f"{_base()}/api/prospeccao/history/summary", session,
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


def get_leads_kanban(session: dict) -> list:
    """Leads nas categorias de prospecção (to-prospect, in-progress, qualification)."""
    resp = _request("GET", f"{_base()}/api/leads", session, timeout=20)
    resp.raise_for_status()
    all_leads = resp.json() if isinstance(resp.json(), list) else []
    prospection_cats = {"to-prospect", "in-progress", "qualification"}
    return [l for l in all_leads if l.get("category") in prospection_cats]


def move_lead_category(session: dict, lead_id: int, category: str) -> None:
    """Move lead para nova categoria (PATCH /api/leads/{id})."""
    resp = _request(
        "PATCH", f"{_base()}/api/leads/{lead_id}", session,
        json={"category": category},
        timeout=15,
    )
    resp.raise_for_status()


def generate_copy(
    session: dict,
    company_name: str,
    sector: str = "",
    contact_name: str = "",
    channel: str = "whatsapp",
    tone: str = "profissional e próximo",
    custom_prompt_template: str = "",
) -> str:
    """Gera copy de prospecção via LLM. Retorna o texto gerado."""
    body: dict = {
        "company_name": company_name,
        "sector": sector,
        "contact_name": contact_name,
        "channel": channel,
        "tone": tone,
    }
    if custom_prompt_template:
        body["custom_prompt_template"] = custom_prompt_template
    resp = _request(
        "POST", f"{_base()}/api/prospeccao/generate-copy", session,
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("message", "")


# ── Automação de prospecção ────────────────────────────────────────────────────

def get_agent_overview(session: dict) -> dict:
    """Estado dos agentes locais: online/offline e summary de jobs."""
    resp = _request("GET", f"{_base()}/api/agents/overview", session, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_whatsapp_queue_count(session: dict) -> int:
    """Número de mensagens WhatsApp pendentes na fila do utilizador."""
    resp = _request(
        "GET", f"{_base()}/api/prospeccao/whatsapp/queue",
        session, params={"limit": 50}, timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return len(data) if isinstance(data, list) else 0


def get_whatsapp_recent(session: dict, since_secs: int = 90) -> list:
    """Resultados recentes de envio WhatsApp (sent/failed) nos últimos N segundos."""
    resp = _request(
        "GET", f"{_base()}/api/prospeccao/whatsapp/recent",
        session, params={"since_secs": since_secs}, timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def enqueue_whatsapp(session: dict, lead_ids: list, message: str = None) -> dict:
    """Enfileira leads para envio automático de WhatsApp pelo agente."""
    payload: Dict[str, Any] = {"lead_ids": [int(lid) for lid in lead_ids]}
    if message:
        payload["message"] = message
    resp = _request(
        "POST", f"{_base()}/api/prospeccao/whatsapp/enqueue",
        session, json=payload, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def enqueue_email(session: dict, lead_ids: list, subject: str = None, message: str = None) -> dict:
    """Enfileira leads para envio automático de email pelo agente."""
    payload: Dict[str, Any] = {"lead_ids": [int(lid) for lid in lead_ids]}
    if subject:
        payload["subject"] = subject
    if message:
        payload["message"] = message
    resp = _request(
        "POST", f"{_base()}/api/prospeccao/email/enqueue",
        session, json=payload, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ── Assistente IA (upload em lote + geração de copy) ─────────────────────────

def upload_file(session: dict, file_path: str) -> Dict[str, Any]:
    """
    Envia ficheiro CSV/XLSX para o backend-crm.
    Retorna: { upload_id, filename, ext, columns, sample (lista de dicts) }
    """
    with open(file_path, "rb") as fh:
        name = fh.name.split("\\")[-1].split("/")[-1]
        resp = _request(
            "POST", f"{_base()}/api/uploads",
            session,
            files={"file": (name, fh)},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()


def preview_assistente_ia(
    session: dict,
    upload_id: str,
    overwrite: str,
    column_map: Dict[str, str],
) -> Dict[str, Any]:
    """
    Analisa duplicados e prevê acções por linha.
    Retorna: { stats: {total, pred_create, pred_update, pred_skip, ...}, rows: [...] }
    """
    resp = _request(
        "POST", f"{_base()}/api/assistente-ia/preview",
        session,
        json={"upload_id": upload_id, "overwrite": overwrite, "column_map": column_map},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_lead_messages(session: dict, lead_id: int) -> list:
    """
    Mensagens de prospecção geradas para um lead (por canal).
    Retorna lista de dicts: { id, channel, subject, body, model, createdAt }
    """
    resp = _request(
        "GET", f"{_base()}/api/assistente-ia/messages/{lead_id}",
        session, params={"latest": True}, timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("messages", []) if isinstance(data, dict) else []


def upsert_lead_message(
    session: dict,
    lead_id: int,
    channel: str,
    body: str,
    *,
    message_id: int | None = None,
    subject: str | None = None,
) -> Dict[str, Any]:
    """Cria ou actualiza uma mensagem de prospecção (copy) editada manualmente."""
    payload: Dict[str, Any] = {"lead_id": lead_id, "channel": channel, "body": body}
    if message_id is not None:
        payload["message_id"] = message_id
    if subject is not None:
        payload["subject"] = subject
    resp = _request(
        "POST", f"{_base()}/api/assistente-ia/messages/upsert", session,
        json=payload, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def processar_assistente_ia(
    session: dict,
    upload_id: str,
    *,
    create_cards: bool = True,
    generate_copys: bool = False,
    channels: list | None = None,
    overwrite: str = "skip",
    tone: str = "profissional e próximo",
    language: str = "pt-PT",
    column_map: Dict[str, str] | None = None,
    custom_prompt_template: str = "",
) -> Dict[str, Any]:
    """
    Processa o upload: cria leads e/ou gera copys via LLM.
    Retorna: { stats: {created, updated, skipped, messages}, errors: [...] }
    """
    body: dict = {
        "upload_id": upload_id,
        "create_cards": create_cards,
        "generate_copys": generate_copys,
        "channels": channels or ["whatsapp"],
        "overwrite": overwrite,
        "tone": tone,
        "language": language,
        "column_map": column_map or {},
    }
    if custom_prompt_template:
        body["custom_prompt_template"] = custom_prompt_template
    resp = _request(
        "POST", f"{_base()}/api/assistente-ia/processar",
        session,
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()
