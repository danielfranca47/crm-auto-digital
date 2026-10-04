import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import database
from database import get_connection, init_db
from services.whatsapp_inbound import inbound_handler

_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
BUFFER_SECONDS = 8


def _grid_open_only_in_two_days() -> tuple[str, int]:
    """Grade aberta só daqui a dois dias (10:00–16:00): fechada agora, a qualquer hora do teste."""
    target_weekday = (datetime.utcnow() + timedelta(days=2)).weekday()
    grid = {key: ("10:00-16:00" if idx == target_weekday else "") for idx, key in enumerate(_DAY_KEYS)}
    return json.dumps(grid), target_weekday


class DummyBundle:
    def __init__(self, ai_profile):
        self.ai_profile = ai_profile
        self.playbook = {"template_key": "sdr_padrao"}
        self.metadata = {"ai_profile_status": "ok"}


class InboundBufferWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["CRM_WHATSAPP_STUB"] = "1"
        os.environ["CRM_STUB_USER_ID"] = "123"
        os.environ["CRM_DISABLE_LOCAL_ORCHESTRATOR"] = "1"
        self._original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "crm-test.db")
        init_db()
        self._original_build_bundle = inbound_handler.build_context_bundle_from_inbound

    def tearDown(self):
        inbound_handler.build_context_bundle_from_inbound = self._original_build_bundle
        database.DB_PATH = self._original_db_path
        self.temp_dir.cleanup()
        for key in ("CRM_WHATSAPP_STUB", "CRM_STUB_USER_ID", "CRM_DISABLE_LOCAL_ORCHESTRATOR"):
            os.environ.pop(key, None)

    def _use_profile(self, mode, schedule=None):
        ai_profile = {
            "template_key": "sdr_padrao",
            "multi_message_buffer_seconds": BUFFER_SECONDS,
            "availability_mode": mode,
            "availability_schedule": schedule,
            "timezone": "UTC",
        }
        inbound_handler.build_context_bundle_from_inbound = lambda _event: DummyBundle(ai_profile)

    def _call_inbound(self, message_id, text="Oi"):
        return inbound_handler.handle_inbound(
            {
                "instance_id": "inst-1",
                "from": "+5511999999999",
                "message_text": text,
                "message_id": message_id,
                "provider": "uazapi",
            }
        )

    def _jobs(self):
        with get_connection() as conn:
            rows = conn.execute("SELECT scheduled_at, payload FROM jobs ORDER BY id").fetchall()
        return [(datetime.fromisoformat(str(row["scheduled_at"])), json.loads(row["payload"])) for row in rows]

    def test_buffer_with_closed_window_waits_for_opening(self):
        grid, target_weekday = _grid_open_only_in_two_days()
        self._use_profile("custom", grid)

        self._call_inbound("msg-closed-1")

        jobs = self._jobs()
        self.assertEqual(len(jobs), 1)
        scheduled_at, _payload = jobs[0]
        self.assertEqual(scheduled_at.weekday(), target_weekday)
        self.assertEqual((scheduled_at.hour, scheduled_at.minute), (10, 0))
        self.assertGreater(scheduled_at, datetime.utcnow() + timedelta(hours=24))

    def test_accumulated_message_keeps_waiting_for_opening(self):
        grid, target_weekday = _grid_open_only_in_two_days()
        self._use_profile("custom", grid)

        self._call_inbound("msg-acc-1", "Oi")
        result = self._call_inbound("msg-acc-2", "Tem horário?")

        self.assertEqual(result["status"], "buffered")
        jobs = self._jobs()
        self.assertEqual(len(jobs), 1)
        scheduled_at, payload = jobs[0]
        self.assertEqual(scheduled_at.weekday(), target_weekday)
        self.assertEqual((scheduled_at.hour, scheduled_at.minute), (10, 0))
        self.assertEqual(payload["message_text"], "Oi\nTem horário?")

    def test_buffer_with_open_window_only_waits_for_buffer(self):
        self._use_profile("24h")

        before = datetime.utcnow()
        self._call_inbound("msg-open-1")
        after = datetime.utcnow()

        scheduled_at, _payload = self._jobs()[0]
        self.assertGreaterEqual(scheduled_at, before + timedelta(seconds=BUFFER_SECONDS))
        self.assertLessEqual(scheduled_at, after + timedelta(seconds=BUFFER_SECONDS))


if __name__ == "__main__":
    unittest.main()
