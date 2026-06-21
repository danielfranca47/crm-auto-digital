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
spec = importlib.util.spec_from_file_location("inbound_handler", HANDLER_PATH)
inbound_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inbound_handler)


class DummyBundle:
    def __init__(self, ai_profile=None):
        self.ai_profile = ai_profile if ai_profile is not None else {"template_key": "sdr_padrao"}
        self.playbook = {"template_key": "sdr_padrao"}
        self.metadata = {"ai_profile_status": "ok"}


class MeetingManagementGateTests(unittest.TestCase):
    """Fase 5: o gate de bot_disabled_reason='meeting_scheduled' (Fase 1) só deixa a
    mensagem passar quando ai_profile.meeting_management_enabled também permite — caso
    contrário o lead fica mudo, como qualquer outro bot_disabled_reason (handoff manual).
    """

    PHONE = "+5511988887777"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "crm-test.db")
        os.environ["CRM_WHATSAPP_STUB"] = "1"
        os.environ["CRM_STUB_USER_ID"] = "123"
        os.environ["CRM_DISABLE_LOCAL_ORCHESTRATOR"] = "1"
        database.DB_PATH = self.db_path
        init_db()

        inbound_handler.decide_next_action = lambda _bundle: {
            "next_action": "reply",
            "reason": "unit_test",
            "questions": [],
        }

    def tearDown(self):
        self.temp_dir.cleanup()
        for key in ("CRM_WHATSAPP_STUB", "CRM_STUB_USER_ID", "CRM_DISABLE_LOCAL_ORCHESTRATOR"):
            os.environ.pop(key, None)

    def _call_inbound(self, message_id: str, ai_profile=None):
        inbound_handler.build_context_bundle_from_inbound = lambda _event: DummyBundle(ai_profile)
        payload = {
            "instance_id": "inst-1",
            "from": self.PHONE,
            "message_text": "Oi",
            "message_id": message_id,
            "timestamp": "2025-01-01T10:00:00",
            "provider": "uazapi",
        }
        return inbound_handler.handle_inbound(payload)

    def _count_jobs(self) -> int:
        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(1) as total FROM jobs").fetchone()
        return int(row["total"])

    def _disable_lead_as_meeting_scheduled(self) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM leads WHERE phone = ?", (self.PHONE,)
            ).fetchone()
            lead_id = int(row["id"])
            conn.execute(
                "UPDATE leads SET bot_disabled = 1, bot_disabled_reason = 'meeting_scheduled' WHERE id = ?",
                (lead_id,),
            )
            conn.commit()
        return lead_id

    def test_skips_when_meeting_management_disabled(self):
        self._call_inbound("msg-1")  # cria o lead
        self._disable_lead_as_meeting_scheduled()
        jobs_before = self._count_jobs()

        result = self._call_inbound("msg-2", ai_profile={"meeting_management_enabled": False})

        self.assertEqual(result.get("status"), "skipped")
        self.assertEqual(self._count_jobs(), jobs_before)

    def test_passes_when_meeting_management_enabled(self):
        self._call_inbound("msg-1")  # cria o lead
        self._disable_lead_as_meeting_scheduled()
        jobs_before = self._count_jobs()

        result = self._call_inbound("msg-2", ai_profile={"meeting_management_enabled": True})

        self.assertNotEqual(result.get("status"), "skipped")
        self.assertEqual(self._count_jobs(), jobs_before + 1)

    def test_passes_by_default_when_profile_omits_field(self):
        """Perfis antigos (antes da migração) não têm o campo — default deve ser True."""
        self._call_inbound("msg-1")  # cria o lead
        self._disable_lead_as_meeting_scheduled()
        jobs_before = self._count_jobs()

        result = self._call_inbound("msg-2", ai_profile={"template_key": "sdr_padrao"})

        self.assertNotEqual(result.get("status"), "skipped")
        self.assertEqual(self._count_jobs(), jobs_before + 1)

    def test_skips_for_other_bot_disabled_reasons_regardless_of_flag(self):
        self._call_inbound("msg-1")  # cria o lead
        with get_connection() as conn:
            conn.execute(
                "UPDATE leads SET bot_disabled = 1, bot_disabled_reason = 'manual_disable' WHERE phone = ?",
                (self.PHONE,),
            )
            conn.commit()
        jobs_before = self._count_jobs()

        result = self._call_inbound("msg-2", ai_profile={"meeting_management_enabled": True})

        self.assertEqual(result.get("status"), "skipped")
        self.assertEqual(self._count_jobs(), jobs_before)


if __name__ == "__main__":
    unittest.main()
