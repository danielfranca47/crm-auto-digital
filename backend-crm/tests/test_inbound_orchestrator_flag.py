import importlib.util
import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import database
from database import get_connection, init_db
HANDLER_PATH = os.path.join(PROJECT_ROOT, "services", "whatsapp_inbound", "inbound_handler.py")
spec = importlib.util.spec_from_file_location("inbound_handler_orchestrator_flag", HANDLER_PATH)
inbound_handler = importlib.util.module_from_spec(spec)
# O pydantic resolve as anotações de InboundWebhookPayload via sys.modules[<módulo>].
sys.modules[spec.name] = inbound_handler
spec.loader.exec_module(inbound_handler)


class DummyBundle:
    def __init__(self):
        self.ai_profile = {"template_key": "sdr_padrao"}
        self.playbook = {"template_key": "sdr_padrao"}
        self.metadata = {"ai_profile_status": "ok"}


class InboundOrchestratorFlagTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "crm-test.db")
        os.environ["CRM_WHATSAPP_STUB"] = "1"
        os.environ["CRM_STUB_USER_ID"] = "123"
        database.DB_PATH = self.db_path
        init_db()

        inbound_handler.build_context_bundle_from_inbound = lambda _event: DummyBundle()
        inbound_handler.decide_next_action = lambda _bundle: {
            "next_action": "reply",
            "reason": "unit_test",
            "questions": [],
        }

    def tearDown(self):
        self.temp_dir.cleanup()
        for key in ("CRM_WHATSAPP_STUB", "CRM_STUB_USER_ID", "CRM_DISABLE_LOCAL_ORCHESTRATOR"):
            os.environ.pop(key, None)

    def _call_inbound(self, message_id: str):
        payload = {
            "instance_id": "inst-1",
            "from": "+5511999999999",
            "message_text": "Oi",
            "message_id": message_id,
            "timestamp": "2025-01-01T10:00:00",
            "provider": "uazapi",
        }
        return inbound_handler.handle_inbound(payload)

    def _count_logs(self, action: str) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(1) as total FROM prospection_logs WHERE action = ?",
                (action,),
            ).fetchone()
        return int(row["total"])

    def _count_jobs(self) -> int:
        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(1) as total FROM jobs").fetchone()
        return int(row["total"])

    def test_orchestrator_disabled_skips_ai_decided(self):
        os.environ["CRM_DISABLE_LOCAL_ORCHESTRATOR"] = "1"
        self._call_inbound("msg-flag-on")
        self.assertEqual(self._count_logs("ai_decided"), 0)
        self.assertEqual(self._count_jobs(), 1)

    def test_orchestrator_enabled_logs_ai_decided(self):
        os.environ["CRM_DISABLE_LOCAL_ORCHESTRATOR"] = "0"
        self._call_inbound("msg-flag-off")
        self.assertEqual(self._count_logs("ai_decided"), 1)
        self.assertEqual(self._count_jobs(), 1)


if __name__ == "__main__":
    unittest.main()
