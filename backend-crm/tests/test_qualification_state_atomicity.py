import gc
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import qualification_state
from services.qualification_state import upsert_qualification_state


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            agent_type TEXT
        );

        CREATE TABLE lead_qualification_state (
            lead_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            stage TEXT,
            agent_mode_normalized TEXT,
            playbook_key TEXT,
            playbook_version TEXT,
            data_json TEXT,
            confidence_json TEXT,
            last_questioned_field TEXT,
            attempts_json TEXT,
            asked_questions_json TEXT,
            last_question_text TEXT,
            power_score INTEGER DEFAULT 0,
            priority_score INTEGER DEFAULT 0,
            price_score INTEGER DEFAULT 0,
            timing_score INTEGER DEFAULT 0,
            qualification_total_score INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


class UpsertQualificationStateAtomicityTest(unittest.TestCase):
    """Regressão do bug reportado em produção: duas gravações de qualificação para o
    mesmo lead próximas no tempo (duas mensagens do lead processadas em sequência, ou
    uma edição manual do card coincidindo com uma extração do bot em andamento) podiam
    se sobrescrever, perdendo um campo já capturado — ver
    docs/implementations/fix-qualificacao-race-condition-e-refresh.md.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix="_qualification_state_atomicity.db")
        os.close(fd)
        conn = sqlite3.connect(self.db_path)
        _create_schema(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO leads (user_id, category, agent_type) VALUES (99, 'qualification', 'agent_1')"
        )
        self.lead_id = int(cur.lastrowid)
        conn.commit()
        conn.close()

    def tearDown(self):
        # upsert_qualification_state() abre conexões via get_connection() sem fechá-las
        # explicitamente (padrão já existente no módulo) — no Windows, o handle do SQLite
        # só é liberado quando o objeto é coletado, então força o GC antes de remover o
        # arquivo temporário para evitar PermissionError (WinError 32).
        gc.collect()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def _get_connection(self) -> sqlite3.Connection:
        # timeout alto o suficiente para a 2ª thread esperar o BEGIN IMMEDIATE da 1ª
        # liberar, em vez de estourar "database is locked".
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def test_concurrent_upserts_for_same_lead_do_not_lose_fields(self):
        """Força deterministicamente o intercalamento que causava lost-update: a thread 1
        é pausada logo depois de ler o estado (primeira chamada a merge_data) e só
        retoma (mescla + grava) depois de a thread 2 já ter completado sua própria
        gravação. Sem o fix, a thread 1 grava por cima usando a leitura desatualizada e
        o campo da thread 2 desaparece. Com o fix (leitura dentro do BEGIN IMMEDIATE da
        escrita), a thread 2 fica bloqueada esperando a thread 1 liberar o lock — quando
        ela finalmente lê, já vê o campo da thread 1 e ambos sobrevivem.
        """
        real_merge_data = qualification_state.merge_data
        thread1_ident: dict[str, int] = {}
        paused = threading.Event()
        resume = threading.Event()
        errors: list[Exception] = []

        def paused_merge_data(existing, patch_dict):
            if threading.get_ident() == thread1_ident.get("id") and not paused.is_set():
                paused.set()
                resume.wait(timeout=5)
            return real_merge_data(existing, patch_dict)

        def _run_thread1():
            thread1_ident["id"] = threading.get_ident()
            try:
                upsert_qualification_state(
                    lead_id=self.lead_id, user_id=99, patch={"data_json": {"campo_a": "valor_a"}}
                )
            except Exception as exc:  # pragma: no cover - reportado via assertEqual(errors, [])
                errors.append(exc)

        def _run_thread2():
            try:
                upsert_qualification_state(
                    lead_id=self.lead_id, user_id=99, patch={"data_json": {"campo_b": "valor_b"}}
                )
            except Exception as exc:  # pragma: no cover - reportado via assertEqual(errors, [])
                errors.append(exc)

        with patch("services.qualification_state.get_connection", side_effect=self._get_connection), \
                patch("services.qualification_state.merge_data", side_effect=paused_merge_data):
            t1 = threading.Thread(target=_run_thread1)
            t1.start()
            self.assertTrue(paused.wait(timeout=5), "thread 1 não pausou a tempo")

            t2 = threading.Thread(target=_run_thread2)
            t2.start()
            # dá tempo da thread 2 pelo menos tentar (ler ou bloquear no lock) antes de liberar a 1ª
            time.sleep(0.3)

            resume.set()
            t1.join(timeout=10)
            t2.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        conn = self._get_connection()
        row = conn.execute(
            "SELECT data_json FROM lead_qualification_state WHERE lead_id = ?", (self.lead_id,)
        ).fetchone()
        conn.close()

        data = json.loads(row["data_json"])
        self.assertEqual(data.get("campo_a"), "valor_a")
        self.assertEqual(data.get("campo_b"), "valor_b")

    def test_sequential_upserts_merge_without_overwriting(self):
        with patch("services.qualification_state.get_connection", side_effect=self._get_connection):
            upsert_qualification_state(
                lead_id=self.lead_id, user_id=99, patch={"data_json": {"campo_a": "valor_a"}}
            )
            result = upsert_qualification_state(
                lead_id=self.lead_id, user_id=99, patch={"data_json": {"campo_b": "valor_b"}}
            )

        self.assertEqual(result["data_json"].get("campo_a"), "valor_a")
        self.assertEqual(result["data_json"].get("campo_b"), "valor_b")


if __name__ == "__main__":
    unittest.main()
