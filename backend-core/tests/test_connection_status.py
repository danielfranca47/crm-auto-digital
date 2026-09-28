import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.api import whatsapp_instances
from app.db import Base
from app.services import whatsapp_connections


class ConnectionStatusNormalizationTests(unittest.TestCase):
    def test_connected_maps_to_active(self):
        self.assertEqual(
            whatsapp_connections.normalize_connection_status_for_crm("connected"),
            "active",
        )

    def test_disconnected_maps_to_inactive(self):
        self.assertEqual(
            whatsapp_connections.normalize_connection_status_for_crm("disconnected"),
            "inactive",
        )


class ConnectionStatusChangeEmailTests(unittest.TestCase):
    """Transições ativo↔inativo e os emails de desconexão/reconexão, venham elas
    do webhook, do polling de status (tela do QR) ou do job de 6h."""

    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        user = models.User(email="dono@example.com", password_hash="x", name="Dono")
        self.db.add(user)
        self.db.commit()
        self.connection = models.WhatsappConnection(
            user_id=user.id,
            instance_id="crm-1-teste",
            instance_token_encrypted="x",
            status="connected",
        )
        self.db.add(self.connection)
        self.db.commit()

        patcher = patch.object(whatsapp_connections, "send_email")
        self.send_email = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.db.close)

    def _subjects(self):
        return [call.kwargs["subject"] for call in self.send_email.call_args_list]

    def _apply(self, status):
        whatsapp_connections.apply_connection_status_change(self.db, self.connection, status)

    def test_queda_e_retorno_mandam_os_dois_emails(self):
        self._apply("disconnected")
        self._apply("connecting")
        self._apply("connected")

        subjects = self._subjects()
        self.assertEqual(len(subjects), 2)
        self.assertIn("desconectou", subjects[0])
        self.assertIn("reconectou", subjects[1])
        self.assertIsNone(self.connection.disconnect_alert_sent_at)

    def test_connected_repetido_nao_duplica_email_de_reconexao(self):
        # Polling vê "connected" primeiro, webhook repete logo depois.
        self._apply("disconnected")
        self._apply("connected")
        self._apply("connected")

        self.assertEqual(len(self._subjects()), 2)

    def test_oscilacao_dentro_do_cooldown_nao_reenvia(self):
        self._apply("disconnected")
        self._apply("connected")
        self._apply("disconnected")
        self._apply("connected")

        # Segunda queda cai no cooldown de 30min → sem email de queda nem o de
        # reconexão pareado.
        self.assertEqual(len(self._subjects()), 2)

    def test_queda_depois_do_cooldown_volta_a_avisar(self):
        self._apply("disconnected")
        self._apply("connected")
        self.connection.last_disconnect_email_at = datetime.utcnow() - timedelta(minutes=31)
        self.db.commit()
        self._apply("disconnected")

        self.assertEqual(len(self._subjects()), 3)

    def test_polling_de_status_dispara_email_de_reconexao(self):
        """Regressão (Fase 4): GET /whatsapp-instances/status gravava o status
        direto, o webhook seguinte já não via transição e o email de reconexão
        nunca saía."""
        self._apply("disconnected")
        self.send_email.reset_mock()

        with patch.object(whatsapp_instances, "_resolve_instance_token", return_value="tok"), patch.object(
            whatsapp_instances.uazapi_admin,
            "get_status",
            new=AsyncMock(return_value={"instance": {"status": "connected"}}),
        ):
            asyncio.run(whatsapp_instances.status_instance(instance_id="crm-1-teste", db=self.db, _="svc"))

        self.assertEqual(self.connection.status, "connected")
        subjects = self._subjects()
        self.assertEqual(len(subjects), 1)
        self.assertIn("reconectou", subjects[0])

        # Webhook "connected" que chega depois não repete o email.
        self._apply("connected")
        self.assertEqual(len(self._subjects()), 1)


if __name__ == "__main__":
    unittest.main()
