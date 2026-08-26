import asyncio
import unittest

import httpx

from app.providers import uazapi_client


class _FakeResponse:
    def __init__(self, status_code: int, json_data=None, text: str = "", headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.headers = headers or {}

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class UazapiClientRetryTests(unittest.TestCase):
    def setUp(self):
        import unittest.mock as mock

        self._sleep_patch = mock.patch.object(uazapi_client.asyncio, "sleep", self._fake_sleep)
        self._sleep_patch.start()
        self.addCleanup(self._sleep_patch.stop)

    async def _fake_sleep(self, _seconds):
        return None

    def _run(self, coro):
        return asyncio.run(coro)

    def _patch(self, responses):
        import unittest.mock as mock

        fake_client = _FakeAsyncClient(responses)
        patcher = mock.patch.object(uazapi_client.httpx, "AsyncClient", lambda timeout: fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake_client

    def test_first_attempt_success_no_retry(self):
        fake_client = self._patch([_FakeResponse(200, json_data={"id": "msg1"})])
        result = self._run(
            uazapi_client.send_text(base_url="https://api.example.com", token="tok", number="5511999999999", text="hi")
        )
        self.assertEqual(result, {"id": "msg1"})
        self.assertEqual(fake_client.calls, 1)

    def test_429_then_success_retries_once(self):
        fake_client = self._patch(
            [
                _FakeResponse(429, text="rate limited"),
                _FakeResponse(200, json_data={"id": "msg2"}),
            ]
        )
        result = self._run(
            uazapi_client.send_text(base_url="https://api.example.com", token="tok", number="5511999999999", text="hi")
        )
        self.assertEqual(result, {"id": "msg2"})
        self.assertEqual(fake_client.calls, 2)

    def test_503_then_success_retries(self):
        fake_client = self._patch(
            [
                _FakeResponse(503, text="unavailable"),
                _FakeResponse(200, json_data={"id": "msg3"}),
            ]
        )
        result = self._run(
            uazapi_client.send_text(base_url="https://api.example.com", token="tok", number="5511999999999", text="hi")
        )
        self.assertEqual(result, {"id": "msg3"})
        self.assertEqual(fake_client.calls, 2)

    def test_500_then_success_retries(self):
        fake_client = self._patch(
            [
                _FakeResponse(500, text="internal error"),
                _FakeResponse(200, json_data={"id": "msg5"}),
            ]
        )
        result = self._run(
            uazapi_client.send_text(base_url="https://api.example.com", token="tok", number="5511999999999", text="hi")
        )
        self.assertEqual(result, {"id": "msg5"})
        self.assertEqual(fake_client.calls, 2)

    def test_502_then_success_retries(self):
        fake_client = self._patch(
            [
                _FakeResponse(502, text="bad gateway"),
                _FakeResponse(200, json_data={"id": "msg6"}),
            ]
        )
        result = self._run(
            uazapi_client.send_text(base_url="https://api.example.com", token="tok", number="5511999999999", text="hi")
        )
        self.assertEqual(result, {"id": "msg6"})
        self.assertEqual(fake_client.calls, 2)

    def test_504_then_success_retries(self):
        fake_client = self._patch(
            [
                _FakeResponse(504, text="gateway timeout"),
                _FakeResponse(200, json_data={"id": "msg7"}),
            ]
        )
        result = self._run(
            uazapi_client.send_text(base_url="https://api.example.com", token="tok", number="5511999999999", text="hi")
        )
        self.assertEqual(result, {"id": "msg7"})
        self.assertEqual(fake_client.calls, 2)

    def test_401_does_not_retry(self):
        fake_client = self._patch([_FakeResponse(401, text="unauthorized")])
        with self.assertRaises(uazapi_client.UazapiClientError) as ctx:
            self._run(
                uazapi_client.send_text(
                    base_url="https://api.example.com", token="tok", number="5511999999999", text="hi"
                )
            )
        self.assertEqual(fake_client.calls, 1)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_exhausts_attempts_and_raises(self):
        fake_client = self._patch(
            [
                _FakeResponse(429, text="rate limited 1"),
                _FakeResponse(429, text="rate limited 2"),
                _FakeResponse(429, text="rate limited 3"),
            ]
        )
        with self.assertRaises(uazapi_client.UazapiClientError) as ctx:
            self._run(
                uazapi_client.send_text(
                    base_url="https://api.example.com", token="tok", number="5511999999999", text="hi"
                )
            )
        self.assertEqual(fake_client.calls, uazapi_client._MAX_ATTEMPTS)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_400_does_not_retry(self):
        fake_client = self._patch([_FakeResponse(400, text="bad request")])
        with self.assertRaises(uazapi_client.UazapiClientError) as ctx:
            self._run(
                uazapi_client.send_text(
                    base_url="https://api.example.com", token="tok", number="5511999999999", text="hi"
                )
            )
        self.assertEqual(fake_client.calls, 1)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_retry_after_header_respected_and_capped(self):
        fake_client = self._patch(
            [
                _FakeResponse(429, text="rate limited", headers={"Retry-After": "999"}),
                _FakeResponse(200, json_data={"id": "msg4"}),
            ]
        )
        result = self._run(
            uazapi_client.send_text(base_url="https://api.example.com", token="tok", number="5511999999999", text="hi")
        )
        self.assertEqual(result, {"id": "msg4"})
        self.assertEqual(fake_client.calls, 2)

    def test_timeout_does_not_retry(self):
        fake_client = self._patch([httpx.TimeoutException("timed out")])
        with self.assertRaises(uazapi_client.UazapiTimeoutError):
            self._run(
                uazapi_client.send_text(
                    base_url="https://api.example.com", token="tok", number="5511999999999", text="hi"
                )
            )
        self.assertEqual(fake_client.calls, 1)

    def test_send_media_retries_on_429(self):
        fake_client = self._patch(
            [
                _FakeResponse(429, text="rate limited"),
                _FakeResponse(200, json_data={"id": "media1"}),
            ]
        )
        result = self._run(
            uazapi_client.send_media(
                base_url="https://api.example.com",
                token="tok",
                number="5511999999999",
                media_url="https://cdn.example.com/img.png",
                media_type="image",
            )
        )
        self.assertEqual(result, {"id": "media1"})
        self.assertEqual(fake_client.calls, 2)


if __name__ == "__main__":
    unittest.main()
