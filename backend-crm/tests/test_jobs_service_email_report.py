import os
import sqlite3
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.jobs_service import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    _handle_email_report as handle_email_report,
)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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


class HandleEmailReportTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _rows(self):
        return self.conn.execute(
            "SELECT lead_id, channel, message_id, action, notes, email, user_id FROM prospection_logs"
        ).fetchall()

    def test_completed_job_logs_sent_with_channel_and_email(self):
        payload = {"lead_id": 7, "message_id": 3, "email": "lead@example.com"}

        handle_email_report(
            self.conn,
            payload,
            JOB_STATUS_COMPLETED,
            {"status": "sent", "lead_id": 7, "email": "lead@example.com"},
            None,
            user_id=1,
        )
        self.conn.commit()

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["lead_id"], 7)
        self.assertEqual(row["channel"], "email")
        self.assertEqual(row["message_id"], 3)
        self.assertEqual(row["action"], "sent")
        self.assertEqual(row["email"], "lead@example.com")
        self.assertEqual(row["user_id"], 1)

    def test_failed_job_logs_failed_with_error_notes(self):
        payload = {"lead_id": 7, "message_id": 3, "email": "lead@example.com"}

        handle_email_report(
            self.conn,
            payload,
            JOB_STATUS_FAILED,
            None,
            "autenticação SMTP recusada",
            user_id=1,
        )
        self.conn.commit()

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["action"], "failed")
        self.assertEqual(row["channel"], "email")
        self.assertEqual(row["notes"], "autenticação SMTP recusada")
        self.assertEqual(row["email"], "lead@example.com")

    def test_missing_lead_id_is_noop(self):
        handle_email_report(
            self.conn,
            {"email": "lead@example.com"},
            JOB_STATUS_COMPLETED,
            {"status": "sent"},
            None,
            user_id=1,
        )
        self.conn.commit()

        self.assertEqual(len(self._rows()), 0)


if __name__ == "__main__":
    unittest.main()
