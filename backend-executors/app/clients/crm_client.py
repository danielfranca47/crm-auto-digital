from typing import Any, Dict

import httpx

from app.core.config import settings


class CRMClientError(RuntimeError):
    pass


def _require_token() -> str:
    token = settings.crm_service_token
    if not token:
        raise CRMClientError("CRM_SERVICE_TOKEN não configurado")
    return token


def _headers() -> Dict[str, str]:
    return {"X-Service-Token": _require_token()}


def _handle_response(response: httpx.Response, job_id: str, for_context: bool) -> Dict[str, Any]:
    if response.status_code in {401, 403}:
        raise CRMClientError("CRM service token inválido ou sem permissão")
    if response.status_code == 404:
        raise CRMClientError("Job não encontrado")
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
