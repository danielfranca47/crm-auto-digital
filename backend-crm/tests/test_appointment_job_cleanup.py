import json
import os
import sqlite3
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.appointments import _cancel_pending_appointment_jobs


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


class CancelPendingAppointmentJobsTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _insert_job(self, *, job_type, appointment_id, status="pending"):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO jobs (type, payload, status) VALUES (?, ?, ?)",
            (job_type, json.dumps({"appointment_id": appointment_id}), status),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def test_cancels_reminder_and_briefing_jobs_for_appointment(self):
        reminder_id = self._insert_job(
            job_type="whatsapp.appointment.reminder", appointment_id=42
        )
        briefing_id = self._insert_job(
            job_type="whatsapp.appointment.briefing", appointment_id=42
        )

        cancelled = _cancel_pending_appointment_jobs(self.conn, 42)

        self.assertEqual(cancelled, 2)
        for job_id in (reminder_id, briefing_id):
            row = self.conn.execute(
                "SELECT status FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            self.assertEqual(row["status"], "cancelled")

    def test_does_not_touch_jobs_from_other_appointments(self):
        other_id = self._insert_job(
            job_type="whatsapp.appointment.reminder", appointment_id=99
        )

        cancelled = _cancel_pending_appointment_jobs(self.conn, 42)

        self.assertEqual(cancelled, 0)
        row = self.conn.execute("SELECT status FROM jobs WHERE id = ?", (other_id,)).fetchone()
        self.assertEqual(row["status"], "pending")

    def test_does_not_touch_already_completed_jobs(self):
        completed_id = self._insert_job(
            job_type="whatsapp.appointment.reminder", appointment_id=42, status="completed"
        )

        cancelled = _cancel_pending_appointment_jobs(self.conn, 42)

        self.assertEqual(cancelled, 0)
        row = self.conn.execute(
            "SELECT status FROM jobs WHERE id = ?", (completed_id,)
        ).fetchone()
        self.assertEqual(row["status"], "completed")

    def test_ignores_unrelated_job_types(self):
        unrelated_id = self._insert_job(job_type="whatsapp.send.local", appointment_id=42)

        cancelled = _cancel_pending_appointment_jobs(self.conn, 42)

        self.assertEqual(cancelled, 0)
        row = self.conn.execute(
            "SELECT status FROM jobs WHERE id = ?", (unrelated_id,)
        ).fetchone()
        self.assertEqual(row["status"], "pending")


if __name__ == "__main__":
    unittest.main()
