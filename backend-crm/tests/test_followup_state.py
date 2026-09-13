import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.followup_state import (
    STOP_INBOUND_REPLY,
    STOP_MAX_ATTEMPTS_REACHED,
    pause_followup_manually,
    progress_followup_after_auto_send,
    stop_followup_on_handoff,
    stop_followup_on_inbound_reply,
)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            bot_disabled INTEGER DEFAULT 0,
            followup_contract TEXT,
            followup_status TEXT,
            next_followup_at DATETIME,
            lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP
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

        -- CHECK igual ao real (backend-crm/database.py::ensure_jobs_tables) --
        -- de propósito, para que um status fora do enum quebre o teste com
        -- IntegrityError, do mesmo jeito que quebrava em produção.
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','failed')),
            result TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE followup_reconcile_guard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            due_at DATETIME NOT NULL,
            job_id INTEGER,
            status TEXT NOT NULL DEFAULT 'enqueued'
        );
        """
    )
    conn.commit()


class FollowupStateTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix="_followup_state.db")
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

    def test_inbound_reply_pauses_followup_and_sets_stop_reason(self):
        contract = {
            "phase": "follow-up",
            "status": "active",
            "attempts": 0,
            "max_attempts": 4,
            "next_followup_at": "2026-01-01T10:00:00Z",
            "stop_reason": None,
            "followup_variant": "sdr_scheduler",
        }
        self.conn.execute(
            "INSERT INTO leads (user_id, category, bot_disabled, followup_contract, followup_status, next_followup_at) VALUES (11, 'follow-up', 0, ?, 'active', ?)",
            (json.dumps(contract), contract["next_followup_at"]),
        )
        lead_id = int(self.conn.execute("SELECT id FROM leads").fetchone()["id"])

        changed = stop_followup_on_inbound_reply(
            self.conn,
            lead_id=lead_id,
            user_id=11,
            inbound_message_id="msg-1",
        )
        self.conn.commit()

        self.assertTrue(changed)
        row = self.conn.execute(
            "SELECT followup_contract, followup_status, next_followup_at FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        saved = json.loads(row["followup_contract"])
        self.assertEqual(saved["status"], "paused")
        self.assertEqual(saved["stop_reason"], STOP_INBOUND_REPLY)
        self.assertIsNone(saved["next_followup_at"])
        self.assertEqual(row["followup_status"], "paused")
        self.assertIsNone(row["next_followup_at"])

    def test_auto_send_progresses_attempts_and_closes_on_max_attempts(self):
        contract = {
            "phase": "follow-up",
            "status": "active",
            "attempts": 1,
            "max_attempts": 2,
            "next_followup_at": "2026-01-01T10:00:00Z",
            "last_followup_at": None,
            "stop_reason": None,
            "followup_variant": "hybrid_scheduler",
        }
        self.conn.execute(
            "INSERT INTO leads (user_id, category, bot_disabled, followup_contract, followup_status, next_followup_at) VALUES (11, 'follow-up', 0, ?, 'active', ?)",
            (json.dumps(contract), contract["next_followup_at"]),
        )
        lead_id = int(self.conn.execute("SELECT id FROM leads").fetchone()["id"])

        result = progress_followup_after_auto_send(
            self.conn,
            lead_id=lead_id,
            user_id=11,
            source_job_id=99,
        )
        self.conn.commit()

        self.assertTrue(result["updated"])
        self.assertEqual(result["reason"], "max_attempts_reached")
        row = self.conn.execute(
            "SELECT followup_contract, followup_status, next_followup_at FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        saved = json.loads(row["followup_contract"])
        self.assertEqual(saved["attempts"], 2)
        self.assertEqual(saved["status"], "closed")
        self.assertEqual(saved["stop_reason"], STOP_MAX_ATTEMPTS_REACHED)
        self.assertIsNone(saved["next_followup_at"])
        self.assertEqual(row["followup_status"], "closed")
        self.assertIsNone(row["next_followup_at"])

    def test_auto_send_progresses_without_reaching_max_attempts(self):
        """Branch "progride sem fechar" -- o único que chamava create_job()
        internamente antes da correção (o branch max_attempts_reached, testado
        acima, retorna antes de chegar lá). O schema deste teste não tem
        tabela `jobs` de propósito: se a função ainda tentasse abrir conexão
        e criar o job aqui dentro, este teste quebraria com "no such table:
        jobs" em vez de passar."""
        contract = {
            "phase": "follow-up",
            "status": "active",
            "attempts": 0,
            "max_attempts": 3,
            "next_followup_at": "2026-01-01T10:00:00Z",
            "last_followup_at": None,
            "stop_reason": None,
            "followup_variant": "sdr_scheduler",
        }
        self.conn.execute(
            "INSERT INTO leads (user_id, category, bot_disabled, followup_contract, followup_status, next_followup_at) VALUES (11, 'follow-up', 0, ?, 'active', ?)",
            (json.dumps(contract), contract["next_followup_at"]),
        )
        lead_id = int(self.conn.execute("SELECT id FROM leads").fetchone()["id"])

        result = progress_followup_after_auto_send(
            self.conn,
            lead_id=lead_id,
            user_id=11,
            source_job_id=99,
        )
        self.conn.commit()

        self.assertTrue(result["updated"])
        self.assertEqual(result["reason"], "progressed")
        self.assertEqual(result["attempts"], 1)
        row = self.conn.execute(
            "SELECT followup_contract, followup_status, next_followup_at FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        saved = json.loads(row["followup_contract"])
        self.assertEqual(saved["attempts"], 1)
        self.assertEqual(saved["status"], "active")
        self.assertIsNotNone(row["next_followup_at"])

    def test_handoff_pauses_followup(self):
        contract = {
            "phase": "follow-up",
            "status": "active",
            "attempts": 0,
            "max_attempts": 3,
            "next_followup_at": "2026-01-01T10:00:00Z",
            "stop_reason": None,
            "followup_variant": "hybrid_scheduler",
        }
        self.conn.execute(
            "INSERT INTO leads (user_id, category, bot_disabled, followup_contract, followup_status, next_followup_at) VALUES (11, 'follow-up', 1, ?, 'active', ?)",
            (json.dumps(contract), contract["next_followup_at"]),
        )
        lead_id = int(self.conn.execute("SELECT id FROM leads").fetchone()["id"])

        changed = stop_followup_on_handoff(self.conn, lead_id=lead_id, user_id=11, reason="manual")
        self.conn.commit()
        self.assertTrue(changed)

        row = self.conn.execute("SELECT followup_contract, followup_status FROM leads WHERE id = ?", (lead_id,)).fetchone()
        saved = json.loads(row["followup_contract"])
        self.assertEqual(saved["status"], "paused")
        self.assertEqual(saved["stop_reason"], "handoff_human")
        self.assertEqual(row["followup_status"], "paused")

    def test_pause_with_pending_job_completes_job_instead_of_integrity_error(self):
        """Antes desta correção, UPDATE jobs SET status='cancelled' violava o
        CHECK constraint (só aceita pending/in_progress/completed/failed) --
        IntegrityError derrubava a transação inteira, e pausar o follow-up
        pela UI falhava sempre que havia job pendente."""
        contract = {
            "phase": "follow-up",
            "status": "active",
            "attempts": 1,
            "max_attempts": 3,
            "next_followup_at": "2026-01-01T10:00:00Z",
            "stop_reason": None,
            "followup_variant": "sdr_scheduler",
        }
        self.conn.execute(
            "INSERT INTO leads (user_id, category, bot_disabled, followup_contract, followup_status, next_followup_at) VALUES (11, 'follow-up', 0, ?, 'active', ?)",
            (json.dumps(contract), contract["next_followup_at"]),
        )
        lead_id = int(self.conn.execute("SELECT id FROM leads").fetchone()["id"])
        self.conn.execute(
            "INSERT INTO jobs (id, user_id, type, payload, status) VALUES (501, 11, 'whatsapp.followup.pregenerate', '{}', 'pending')"
        )
        self.conn.execute(
            "INSERT INTO followup_reconcile_guard (lead_id, due_at, job_id) VALUES (?, ?, 501)",
            (lead_id, contract["next_followup_at"]),
        )

        result = pause_followup_manually(self.conn, lead_id=lead_id, user_id=11)
        self.conn.commit()

        self.assertTrue(result["updated"])
        self.assertEqual(result["reason"], "paused")
        job_row = self.conn.execute("SELECT status, result FROM jobs WHERE id = 501").fetchone()
        self.assertEqual(job_row["status"], "completed")
        self.assertEqual(json.loads(job_row["result"]), {"skipped": True, "reason": "followup_paused_or_cancelled"})
        self.assertIsNone(self.conn.execute("SELECT 1 FROM followup_reconcile_guard WHERE job_id = 501").fetchone())


if __name__ == "__main__":
    unittest.main()
