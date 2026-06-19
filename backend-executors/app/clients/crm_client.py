from typing import Any, Dict

import httpx

from app.core.config import settings


class CRMClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        error_type: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.error_type = error_type


class CRMClientConflictError(CRMClientError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        error_type: str | None = None,
    ):
        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            error_type=error_type,
        )


def _require_token() -> str:
    token = settings.crm_service_token
    if not token:
        raise CRMClientError("CRM_SERVICE_TOKEN não configurado")
    return token


def _headers() -> Dict[str, str]:
    return {"X-Service-Token": _require_token()}


def _send_request(
    method: str,
    url: str,
    *,
    json: Dict[str, Any] | None = None,
    params: Dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> httpx.Response:
    with httpx.Client(timeout=timeout) as client:
        try:
            return client.request(method, url, headers=_headers(), json=json, params=params)
        except httpx.RequestError as exc:
            raise CRMClientError(
                f"Erro de rede do CRM: {exc}",
                error_type="network",
            ) from exc

def _handle_response(
    response: httpx.Response,
    request_ref: str,
    for_context: bool,
    *,
    not_found_message: str = "Job não encontrado",
) -> Dict[str, Any]:
    if response.status_code in {401, 403}:
        raise CRMClientError(
            "CRM service token inválido ou sem permissão",
            status_code=response.status_code,
            response_body=response.text,
        )
    if response.status_code == 404:
        raise CRMClientError(not_found_message, status_code=404, response_body=response.text)
    if response.status_code == 400 and for_context:
        raise CRMClientError(
            "Payload do job incompleto para montar contexto",
            status_code=400,
            response_body=response.text,
        )
    if response.is_success:
        return response.json()
    body = response.text
    raise CRMClientError(
        f"Erro do CRM (status={response.status_code}) ref={request_ref} body={body}",
        status_code=response.status_code,
        response_body=body,
    )


def get_job(job_id: str) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/jobs/{job_id}"
    response = _send_request("GET", url)
    payload = _handle_response(response, job_id, for_context=False)
    return payload.get("job", {})


def get_next_job(types: list[str], limit: int = 1) -> Dict[str, Any] | None:
    if not types:
        raise CRMClientError("types é obrigatório para buscar próximo job")
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/jobs/next"
    params = {"types": ",".join(types), "limit": limit}
    response = _send_request("GET", url, params=params)
    if response.status_code == 204:
        return None
    payload = _handle_response(response, "next", for_context=False)
    return payload.get("job")


def get_whatsapp_execution_context(job_id: str) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/execution-context"
    response = _send_request("GET", url, params={"job_id": job_id})
    return _handle_response(response, job_id, for_context=True)


def save_pregenerated_message(lead_id: int, user_id: int, content: str) -> None:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/followup/scheduled-message"
    body = {"lead_id": lead_id, "user_id": user_id, "content": content}
    response = _send_request("PUT", url, json=body)
    _handle_response(response, str(lead_id), for_context=False)


def claim_job(job_id: str, lease_owner: str, ttl_seconds: int) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/jobs/{job_id}/claim"
    payload = {"lease_owner": lease_owner, "lease_ttl_seconds": ttl_seconds}
    response = _send_request("POST", url, json=payload)
    if response.status_code == 409:
        raise CRMClientConflictError(
            "Job já está em execução",
            status_code=409,
            response_body=response.text,
        )
    return _handle_response(response, job_id, for_context=False)


def complete_job(job_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/jobs/{job_id}/complete"
    payload = {"result": result}
    response = _send_request("POST", url, json=payload)
    return _handle_response(response, job_id, for_context=False)


def fail_job(job_id: str, error: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/jobs/{job_id}/fail"
    payload: Dict[str, Any] = {"error": error}
    if details is not None:
        payload["details"] = details
    response = _send_request("POST", url, json=payload)
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
    response = _send_request("POST", url, json=payload)
    return _handle_response(response, str(lead_id), for_context=False)


def list_appointments(
    *,
    start: str,
    end: str,
    lead_id: int | None = None,
    status: str | None = None,
) -> list[Dict[str, Any]]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/appointments"
    params: Dict[str, Any] = {"start": start, "end": end}
    if lead_id is not None:
        params["lead_id"] = lead_id
    if status:
        params["status"] = status
    response = _send_request("GET", url, params=params)
    payload = _handle_response(response, "appointments", for_context=False)
    if isinstance(payload, list):
        return payload
    return payload.get("appointments", []) if isinstance(payload, dict) else []


def create_lead_appointment(
    *,
    lead_id: int,
    title: str,
    description: str | None,
    appointment_type: str,
    start_at: str,
    end_at: str | None = None,
    source: str | None = None,
) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/appointments"
    payload: Dict[str, Any] = {
        "lead_id": lead_id,
        "title": title,
        "description": description,
        "type": appointment_type,
        "status": "pending",
        "start_at": start_at,
        "end_at": end_at or start_at,
    }
    if source:
        payload["source"] = source
    response = _send_request("POST", url, json=payload)
    return _handle_response(response, str(lead_id), for_context=False)


def log_meeting_scheduled(
    *,
    lead_id: int,
    user_id: int | None,
    job_id: int | None,
    reason: str,
) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/logs/meeting-scheduled"
    payload: Dict[str, Any] = {
        "lead_id": lead_id,
        "reason": reason,
    }
    if user_id is not None:
        payload["user_id"] = user_id
    if job_id is not None:
        payload["job_id"] = job_id
    response = _send_request("POST", url, json=payload)
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
    response = _send_request("POST", url, json=payload)
    return _handle_response(response, str(job_id), for_context=False)


def register_whatsapp_outbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/outbound"
    response = _send_request("POST", url, json=payload)
    return _handle_response(
        response,
        str(payload.get("job_id", "")),
        for_context=False,
        not_found_message="Outbound endpoint não encontrado",
    )


def mark_whatsapp_outbound_sent(outbound_event_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/outbound/{outbound_event_id}/mark-sent"
    response = _send_request("POST", url, json=payload)
    return _handle_response(
        response,
        str(outbound_event_id),
        for_context=False,
        not_found_message="Outbound event não encontrado",
    )


def attach_whatsapp_outbound_provider(outbound_event_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/whatsapp/outbound/{outbound_event_id}/attach-provider"
    response = _send_request("POST", url, json=payload)
    return _handle_response(
        response,
        str(outbound_event_id),
        for_context=False,
        not_found_message="Outbound event não encontrado",
    )


def create_buying_signal_notification(lead_id: int) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/leads/{lead_id}/buying-signal"
    response = _send_request("POST", url)
    return _handle_response(response, str(lead_id), for_context=False)


def get_lead_qualification_state(lead_id: int) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/leads/{lead_id}/qualification-state"
    response = _send_request("GET", url)
    payload = _handle_response(response, str(lead_id), for_context=False)
    return payload.get("qualification_state", {}) if isinstance(payload, dict) else {}


def upsert_lead_qualification_state(lead_id: int, user_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/leads/{lead_id}/qualification-state"
    response = _send_request("POST", url, json={"user_id": user_id, "patch": patch})
    payload = _handle_response(response, str(lead_id), for_context=False)
    return payload.get("qualification_state", {}) if isinstance(payload, dict) else {}


def increment_lead_qualification_attempt(lead_id: int, user_id: int, field: str) -> Dict[str, Any]:
    base_url = settings.crm_api_base.rstrip("/")
    url = f"{base_url}/api/internal/leads/{lead_id}/qualification-state/increment-attempt"
    response = _send_request("POST", url, json={"user_id": user_id, "field": field})
    payload = _handle_response(response, str(lead_id), for_context=False)
    return payload.get("qualification_state", {}) if isinstance(payload, dict) else {}
