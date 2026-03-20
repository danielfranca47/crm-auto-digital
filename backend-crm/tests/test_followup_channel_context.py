import importlib.machinery
import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if "fastapi" not in sys.modules:
    fastapi_stub = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("fastapi", None))

    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi_stub.HTTPException = HTTPException
    sys.modules["fastapi"] = fastapi_stub

if "httpx" not in sys.modules:
    httpx_stub = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("httpx", None))

    class RequestError(Exception):
        pass

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class Response:
        status_code = 200
        headers = {}
        text = ""

        def json(self):
            return {}

    httpx_stub.RequestError = RequestError
    httpx_stub.Client = Client
    httpx_stub.Response = Response
    sys.modules["httpx"] = httpx_stub

from fastapi import HTTPException
from services.followup_channel_context import resolve_followup_tick_channel_context


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            payload TEXT,
            status TEXT
        );
        """
    )
    conn.commit()


class FollowupChannelContextTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix="_followup_channel_context.db")
        os.close(fd)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_resolves_from_active_core_connection_by_user(self):
        with patch(
            "core_client.fetch_core_whatsapp_connection_by_user",
            return_value={
                "instance_id": "inst-core-active",
                "provider": "uazapi",
                "connection_status": "active",
                "phone_e164": "+55118888",
            },
        ):
            ctx = resolve_followup_tick_channel_context(self.conn, lead_id=77, user_id=11)

        self.assertEqual(ctx["instance_id"], "inst-core-active")
        self.assertEqual(ctx["provider"], "uazapi")
        self.assertEqual(ctx["phone"], "+55118888")

    def test_falls_back_to_latest_inbound_when_core_connection_not_found(self):
        self.conn.execute(
            """
            INSERT INTO jobs (user_id, type, payload, status)
            VALUES (11, 'whatsapp.inbound.n8n', '{"lead_id": 77, "instance_id": "inst-1", "provider": "uazapi", "phone": "+55119999"}', 'completed')
            """
        )
        self.conn.commit()

        with patch(
            "core_client.fetch_core_whatsapp_connection_by_user",
            side_effect=HTTPException(status_code=404, detail="Connection not found"),
        ):
            ctx = resolve_followup_tick_channel_context(self.conn, lead_id=77, user_id=11)
        self.assertEqual(ctx["instance_id"], "inst-1")
        self.assertEqual(ctx["provider"], "uazapi")

    def test_raises_early_when_core_connection_is_inactive(self):
        with patch(
            "core_client.fetch_core_whatsapp_connection_by_user",
            return_value={
                "instance_id": "inst-inactive",
                "provider": "uazapi",
                "connection_status": "inactive",
            },
        ):
            with self.assertRaises(HTTPException) as ctx:
                resolve_followup_tick_channel_context(self.conn, lead_id=77, user_id=11)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_raises_when_no_valid_inbound_context(self):
        self.conn.execute(
            """
            INSERT INTO jobs (user_id, type, payload, status)
            VALUES (11, 'whatsapp.inbound.n8n', '{"lead_id": 77}', 'completed')
            """
        )
        self.conn.commit()

        with patch(
            "core_client.fetch_core_whatsapp_connection_by_user",
            side_effect=HTTPException(status_code=404, detail="Connection not found"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                resolve_followup_tick_channel_context(self.conn, lead_id=77, user_id=11)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
