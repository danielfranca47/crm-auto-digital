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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, *args, **kwargs):
        self.calls += 1
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
