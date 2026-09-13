import io
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException, UploadFile

import routes.uploads as uploads_module
import routes.assistente_ia as assistente_ia_module
from security_core import CurrentUser


def _make_upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(io.BytesIO(content), filename=filename)


class _ChdirTestCase(unittest.IsolatedAsyncioTestCase):
    """Base que roda cada teste dentro de um cwd temporário, já que
    `routes/uploads.py` e `routes/assistente_ia.py` resolvem
    `data/uploads/ai/...` como caminho relativo ao processo (mesmo
    comportamento de produção — não precisa mockar `Path`/`BASE`)."""

    def setUp(self):
        self._original_cwd = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class UploadsRouteAuthTest(_ChdirTestCase):
    """Regressão do achado de segurança: POST /api/uploads aceitava qualquer
    chamada anônima, sem limite de tamanho, gravando tudo numa pasta plana
    compartilhada entre tenants (`backend-crm/routes/uploads.py:46`).

    Cobre: extensão inválida (comportamento já existente, sem teste até
    então), corte por limite de tamanho, e isolamento dos arquivos por
    `user_id`.
    """

    def setUp(self):
        super().setUp()
        self.owner = CurrentUser(id=1, email="dono@teste.com")
        self.intruder = CurrentUser(id=2, email="intruso@teste.com")

    async def test_upload_rejects_invalid_extension(self):
        upload = _make_upload("leads.txt", b"a,b\n1,2\n")
        with self.assertRaises(HTTPException) as ctx:
            await uploads_module.upload_planilha(upload, self.owner)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_upload_rejects_file_above_limit(self):
        with patch.object(uploads_module, "MAX_UPLOAD_BYTES", 10):
            upload = _make_upload("leads.csv", b"nome,telefone\n" + b"9" * 50)
            with self.assertRaises(HTTPException) as ctx:
                await uploads_module.upload_planilha(upload, self.owner)
            self.assertEqual(ctx.exception.status_code, 413)

        # nenhum arquivo (nem parcial) fica em disco depois do corte
        user_dir = uploads_module.BASE / str(self.owner.id)
        leftover = list(user_dir.glob("*")) if user_dir.exists() else []
        self.assertEqual(leftover, [])

    async def test_upload_isolates_by_user(self):
        content = b"nome,telefone\nJoao,11999999999\n"
        upload = _make_upload("leads.csv", content)
        result = await uploads_module.upload_planilha(upload, self.owner)
        upload_id = result["upload_id"]

        owner_file = uploads_module.BASE / str(self.owner.id) / f"{upload_id}.csv"
        self.assertTrue(owner_file.exists())

        intruder_file = uploads_module.BASE / str(self.intruder.id) / f"{upload_id}.csv"
        self.assertFalse(intruder_file.exists())


class AssistenteIAUploadIsolationTest(_ChdirTestCase):
    """Usuário B não consegue processar/pré-visualizar um upload_id que
    pertence ao usuário A, mesmo autenticado — o arquivo fica dentro da
    pasta isolada por `user_id` (`routes/assistente_ia.py` `/processar` e
    `/preview`)."""

    def setUp(self):
        super().setUp()
        self.owner = CurrentUser(id=10, email="dono@teste.com")
        self.intruder = CurrentUser(id=20, email="intruso@teste.com")

    async def _upload_as_owner(self) -> str:
        content = b"nome,telefone\nJoao,11999999999\n"
        upload = _make_upload("leads.csv", content)
        result = await uploads_module.upload_planilha(upload, self.owner)
        return result["upload_id"]

    async def test_preview_denies_non_owner(self):
        upload_id = await self._upload_as_owner()

        with self.assertRaises(HTTPException) as ctx:
            assistente_ia_module.preview({"upload_id": upload_id}, self.intruder)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_preview_allows_owner(self):
        upload_id = await self._upload_as_owner()

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE leads (id INTEGER PRIMARY KEY, user_id INTEGER, phone TEXT, email TEXT, companyName TEXT)"
        )
        conn.commit()

        with patch("routes.assistente_ia.get_connection", return_value=conn):
            result = assistente_ia_module.preview({"upload_id": upload_id}, self.owner)

        self.assertEqual(result["stats"]["total"], 1)
        self.assertEqual(len(result["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
