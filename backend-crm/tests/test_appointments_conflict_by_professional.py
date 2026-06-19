import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException

from routes.appointments import _check_conflict, _resolve_owner_user_id


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            user_id INTEGER,
            start_at TEXT,
            end_at TEXT
        );
        """
    )
    conn.commit()


class AppointmentConflictByProfessionalTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _insert_lead(self, user_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO leads (user_id, companyName) VALUES (?, 'ACME')", (user_id,))
        self.conn.commit()
        return int(cur.lastrowid)

    def _insert_appointment(self, *, lead_id, user_id, start_at, end_at):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO appointments (lead_id, user_id, start_at, end_at) VALUES (?, ?, ?, ?)",
            (lead_id, user_id, start_at, end_at),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def test_resolve_owner_user_id_from_lead(self):
        lead_id = self._insert_lead(user_id=7)
        self.assertEqual(_resolve_owner_user_id(self.conn, lead_id=lead_id), 7)

    def test_resolve_owner_user_id_falls_back_when_no_lead(self):
        self.assertEqual(
            _resolve_owner_user_id(self.conn, lead_id=None, fallback_user_id=42), 42
        )

    def test_conflict_blocks_different_leads_same_professional(self):
        lead_a = self._insert_lead(user_id=1)
        lead_b = self._insert_lead(user_id=1)
        self._insert_appointment(
            lead_id=lead_a, user_id=None,
            start_at="2026-03-01T10:00:00+00:00", end_at="2026-03-01T11:00:00+00:00",
        )
        import datetime as dt

        with self.assertRaises(HTTPException) as ctx:
            _check_conflict(
                self.conn, 1,
                dt.datetime.fromisoformat("2026-03-01T10:30:00+00:00"),
                dt.datetime.fromisoformat("2026-03-01T11:30:00+00:00"),
            )
        self.assertEqual(ctx.exception.status_code, 409)
        # garante que o conflito não é do lead_b (que nem tem appointment ainda) — é do profissional
        self.assertNotEqual(lead_a, lead_b)

    def test_no_conflict_for_different_professionals(self):
        lead_a = self._insert_lead(user_id=1)
        self._insert_appointment(
            lead_id=lead_a, user_id=None,
            start_at="2026-03-01T10:00:00+00:00", end_at="2026-03-01T11:00:00+00:00",
        )
        import datetime as dt

        # user_id=2 é outro profissional — mesmo horário não deve conflitar
        _check_conflict(
            self.conn, 2,
            dt.datetime.fromisoformat("2026-03-01T10:30:00+00:00"),
            dt.datetime.fromisoformat("2026-03-01T11:30:00+00:00"),
        )  # não levanta excecao

    def test_conflict_includes_google_imported_appointment(self):
        self._insert_appointment(
            lead_id=None, user_id=1,
            start_at="2026-03-02T09:00:00+00:00", end_at="2026-03-02T09:30:00+00:00",
        )
        import datetime as dt

        with self.assertRaises(HTTPException) as ctx:
            _check_conflict(
                self.conn, 1,
                dt.datetime.fromisoformat("2026-03-02T09:10:00+00:00"),
                dt.datetime.fromisoformat("2026-03-02T09:40:00+00:00"),
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_exclude_id_ignores_self(self):
        lead_a = self._insert_lead(user_id=1)
        appt_id = self._insert_appointment(
            lead_id=lead_a, user_id=None,
            start_at="2026-03-03T10:00:00+00:00", end_at="2026-03-03T11:00:00+00:00",
        )
        import datetime as dt

        _check_conflict(
            self.conn, 1,
            dt.datetime.fromisoformat("2026-03-03T10:00:00+00:00"),
            dt.datetime.fromisoformat("2026-03-03T11:00:00+00:00"),
            exclude_id=appt_id,
        )  # não levanta excecao — é o próprio appointment sendo actualizado

    def test_none_user_id_skips_check(self):
        import datetime as dt

        _check_conflict(
            self.conn, None,
            dt.datetime.fromisoformat("2026-03-04T10:00:00+00:00"),
            dt.datetime.fromisoformat("2026-03-04T11:00:00+00:00"),
        )  # sem user_id resolvido, não há o que checar


if __name__ == "__main__":
    unittest.main()
