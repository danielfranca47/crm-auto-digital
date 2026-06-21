import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import routes.appointments as appointments_module
from models import AppointmentUpdate


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT,
            contactName TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            type TEXT,
            start_at TEXT,
            end_at TEXT,
            status TEXT DEFAULT 'pending',
            outcome TEXT,
            outcome_note TEXT,
            outcome_at TEXT,
            location TEXT,
            google_event_id TEXT,
            source TEXT DEFAULT 'crm',
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','failed')),
            result TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


class UpdateAppointmentRouteTest(unittest.TestCase):
    """Regressão: PUT /api/appointments/{id} sem lead_id no payload (AppointmentUpdate
    não tem esse campo, por design) não deve quebrar com AttributeError.

    Esse bug pré-existente só foi descoberto porque meeting_scheduler.py passou a ser o
    primeiro caller real deste endpoint (crm_client.reschedule_appointment) — os testes da
    Fase 2 mockavam o crm_client e nunca exercitaram esta rota de verdade.
    """

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

        cur = self.conn.cursor()
        cur.execute("INSERT INTO leads (user_id, companyName) VALUES (1, 'ACME')")
        self.lead_id = cur.lastrowid

        now = datetime.now(timezone.utc)
        cur.execute(
            "INSERT INTO appointments (lead_id, title, start_at, end_at, status, source, created_at, updated_at)"
            " VALUES (?, 'Sessao', ?, ?, 'pending', 'crm', ?, ?)",
            (
                self.lead_id,
                (now + timedelta(days=2)).isoformat(),
                (now + timedelta(days=2, minutes=30)).isoformat(),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        self.appointment_id = cur.lastrowid
        self.conn.commit()

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def test_update_start_at_without_lead_id_does_not_raise(self):
        new_start = datetime.now(timezone.utc) + timedelta(days=3)
        new_end = new_start + timedelta(minutes=30)
        payload = AppointmentUpdate(start_at=new_start, end_at=new_end)

        with patch("routes.appointments.get_connection", return_value=self.conn), \
                patch("routes.appointments.gcal_update"), \
                patch("routes.appointments.schedule_appointment_reminder_jobs"), \
                patch("routes.appointments.schedule_briefing_job_for_appointment"):
            result = appointments_module.update_appointment(self.appointment_id, payload)

        self.assertEqual(result.id, self.appointment_id)
        self.assertEqual(result.start_at, new_start)
        self.assertEqual(result.end_at, new_end)

    def test_update_title_only_does_not_raise(self):
        payload = AppointmentUpdate(title="Novo titulo")

        with patch("routes.appointments.get_connection", return_value=self.conn):
            result = appointments_module.update_appointment(self.appointment_id, payload)

        self.assertEqual(result.title, "Novo titulo")


if __name__ == "__main__":
    unittest.main()
