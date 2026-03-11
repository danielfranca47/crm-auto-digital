import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException

from models import StartFollowupPayload
from routes.leads import _map_lead_row, start_followup_transition
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
            followup_status TEXT,
            next_followup_at DATETIME,
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


def _create_legacy_schema_without_followup_mirror_columns(conn: sqlite3.Connection) -> None:
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
            "SELECT category, bot_disabled, bot_disabled_reason, followup_contract, followup_status, next_followup_at FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        self.assertEqual(row["category"], "follow-up")
        self.assertEqual(int(row["bot_disabled"] or 0), 0)
        self.assertIsNone(row["bot_disabled_reason"])
        contract = json.loads(row["followup_contract"])
        self.assertEqual(contract["version"], 1)
        self.assertEqual(contract["status"], "active")
        self.assertEqual(contract["attempts"], 0)
        self.assertIsNone(contract["last_followup_at"])
        self.assertIsNone(contract["stop_reason"])
        self.assertEqual(contract["followup_variant"], "sdr_scheduler")
        self.assertEqual(contract["max_attempts"], 4)
        self.assertIsNotNone(contract["next_followup_at"])
        created_at = datetime.fromisoformat(contract["created_at"])
        next_followup_at = datetime.fromisoformat(contract["next_followup_at"])
        self.assertEqual(int((next_followup_at - created_at).total_seconds()), 30 * 60)
        self.assertEqual(contract["followup_goal"], "nurture")
        self.assertEqual(row["followup_status"], "active")
        self.assertEqual(row["next_followup_at"], contract["next_followup_at"])
        check_conn.close()

    def test_start_followup_for_agent_3_no_show_uses_hybrid_defaults(self):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, category, bot_disabled, bot_disabled_reason, agent_type) VALUES (?, ?, 1, 'meeting_scheduled', ?)",
            (11, "apresentation", "agent_3"),
        )
        lead_id = int(cur.lastrowid)
        self.conn.commit()

        payload = StartFollowupPayload(
            lead_id=lead_id,
            agent_type="agent_3",
            meeting_or_session_happened="no_show",
            outcome="warm",
            followup_goal="reschedule",
            proposal_sent=False,
        )

        with patch("routes.leads.get_connection", return_value=self.conn):
            start_followup_transition(
                payload,
                current_user=CurrentUser(id=11, email="x@example.com", token="t"),
            )

        check_conn = sqlite3.connect(self.db_path)
        check_conn.row_factory = sqlite3.Row
        row = check_conn.execute(
            "SELECT followup_contract FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        contract = json.loads(row["followup_contract"])
        self.assertEqual(contract["followup_variant"], "hybrid_scheduler")
        self.assertEqual(contract["max_attempts"], 3)
        created_at = datetime.fromisoformat(contract["created_at"])
        next_followup_at = datetime.fromisoformat(contract["next_followup_at"])
        self.assertEqual(int((next_followup_at - created_at).total_seconds()), 30 * 60)
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

    def test_map_lead_row_keeps_legacy_followup_contract_compatible(self):
        row = {
            "id": 1,
            "companyName": "ACME",
            "contactName": "John",
            "phone": "+55119999",
            "email": "john@example.com",
            "origin": "Manual",
            "category": "follow-up",
            "customMessage": None,
            "observations": None,
            "agent_type": "agent_1",
            "followup_contract": json.dumps({"phase": "follow-up", "followup_goal": "nurture"}),
            "createdAt": "2026-01-01 10:00:00",
            "lastMovement": "2026-01-01 10:00:00",
            "next_start_at": None,
            "next_description": None,
        }

        mapped = _map_lead_row(row)
        contract = mapped["followup_contract"]
        self.assertIsInstance(contract, dict)
        self.assertEqual(contract["followup_goal"], "nurture")
        self.assertEqual(contract["status"], "active")
        self.assertEqual(contract["attempts"], 0)
        self.assertEqual(contract["max_attempts"], 4)
        self.assertIn("next_followup_at", contract)
        self.assertIsNone(contract["next_followup_at"])
        self.assertEqual(mapped["followup_status"], "active")
        self.assertIsNone(mapped["next_followup_at"])

    def test_start_followup_works_with_legacy_schema_without_mirror_columns(self):
        fd, legacy_db_path = tempfile.mkstemp(suffix="_followup_transition_legacy.db")
        os.close(fd)
        legacy_conn = sqlite3.connect(legacy_db_path)
        legacy_conn.row_factory = sqlite3.Row
        _create_legacy_schema_without_followup_mirror_columns(legacy_conn)
        try:
            cur = legacy_conn.cursor()
            cur.execute(
                "INSERT INTO leads (user_id, category, bot_disabled, bot_disabled_reason, agent_type) VALUES (?, ?, 1, 'meeting_scheduled', ?)",
                (11, "apresentation", "agent_1"),
            )
            lead_id = int(cur.lastrowid)
            legacy_conn.commit()

            payload = StartFollowupPayload(
                lead_id=lead_id,
                agent_type="agent_1",
                meeting_or_session_happened="yes",
            )

            with patch("routes.leads.get_connection", return_value=legacy_conn):
                result = start_followup_transition(
                    payload,
                    current_user=CurrentUser(id=11, email="x@example.com", token="t"),
                )
            self.assertEqual(result["status"], "ok")
        finally:
            legacy_conn.close()
            if os.path.exists(legacy_db_path):
                os.remove(legacy_db_path)


if __name__ == "__main__":
    unittest.main()
