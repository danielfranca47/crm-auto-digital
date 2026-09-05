"""
Garante que POST /public/leads (formulário de contato do website) grava o
lead com o user_id configurado via PUBLIC_LEAD_USER_ID, em vez de user_id
nulo (bug real: lead ficava órfão, invisível em todo Kanban).
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes import public  # noqa: E402


def _make_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_leads_table(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT,
            contactName TEXT,
            phone TEXT,
            email TEXT,
            origin TEXT DEFAULT 'Manual',
            category TEXT DEFAULT 'to-prospect',
            customMessage TEXT,
            observations TEXT,
            agent_type TEXT,
            priority INTEGER DEFAULT 1,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()


class TestPublicLeadUserId(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        _create_leads_table(self.db_path)

        os.environ["FORM_TOKEN"] = "test-token"
        os.environ.setdefault("SMTP_HOST", "localhost")
        os.environ.setdefault("EMAIL_FROM", "test@example.com")
        os.environ.pop("EMAIL_TO", None)
        os.environ.pop("PUBLIC_LEAD_USER_ID", None)

        patcher = patch("routes.public.get_connection", lambda: _make_connection(self.db_path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        os.environ.pop("PUBLIC_LEAD_USER_ID", None)
        os.remove(self.db_path)

    def _payload(self) -> "public.PublicLeadPayload":
        return public.PublicLeadPayload(
            fullName="Lead Teste",
            email="lead@example.com",
            phone="+551199999999",
        )

    def test_lead_gravado_com_user_id_configurado(self):
        os.environ["PUBLIC_LEAD_USER_ID"] = "15"

        result = public.create_public_lead(self._payload(), x_form_token="test-token", bg=None)
        self.assertEqual(result["status"], "created")

        conn = _make_connection(self.db_path)
        row = conn.execute(
            "SELECT user_id, origin, category FROM leads WHERE id=?", (result["id"],)
        ).fetchone()
        conn.close()

        self.assertEqual(row["user_id"], 15)
        self.assertEqual(row["origin"], "Formulário Website")
        self.assertEqual(row["category"], "to-prospect")

    def test_falha_clara_sem_env_var(self):
        with self.assertRaises(Exception) as ctx:
            public.create_public_lead(self._payload(), x_form_token="test-token", bg=None)
        self.assertEqual(getattr(ctx.exception, "status_code", None), 500)

        conn = _make_connection(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0, "nenhum lead deve ser gravado quando a env var está ausente")


if __name__ == "__main__":
    unittest.main()
