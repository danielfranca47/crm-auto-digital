import asyncio
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.api import whatsapp_instances
from app.db import Base
from app.services import uazapi_admin, uazapi_capacity

NOW = datetime(2026, 9, 29, 12, 0, 0)
OLD = "2026-09-20 10:00:00.000Z"
LIMIT_BODY = '{"error":"Maximum number of instances reached","info":"Cannot create more than 6 instances (current: 6, limit: 3)"}'


def _item(name, status="disconnected", created=OLD, last_disconnect=None):
    return {"name": name, "token": f"tok-{name}", "status": status, "created": created, "lastDisconnect": last_disconnect}


class _DbTestCase(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(self.db.close)
        user = models.User(email="dono@example.com", password_hash="x")
        self.db.add(user)
        self.db.commit()
        self.user_id = user.id

    def _add_connection(self, instance_id, status="disconnected", role="agent"):
        connection = models.WhatsappConnection(
            user_id=self.user_id,
            instance_id=instance_id,
            instance_token_encrypted="x",
            status=status,
            role=role,
        )
        self.db.add(connection)
        self.db.commit()
        return connection

    def _exists(self, instance_id):
        return (
            self.db.query(models.WhatsappConnection)
            .filter(models.WhatsappConnection.instance_id == instance_id)
            .first()
            is not None
        )


class ClassifyInstancesTests(_DbTestCase):
    def test_separa_orfas_recentes_mortas_e_ignora_vivas(self):
        self._add_connection("crm-1-morta", status="disconnected")
        self._add_connection("crm-1-viva", status="connected")
        self._add_connection("crm-1-banco-acha-viva", status="connected")
        listing = [
            _item("orfa-antiga"),
            _item("orfa-recente", created=(NOW - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S.000Z")),
            _item("orfa-a-ler-qr", status="connecting"),
            _item("crm-1-morta", last_disconnect="2026-09-25 08:00:00.000Z"),
            _item("crm-1-viva", status="connected"),
            _item("crm-1-banco-acha-viva"),
            {"name": "sem-token", "status": "disconnected"},
        ]

        orphans, young, dead = uazapi_capacity.classify_instances(self.db, listing, now=NOW)

        self.assertEqual([c.name for c in orphans], ["orfa-antiga"])
        self.assertEqual([c.name for c in young], ["orfa-recente"])
        self.assertEqual([c.name for c in dead], ["crm-1-morta"])

    def test_ordena_orfas_por_criacao_e_mortas_pela_queda_mais_antiga(self):
        self._add_connection("morta-recente")
        self._add_connection("morta-antiga")
        listing = [
            _item("orfa-2", created="2026-09-10 00:00:00.000Z"),
            _item("orfa-1", created="2026-09-01 00:00:00.000Z"),
            _item("morta-recente", last_disconnect="2026-09-28 00:00:00.000Z"),
            _item("morta-antiga", last_disconnect="2026-09-02 00:00:00.000Z"),
        ]

        orphans, _, dead = uazapi_capacity.classify_instances(self.db, listing, now=NOW)

        self.assertEqual([c.name for c in orphans], ["orfa-1", "orfa-2"])
        self.assertEqual([c.name for c in dead], ["morta-antiga", "morta-recente"])


class ReclaimAndCleanupTests(_DbTestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {"UAZAPI_INSTANCE_CLEANUP_ENABLED": "true"})
        env.start()
        self.addCleanup(env.stop)

    def _patch_uazapi(self, listing, delete_side_effect=None):
        list_mock = AsyncMock(return_value=listing)
        delete_mock = AsyncMock(side_effect=delete_side_effect)
        p1 = patch.object(uazapi_admin, "list_instances", new=list_mock)
        p2 = patch.object(uazapi_admin, "delete_instance", new=delete_mock)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return delete_mock

    def test_reclaim_prefere_orfa_a_instancia_de_cliente(self):
        self._add_connection("crm-1-morta")
        delete_mock = self._patch_uazapi([_item("crm-1-morta"), _item("orfa")])

        deleted = asyncio.run(uazapi_capacity.reclaim_instance_slots(self.db, needed=1))

        self.assertEqual(deleted, ["orfa"])
        self.assertEqual(delete_mock.await_count, 1)
        self.assertEqual(delete_mock.await_args.kwargs["instance_token"], "tok-orfa")
        self.assertTrue(self._exists("crm-1-morta"))

    def test_reclaim_apaga_morta_de_cliente_e_a_linha_local_quando_nao_ha_orfas(self):
        self._add_connection("crm-1-morta")
        self._patch_uazapi([_item("crm-1-morta")])

        deleted = asyncio.run(uazapi_capacity.reclaim_instance_slots(self.db, needed=1))

        self.assertEqual(deleted, ["crm-1-morta"])
        self.assertFalse(self._exists("crm-1-morta"))

    def test_reclaim_nunca_apaga_vivas_nem_a_conectar(self):
        self._add_connection("crm-1-viva", status="connected")
        delete_mock = self._patch_uazapi([_item("crm-1-viva", status="connected"), _item("orfa-qr", status="connecting")])

        deleted = asyncio.run(uazapi_capacity.reclaim_instance_slots(self.db, needed=1))

        self.assertEqual(deleted, [])
        delete_mock.assert_not_awaited()

    def test_reclaim_segue_para_a_proxima_se_um_delete_falhar(self):
        self._patch_uazapi(
            [_item("orfa-1", created="2026-09-01 00:00:00.000Z"), _item("orfa-2")],
            delete_side_effect=[uazapi_admin.UazapiAdminError("x", status_code=500), None],
        )

        deleted = asyncio.run(uazapi_capacity.reclaim_instance_slots(self.db, needed=1))

        self.assertEqual(deleted, ["orfa-2"])

    def test_cleanup_diario_so_apaga_orfas(self):
        self._add_connection("crm-1-morta")
        delete_mock = self._patch_uazapi(
            [
                _item("orfa"),
                _item("crm-1-morta"),
                _item("orfa-recente", created=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.000Z")),
            ]
        )

        summary = asyncio.run(uazapi_capacity.cleanup_orphans(self.db))

        self.assertEqual(summary["deleted_orphans"], ["orfa"])
        self.assertEqual(summary["young_orphans_skipped"], 1)
        self.assertEqual(summary["dead_with_record"], 1)
        self.assertEqual(summary["total_after"], 2)
        self.assertEqual(delete_mock.await_count, 1)
        self.assertTrue(self._exists("crm-1-morta"))


class CleanupSafetyGuardTests(_DbTestCase):
    """Fora do Railway (backend-core local a apontar para a UazAPI de produção
    com um banco local), nada pode ser apagado."""

    def test_local_sem_railway_nao_apaga_nada(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RAILWAY_ENVIRONMENT", None)
            os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
            os.environ.pop("UAZAPI_INSTANCE_CLEANUP_ENABLED", None)
            delete_mock = AsyncMock()
            with patch.object(
                uazapi_admin, "list_instances", new=AsyncMock(return_value=[_item("instancia-de-producao")])
            ), patch.object(uazapi_admin, "delete_instance", new=delete_mock):
                deleted = asyncio.run(uazapi_capacity.reclaim_instance_slots(self.db, needed=1))
                summary = asyncio.run(uazapi_capacity.cleanup_orphans(self.db))

        self.assertEqual(deleted, [])
        self.assertEqual(summary["skipped"], "cleanup_disabled")
        delete_mock.assert_not_awaited()

    def test_railway_liga_por_omissao_e_flag_explicita_desliga(self):
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT": "production"}, clear=False):
            os.environ.pop("UAZAPI_INSTANCE_CLEANUP_ENABLED", None)
            self.assertTrue(uazapi_capacity.cleanup_enabled())
            os.environ["UAZAPI_INSTANCE_CLEANUP_ENABLED"] = "false"
            self.assertFalse(uazapi_capacity.cleanup_enabled())


class InitInstanceLimitTests(_DbTestCase):
    def _payload(self):
        return whatsapp_instances.InstanceInitPayload(user_id=self.user_id, instance_id="crm-1-nova")

    def _run_init(self):
        return asyncio.run(whatsapp_instances.init_instance(payload=self._payload(), db=self.db, _="svc"))

    def test_teto_atingido_liberta_vaga_e_repete_o_init(self):
        limit_error = uazapi_admin.UazapiAdminError("limit", status_code=429, body=LIMIT_BODY)
        init_mock = AsyncMock(side_effect=[limit_error, {"name": "crm-1-nova", "token": "tok-nova", "status": "disconnected"}])
        reclaim_mock = AsyncMock(return_value=["orfa"])
        with patch.object(uazapi_admin, "init_instance", new=init_mock), patch.object(
            whatsapp_instances.uazapi_capacity, "reclaim_instance_slots", new=reclaim_mock
        ):
            self._run_init()

        self.assertEqual(init_mock.await_count, 2)
        reclaim_mock.assert_awaited_once()
        self.assertTrue(self._exists("crm-1-nova"))

    def test_teto_atingido_sem_nada_para_libertar_devolve_503_claro(self):
        limit_error = uazapi_admin.UazapiAdminError("limit", status_code=429, body=LIMIT_BODY)
        with patch.object(uazapi_admin, "init_instance", new=AsyncMock(side_effect=limit_error)), patch.object(
            whatsapp_instances.uazapi_capacity, "reclaim_instance_slots", new=AsyncMock(return_value=[])
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._run_init()

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Limite de conexões", ctx.exception.detail)

    def test_429_de_rate_limit_comum_nao_dispara_limpeza(self):
        rate_error = uazapi_admin.UazapiAdminError("rate", status_code=429, body='{"error":"Too many requests"}')
        reclaim_mock = AsyncMock(return_value=["orfa"])
        with patch.object(uazapi_admin, "init_instance", new=AsyncMock(side_effect=rate_error)), patch.object(
            whatsapp_instances.uazapi_capacity, "reclaim_instance_slots", new=reclaim_mock
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._run_init()

        self.assertEqual(ctx.exception.status_code, 429)
        reclaim_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
