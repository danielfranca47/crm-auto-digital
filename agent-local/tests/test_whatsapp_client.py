"""
Testes de whatsapp_client — wrapper sobre WhatsAppRunner.

Como WhatsAppRunner é importado de forma lazy dentro de _get_runner(),
injectamos o mock directamente em wac._runner para isolar de Selenium/Chrome.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.whatsapp_client as wac


def _make_runner(status: str = "sent", notes: str = "ok") -> MagicMock:
    runner = MagicMock()
    runner.send_whatsapp.return_value = {"status": status, "notes": notes}
    return runner


class TestSendMessage(unittest.TestCase):

    def setUp(self):
        wac._runner = None  # garantir singleton limpo antes de cada teste

    def tearDown(self):
        wac._runner = None  # cleanup após cada teste

    def test_send_message_success_returns_sent(self):
        wac._runner = _make_runner("sent")
        result = wac.send_message("351912345678", "Olá!")
        self.assertEqual(result["status"], "sent")

    def test_send_message_failed_returns_failed(self):
        wac._runner = _make_runner("failed", "invalid_number")
        result = wac.send_message("00000", "Olá!")
        self.assertEqual(result["status"], "failed")
        self.assertIn("inválido", result["reason"].lower())

    def test_send_message_not_logged_friendly_message(self):
        wac._runner = _make_runner("failed", "not_logged")
        result = wac.send_message("351912345678", "msg")
        self.assertEqual(result["status"], "failed")
        self.assertIn("QR", result["reason"])

    def test_send_message_open_timeout_friendly_message(self):
        wac._runner = _make_runner("failed", "open_timeout")
        result = wac.send_message("351912345678", "msg")
        self.assertEqual(result["status"], "failed")
        self.assertIn("Tempo esgotado", result["reason"])

    def test_singleton_reused_between_calls(self):
        """O mesmo runner é usado em chamadas consecutivas sem recriar o Chrome."""
        runner = _make_runner("sent")
        wac._runner = runner
        wac.send_message("351912345678", "msg1")
        wac.send_message("351912345678", "msg2")
        # send_whatsapp foi chamado duas vezes mas o runner é o mesmo objecto
        self.assertEqual(runner.send_whatsapp.call_count, 2)
        self.assertIs(wac._runner, runner)

    def test_runner_not_closed_after_send(self):
        """Chrome fica aberto após envio — runner.close() NÃO é chamado."""
        runner = _make_runner("sent")
        wac._runner = runner
        wac.send_message("351912345678", "msg")
        runner.close.assert_not_called()

    def test_runner_reset_on_exception(self):
        """Se o runner levantar excepção, o singleton é descartado para recriação limpa."""
        runner = MagicMock()
        runner.send_whatsapp.side_effect = RuntimeError("crash")
        wac._runner = runner
        result = wac.send_message("351912345678", "msg")
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(wac._runner)  # singleton descartado

    def test_progress_callback_called(self):
        wac._runner = _make_runner("sent")
        calls = []
        wac.send_message("351912345678", "msg", on_progress=calls.append)
        self.assertTrue(len(calls) > 0, "callback deve ter sido chamado pelo menos uma vez")

    def test_close_runner_noop_when_none(self):
        """close_runner() sem runner activo não deve lançar excepção."""
        wac._runner = None
        wac.close_runner()  # não deve explodir

    def test_close_runner_calls_close_and_clears_singleton(self):
        runner = _make_runner("sent")
        wac._runner = runner  # simular runner activo
        wac.close_runner()
        runner.close.assert_called_once()
        self.assertIsNone(wac._runner)


class TestSessionTemplates(unittest.TestCase):
    """Testes dos helpers de templates em session.py."""

    def setUp(self):
        self._session: dict = {"access_token": "x", "subscription_status": "active"}

    def _mod(self):
        from app import session as s
        return s

    def test_get_templates_empty_by_default(self):
        s = self._mod()
        self.assertEqual(s.get_templates(self._session), [])

    @patch("app.session.save_session")
    def test_save_template_adds_entry(self, _mock_save):
        s = self._mod()
        s.save_template(self._session, "Introdução", "Olá, tudo bem?")
        templates = s.get_templates(self._session)
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["name"], "Introdução")
        self.assertEqual(templates[0]["text"], "Olá, tudo bem?")

    @patch("app.session.save_session")
    def test_save_template_updates_existing(self, _mock_save):
        s = self._mod()
        s.save_template(self._session, "Intro", "v1")
        s.save_template(self._session, "Intro", "v2")
        templates = s.get_templates(self._session)
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["text"], "v2")

    @patch("app.session.save_session")
    def test_delete_template_removes_by_name(self, _mock_save):
        s = self._mod()
        s.save_template(self._session, "A", "texto A")
        s.save_template(self._session, "B", "texto B")
        s.delete_template(self._session, "A")
        names = [t["name"] for t in s.get_templates(self._session)]
        self.assertNotIn("A", names)
        self.assertIn("B", names)

    @patch("app.session.save_session")
    def test_multiple_templates_coexist(self, _mock_save):
        s = self._mod()
        s.save_template(self._session, "T1", "texto 1")
        s.save_template(self._session, "T2", "texto 2")
        self.assertEqual(len(s.get_templates(self._session)), 2)


if __name__ == "__main__":
    unittest.main()
