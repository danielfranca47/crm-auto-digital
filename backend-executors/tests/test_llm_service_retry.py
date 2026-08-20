import httpx
import pytest

from app.services import llm_service


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.post_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, *args, **kwargs):
        self.calls += 1
        self.post_calls.append({"args": args, "kwargs": kwargs})
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _llm_key_and_no_sleep(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(llm_service.time, "sleep", lambda _seconds: None)


def _patch_client(monkeypatch, responses):
    fake_client = _FakeClient(responses)
    monkeypatch.setattr(llm_service.httpx, "Client", lambda timeout: fake_client)
    return fake_client


def test_first_attempt_success_no_retry(monkeypatch):
    fake_client = _patch_client(
        monkeypatch, [_FakeResponse(200, json_data={"output_text": "ok"})]
    )
    result = llm_service._post_with_retry({"input": "x"})
    assert result == {"output_text": "ok"}
    assert fake_client.calls == 1


def test_request_error_then_success_retries_once(monkeypatch):
    fake_client = _patch_client(
        monkeypatch,
        [httpx.ConnectError("boom"), _FakeResponse(200, json_data={"output_text": "ok"})],
    )
    result = llm_service._post_with_retry({"input": "x"})
    assert result == {"output_text": "ok"}
    assert fake_client.calls == 2


def test_request_error_twice_raises_after_max_attempts(monkeypatch):
    fake_client = _patch_client(
        monkeypatch, [httpx.ConnectError("boom1"), httpx.ConnectError("boom2")]
    )
    with pytest.raises(httpx.ConnectError):
        llm_service._post_with_retry({"input": "x"})
    assert fake_client.calls == 2


def test_status_503_then_200_retries(monkeypatch):
    fake_client = _patch_client(
        monkeypatch,
        [_FakeResponse(503, text="unavailable"), _FakeResponse(200, json_data={"output_text": "ok"})],
    )
    result = llm_service._post_with_retry({"input": "x"})
    assert result == {"output_text": "ok"}
    assert fake_client.calls == 2


def test_status_500_twice_raises_http_status_error(monkeypatch):
    fake_client = _patch_client(
        monkeypatch, [_FakeResponse(500, text="err1"), _FakeResponse(500, text="err2")]
    )
    with pytest.raises(httpx.HTTPStatusError):
        llm_service._post_with_retry({"input": "x"})
    assert fake_client.calls == 2


def test_status_400_does_not_retry(monkeypatch):
    fake_client = _patch_client(monkeypatch, [_FakeResponse(400, text="bad request")])
    with pytest.raises(httpx.HTTPStatusError):
        llm_service._post_with_retry({"input": "x"})
    assert fake_client.calls == 1


def test_status_429_retries(monkeypatch):
    fake_client = _patch_client(
        monkeypatch,
        [_FakeResponse(429, text="rate limited"), _FakeResponse(200, json_data={"output_text": "ok"})],
    )
    result = llm_service._post_with_retry({"input": "x"})
    assert result == {"output_text": "ok"}
    assert fake_client.calls == 2


@pytest.mark.parametrize(
    "func_call",
    [
        lambda: llm_service.generate_mother_route("prompt"),
        lambda: llm_service.generate_decision_text("prompt"),
        lambda: llm_service.generate_child_result("recepcao", "prompt"),
    ],
)
def test_public_functions_use_retry_helper(monkeypatch, func_call):
    _patch_client(
        monkeypatch,
        [httpx.ConnectError("boom"), _FakeResponse(200, json_data={"output_text": "resposta"})],
    )
    assert func_call() == "resposta"


def test_stub_mode_no_http_call_when_no_api_key(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "llm_api_key", None)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("não devia fazer chamada HTTP em modo stub")

    monkeypatch.setattr(llm_service.httpx, "Client", _fail_if_called)

    assert "stub_no_key" in llm_service.generate_mother_route("prompt")
    assert "stub_no_key" in llm_service.generate_decision_text("prompt")
    assert llm_service.generate_child_result("recepcao", "prompt")


# ---------------------------------------------------------------------------
# Resolução de provedor (OpenAI padrão / OpenRouter alternativo)
# ---------------------------------------------------------------------------


def test_resolve_provider_config_default_is_openai_when_no_ai_profile(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
    cfg = llm_service._resolve_provider_config(None)
    assert cfg.name == llm_service.PROVIDER_OPENAI
    assert cfg.api_key == "test-key"
    assert cfg.model == llm_service.settings.llm_model


def test_resolve_provider_config_openai_explicit(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
    cfg = llm_service._resolve_provider_config({"llm_provider": "openai"})
    assert cfg.name == llm_service.PROVIDER_OPENAI


def test_resolve_provider_config_openrouter_default_model(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
    cfg = llm_service._resolve_provider_config({"llm_provider": "openrouter"})
    assert cfg.name == llm_service.PROVIDER_OPENROUTER
    assert cfg.api_key == "or-key"
    assert cfg.model == llm_service.OPENROUTER_MODEL_DEFAULT


def test_resolve_provider_config_openrouter_quality_model(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
    cfg = llm_service._resolve_provider_config(
        {"llm_provider": "openrouter", "llm_provider_model": llm_service.OPENROUTER_MODEL_QUALITY}
    )
    assert cfg.model == llm_service.OPENROUTER_MODEL_QUALITY


def test_resolve_provider_config_openrouter_unknown_model_clamped_to_default(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
    cfg = llm_service._resolve_provider_config(
        {"llm_provider": "openrouter", "llm_provider_model": "some/unvetted-model"}
    )
    assert cfg.model == llm_service.OPENROUTER_MODEL_DEFAULT


def test_resolve_provider_config_openrouter_missing_key_falls_back_to_openai(monkeypatch, caplog):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", None)
    with caplog.at_level("WARNING"):
        cfg = llm_service._resolve_provider_config({"llm_provider": "openrouter"})
    assert cfg.name == llm_service.PROVIDER_OPENAI
    assert cfg.api_key == "test-key"
    assert "event=llm_provider_fallback" in caplog.text


def test_extract_text_openrouter_parses_choices_message_content():
    cfg = llm_service._ProviderConfig(
        name=llm_service.PROVIDER_OPENROUTER, api_base="x", api_key="k", model="m"
    )
    payload = {"choices": [{"message": {"content": "resposta gerada"}}]}
    assert llm_service._extract_output_text(cfg, payload) == "resposta gerada"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_extract_text_openrouter_raises_on_malformed_payload(payload):
    cfg = llm_service._ProviderConfig(
        name=llm_service.PROVIDER_OPENROUTER, api_base="x", api_key="k", model="m"
    )
    with pytest.raises(ValueError):
        llm_service._extract_output_text(cfg, payload)


def test_build_payload_openrouter_uses_chat_completions_shape():
    cfg = llm_service._ProviderConfig(
        name=llm_service.PROVIDER_OPENROUTER, api_base="x", api_key="k", model="meta-llama/llama-3.3-70b-instruct"
    )
    payload = llm_service._build_payload(cfg, "prompt texto", json_mode=True, route="qualification")
    assert payload["model"] == "meta-llama/llama-3.3-70b-instruct"
    assert payload["messages"] == [{"role": "user", "content": "prompt texto"}]
    assert payload["response_format"] == {"type": "json_object"}
    assert "input" not in payload
    assert "metadata" not in payload  # route não é enviado para OpenRouter


def test_build_payload_openai_unchanged_shape():
    cfg = llm_service._ProviderConfig(
        name=llm_service.PROVIDER_OPENAI, api_base="x", api_key="k", model="gpt-4o-mini"
    )
    payload = llm_service._build_payload(cfg, "prompt texto", json_mode=True, route="qualification")
    assert payload == {
        "model": "gpt-4o-mini",
        "input": "prompt texto",
        "text": {"format": {"type": "json_object"}},
        "metadata": {"route": "qualification"},
    }


def test_generate_child_result_routes_to_openrouter_endpoint(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", "or-key")
    fake_client = _patch_client(
        monkeypatch,
        [_FakeResponse(200, json_data={"choices": [{"message": {"content": "resposta"}}]})],
    )
    result = llm_service.generate_child_result(
        "recepcao", "prompt", ai_profile={"llm_provider": "openrouter"}
    )
    assert result == "resposta"
    assert fake_client.calls == 1
    sent_url = fake_client.post_calls[0]["args"][0]
    assert sent_url == llm_service.settings.openrouter_api_base
    sent_payload = fake_client.post_calls[0]["kwargs"]["json"]
    assert sent_payload["model"] == llm_service.OPENROUTER_MODEL_DEFAULT
    assert "messages" in sent_payload


def test_generate_child_result_openrouter_without_key_falls_back_to_openai(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "openrouter_api_key", None)
    fake_client = _patch_client(
        monkeypatch,
        [_FakeResponse(200, json_data={"output_text": "resposta openai"})],
    )
    result = llm_service.generate_child_result(
        "recepcao", "prompt", ai_profile={"llm_provider": "openrouter"}
    )
    assert result == "resposta openai"
    sent_url = fake_client.post_calls[0]["args"][0]
    assert sent_url == llm_service.settings.llm_api_base
