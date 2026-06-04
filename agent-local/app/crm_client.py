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

    resp = requests.post(
        f"{_base()}/api/leads",
        json=payload,
        headers=_auth(session),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def log_outbound(session: dict, lead_id: int, message: str) -> None:
    """
    Regista envio outbound no CRM: seta origin=outbound + prospection_context.
    Idempotente — se origin já for outbound, o backend mantém o valor.
    """
    resp = requests.patch(
        f"{_base()}/api/leads/{lead_id}",
        json={"origin": "outbound", "prospection_context": message},
        headers=_auth(session),
        timeout=15,
    )
    resp.raise_for_status()
