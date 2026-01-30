import importlib.util
import os
import sqlite3
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GUARDRAIL_PATH = os.path.join(
    PROJECT_ROOT,
    "services",
    "whatsapp_inbound",
    "guardrail.py",
)
spec = importlib.util.spec_from_file_location("whatsapp_inbound_guardrail", GUARDRAIL_PATH)
guardrail = importlib.util.module_from_spec(spec)
sys.modules["whatsapp_inbound_guardrail"] = guardrail
spec.loader.exec_module(guardrail)

INBOUND_DEFAULT_CATEGORY = guardrail.INBOUND_DEFAULT_CATEGORY
find_or_create_lead_by_phone = guardrail.find_or_create_lead_by_phone
maybe_promote_lead_on_inbound = guardrail.maybe_promote_lead_on_inbound


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT NOT NULL,
            contactName TEXT,
            phone TEXT,
            origin TEXT DEFAULT 'Manual',
            category TEXT DEFAULT 'to-prospect',
            lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lead_id INTEGER NOT NULL,
            channel TEXT NULL,
            message_id INTEGER NULL,
            action TEXT NOT NULL,
            notes TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


class InboundGuardrailTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_tables(self.conn)
        self.user_id = 42

    def tearDown(self):
        self.conn.close()

    def test_new_lead_starts_in_qualification(self):
        lead_id, created = find_or_create_lead_by_phone(
            self.conn,
            user_id=self.user_id,
            phone_norm="5511999999999",
            payload={"company": "ACME", "contact_name": "Ana"},
        )
        self.assertTrue(created)
        row = self.conn.execute(
            "SELECT category FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, self.user_id),
        ).fetchone()
        self.assertEqual(row["category"], INBOUND_DEFAULT_CATEGORY)

    def test_existing_to_prospect_is_promoted(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO leads (user_id, companyName, contactName, phone, origin, category)
            VALUES (?, ?, ?, ?, 'whatsapp_inbound', 'to-prospect')
            """,
            (self.user_id, "ACME", "Ana", "5511888888888"),
        )
        lead_id = int(cur.lastrowid)
        self.conn.commit()

        moved = maybe_promote_lead_on_inbound(self.conn, lead_id=lead_id, user_id=self.user_id)
        self.assertTrue(moved)

        row = self.conn.execute(
            "SELECT category FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, self.user_id),
        ).fetchone()
        self.assertEqual(row["category"], INBOUND_DEFAULT_CATEGORY)

        log_row = self.conn.execute(
            """
            SELECT action, notes
              FROM prospection_logs
             WHERE lead_id = ? AND user_id = ?
            """,
            (lead_id, self.user_id),
        ).fetchone()
        self.assertEqual(log_row["action"], "moved_stage")
        self.assertIn("system:to-prospect->qualification|inbound_auto", log_row["notes"])

    def test_existing_follow_up_is_unchanged(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO leads (user_id, companyName, contactName, phone, origin, category)
            VALUES (?, ?, ?, ?, 'whatsapp_inbound', 'follow-up')
            """,
            (self.user_id, "ACME", "Ana", "5511777777777"),
        )
        lead_id = int(cur.lastrowid)
        self.conn.commit()

        moved = maybe_promote_lead_on_inbound(
            self.conn, lead_id=lead_id, user_id=self.user_id
        )
        self.assertFalse(moved)

        row = self.conn.execute(
            "SELECT category FROM leads WHERE id = ? AND user_id = ?",
            (lead_id, self.user_id),
        ).fetchone()
        self.assertEqual(row["category"], "follow-up")

        log_row = self.conn.execute(
            "SELECT id FROM prospection_logs WHERE lead_id = ? AND user_id = ?",
            (lead_id, self.user_id),
        ).fetchone()
        self.assertIsNone(log_row)


if __name__ == "__main__":
    unittest.main()
