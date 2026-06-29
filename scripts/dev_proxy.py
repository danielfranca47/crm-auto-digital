"""Reverse proxy local: junta backend-core (8001) e backend-crm (8000) numa
unica porta, para expor um so tunel ngrok no plano gratuito (1 endpoint).

Roteamento: /auth/* e /me/* -> backend-core; tudo o resto -> backend-crm.

Uso: python scripts/dev_proxy.py [porta]   (porta padrao: 9000)
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CORE_BASE = "http://127.0.0.1:8001"
CRM_BASE = "http://127.0.0.1:8000"
CORE_PREFIXES = ("/auth", "/me")

HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "content-encoding", "host", "content-length"}


class ProxyHandler(BaseHTTPRequestHandler):
    def _target_base(self) -> str:
        return CORE_BASE if any(self.path.startswith(p) for p in CORE_PREFIXES) else CRM_BASE

    def _proxy(self) -> None:
        target = self._target_base() + self.path
        length = self.headers.get("Content-Length")
        body = self.rfile.read(int(length)) if length else None

        req = urllib.request.Request(target, data=body, method=self.command)
        for key, value in self.headers.items():
            if key.lower() not in HOP_BY_HOP:
                req.add_header(key, value)

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                self._relay(resp.status, resp.headers.items(), resp.read())
        except urllib.error.HTTPError as exc:
            self._relay(exc.code, exc.headers.items() if exc.headers else [], exc.read())
        except Exception as exc:  # backend offline, timeout, etc.
            payload = f'{{"detail": "Proxy error: {exc}"}}'.encode()
            self._relay(502, [("Content-Type", "application/json")], payload)

    def _relay(self, status: int, headers, body: bytes) -> None:
        self.send_response(status)
        for key, value in headers:
            if key.lower() not in HOP_BY_HOP:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _proxy

    def log_message(self, fmt, *args):  # silencia logs default, mantem so o essencial
        print(f"[proxy] {self._target_base()} <- {self.command} {self.path}")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    server = ThreadingHTTPServer(("127.0.0.1", port), ProxyHandler)
    print(f"dev_proxy escutando em http://127.0.0.1:{port}")
    print(f"  {CORE_PREFIXES} -> {CORE_BASE}")
    print(f"  demais rotas    -> {CRM_BASE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
