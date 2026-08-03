import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException

import routes.executor as executor_module
from models import AppointmentCreate, AppointmentUpdate


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


class RequireServiceTokenTest(unittest.TestCase):
    """`_require_service_token` é o mecanismo de auth das rotas /api/internal/appointments/*
    — token de serviço (CRM_SERVICE_TOKEN/CORE_SERVICE_TOKEN), nunca JWT de usuário."""

    def test_accepts_valid_token(self):
        with patch.dict(os.environ, {"CRM_SERVICE_TOKEN": "segredo-valido"}):
            result = executor_module._require_service_token(x_service_token="segredo-valido")
        self.assertEqual(result, "segredo-valido")

    def test_rejects_wrong_token(self):
        with patch.dict(os.environ, {"CRM_SERVICE_TOKEN": "segredo-valido"}):
            with self.assertRaises(HTTPException) as ctx:
                executor_module._require_service_token(x_service_token="errado")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_rejects_missing_token(self):
        with patch.dict(os.environ, {"CRM_SERVICE_TOKEN": "segredo-valido"}):
            with self.assertRaises(HTTPException) as ctx:
                executor_module._require_service_token(x_service_token=None)
        self.assertEqual(ctx.exception.status_code, 401)


class InternalAppointmentsRoutesTest(unittest.TestCase):
    """Regressão da Fase 2 de docs/implementations/fix-confirm-exact-agenda-vazia.md:
    backend-executors só tem X-Service-Token (nunca JWT de usuário), mas POST/PUT/cancel
    de /api/appointments passaram a exigir require_crm_access desde o commit 6aebb6f
    (correção de segurança legítima, sem essa exceção). Essas rotas internas replicam o
    mesmo padrão de confiança já usado em /internal/logs/meeting-scheduled: token de
    serviço + ID explícito, sem checagem de JWT de usuário.
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

    # --- POST /internal/appointments ---

    def test_create_appointment_internal_success(self):
        start = datetime.now(timezone.utc) + timedelta(days=5)
        payload = AppointmentCreate(
            lead_id=self.lead_id, title="Nova sessao", start_at=start, end_at=start + timedelta(hours=1)
        )
        with patch("routes.executor.get_connection", return_value=self.conn), \
                patch("routes.appointments.gcal_push", return_value=None), \
                patch("routes.appointments.schedule_appointment_reminder_jobs"), \
                patch("routes.appointments.schedule_briefing_job_for_appointment"):
            result = executor_module.create_appointment_internal(payload, "token-valido")

        self.assertEqual(result.lead_id, self.lead_id)
        self.assertEqual(result.title, "Nova sessao")

    def test_create_appointment_internal_missing_lead_returns_404(self):
        start = datetime.now(timezone.utc) + timedelta(days=5)
        payload = AppointmentCreate(
            lead_id=999999, title="X", start_at=start, end_at=start + timedelta(hours=1)
        )
        with patch("routes.executor.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                executor_module.create_appointment_internal(payload, "token-valido")
        self.assertEqual(ctx.exception.status_code, 404)

    # --- PUT /internal/appointments/{id} ---

    def test_update_appointment_internal_reschedules(self):
        new_start = datetime.now(timezone.utc) + timedelta(days=3)
        new_end = new_start + timedelta(minutes=30)
        payload = AppointmentUpdate(start_at=new_start, end_at=new_end)

        with patch("routes.executor.get_connection", return_value=self.conn), \
                patch("routes.appointments.gcal_update"), \
                patch("routes.appointments.schedule_appointment_reminder_jobs"), \
                patch("routes.appointments.schedule_briefing_job_for_appointment"):
            result = executor_module.update_appointment_internal(self.appointment_id, payload, "token-valido")

        self.assertEqual(result.id, self.appointment_id)
        self.assertEqual(result.start_at, new_start)
        self.assertEqual(result.end_at, new_end)

    def test_update_appointment_internal_missing_appointment_returns_404(self):
        payload = AppointmentUpdate(title="X")
        with patch("routes.executor.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                executor_module.update_appointment_internal(999999, payload, "token-valido")
        self.assertEqual(ctx.exception.status_code, 404)

    # --- POST /internal/appointments/{id}/cancel ---

    def test_cancel_appointment_internal_cancels(self):
        with patch("routes.executor.get_connection", return_value=self.conn), \
                patch("routes.appointments.get_connection", return_value=self.conn):
            result = executor_module.cancel_appointment_internal(self.appointment_id, "token-valido")

        self.assertEqual(result.status, "canceled")

    def test_cancel_appointment_internal_missing_appointment_returns_404(self):
        with patch("routes.executor.get_connection", return_value=self.conn), \
                patch("routes.appointments.get_connection", return_value=self.conn):
            with self.assertRaises(HTTPException) as ctx:
                executor_module.cancel_appointment_internal(999999, "token-valido")
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
