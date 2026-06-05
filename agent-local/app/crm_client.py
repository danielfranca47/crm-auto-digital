"""Chamadas ao backend-crm autenticadas com JWT do utilizador (assinantes)."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


def _base() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


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
        from app.auth import refresh_access_token
        from app.session import save_session
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


def generate_copy(
    session: dict,
    company_name: str,
    sector: str = "",
    contact_name: str = "",
    channel: str = "whatsapp",
    tone: str = "profissional e próximo",
) -> str:
    """Gera copy de prospecção via LLM. Retorna o texto gerado."""
    resp = _request(
        "POST", f"{_base()}/api/prospeccao/generate-copy", session,
        json={
            "company_name": company_name,
            "sector": sector,
            "contact_name": contact_name,
            "channel": channel,
            "tone": tone,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("message", "")
