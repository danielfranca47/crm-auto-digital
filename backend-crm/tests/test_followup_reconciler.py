import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.followup_reconciler import TYPE_FOLLOWUP_TICK, reconcile_due_followups


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            bot_disabled INTEGER DEFAULT 0,
            followup_status TEXT,
            next_followup_at DATETIME,
            followup_contract TEXT
        );

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

        CREATE TABLE prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            channel TEXT,
            message_id INTEGER,
            action TEXT,
            notes TEXT,
            user_id INTEGER
        );

        CREATE TABLE followup_reconcile_guard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            due_at DATETIME NOT NULL,
            job_id INTEGER,
            status TEXT NOT NULL DEFAULT 'enqueued',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lead_id, due_at)
        );
        """
    )
    conn.commit()


class FollowupReconcilerTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix="_followup_reconciler.db")
        os.close(fd)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_reconciles_only_eligible_and_enqueues_canonical_job(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO leads (user_id, category, bot_disabled, followup_status, next_followup_at, followup_contract)
            VALUES (11, 'follow-up', 0, 'active', datetime('now', '-1 minute'), '{}')
            """
        )
        lead_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO leads (user_id, category, bot_disabled, followup_status, next_followup_at, followup_contract)
            VALUES (11, 'follow-up', 1, 'active', datetime('now', '-1 minute'), '{}')
            """
        )
        cur.execute(
            """
            INSERT INTO leads (user_id, category, bot_disabled, followup_status, next_followup_at, followup_contract)
            VALUES (11, 'follow-up', 0, 'paused', datetime('now', '-1 minute'), '{}')
            """
        )
        self.conn.commit()

        with patch("services.followup_reconciler.get_connection", return_value=self.conn):
            result = reconcile_due_followups(limit=100)

        self.assertEqual(result["job_type"], TYPE_FOLLOWUP_TICK)
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["enqueued"], 1)
        self.assertEqual(result["skipped_duplicate"], 0)

        job = self.conn.execute("SELECT type, payload, status FROM jobs ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(job["type"], TYPE_FOLLOWUP_TICK)
        self.assertEqual(job["status"], "pending")
        payload = json.loads(job["payload"])
        self.assertEqual(payload["lead_id"], lead_id)

    def test_reconcile_is_idempotent_for_same_lead_due_at(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO leads (user_id, category, bot_disabled, followup_status, next_followup_at, followup_contract)
            VALUES (22, 'follow-up', 0, 'active', datetime('now', '-2 minute'), '{}')
            """
        )
        self.conn.commit()

        with patch("services.followup_reconciler.get_connection", return_value=self.conn):
            first = reconcile_due_followups(limit=10)
            second = reconcile_due_followups(limit=10)

        self.assertEqual(first["enqueued"], 1)
        self.assertEqual(second["enqueued"], 0)
        self.assertGreaterEqual(second["skipped_duplicate"], 1)

        jobs_count = self.conn.execute("SELECT COUNT(1) AS c FROM jobs").fetchone()["c"]
        self.assertEqual(jobs_count, 1)

    def test_reconcile_releases_guard_when_previous_job_failed(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO leads (user_id, category, bot_disabled, followup_status, next_followup_at, followup_contract)
            VALUES (33, 'follow-up', 0, 'active', datetime('now', '-2 minute'), '{}')
            """
        )
        lead_id = int(cur.lastrowid)
        due_at = cur.execute("SELECT next_followup_at FROM leads WHERE id = ?", (lead_id,)).fetchone()["next_followup_at"]

        cur.execute(
            """
            INSERT INTO jobs (user_id, type, payload, status)
            VALUES (33, 'whatsapp.followup.tick', '{"lead_id": 1}', 'failed')
            """
        )
        failed_job_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO followup_reconcile_guard (lead_id, due_at, job_id, status)
            VALUES (?, ?, ?, 'enqueued')
            """,
            (lead_id, due_at, failed_job_id),
        )
        self.conn.commit()

        with patch("services.followup_reconciler.get_connection", return_value=self.conn):
            result = reconcile_due_followups(limit=10)

        self.assertEqual(result["enqueued"], 1)
        latest_job = self.conn.execute(
            "SELECT id, status FROM jobs WHERE type = 'whatsapp.followup.tick' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(latest_job["status"], "pending")
        self.assertNotEqual(int(latest_job["id"]), failed_job_id)


if __name__ == "__main__":
    unittest.main()
