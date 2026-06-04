"""
Testes para a lógica de prospecção em lote (BulkProspectDialog._run_bulk equivalente).
Testa o loop de envio, delay, cancel flag, e integração CRM para assinantes.
"""
import sys
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.whatsapp_client as wac


def _make_runner(status: str = "sent") -> MagicMock:
    runner = MagicMock()
    runner.send_whatsapp.return_value = {"status": status, "notes": "ok"}
    return runner


def _run_bulk(leads, message, delay, save_crm, session, cancel_flag=None):
    """Replica a lógica de _run_bulk sem depender de CustomTkinter."""
    from app.session import append_prospect_log
    import datetime

    if cancel_flag is None:
        cancel_flag = threading.Event()

    sent = failed = crm_saved = 0
    total = len(leads)
    results = []

    for i, lead in enumerate(leads):
        if cancel_flag.is_set():
            break

        phone = (lead.get("phone") or "").replace(" ", "").replace("-", "")
        if not phone:
            failed += 1
            results.append(("failed", "no_phone"))
            continue

        result = wac.send_message(phone, message)
        status = result["status"]
        results.append((status, result.get("reason", "")))

        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "name": lead.get("name", "Lead"),
            "phone": phone,
            "status": status,
            "reason": result.get("reason", ""),
        }
        append_prospect_log(entry)

        if status == "sent":
            sent += 1
            if save_crm:
                try:
                    from app.crm_client import create_lead, log_outbound
                    resp = create_lead(session, name=lead.get("name", "Lead"), phone=phone)
                    lead_id = resp.get("id")
                    if lead_id:
                        log_outbound(session, lead_id, message)
                        crm_saved += 1
                except Exception:
                    pass
        else:
            failed += 1

        if i < total - 1 and not cancel_flag.is_set():
            time.sleep(delay)

    return sent, failed, crm_saved, results


class TestBulkProspectLogic(unittest.TestCase):

    LEADS = [
        {"name": "Empresa A", "phone": "351911111111"},
        {"name": "Empresa B", "phone": "351922222222"},
        {"name": "Empresa C", "phone": "351933333333"},
    ]
    SESSION = {"access_token": "jwt", "subscription_status": "active"}

    def setUp(self):
        wac._runner = None

    def tearDown(self):
        wac._runner = None

    @patch("app.session.save_session")
    def test_all_sent_no_crm(self, _mock_save):
        """Sem CRM: envia todos, conta correctamente."""
        wac._runner = _make_runner("sent")
        sent, failed, crm_saved, _ = _run_bulk(
            self.LEADS, "Olá!", delay=0, save_crm=False, session=self.SESSION
        )
        self.assertEqual(sent, 3)
        self.assertEqual(failed, 0)
        self.assertEqual(crm_saved, 0)

    @patch("app.session.save_session")
    def test_failed_not_saved_to_crm(self, _mock_save):
        """Envio falhado não deve chamar create_lead nem log_outbound."""
        wac._runner = _make_runner("failed")
        with patch("app.crm_client.requests.post") as mock_post, \
             patch("app.crm_client.requests.patch") as mock_patch:
            _run_bulk(
                self.LEADS[:1], "msg", delay=0, save_crm=True, session=self.SESSION
            )
            mock_post.assert_not_called()
            mock_patch.assert_not_called()

    @patch("app.session.save_session")
    def test_cancel_flag_stops_loop(self, _mock_save):
        """cancel_flag interrompe o loop antes de processar todos os leads."""
        wac._runner = _make_runner("sent")
        flag = threading.Event()
        flag.set()  # já cancelado antes de começar
        sent, failed, crm_saved, results = _run_bulk(
            self.LEADS, "msg", delay=0, save_crm=False,
            session=self.SESSION, cancel_flag=flag
        )
        self.assertEqual(len(results), 0)

    @patch("app.session.save_session")
    def test_lead_without_phone_counted_as_failed(self, _mock_save):
        """Lead sem telefone conta como falhado sem chamar WhatsApp."""
        runner = _make_runner("sent")
        wac._runner = runner
        leads = [{"name": "Sem Tel", "phone": ""}]
        sent, failed, _, _ = _run_bulk(
            leads, "msg", delay=0, save_crm=False, session=self.SESSION
        )
        self.assertEqual(failed, 1)
        self.assertEqual(sent, 0)
        # runner existia mas send_whatsapp nunca foi chamado (phone vazio → skip)
        runner.send_whatsapp.assert_not_called()

    @patch("app.session.save_session")
    @patch("app.crm_client.requests.post")
    @patch("app.crm_client.requests.patch")
    def test_subscriber_crm_saved_on_success(self, mock_patch, mock_post, _mock_save):
        """Assinante com save_crm=True: create_lead + log_outbound chamados em sucesso."""
        wac._runner = _make_runner("sent")

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.ok = True
        post_resp.json.return_value = {"id": 42}
        post_resp.raise_for_status = MagicMock()
        mock_post.return_value = post_resp

        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.ok = True
        patch_resp.raise_for_status = MagicMock()
        mock_patch.return_value = patch_resp

        sent, failed, crm_saved, _ = _run_bulk(
            self.LEADS[:1], "Olá!", delay=0, save_crm=True, session=self.SESSION
        )
        self.assertEqual(sent, 1)
        self.assertEqual(crm_saved, 1)
        mock_post.assert_called_once()
        mock_patch.assert_called_once()

    @patch("app.session.save_session")
    def test_append_prospect_log_called_per_lead(self, _mock_save):
        """append_prospect_log deve ser chamado uma vez por lead processado."""
        wac._runner = _make_runner("sent")
        with patch("app.session.append_prospect_log") as mock_log:
            _run_bulk(
                self.LEADS[:2], "msg", delay=0, save_crm=False, session=self.SESSION
            )
            self.assertEqual(mock_log.call_count, 2)


class TestProspectLogHelpers(unittest.TestCase):
    """Testa append_prospect_log e get_prospect_log usando ficheiro temporário."""

    def setUp(self):
        import tempfile
        self._tmp_dir = tempfile.mkdtemp()

    @patch("app.session._PROSPECT_LOG")
    @patch("app.session._SESSION_DIR")
    @patch("app.session.save_session")
    def test_log_roundtrip(self, _mock_save, mock_dir, mock_log_path):
        import tempfile
        from pathlib import Path

        tmp = Path(self._tmp_dir) / "prospect_log.jsonl"
        mock_log_path.__str__ = lambda s: str(tmp)
        mock_log_path.exists.return_value = False
        mock_log_path.open = tmp.open
        mock_log_path.__truediv__ = lambda s, o: tmp
        mock_dir.mkdir = MagicMock()

        # Simpler: patch _PROSPECT_LOG directly in the module
        import app.session as s_mod
        original = s_mod._PROSPECT_LOG
        s_mod._PROSPECT_LOG = tmp
        s_mod._SESSION_DIR = Path(self._tmp_dir)

        try:
            entry = {"ts": "2026-06-05T10:00:00", "name": "A", "phone": "351911", "status": "sent", "reason": ""}
            s_mod.append_prospect_log(entry)
            result = s_mod.get_prospect_log(10)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "A")
        finally:
            s_mod._PROSPECT_LOG = original


if __name__ == "__main__":
    unittest.main()
