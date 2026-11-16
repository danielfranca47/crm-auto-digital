import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from pydantic import ValidationError

import database
import routes.agent_fix_requests as rotas
from security_core import CurrentUser


class PedidosCorrecaoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "crm.db")
        conn = sqlite3.connect(self.db)
        database.ensure_agent_fix_requests_table(conn)
        database.ensure_agent_fix_requests_table(conn)  # idempotente
        conn.close()

        def _conn():
            c = sqlite3.connect(self.db)
            c.row_factory = sqlite3.Row
            return c

        self.p = patch.object(rotas, "_conn", _conn)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def _user(self, uid=5):
        return CurrentUser(id=uid, email=f"u{uid}@example.com", token="t")

    def _criar(self, uid=5, titulo="Grava a proposta antiga"):
        return rotas.criar_pedido(rotas.PedidoCreate(titulo=titulo, sintoma="cliente aceitou a 2.ª, gravou a 1.ª",
                                                     evidencia="T4: gravou qui 18h30", cenarios_json="{}", bancada="x"),
                                  current_user=self._user(uid))

    def test_create_and_list_only_own(self):
        a = self._criar(5)
        self._criar(6, "outro")
        self.assertEqual(a["estado"], "novo")
        self.assertEqual(a["user_email"], "u5@example.com")
        meus = rotas.listar_meus(current_user=self._user(5))
        self.assertEqual([p["id"] for p in meus], [a["id"]])

    def test_admin_list_and_update(self):
        a = self._criar(5)
        self.assertEqual(len(rotas.admin_listar(estado=None, _={})), 1)
        r = rotas.admin_atualizar(a["id"], rotas.PedidoUpdate(estado="em_curso", nota_admin="a tratar"), _={})
        self.assertEqual((r["estado"], r["nota_admin"]), ("em_curso", "a tratar"))
        self.assertEqual(len(rotas.admin_listar(estado="novo", _={})), 0)
        self.assertEqual(rotas.listar_meus(current_user=self._user(5))[0]["estado"], "em_curso")

    def test_update_missing_is_404(self):
        with self.assertRaises(HTTPException) as ctx:
            rotas.admin_atualizar(999, rotas.PedidoUpdate(estado="feito"), _={})
        self.assertEqual(ctx.exception.status_code, 404)

    def test_limit_of_open_requests(self):
        for i in range(20):
            self._criar(5, f"pedido {i}")
        with self.assertRaises(HTTPException) as ctx:
            self._criar(5, "um a mais")
        self.assertEqual(ctx.exception.status_code, 429)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            rotas.PedidoCreate(titulo="x", sintoma="algo")
        with self.assertRaises(ValidationError):
            rotas.PedidoUpdate(estado="aprovado")


if __name__ == "__main__":
    unittest.main()
