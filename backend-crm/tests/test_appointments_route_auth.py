import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException

import routes.appointments as appointments_module
from models import AppointmentCreate
from security_core import CurrentUser


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


class AppointmentsRouteAuthTest(unittest.TestCase):
    """Regressão do achado crítico da auditoria de segurança: as 6 rotas de
    appointments.py não tinham autenticação nem checagem de dono — qualquer
    chamada conseguia ler/criar/alterar/apagar compromissos de qualquer tenant.

    Cobre o caso negativo (usuário que não é dono -> 404) para as 6 rotas
    corrigidas, e o caso positivo (dono -> sucesso) para as que ainda não
    tinham teste de sucesso (list_by_lead, create, delete, complete, cancel;
    update_appointment já tem cobertura de sucesso em
    test_update_appointment_route.py).
    """

    def setUp(self):
        # Arquivo temporário (não :memory:) porque algumas rotas fecham a conexão
        # no próprio `finally` — precisamos reabrir para verificar o estado do
        # banco depois da chamada, o que :memory: não permite.
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

        cur = self.conn.cursor()
        cur.execute("INSERT INTO leads (user_id, companyName) VALUES (1, 'ACME (dono)')")
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

        self.owner = CurrentUser(id=1, email="dono@teste.com")
        self.intruder = CurrentUser(id=2, email="intruso@teste.com")

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def _reopen(self) -> sqlite3.Connection:
        """Abre uma nova conexão ao mesmo arquivo — usado para verificar estado
        depois que a rota já fechou `self.conn` no seu `finally`."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # --- GET /lead/{lead_id} ---

    def test_list_by_lead_denies_non_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                appointments_module.list_by_lead(self.lead_id, self.intruder)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_list_by_lead_allows_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            result = appointments_module.list_by_lead(self.lead_id, self.owner)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, self.appointment_id)

    # --- POST "" (create_appointment) ---

    def test_create_appointment_denies_non_owner(self):
        start = datetime.now(timezone.utc) + timedelta(days=5)
        payload = AppointmentCreate(lead_id=self.lead_id, title="Tentativa", start_at=start, end_at=start + timedelta(hours=1))
        with patch("routes.appointments.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                appointments_module.create_appointment(payload, self.intruder)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_appointment_allows_owner(self):
        start = datetime.now(timezone.utc) + timedelta(days=5)
        payload = AppointmentCreate(lead_id=self.lead_id, title="Nova sessao", start_at=start, end_at=start + timedelta(hours=1))
        with patch("routes.appointments.get_connection", return_value=self.conn), \
                patch("routes.appointments.gcal_push", return_value=None), \
                patch("routes.appointments.schedule_appointment_reminder_jobs"), \
                patch("routes.appointments.schedule_briefing_job_for_appointment"):
            result = appointments_module.create_appointment(payload, self.owner)
        self.assertEqual(result.lead_id, self.lead_id)
        self.assertEqual(result.title, "Nova sessao")

    # --- PUT /{appointment_id} (update_appointment) ---
    # Caso positivo já coberto em test_update_appointment_route.py

    def test_update_appointment_denies_non_owner(self):
        from models import AppointmentUpdate

        payload = AppointmentUpdate(title="Hackeado")
        with patch("routes.appointments.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                appointments_module.update_appointment(self.appointment_id, payload, self.intruder)
        self.assertEqual(ctx.exception.status_code, 404)

    # --- DELETE /{appointment_id} ---

    def test_delete_appointment_denies_non_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                appointments_module.delete_appointment(self.appointment_id, self.intruder)
        self.assertEqual(ctx.exception.status_code, 404)

        # confirma que o compromisso do dono NÃO foi apagado pela tentativa do intruso
        check_conn = self._reopen()
        cur = check_conn.cursor()
        cur.execute("SELECT 1 FROM appointments WHERE id = ?", (self.appointment_id,))
        self.assertIsNotNone(cur.fetchone())
        check_conn.close()

    def test_delete_appointment_allows_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            appointments_module.delete_appointment(self.appointment_id, self.owner)

        check_conn = self._reopen()
        cur = check_conn.cursor()
        cur.execute("SELECT 1 FROM appointments WHERE id = ?", (self.appointment_id,))
        self.assertIsNone(cur.fetchone())
        check_conn.close()

    # --- POST /{appointment_id}/complete e /cancel ---

    def test_mark_completed_denies_non_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                appointments_module.mark_completed(self.appointment_id, self.intruder)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_mark_completed_allows_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            result = appointments_module.mark_completed(self.appointment_id, self.owner)
        self.assertEqual(result.status, "completed")

    def test_mark_canceled_denies_non_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                appointments_module.mark_canceled(self.appointment_id, self.intruder)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_mark_canceled_allows_owner(self):
        with patch("routes.appointments.get_connection", return_value=self.conn):
            result = appointments_module.mark_canceled(self.appointment_id, self.owner)
        self.assertEqual(result.status, "canceled")


if __name__ == "__main__":
    unittest.main()
