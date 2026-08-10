import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.jobs_service import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PENDING,
    TYPE_EMAIL_SEND_COLD,
    TYPE_WHATSAPP_SEND,
    get_prospection_summary,
)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            user_id INTEGER
        );
        CREATE TABLE prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lead_id INTEGER NOT NULL,
            channel TEXT NULL,
            message_id INTEGER NULL,
            action TEXT NOT NULL,
            notes TEXT,
            email TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


class GetProspectionSummaryTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)
        self.patcher = patch("services.jobs_service.get_connection", return_value=self.conn)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def _insert_job(self, *, job_type, status, user_id=1):
        self.conn.execute(
            "INSERT INTO jobs (type, status, user_id) VALUES (?, ?, ?)",
            (job_type, status, user_id),
        )
        self.conn.commit()

    def _insert_log(self, *, channel, action, user_id=1, lead_id=1, message_id=1):
        self.conn.execute(
            """
            INSERT INTO prospection_logs (user_id, lead_id, channel, message_id, action)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, lead_id, channel, message_id, action),
        )
        self.conn.commit()

    def test_pending_job_counts_as_queued(self):
        self._insert_job(job_type=TYPE_EMAIL_SEND_COLD, status=JOB_STATUS_PENDING)

        summary = get_prospection_summary(user_id=1)

        self.assertEqual(summary, {"sent": 0, "failed": 0, "queued": 1})

    def test_resolved_job_does_not_double_count_as_queued(self):
        # Job já completou: existe a linha "queued" original (evento de enfileiramento)
        # e a linha "sent" do resultado, mas NÃO existe mais um job com status='pending'.
        self._insert_job(job_type=TYPE_EMAIL_SEND_COLD, status=JOB_STATUS_COMPLETED)
        self._insert_log(channel="email", action="queued")
        self._insert_log(channel="email", action="sent")

        summary = get_prospection_summary(user_id=1)

        self.assertEqual(summary, {"sent": 1, "failed": 0, "queued": 0})

    def test_channel_filter_isolates_whatsapp_from_email(self):
        self._insert_job(job_type=TYPE_WHATSAPP_SEND, status=JOB_STATUS_PENDING)
        self._insert_job(job_type=TYPE_EMAIL_SEND_COLD, status=JOB_STATUS_PENDING)
        self._insert_log(channel="whatsapp", action="sent")
        self._insert_log(channel="email", action="failed")

        whatsapp_summary = get_prospection_summary(user_id=1, channel="whatsapp")
        email_summary = get_prospection_summary(user_id=1, channel="email")

        self.assertEqual(whatsapp_summary, {"sent": 1, "failed": 0, "queued": 1})
        self.assertEqual(email_summary, {"sent": 0, "failed": 1, "queued": 1})

    def test_scoped_by_user_id(self):
        self._insert_job(job_type=TYPE_EMAIL_SEND_COLD, status=JOB_STATUS_PENDING, user_id=2)
        self._insert_log(channel="email", action="sent", user_id=2)

        summary = get_prospection_summary(user_id=1)

        self.assertEqual(summary, {"sent": 0, "failed": 0, "queued": 0})


if __name__ == "__main__":
    unittest.main()
