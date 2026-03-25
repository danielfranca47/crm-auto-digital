from typing import Any, Dict

import httpx

from app.core.config import settings


class CoreClientError(RuntimeError):
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


def _require_token() -> str:
    token = settings.core_service_token
    if not token:
        raise CoreClientError("CORE_SERVICE_TOKEN não configurado")
    return token


def _headers() -> Dict[str, str]:
    return {"X-Service-Token": _require_token()}


def _handle_response(response: httpx.Response) -> Dict[str, Any]:
    if response.status_code in {401, 403}:
        raise CoreClientError(
            "Core service token inválido ou sem permissão",
            status_code=response.status_code,
            response_body=response.text,
        )
    if response.is_success:
        return response.json()
    body = response.text
    raise CoreClientError(
        f"Erro do Core (status={response.status_code}) body={body}",
        status_code=response.status_code,
        response_body=body,
    )


def send_whatsapp_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.core_api_base.rstrip("/")
    url = f"{base_url}/whatsapp/send"
    with httpx.Client(timeout=15.0) as client:
        try:
            response = client.post(url, headers=_headers(), json=payload)
        except httpx.RequestError as exc:
            raise CoreClientError(
                f"Erro de rede do Core: {exc}",
                error_type="network",
            ) from exc
    return _handle_response(response)
