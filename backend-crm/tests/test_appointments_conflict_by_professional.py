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
            google_transparency TEXT,
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

    def test_google_free_event_does_not_conflict(self):
        """Evento do Google marcado como Disponível (ex.: aniversário de dia inteiro) não bloqueia."""
        appt_id = self._insert_appointment(
            lead_id=None, user_id=1,
            start_at="2026-03-03", end_at="2026-03-04",
        )
        self.conn.execute("UPDATE appointments SET google_transparency = 'transparent' WHERE id = ?", (appt_id,))
        self.conn.commit()
        import datetime as dt

        _check_conflict(
            self.conn, 1,
            dt.datetime.fromisoformat("2026-03-03T10:00:00+00:00"),
            dt.datetime.fromisoformat("2026-03-03T11:00:00+00:00"),
        )  # não levanta excecao

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

    def test_session_starting_when_google_event_ends_is_free(self):
        """PROD07 p-val-17h: evento do Google 15–16h gravado com `Z`; sessão das 16h não colide."""
        self._insert_appointment(
            lead_id=None, user_id=1,
            start_at="2026-10-29T15:00:00Z", end_at="2026-10-29T16:00:00Z",
        )
        import datetime as dt

        _check_conflict(
            self.conn, 1,
            dt.datetime.fromisoformat("2026-10-29T16:00:00+00:00"),
            dt.datetime.fromisoformat("2026-10-29T17:00:00+00:00"),
        )  # não levanta excecao — "16:00:00Z" e "16:00:00+00:00" são a mesma hora

    def test_real_overlap_with_google_z_event_conflicts(self):
        self._insert_appointment(
            lead_id=None, user_id=1,
            start_at="2026-10-29T15:00:00Z", end_at="2026-10-29T16:00:00Z",
        )
        import datetime as dt

        with self.assertRaises(HTTPException) as ctx:
            _check_conflict(
                self.conn, 1,
                dt.datetime.fromisoformat("2026-10-29T15:30:00+00:00"),
                dt.datetime.fromisoformat("2026-10-29T16:30:00+00:00"),
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_google_event_with_summer_offset_compared_in_utc(self):
        """Lisboa no verão: 16:00+01:00 é 15:00 UTC — como texto errava por uma hora inteira."""
        self._insert_appointment(
            lead_id=None, user_id=1,
            start_at="2026-07-02T16:00:00+01:00", end_at="2026-07-02T17:00:00+01:00",
        )
        import datetime as dt

        _check_conflict(
            self.conn, 1,
            dt.datetime.fromisoformat("2026-07-02T16:00:00+00:00"),
            dt.datetime.fromisoformat("2026-07-02T17:00:00+00:00"),
        )  # não levanta excecao — o evento acaba às 16:00 UTC
        with self.assertRaises(HTTPException):
            _check_conflict(
                self.conn, 1,
                dt.datetime.fromisoformat("2026-07-02T15:30:00+00:00"),
                dt.datetime.fromisoformat("2026-07-02T16:30:00+00:00"),
            )

    def test_busy_all_day_google_event_conflicts(self):
        """Dia inteiro marcado como Ocupado (gravado só com a data) bloqueia o dia."""
        self._insert_appointment(
            lead_id=None, user_id=1,
            start_at="2026-03-05", end_at="2026-03-06",
        )
        import datetime as dt

        with self.assertRaises(HTTPException):
            _check_conflict(
                self.conn, 1,
                dt.datetime.fromisoformat("2026-03-05T10:00:00+00:00"),
                dt.datetime.fromisoformat("2026-03-05T11:00:00+00:00"),
            )
        _check_conflict(
            self.conn, 1,
            dt.datetime.fromisoformat("2026-03-06T10:00:00+00:00"),
            dt.datetime.fromisoformat("2026-03-06T11:00:00+00:00"),
        )  # dia seguinte livre

    def test_none_user_id_skips_check(self):
        import datetime as dt

        _check_conflict(
            self.conn, None,
            dt.datetime.fromisoformat("2026-03-04T10:00:00+00:00"),
            dt.datetime.fromisoformat("2026-03-04T11:00:00+00:00"),
        )  # sem user_id resolvido, não há o que checar

    def test_outcome_reschedule_conflict_compares_as_dates(self):
        """Remarcar pelo resultado da sessão (appointment_outcomes) usa a mesma comparação por datas."""
        from services.appointment_outcomes import _check_conflict as outcome_check_conflict
        import datetime as dt

        lead_id = self._insert_lead(user_id=1)
        self._insert_appointment(
            lead_id=lead_id, user_id=None,
            start_at="2026-10-29T15:00:00Z", end_at="2026-10-29T16:00:00Z",
        )
        outcome_check_conflict(
            self.conn, lead_id,
            dt.datetime.fromisoformat("2026-10-29T16:00:00+00:00"),
            dt.datetime.fromisoformat("2026-10-29T17:00:00+00:00"),
        )  # não levanta excecao
        with self.assertRaises(ValueError):
            outcome_check_conflict(
                self.conn, lead_id,
                dt.datetime.fromisoformat("2026-10-29T15:30:00+00:00"),
                dt.datetime.fromisoformat("2026-10-29T16:30:00+00:00"),
            )


if __name__ == "__main__":
    unittest.main()
