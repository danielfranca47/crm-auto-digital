"""Entrypoint que serve a app FastAPI em dois sockets (IPv4 e IPv6) na mesma porta.

Necessário porque o runtime de container do Railway não dá bind dual-stack real
em "::" — bind explícito em IPv6 vira IPv6-only e perde o acesso via domínio
público (IPv4). Dois sockets independentes resolvem isso sem depender do SO.
"""
from __future__ import annotations

import asyncio
import os

import uvicorn

from app.main import app


async def _serve() -> None:
    port = int(os.environ.get("PORT", "8002"))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()

    servers = [
        uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level=log_level)),
        uvicorn.Server(uvicorn.Config(app, host="::", port=port, log_level=log_level)),
    ]
    await asyncio.gather(*(server.serve() for server in servers))


if __name__ == "__main__":
    asyncio.run(_serve())
