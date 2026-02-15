import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException

from routes.leads import excluir_lead
from security_core import CurrentUser


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT NOT NULL
        );

        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            body TEXT
        );

        CREATE TABLE prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            action TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            title TEXT
        );

        CREATE TABLE lead_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            outcome TEXT
        );

        CREATE TABLE message_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            message_id INTEGER
        );

        CREATE TABLE prospection_whatsapp_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            body TEXT
        );

        CREATE TABLE outbound_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            phone TEXT
        );

        CREATE TABLE orion_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            phone_e164 TEXT
        );

        CREATE TABLE atividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            tipo TEXT
        );

        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT
        );
        """
    )
    conn.commit()


class LeadDeleteTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _seed_lead_with_children(self, *, user_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO leads (user_id, companyName) VALUES (?, ?)", (user_id, "ACME"))
        lead_id = int(cur.lastrowid)

        tables = [
            ("messages", "INSERT INTO messages (lead_id, body) VALUES (?, 'm')"),
            ("prospection_logs", "INSERT INTO prospection_logs (lead_id, action) VALUES (?, 'a')"),
            ("appointments", "INSERT INTO appointments (lead_id, title) VALUES (?, 't')"),
            ("lead_outcomes", "INSERT INTO lead_outcomes (lead_id, outcome) VALUES (?, 'won')"),
            ("message_selections", "INSERT INTO message_selections (lead_id, message_id) VALUES (?, 1)"),
            ("prospection_whatsapp_queue", "INSERT INTO prospection_whatsapp_queue (lead_id, body) VALUES (?, 'b')"),
            ("outbound_events", "INSERT INTO outbound_events (lead_id, phone) VALUES (?, '+5511')"),
            ("orion_conversations", "INSERT INTO orion_conversations (lead_id, phone_e164) VALUES (?, '+5511')"),
            ("atividades", "INSERT INTO atividades (lead_id, tipo) VALUES (?, 'x')"),
        ]
        for _, sql in tables:
            cur.execute(sql, (lead_id,))

        cur.execute("INSERT INTO jobs (payload) VALUES ('{\"lead_id\": 999}')")
        self.conn.commit()
        return lead_id

    def test_delete_lead_removes_children_and_keeps_jobs(self):
        user_id = 7
        lead_id = self._seed_lead_with_children(user_id=user_id)

        with patch("routes.leads.get_connection", return_value=self.conn):
            response = excluir_lead(
                lead_id,
                current_user=CurrentUser(id=user_id, email="a@example.com", token="t"),
            )

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["deleted_lead_id"], lead_id)

        lead_count = self.conn.execute("SELECT COUNT(*) AS c FROM leads WHERE id = ?", (lead_id,)).fetchone()["c"]
        self.assertEqual(lead_count, 0)

        for table in [
            "messages",
            "prospection_logs",
            "appointments",
            "lead_outcomes",
            "message_selections",
            "prospection_whatsapp_queue",
            "outbound_events",
            "orion_conversations",
            "atividades",
        ]:
            count = self.conn.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE lead_id = ?",
                (lead_id,),
            ).fetchone()["c"]
            self.assertEqual(count, 0, f"Tabela {table} ainda possui dados do lead")

        jobs_count = self.conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
        self.assertEqual(jobs_count, 1)

    def test_delete_other_user_lead_returns_404(self):
        owner_id = 7
        intruder_id = 8
        lead_id = self._seed_lead_with_children(user_id=owner_id)

        with patch("routes.leads.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as exc_ctx:
                excluir_lead(
                    lead_id,
                    current_user=CurrentUser(id=intruder_id, email="b@example.com", token="t"),
                )

        self.assertEqual(exc_ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
