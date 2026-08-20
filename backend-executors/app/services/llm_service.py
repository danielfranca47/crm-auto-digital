from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 2
_RETRY_BACKOFF_SECONDS = 1.0

PROVIDER_OPENAI = "openai"
PROVIDER_OPENROUTER = "openrouter"

# Modelos curados do OpenRouter — dropdown fechado no AI Profile, nunca texto livre.
# Trocar/adicionar modelo aqui é uma mudança de código (deploy), de propósito: cada
# opção foi validada quanto a confiabilidade de JSON estruturado e qualidade em PT-BR
# antes de entrar na lista. Ver docs/architecture/llm-architecture.md.
OPENROUTER_MODEL_DEFAULT = "meta-llama/llama-3.3-70b-instruct"
OPENROUTER_MODEL_QUALITY = "nousresearch/hermes-3-llama-3.1-405b"
_OPENROUTER_ALLOWED_MODELS = {OPENROUTER_MODEL_DEFAULT, OPENROUTER_MODEL_QUALITY}


class _ProviderConfig:
    __slots__ = ("name", "api_base", "api_key", "model")

    def __init__(self, name: str, api_base: str, api_key: Optional[str], model: str) -> None:
        self.name = name
        self.api_base = api_base
        self.api_key = api_key
        self.model = model


def _resolve_provider_config(ai_profile: Optional[Dict[str, Any]]) -> _ProviderConfig:
    """Decide o provider/modelo desta chamada a partir do ai_profile.

    - Ausente/None ou llm_provider ausente/"openai" -> OpenAI (comportamento atual).
    - llm_provider == "openrouter" e OPENROUTER_API_KEY configurada -> OpenRouter, com
      o modelo curado de ai_profile.llm_provider_model (ou o default se ausente/fora
      da lista curada — a validação Pydantic em backend-core já bloqueia texto livre,
      isto é uma segunda camada de defesa para valores antigos já persistidos).
    - llm_provider == "openrouter" mas OPENROUTER_API_KEY ausente no servidor -> cai
      para OpenAI (problema de deploy do operador, não deve quebrar o turno do lead).
      Se a chave da OpenAI também estiver ausente, o caller cai no stub normal — sem
      caso especial adicional.
    """
    provider = (ai_profile or {}).get("llm_provider") or PROVIDER_OPENAI

    if provider == PROVIDER_OPENROUTER:
        if settings.openrouter_api_key:
            model = (ai_profile or {}).get("llm_provider_model")
            if model not in _OPENROUTER_ALLOWED_MODELS:
                model = OPENROUTER_MODEL_DEFAULT
            return _ProviderConfig(
                name=PROVIDER_OPENROUTER,
                api_base=settings.openrouter_api_base,
                api_key=settings.openrouter_api_key,
                model=model,
            )
        logger.warning(
            "event=llm_provider_fallback provider=openrouter reason=missing_api_key fallback=openai"
        )

    return _ProviderConfig(
        name=PROVIDER_OPENAI,
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )


def _stub_response() -> str:
    payload = {
        "next_action": "reply",
        "message_text": "Olá! Como posso ajudar?",
        "questions": [],
        "reason": "stub_no_key",
    }
    return json.dumps(payload, ensure_ascii=False)


def _stub_mother_response() -> str:
    payload = {
        "route_to": "qualification",
        "confidence": 0.5,
        "reason": "stub_no_key",
    }
    return json.dumps(payload, ensure_ascii=False)


def _stub_child_response() -> str:
    payload = {
        "message_text": "Olá! Como posso ajudar?",
        "did_complete_phase": False,
        "recommended_next_category": None,
        "outcome": None,
        "kanban_highlight": None,
        "signals": [],
        "confidence": 0.5,
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_text_openai(payload: Dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    output_items = payload.get("output")
    if not isinstance(output_items, list):
        raise ValueError("LLM response missing output")

    chunks: list[str] = []
    for item in output_items:
        contents = item.get("content") if isinstance(item, dict) else None
        if not isinstance(contents, list):
            continue
        for content in contents:
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and isinstance(content.get("text"), str)
            ):
                chunks.append(content["text"])

    if not chunks:
        raise ValueError("LLM response missing output_text")
    return "".join(chunks)


def _extract_text_openrouter(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response missing choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content:
        raise ValueError("LLM response missing message content")
    return content


def _extract_output_text(cfg: _ProviderConfig, payload: Dict[str, Any]) -> str:
    if cfg.name == PROVIDER_OPENROUTER:
        return _extract_text_openrouter(payload)
    return _extract_text_openai(payload)


def _build_payload(
    cfg: _ProviderConfig, prompt: str, *, json_mode: bool, route: Optional[str] = None
) -> Dict[str, Any]:
    if cfg.name == PROVIDER_OPENROUTER:
        payload: Dict[str, Any] = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    payload = {"model": cfg.model, "input": prompt}
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}
    if route:
        payload["metadata"] = {"route": route}
    return payload


def _post_with_retry(
    payload: Dict[str, Any],
    *,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """POST para a LLM API com retry curto para falhas transitórias.

    Re-tenta em httpx.RequestError (timeout/erro de rede) e em status codes
    retryable (429/500/502/503/504). Não re-tenta em 4xx não-retryable
    (400/401/403/422) — falha imediatamente, pois retry não resolveria.

    api_base/api_key por omissão usam a config da OpenAI (settings.llm_*) — quem
    chama por um provedor alternativo (OpenRouter) passa-os explicitamente.
    """
    resolved_base = api_base if api_base is not None else settings.llm_api_base
    resolved_key = api_key if api_key is not None else settings.llm_api_key
    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.llm_timeout_seconds)
    last_exc: Optional[Exception] = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(resolved_base, headers=headers, json=payload)
        except httpx.RequestError as exc:
            last_exc = exc
            logger.warning(
                "event=llm_request_error attempt=%s/%s exc_type=%s exc=%s",
                attempt, _MAX_ATTEMPTS, type(exc).__name__, exc,
            )
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF_SECONDS)
                continue
            raise
        if response.status_code != 200:
            truncated = response.text[:1000]
            logger.warning(
                "event=llm_response_error attempt=%s/%s status=%s body=%s",
                attempt, _MAX_ATTEMPTS, response.status_code, truncated,
            )
        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF_SECONDS)
            continue
        response.raise_for_status()
        return response.json()
    if last_exc:
        raise last_exc
    raise RuntimeError("llm request failed without exception")


def _generate_json(
    prompt: str,
    *,
    stub,
    ai_profile: Optional[Dict[str, Any]] = None,
    route: Optional[str] = None,
) -> str:
    cfg = _resolve_provider_config(ai_profile)
    if not cfg.api_key:
        return stub()
    payload = _build_payload(cfg, prompt, json_mode=True, route=route)
    response = _post_with_retry(payload, api_base=cfg.api_base, api_key=cfg.api_key)
    return _extract_output_text(cfg, response)


def _generate_text(prompt: str, *, ai_profile: Optional[Dict[str, Any]] = None) -> str:
    cfg = _resolve_provider_config(ai_profile)
    if not cfg.api_key:
        return ""
    payload = _build_payload(cfg, prompt, json_mode=False)
    response = _post_with_retry(payload, api_base=cfg.api_base, api_key=cfg.api_key)
    return _extract_output_text(cfg, response)


def generate_decision_text(prompt: str, *, ai_profile: Optional[Dict[str, Any]] = None) -> str:
    return _generate_json(prompt, stub=_stub_response, ai_profile=ai_profile)


def generate_mother_route(prompt: str, *, ai_profile: Optional[Dict[str, Any]] = None) -> str:
    return _generate_json(prompt, stub=_stub_mother_response, ai_profile=ai_profile)


def generate_child_result(
    route: str, prompt: str, *, ai_profile: Optional[Dict[str, Any]] = None
) -> str:
    return _generate_json(prompt, stub=_stub_child_response, ai_profile=ai_profile, route=route)


def generate_conflict_message(prompt: str, *, ai_profile: Optional[Dict[str, Any]] = None) -> str:
    return _generate_text(prompt, ai_profile=ai_profile)


def generate_appointment_reminder_message(
    prompt: str, *, ai_profile: Optional[Dict[str, Any]] = None
) -> str:
    return _generate_text(prompt, ai_profile=ai_profile)


def generate_appointment_title_message(
    prompt: str, *, ai_profile: Optional[Dict[str, Any]] = None
) -> str:
    return _generate_text(prompt, ai_profile=ai_profile)
