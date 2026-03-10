import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException

from models import StartFollowupPayload
from routes.leads import start_followup_transition
from security_core import CurrentUser


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            bot_disabled INTEGER DEFAULT 1,
            bot_disabled_reason TEXT,
            agent_type TEXT,
            followup_contract TEXT,
            lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP
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
        """
    )
    conn.commit()


class StartFollowupTransitionTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix="_followup_transition.db")
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

    def test_start_followup_for_agent_1_updates_contract_and_reactivates_bot(self):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, category, bot_disabled, bot_disabled_reason, agent_type) VALUES (?, ?, 1, 'meeting_scheduled', ?)",
            (11, "apresentation", "agent_1"),
        )
        lead_id = int(cur.lastrowid)
        self.conn.commit()

        payload = StartFollowupPayload(
            lead_id=lead_id,
            agent_type="agent_1",
            meeting_or_session_happened="yes",
            outcome="warm",
            followup_goal="nurture",
            proposal_sent=True,
            operator_note="quer validar com sócio",
        )

        with patch("routes.leads.get_connection", return_value=self.conn):
            result = start_followup_transition(
                payload,
                current_user=CurrentUser(id=11, email="x@example.com", token="t"),
            )

        self.assertEqual(result["status"], "ok")
        check_conn = sqlite3.connect(self.db_path)
        check_conn.row_factory = sqlite3.Row
        row = check_conn.execute(
            "SELECT category, bot_disabled, bot_disabled_reason, followup_contract FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        self.assertEqual(row["category"], "follow-up")
        self.assertEqual(int(row["bot_disabled"] or 0), 0)
        self.assertIsNone(row["bot_disabled_reason"])
        contract = json.loads(row["followup_contract"])
        self.assertEqual(contract["followup_variant"], "sdr_scheduler")
        self.assertEqual(contract["followup_goal"], "nurture")
        check_conn.close()

    def test_start_followup_rejects_non_supported_agent(self):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, category, agent_type) VALUES (?, ?, ?)",
            (11, "apresentation", "agent_2"),
        )
        lead_id = int(cur.lastrowid)
        self.conn.commit()

        payload = StartFollowupPayload(
            lead_id=lead_id,
            agent_type="agent_3",
            meeting_or_session_happened="no_show",
            outcome=None,
            followup_goal="register_only",
        )

        with patch("routes.leads.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as exc_ctx:
                start_followup_transition(
                    payload,
                    current_user=CurrentUser(id=11, email="x@example.com", token="t"),
                )

        self.assertEqual(exc_ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
