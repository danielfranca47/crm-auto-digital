import importlib.util
import os
import sys
import tempfile
import unittest
from contextlib import closing

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


import database
from database import get_connection, init_db

WEBHOOKS_PATH = os.path.join(PROJECT_ROOT, "routes", "webhooks.py")
webhooks_spec = importlib.util.spec_from_file_location("webhooks_group_ignore", WEBHOOKS_PATH)
webhooks = importlib.util.module_from_spec(webhooks_spec)
# O pydantic resolve as anotações dos modelos via sys.modules[<módulo>].
sys.modules[webhooks_spec.name] = webhooks
webhooks_spec.loader.exec_module(webhooks)

INBOUND_HANDLER_PATH = os.path.join(PROJECT_ROOT, "services", "whatsapp_inbound", "inbound_handler.py")
inbound_spec = importlib.util.spec_from_file_location("inbound_handler_group_ignore", INBOUND_HANDLER_PATH)
inbound_handler = importlib.util.module_from_spec(inbound_spec)
sys.modules[inbound_spec.name] = inbound_handler
inbound_spec.loader.exec_module(inbound_handler)


class WhatsappGroupIgnoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
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
        with closing(get_connection()) as conn:
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
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "crm-test.db")
        database.DB_PATH = self.db_path
        init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_handle_inbound_ignores_is_group_without_side_effects(self):
        result = inbound_handler.handle_inbound({"is_group": True})
        self.assertEqual(result, {"status": "ignored", "reason": "group_message"})

        with closing(get_connection()) as conn:
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
