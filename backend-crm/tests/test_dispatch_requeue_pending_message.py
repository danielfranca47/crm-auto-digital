import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.executor import _dispatch_system_actions


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            assigned_agent_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            scheduled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            result TEXT,
            error TEXT
        );

        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT,
            contactName TEXT,
            email TEXT
        );
        """
    )
    conn.commit()


class DispatchSystemActionsReturnsSpecsTest(unittest.TestCase):
    """_dispatch_system_actions() não cria job nenhum — só devolve as specs.

    Antes desta correção, a função chamava create_job() diretamente (que abre
    conexão nova via get_connection()) enquanto o chamador (complete_job_internal)
    ainda segurava um BEGIN IMMEDIATE em aberto — "database is locked". Estes
    testes não mockam services.jobs_service.get_connection de propósito: se a
    função voltar a chamar create_job() internamente, ela tentaria abrir uma
    conexão real e falharia (não há um banco real disponível no path default),
    o que já denunciaria a regressão.
    """

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_requeue_pending_message_returns_inbound_job_spec(self):
        pending = _dispatch_system_actions(
            lead_id=42,
            user_id=7,
            phone="5511999999999",
            system_actions=[
                {
                    "type": "requeue_pending_message",
                    "message_text": "gostaria de agendar horário para hoje às 17:30",
                }
            ],
            conn=self.conn,
            instance_id="inst-1",
            provider="uazapi",
            source_message_id="orig-msg-123",
        )

        self.assertEqual(len(pending), 1)
        spec = pending[0]
        self.assertEqual(spec["job_type"], "whatsapp.inbound.n8n")
        payload = spec["payload"]
        self.assertEqual(payload["lead_id"], 42)
        self.assertEqual(payload["user_id"], 7)
        self.assertEqual(payload["instance_id"], "inst-1")
        self.assertEqual(payload["provider"], "uazapi")
        self.assertEqual(payload["phone"], "5511999999999")
        self.assertEqual(payload["message_text"], "gostaria de agendar horário para hoje às 17:30")
        self.assertTrue(payload["message_id"].startswith("requeue:orig-msg-123:"))
        # nada foi inserido na tabela jobs -- criação é responsabilidade do chamador
        self.assertIsNone(self.conn.execute("SELECT * FROM jobs").fetchone())

    def test_skips_when_channel_context_missing(self):
        pending = _dispatch_system_actions(
            lead_id=42,
            user_id=7,
            phone="5511999999999",
            system_actions=[
                {"type": "requeue_pending_message", "message_text": "pergunta pendente"}
            ],
            conn=self.conn,
            instance_id=None,
            provider=None,
            source_message_id="orig-msg-123",
        )
        self.assertEqual(pending, [])

    def test_skips_when_message_text_empty(self):
        pending = _dispatch_system_actions(
            lead_id=42,
            user_id=7,
            phone="5511999999999",
            system_actions=[{"type": "requeue_pending_message", "message_text": "   "}],
            conn=self.conn,
            instance_id="inst-1",
            provider="uazapi",
            source_message_id="orig-msg-123",
        )
        self.assertEqual(pending, [])

    def test_send_message_and_webhook_return_specs_without_creating_job(self):
        self.conn.execute(
            "INSERT INTO leads (id, user_id, companyName, contactName, email) VALUES (1, 7, 'Empresa', 'Contato', 'c@x.com')"
        )
        pending = _dispatch_system_actions(
            lead_id=1,
            user_id=7,
            phone="5511999999999",
            system_actions=[
                {"type": "send_message", "content": "oi, tudo bem?"},
                {"type": "webhook", "url": "https://example.com/hook", "block_id": "b1"},
            ],
            conn=self.conn,
        )
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0]["job_type"], "whatsapp.send.local")
        self.assertEqual(pending[0]["payload"]["body"], "oi, tudo bem?")
        self.assertEqual(pending[1]["job_type"], "sales_flow.webhook.dispatch")
        self.assertEqual(pending[1]["payload"]["url"], "https://example.com/hook")
        self.assertIsNone(self.conn.execute("SELECT * FROM jobs").fetchone())


class NoDeadlockWithRealSeparateConnectionsTest(unittest.TestCase):
    """Regressão de ponta a ponta com 2 conexões SQLite reais (não mockadas).

    Reproduz o cenário real de produção: uma conexão A segura BEGIN IMMEDIATE
    (como complete_job_internal), e só depois do commit dela é que os jobs
    coletados são de fato criados numa conexão B separada (create_job real).
    Antes da correção, isso teria que acontecer ENQUANTO A ainda segurava o
    lock -- aqui provamos que a ordem "commit primeiro, cria job depois"
    nunca colide.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix="_dispatch_no_deadlock.db")
        os.close(fd)
        setup_conn = sqlite3.connect(self.db_path)
        _create_schema(setup_conn)
        setup_conn.close()

    def tearDown(self):
        # create_job() real deixa a conexão que abriu aberta (o context manager
        # do sqlite3 só comita, não fecha) -- no Windows isso impede apagar o
        # arquivo temporário; não é algo que esta implementação precisa corrigir.
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    def _real_get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def test_dispatch_does_not_touch_connection_while_lock_is_held_and_create_job_works_after_commit(self):
        conn_a = sqlite3.connect(self.db_path)
        conn_a.row_factory = sqlite3.Row
        conn_a.execute("PRAGMA busy_timeout = 5000")
        conn_a.execute("BEGIN IMMEDIATE")
        conn_a.execute("INSERT INTO leads (id, user_id, companyName) VALUES (1, 7, 'Empresa')")

        started = time.monotonic()
        pending = _dispatch_system_actions(
            lead_id=1,
            user_id=7,
            phone="5511999999999",
            system_actions=[{"type": "send_message", "content": "oi"}],
            conn=conn_a,
        )
        elapsed = time.monotonic() - started
        # se ainda tentasse abrir conexao nova aqui, ficaria esperando o
        # busy_timeout (5s) com o lock de conn_a ainda aberto -- e nunca
        # conseguiria, porque quem liberaria o lock (conn_a.commit()) so roda
        # depois desta linha.
        self.assertLess(elapsed, 1.0, "chamada demorou como se tivesse tentado abrir conexao nova durante o lock")
        self.assertEqual(len(pending), 1)

        conn_a.commit()
        conn_a.close()

        with patch("services.jobs_service.get_connection", side_effect=self._real_get_connection):
            for spec in pending:
                from services.jobs_service import create_job
                create_job(**spec)

        check_conn = sqlite3.connect(self.db_path)
        check_conn.row_factory = sqlite3.Row
        row = check_conn.execute("SELECT * FROM jobs").fetchone()
        check_conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["type"], "whatsapp.send.local")
        self.assertEqual(json.loads(row["payload"])["body"], "oi")


if __name__ == "__main__":
    unittest.main()
