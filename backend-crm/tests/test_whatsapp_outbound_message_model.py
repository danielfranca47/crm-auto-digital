"""
Garante que mensagens enfileiradas via job whatsapp.send.local são persistidas
com model='outbound', para que o orchestrator as reconheça como contato anterior
(outbound_present) ao responder ao lead.

Cobre também: _handle_whatsapp_report seta origin='outbound' no lead ao confirmar
o envio, sem sobrescrever leads que já têm origin definido (ex: 'whatsapp_inbound').
"""
import importlib.util
import os
import sqlite3
import sys
import unittest


def _install_fastapi_stub() -> None:
    if "fastapi" in sys.modules:
        return

    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi_module = type(sys)("fastapi")
    fastapi_module.HTTPException = HTTPException
    sys.modules["fastapi"] = fastapi_module


def _load_jobs_service():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    module_path = os.path.join(repo_root, "services", "jobs_service.py")
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _install_fastapi_stub()
    spec = importlib.util.spec_from_file_location("jobs_service", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
    return module


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            origin TEXT,
            category TEXT,
            lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP,
            kanban_highlight TEXT,
            kanban_highlight_at DATETIME
        );

        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            subject TEXT,
            body TEXT NOT NULL,
            model TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE message_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            selectedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lead_id, channel)
        );

        CREATE TABLE prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lead_id INTEGER NOT NULL,
            channel TEXT,
            message_id INTEGER,
            action TEXT NOT NULL,
            notes TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE lead_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            user_id INTEGER,
            outcome TEXT,
            highlight TEXT,
            reason TEXT,
            source_job_id INTEGER,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


class WhatsAppOutboundMessageModelTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_tables(self.conn)
        self.jobs_service = _load_jobs_service()

        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, origin, category) VALUES (?, ?, ?)",
            (1, "Manual", "to-prospect"),
        )
        self.lead_id = int(cur.lastrowid)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    # ------------------------------------------------------------------
    # _persist_whatsapp_message
    # ------------------------------------------------------------------

    def test_persist_whatsapp_message_uses_model_outbound(self):
        """Mensagem enfileirada via job deve ter model='outbound'."""
        cur = self.conn.cursor()
        self.jobs_service._persist_whatsapp_message(cur, self.lead_id, "Olá, tudo bem?")
        self.conn.commit()

        row = self.conn.execute(
            "SELECT model FROM messages WHERE lead_id = ?",
            (self.lead_id,),
        ).fetchone()
        self.assertIsNotNone(row, "mensagem devia ter sido inserida")
        self.assertEqual(
            row["model"],
            "outbound",
            "model deve ser 'outbound' para o orchestrator reconhecer como contato anterior",
        )

    # ------------------------------------------------------------------
    # _handle_whatsapp_report: seta origin='outbound'
    # ------------------------------------------------------------------

    def test_handle_whatsapp_report_sets_origin_outbound_when_neutral(self):
        """Ao completar job, lead com origin='Manual' deve ficar 'outbound'."""
        payload = {"lead_id": self.lead_id, "message_id": 10}
        self.jobs_service._handle_whatsapp_report(
            self.conn,
            payload,
            self.jobs_service.JOB_STATUS_COMPLETED,
            {},
            None,
            user_id=1,
        )

        row = self.conn.execute(
            "SELECT origin FROM leads WHERE id = ?", (self.lead_id,)
        ).fetchone()
        self.assertEqual(row["origin"], "outbound")

    def test_handle_whatsapp_report_sets_origin_outbound_when_empty(self):
        """Ao completar job, lead com origin='' deve ficar 'outbound'."""
        self.conn.execute(
            "UPDATE leads SET origin = '' WHERE id = ?", (self.lead_id,)
        )
        self.conn.commit()

        payload = {"lead_id": self.lead_id, "message_id": 11}
        self.jobs_service._handle_whatsapp_report(
            self.conn,
            payload,
            self.jobs_service.JOB_STATUS_COMPLETED,
            {},
            None,
            user_id=1,
        )

        row = self.conn.execute(
            "SELECT origin FROM leads WHERE id = ?", (self.lead_id,)
        ).fetchone()
        self.assertEqual(row["origin"], "outbound")

    def test_handle_whatsapp_report_does_not_overwrite_inbound_origin(self):
        """Lead com origin='whatsapp_inbound' nunca deve ser sobrescrito."""
        self.conn.execute(
            "UPDATE leads SET origin = 'whatsapp_inbound' WHERE id = ?",
            (self.lead_id,),
        )
        self.conn.commit()

        payload = {"lead_id": self.lead_id, "message_id": 12}
        self.jobs_service._handle_whatsapp_report(
            self.conn,
            payload,
            self.jobs_service.JOB_STATUS_COMPLETED,
            {},
            None,
            user_id=1,
        )

        row = self.conn.execute(
            "SELECT origin FROM leads WHERE id = ?", (self.lead_id,)
        ).fetchone()
        self.assertEqual(
            row["origin"],
            "whatsapp_inbound",
            "origin de lead inbound nunca deve ser sobrescrito por job outbound",
        )

    def test_handle_whatsapp_report_does_not_overwrite_existing_outbound(self):
        """Lead já com origin='outbound' mantém o valor (UPDATE idempotente)."""
        self.conn.execute(
            "UPDATE leads SET origin = 'outbound' WHERE id = ?", (self.lead_id,)
        )
        self.conn.commit()

        payload = {"lead_id": self.lead_id, "message_id": 13}
        self.jobs_service._handle_whatsapp_report(
            self.conn,
            payload,
            self.jobs_service.JOB_STATUS_COMPLETED,
            {},
            None,
            user_id=1,
        )

        row = self.conn.execute(
            "SELECT origin FROM leads WHERE id = ?", (self.lead_id,)
        ).fetchone()
        self.assertEqual(row["origin"], "outbound")

    def test_handle_whatsapp_report_failed_does_not_set_origin(self):
        """Job com status=failed não deve alterar origin do lead."""
        payload = {"lead_id": self.lead_id, "message_id": 14}
        self.jobs_service._handle_whatsapp_report(
            self.conn,
            payload,
            self.jobs_service.JOB_STATUS_FAILED,
            None,
            "timeout",
            user_id=1,
        )

        row = self.conn.execute(
            "SELECT origin FROM leads WHERE id = ?", (self.lead_id,)
        ).fetchone()
        self.assertEqual(
            row["origin"],
            "Manual",
            "job falhado não deve alterar origin",
        )


if __name__ == "__main__":
    unittest.main()
