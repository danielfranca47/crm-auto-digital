import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from routes.uploads import MAX_UPLOAD_BYTES, UploadContentLengthGuardMiddleware


def _build_app() -> Starlette:
    """App mínima isolada, só com o middleware montado — não precisa subir o
    app.py completo do CRM (DB/CORS/routers) para testar o guard em si."""

    async def echo_ok(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[
        Route("/api/uploads", echo_ok, methods=["POST"]),
        Route("/api/leads", echo_ok, methods=["POST"]),
    ])
    app.add_middleware(UploadContentLengthGuardMiddleware)
    return app


class TestUploadContentLengthGuard:
    def setup_method(self):
        self.client = TestClient(_build_app())

    def test_rejects_declared_size_above_limit(self):
        oversized = MAX_UPLOAD_BYTES + (1024 * 1024)
        resp = self.client.post(
            "/api/uploads",
            headers={"content-length": str(oversized)},
            content=b"",
        )
        assert resp.status_code == 413
        assert "10MB" in resp.json()["detail"]

    def test_allows_declared_size_within_limit(self):
        resp = self.client.post(
            "/api/uploads",
            headers={"content-length": "1024"},
            content=b"x" * 1024,
        )
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_allows_request_without_content_length(self):
        def stream():
            yield b"x" * 1024

        resp = self.client.post("/api/uploads", content=stream())
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_does_not_affect_other_paths(self):
        oversized = MAX_UPLOAD_BYTES + (1024 * 1024)
        resp = self.client.post(
            "/api/leads",
            headers={"content-length": str(oversized)},
            content=b"",
        )
        assert resp.status_code == 200
        assert resp.text == "ok"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
