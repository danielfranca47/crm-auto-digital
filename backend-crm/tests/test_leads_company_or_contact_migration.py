import os
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import database
from database import init_db, _migrate_leads_company_or_contact


class LeadsCompanyOrContactMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "crm-test.db")
        database.DB_PATH = self.db_path

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fresh_init_db_makes_companyName_nullable_with_check(self):
        init_db()
        conn = database.get_connection()
        try:
            info = {row["name"]: row for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
            self.assertEqual(info["companyName"]["notnull"], 0)

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO leads (companyName, contactName) VALUES (NULL, NULL)"
                )

            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO leads (companyName, contactName) VALUES ('', '   ')"
                )

            conn.execute(
                "INSERT INTO leads (companyName, contactName) VALUES (NULL, 'Ana')"
            )
            conn.execute(
                "INSERT INTO leads (companyName, contactName) VALUES ('ACME', NULL)"
            )
            conn.commit()
            count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            self.assertEqual(count, 2)
        finally:
            conn.close()

    def test_init_db_is_idempotent(self):
        init_db()
        init_db()  # não deve levantar erro na segunda chamada
        conn = database.get_connection()
        try:
            info = {row["name"]: row for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
            self.assertEqual(info["companyName"]["notnull"], 0)
        finally:
            conn.close()

    def test_migration_preserves_existing_rows_from_old_schema(self):
        conn = database.get_connection()
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                """
                CREATE TABLE leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    companyName TEXT NOT NULL,
                    contactName TEXT,
                    phone TEXT,
                    email TEXT,
                    origin TEXT DEFAULT 'Manual',
                    category TEXT DEFAULT 'to-prospect',
                    customMessage TEXT,
                    observations TEXT,
                    potentialValue REAL DEFAULT 0,
                    kanban_highlight TEXT,
                    kanban_highlight_at DATETIME,
                    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                    lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP,
                    priority INTEGER DEFAULT 1,
                    bot_disabled INTEGER NOT NULL DEFAULT 0,
                    bot_disabled_reason TEXT,
                    agent_type TEXT,
                    followup_contract TEXT,
                    followup_status TEXT,
                    next_followup_at DATETIME,
                    followup_auto_trigger_last_fired_at DATETIME,
                    checkout_token TEXT,
                    is_playground INTEGER NOT NULL DEFAULT 0,
                    detected_language TEXT NULL,
                    phases_triggered TEXT NULL,
                    triggers_fired TEXT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO leads (id, user_id, companyName, contactName, phone) "
                "VALUES (1, 7, 'ACME', 'Ana', '+5511999999999')"
            )
            conn.execute(
                "INSERT INTO leads (id, user_id, companyName, contactName, phone) "
                "VALUES (2, 7, 'WhatsApp inbound', NULL, '+5511888888888')"
            )
            conn.commit()

            _migrate_leads_company_or_contact(conn)

            rows = {
                row["id"]: dict(row)
                for row in conn.execute("SELECT * FROM leads ORDER BY id").fetchall()
            }
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["companyName"], "ACME")
            self.assertEqual(rows[1]["contactName"], "Ana")
            self.assertEqual(rows[1]["phone"], "+5511999999999")
            self.assertEqual(rows[2]["companyName"], "WhatsApp inbound")

            info = {row["name"]: row for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
            self.assertEqual(info["companyName"]["notnull"], 0)

            # idempotência: rodar de novo não deve alterar nada nem levantar erro
            _migrate_leads_company_or_contact(conn)
            count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            self.assertEqual(count, 2)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
