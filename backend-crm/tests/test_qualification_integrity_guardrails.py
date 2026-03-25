import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.jobs_service import apply_suggested_category
from services.qualification_guardrails import can_advance_from_qualification


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            bot_disabled INTEGER DEFAULT 0,
            bot_disabled_reason TEXT,
            lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP,
            agent_type TEXT
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

        CREATE TABLE lead_qualification_state (
            lead_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            stage TEXT,
            agent_mode_normalized TEXT,
            playbook_key TEXT,
            playbook_version TEXT,
            data_json TEXT,
            confidence_json TEXT,
            last_questioned_field TEXT,
            attempts_json TEXT,
            asked_questions_json TEXT,
            last_question_text TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


class QualificationIntegrityGuardrailsTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix="_qualification_guardrails.db")
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

    def test_can_advance_returns_missing_fields_when_incomplete(self):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, category, agent_type) VALUES (?, ?, ?)",
            (99, "qualification", "agent_1"),
        )
        lead_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO lead_qualification_state (lead_id, user_id, stage, agent_mode_normalized, data_json)
            VALUES (?, ?, 'qualification', 'agenda', ?)
            """,
            (lead_id, 99, json.dumps({"service_interest": "botox"}, ensure_ascii=False)),
        )
        self.conn.commit()

        can_advance, missing = can_advance_from_qualification(self.conn, lead_id=lead_id, user_id=99)
        self.assertFalse(can_advance)
        self.assertIn("availability_window", missing)
        self.assertIn("location_preference", missing)
        self.assertIn("price_acceptance", missing)

    def test_apply_suggested_category_blocks_advance_when_qualification_incomplete(self):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, category, agent_type) VALUES (?, ?, ?)",
            (55, "qualification", "agent_1"),
        )
        lead_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO lead_qualification_state (lead_id, user_id, stage, agent_mode_normalized, data_json)
            VALUES (?, ?, 'qualification', 'agenda', ?)
            """,
            (lead_id, 55, json.dumps({"service_interest": "botox"}, ensure_ascii=False)),
        )
        self.conn.commit()

        moved = apply_suggested_category(
            self.conn,
            lead_id=lead_id,
            user_id=55,
            suggested_category="apresentation",
            reason="teste",
            inbound_message_text="quero avançar",
            decision_trace={"agent_mode_normalized": "agenda"},
        )
        self.assertFalse(moved)
        row = self.conn.execute("SELECT category FROM leads WHERE id = ?", (lead_id,)).fetchone()
        self.assertEqual(row["category"], "qualification")

