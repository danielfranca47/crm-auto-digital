import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

if "fastapi" not in sys.modules:
    fastapi_stub = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec("fastapi", None)
    )

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def Depends(_dep=None):
        return None

    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.Depends = Depends
    sys.modules["fastapi"] = fastapi_stub

    security_stub = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec("fastapi.security", None)
    )

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
    pydantic_stub = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec("pydantic", None)
    )

    class FieldInfo:
        def __init__(self, default, alias: str | None = None) -> None:
            self.default = default
            self.alias = alias

    def Field(default=None, *, alias: str | None = None, default_factory=None):
        if default is None and default_factory is not None:
            default = default_factory()
        return FieldInfo(default, alias=alias)

    def ConfigDict(**kwargs):
        return dict(**kwargs)

    class BaseModel:
        def __init__(self, **data):
            annotations = getattr(self, "__annotations__", {})
            for name, _type in annotations.items():
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
    httpx_stub = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec("httpx", None)
    )

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
        def __init__(self, status_code: int = 500, text: str = ""):
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

HANDLER_PATH = os.path.join(PROJECT_ROOT, "services", "whatsapp_inbound", "inbound_handler.py")
spec = importlib.util.spec_from_file_location("inbound_handler_media_fallback", HANDLER_PATH)
inbound_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inbound_handler)


USER_ID = 42
PHONE = "+5511999999999"
AI_PROFILE_CONTINUAR = {
    "offer_pack": {
        "media_fallback": "continuar",
        "media_fallback_msg": "Recebi sua mídia, mas só consigo ler texto por aqui :)",
    }
}


class MediaFallbackPauseTests(unittest.TestCase):
    """Regressão: _apply_media_fallback não deve enviar mensagem quando o bot
    está pausado (globalmente pelo Kanban, ou individualmente no lead)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "crm-media-fallback-test.db")
        database.DB_PATH = self.db_path
        init_db()

        self.sent_calls = []

        def _fake_send(instance_id, phone, msg):
            self.sent_calls.append((instance_id, phone, msg))
            return True

        inbound_handler.send_whatsapp_direct = _fake_send

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO leads (id, user_id, companyName, phone, bot_disabled) VALUES (1, ?, 'Lead Teste', ?, 0)",
                (USER_ID, PHONE),
            )
            conn.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _apply(self):
        return inbound_handler._apply_media_fallback(
            USER_ID, "inst-1", AI_PROFILE_CONTINUAR, PHONE, "msg-1"
        )

    def test_sends_fallback_when_bot_active(self):
        result = self._apply()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(self.sent_calls), 1)

    def test_skips_when_globally_paused(self):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO bot_global_pause_state (user_id, is_paused) VALUES (?, 1)",
                (USER_ID,),
            )
            conn.commit()

        result = self._apply()
        self.assertEqual(result, {"status": "skipped", "reason": "global_pause"})
        self.assertEqual(self.sent_calls, [])

    def test_skips_when_lead_bot_disabled(self):
        with get_connection() as conn:
            conn.execute(
                "UPDATE leads SET bot_disabled = 1 WHERE user_id = ? AND phone = ?",
                (USER_ID, PHONE),
            )
            conn.commit()

        result = self._apply()
        self.assertEqual(result, {"status": "skipped", "reason": "bot_disabled"})
        self.assertEqual(self.sent_calls, [])

    def test_ignore_behavior_never_sends_regardless_of_pause(self):
        ai_profile_ignorar = {"offer_pack": {"media_fallback": "ignorar"}}
        result = inbound_handler._apply_media_fallback(
            USER_ID, "inst-1", ai_profile_ignorar, PHONE, "msg-1"
        )
        self.assertEqual(result, {"status": "ignored", "reason": "media_fallback_ignore"})
        self.assertEqual(self.sent_calls, [])


if __name__ == "__main__":
    unittest.main()
