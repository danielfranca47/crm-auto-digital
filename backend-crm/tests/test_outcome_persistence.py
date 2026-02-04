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
            companyName TEXT NOT NULL,
            kanban_highlight TEXT,
            kanban_highlight_at DATETIME
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


class OutcomePersistenceTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_tables(self.conn)
        self.jobs_service = _load_jobs_service()

        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, companyName) VALUES (?, ?)",
            (7, "ACME"),
        )
        self.lead_id = int(cur.lastrowid)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_outcome_persisted_and_highlight_updated(self):
        result = {
            "outcome": "won",
            "kanban_highlight": "green",
            "reason": "ok",
            "source_job_id": 99,
        }
        outcome, highlight, reason, source_job_id = self.jobs_service.extract_outcome_payload(result)
        applied = self.jobs_service.apply_outcome_highlight(
            self.conn,
            lead_id=self.lead_id,
            user_id=7,
            outcome=outcome,
            highlight=highlight,
            reason=reason,
            source_job_id=source_job_id,
        )
        self.assertTrue(applied)

        row = self.conn.execute(
            "SELECT outcome, highlight, reason, source_job_id FROM lead_outcomes WHERE lead_id = ?",
            (self.lead_id,),
        ).fetchone()
        self.assertEqual(row["outcome"], "won")
        self.assertEqual(row["highlight"], "green")
        self.assertEqual(row["reason"], "ok")
        self.assertEqual(row["source_job_id"], 99)

        lead_row = self.conn.execute(
            "SELECT kanban_highlight FROM leads WHERE id = ?",
            (self.lead_id,),
        ).fetchone()
        self.assertEqual(lead_row["kanban_highlight"], "green")


if __name__ == "__main__":
    unittest.main()
