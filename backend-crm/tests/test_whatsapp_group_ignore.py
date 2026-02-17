import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest

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

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def post(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    def Header(default=None, alias=None):
        return default

    def Query(default=None):
        return default

    def Depends(_dep=None):
        return None

    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.APIRouter = APIRouter
    fastapi_stub.Header = Header
    fastapi_stub.Query = Query
    fastapi_stub.Depends = Depends
    sys.modules["fastapi"] = fastapi_stub

    security_stub = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("fastapi.security", None))

    class HTTPAuthorizationCredentials:
        def __init__(self, credentials: str = "") -> None:
            self.credentials = credentials

    class HTTPBearer:
        def __init__(self, auto_error: bool = False) -> None:
            self.auto_error = auto_error

        def __call__(self, *args, **kwargs):
            return None

    security_stub.HTTPAuthorizationCredentials = HTTPAuthorizationCredentials
    security_stub.HTTPBearer = HTTPBearer
    sys.modules["fastapi.security"] = security_stub

if "pydantic" not in sys.modules:
    pydantic_stub = importlib.util.module_from_spec(importlib.machinery.ModuleSpec("pydantic", None))

    class FieldInfo:
        def __init__(self, default, alias=None):
            self.default = default
            self.alias = alias

    def Field(default=None, *, alias=None, default_factory=None):
        if default is None and default_factory is not None:
            default = default_factory()
        return FieldInfo(default, alias=alias)

    def ConfigDict(**kwargs):
        return dict(**kwargs)

    class BaseModel:
        def __init__(self, **data):
            annotations = getattr(self, "__annotations__", {})
            for name in annotations.keys():
                field = getattr(self.__class__, name, None)
                alias = field.alias if isinstance(field, FieldInfo) else None
                key = name if name in data else alias
                if key is None or key not in data:
                    value = field.default if isinstance(field, FieldInfo) else None
                else:
                    value = data.get(key)
                setattr(self, name, value)

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.ConfigDict = ConfigDict
    pydantic_stub.Field = Field
    sys.modules["pydantic"] = pydantic_stub

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

        def get(self, *args, **kwargs):
            raise RequestError("httpx stub")

    class Response:
        def __init__(self, status_code=500, text=""):
            self.status_code = status_code
            self.text = text

        def json(self):
            return {}

    httpx_stub.RequestError = RequestError
    httpx_stub.Client = Client
    httpx_stub.Response = Response
    sys.modules["httpx"] = httpx_stub

import database
from database import get_connection, init_db

WEBHOOKS_PATH = os.path.join(PROJECT_ROOT, "routes", "webhooks.py")
webhooks_spec = importlib.util.spec_from_file_location("webhooks", WEBHOOKS_PATH)
webhooks = importlib.util.module_from_spec(webhooks_spec)
webhooks_spec.loader.exec_module(webhooks)

INBOUND_HANDLER_PATH = os.path.join(PROJECT_ROOT, "services", "whatsapp_inbound", "inbound_handler.py")
inbound_spec = importlib.util.spec_from_file_location("inbound_handler", INBOUND_HANDLER_PATH)
inbound_handler = importlib.util.module_from_spec(inbound_spec)
inbound_spec.loader.exec_module(inbound_handler)


class WhatsappGroupIgnoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "crm-test.db")
        database.DB_PATH = self.db_path
        init_db()

        os.environ["CRM_WEBHOOK_SECRET"] = "test-secret"
        self._orig_handle_inbound = webhooks.handle_inbound
        self.calls = []

        def _fake_handle_inbound(payload):
            self.calls.append(payload)
            return {"status": "accepted", "lead_id": 1, "job_id": 10}

        webhooks.handle_inbound = _fake_handle_inbound

    def tearDown(self):
        webhooks.handle_inbound = self._orig_handle_inbound
        os.environ.pop("CRM_WEBHOOK_SECRET", None)
        self.temp_dir.cleanup()

    def _assert_no_side_effects(self):
        with get_connection() as conn:
            jobs = conn.execute("SELECT COUNT(1) as total FROM jobs").fetchone()["total"]
            leads = conn.execute("SELECT COUNT(1) as total FROM leads").fetchone()["total"]
            messages = conn.execute("SELECT COUNT(1) as total FROM messages").fetchone()["total"]
            inbound_events = conn.execute("SELECT COUNT(1) as total FROM inbound_events").fetchone()["total"]
        self.assertEqual(jobs, 0)
        self.assertEqual(leads, 0)
        self.assertEqual(messages, 0)
        self.assertEqual(inbound_events, 0)

    def _base_payload(self):
        return {
            "event": "message",
            "instance": "inst-1",
            "chat": {"phone": "+5511999999999"},
            "data": {"messageId": "m-1", "text": "oi", "messageType": "text", "fromMe": False},
            "message": {},
        }

    def test_chat_is_group_true_ignored(self):
        payload = self._base_payload()
        payload["chat"]["isGroup"] = True
        result = webhooks.whatsapp_uazapi_webhook(payload, x_webhook_secret="test-secret")
        self.assertEqual(result, {"status": "ignored", "reason": "group_message"})
        self.assertEqual(self.calls, [])
        self._assert_no_side_effects()

    def test_data_is_group_true_ignored(self):
        payload = self._base_payload()
        payload["data"]["isGroup"] = True
        result = webhooks.whatsapp_uazapi_webhook(payload, x_webhook_secret="test-secret")
        self.assertEqual(result, {"status": "ignored", "reason": "group_message"})
        self.assertEqual(self.calls, [])
        self._assert_no_side_effects()

    def test_message_group_id_ignored(self):
        payload = self._base_payload()
        payload["message"]["groupId"] = "12345-1@g.us"
        result = webhooks.whatsapp_uazapi_webhook(payload, x_webhook_secret="test-secret")
        self.assertEqual(result, {"status": "ignored", "reason": "group_message"})
        self.assertEqual(self.calls, [])
        self._assert_no_side_effects()

    def test_remote_jid_group_ignored(self):
        payload = self._base_payload()
        payload["data"]["remoteJid"] = "123456789-123@g.us"
        result = webhooks.whatsapp_uazapi_webhook(payload, x_webhook_secret="test-secret")
        self.assertEqual(result, {"status": "ignored", "reason": "group_message"})
        self.assertEqual(self.calls, [])
        self._assert_no_side_effects()

    def test_personal_message_calls_inbound(self):
        payload = self._base_payload()
        result = webhooks.whatsapp_uazapi_webhook(payload, x_webhook_secret="test-secret")
        self.assertEqual(result, {"status": "accepted", "lead_id": 1, "job_id": 10})
        self.assertEqual(len(self.calls), 1)


class InboundDefenseInDepthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "crm-test.db")
        database.DB_PATH = self.db_path
        init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_handle_inbound_ignores_is_group_without_side_effects(self):
        result = inbound_handler.handle_inbound({"is_group": True})
        self.assertEqual(result, {"status": "ignored", "reason": "group_message"})

        with get_connection() as conn:
            jobs = conn.execute("SELECT COUNT(1) as total FROM jobs").fetchone()["total"]
            leads = conn.execute("SELECT COUNT(1) as total FROM leads").fetchone()["total"]
            messages = conn.execute("SELECT COUNT(1) as total FROM messages").fetchone()["total"]
            inbound_events = conn.execute("SELECT COUNT(1) as total FROM inbound_events").fetchone()["total"]
        self.assertEqual(jobs, 0)
        self.assertEqual(leads, 0)
        self.assertEqual(messages, 0)
        self.assertEqual(inbound_events, 0)


if __name__ == "__main__":
    unittest.main()
