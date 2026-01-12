from typing import Any, Dict

import httpx

from app.core.config import settings


class CRMClientError(RuntimeError):
    pass


class CRMClientConflictError(CRMClientError):
    pass


def _require_token() -> str:
    token = settings.crm_service_token
    if not token:
        raise CRMClientError("CRM_SERVICE_TOKEN não configurado")
    return token


def _headers() -> Dict[str, str]:
    return {"X-Service-Token": _require_token()}


def _handle_response(
    response: httpx.Response,
    job_id: str,
    for_context: bool,
    *,
    not_found_message: str = "Job não encontrado",
) -> Dict[str, Any]:
    if response.status_code in {401, 403}:
        raise CRMClientError("CRM service token inválido ou sem permissão")
    if response.status_code == 404:
        raise CRMClientError(not_found_message)
    if response.status_code == 400 and for_context:
        raise CRMClientError("Payload do job incompleto para montar contexto")
    if response.is_success:
        return response.json()
    body = response.text
    raise CRMClientError(
        f"Erro do CRM (status={response.status_code}) job_id={job_id} body={body}"
    )


def get_job(job_id: str) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/jobs/{job_id}"
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url, headers=_headers())
    payload = _handle_response(response, job_id, for_context=False)
    return payload.get("job", {})


def get_whatsapp_execution_context(job_id: str) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/execution-context"
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url, headers=_headers(), params={"job_id": job_id})
    return _handle_response(response, job_id, for_context=True)


def claim_job(job_id: str, lease_owner: str, ttl_seconds: int) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/jobs/{job_id}/claim"
    payload = {"lease_owner": lease_owner, "lease_ttl_seconds": ttl_seconds}
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=payload)
    if response.status_code == 409:
        raise CRMClientConflictError("Job já está em execução")
    return _handle_response(response, job_id, for_context=False)


def complete_job(job_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/jobs/{job_id}/complete"
    payload = {"result": result}
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=payload)
    return _handle_response(response, job_id, for_context=False)


def fail_job(job_id: str, error: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/jobs/{job_id}/fail"
    payload: Dict[str, Any] = {"error": error}
    if details is not None:
        payload["details"] = details
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=payload)
    return _handle_response(response, job_id, for_context=False)


def set_lead_bot_disabled(
    lead_id: int,
    disabled: bool,
    reason: str | None = None,
) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/leads/{lead_id}/bot-disabled"
    payload: Dict[str, Any] = {"disabled": disabled}
    if reason:
        payload["reason"] = reason
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=payload)
    return _handle_response(response, str(lead_id), for_context=False)


def log_handoff_requested(
    *,
    user_id: int,
    lead_id: int,
    job_id: int,
    message_id: str | None,
    reason: str | None,
    policy: str,
    identity_mode: str,
) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/logs/handoff-requested"
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "lead_id": lead_id,
        "job_id": job_id,
        "message_id": message_id,
        "reason": reason,
        "policy": policy,
        "identity_mode": identity_mode,
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=payload)
    return _handle_response(response, str(job_id), for_context=False)


def register_whatsapp_outbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/outbound"
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=payload)
    return _handle_response(
        response,
        str(payload.get("job_id", "")),
        for_context=False,
        not_found_message="Outbound endpoint não encontrado",
    )


def mark_whatsapp_outbound_sent(outbound_event_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/outbound/{outbound_event_id}/mark-sent"
    with httpx.Client(timeout=15.0) as client:
        response = client.post(url, headers=_headers(), json=payload)
    return _handle_response(
        response,
        str(outbound_event_id),
        for_context=False,
        not_found_message="Outbound event não encontrado",
    )
