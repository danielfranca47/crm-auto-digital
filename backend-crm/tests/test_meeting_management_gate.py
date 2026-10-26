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
spec = importlib.util.spec_from_file_location("inbound_handler_meeting_gate", HANDLER_PATH)
inbound_handler = importlib.util.module_from_spec(spec)
# O pydantic resolve as anotações de InboundWebhookPayload via sys.modules[<módulo>].
sys.modules[spec.name] = inbound_handler
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
