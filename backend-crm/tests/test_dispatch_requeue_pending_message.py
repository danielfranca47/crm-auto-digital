import json
import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.executor import _dispatch_system_actions


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            assigned_agent_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            scheduled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            result TEXT,
            error TEXT
        );
        """
    )
    conn.commit()


class DispatchRequeuePendingMessageTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_creates_new_inbound_job_with_channel_context_from_original_job(self):
        with patch("services.jobs_service.get_connection", return_value=self.conn):
            _dispatch_system_actions(
                lead_id=42,
                user_id=7,
                phone="5511999999999",
                system_actions=[
                    {
                        "type": "requeue_pending_message",
                        "message_text": "gostaria de agendar horário para hoje às 17:30",
                    }
                ],
                conn=self.conn,
                instance_id="inst-1",
                provider="uazapi",
                source_message_id="orig-msg-123",
            )

        row = self.conn.execute("SELECT * FROM jobs").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["type"], "whatsapp.inbound.n8n")
        payload = json.loads(row["payload"])
        self.assertEqual(payload["lead_id"], 42)
        self.assertEqual(payload["user_id"], 7)
        self.assertEqual(payload["instance_id"], "inst-1")
        self.assertEqual(payload["provider"], "uazapi")
        self.assertEqual(payload["phone"], "5511999999999")
        self.assertEqual(payload["message_text"], "gostaria de agendar horário para hoje às 17:30")
        self.assertTrue(payload["message_id"].startswith("requeue:orig-msg-123:"))

    def test_skips_when_channel_context_missing(self):
        with patch("services.jobs_service.get_connection", return_value=self.conn):
            _dispatch_system_actions(
                lead_id=42,
                user_id=7,
                phone="5511999999999",
                system_actions=[
                    {"type": "requeue_pending_message", "message_text": "pergunta pendente"}
                ],
                conn=self.conn,
                instance_id=None,
                provider=None,
                source_message_id="orig-msg-123",
            )

        row = self.conn.execute("SELECT * FROM jobs").fetchone()
        self.assertIsNone(row)

    def test_skips_when_message_text_empty(self):
        with patch("services.jobs_service.get_connection", return_value=self.conn):
            _dispatch_system_actions(
                lead_id=42,
                user_id=7,
                phone="5511999999999",
                system_actions=[{"type": "requeue_pending_message", "message_text": "   "}],
                conn=self.conn,
                instance_id="inst-1",
                provider="uazapi",
                source_message_id="orig-msg-123",
            )

        row = self.conn.execute("SELECT * FROM jobs").fetchone()
        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
