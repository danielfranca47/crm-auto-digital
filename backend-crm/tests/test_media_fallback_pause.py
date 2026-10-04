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
spec = importlib.util.spec_from_file_location("inbound_handler_media_fallback", HANDLER_PATH)
inbound_handler = importlib.util.module_from_spec(spec)
# O pydantic resolve as anotações de InboundWebhookPayload via sys.modules[<módulo>].
sys.modules[spec.name] = inbound_handler
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
