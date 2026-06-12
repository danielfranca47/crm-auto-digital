"""
Testes para o histórico de prospecções — session helpers e crm_client.
"""
import sys
import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestProspectLogFile(unittest.TestCase):
    """Testa append_prospect_log e get_prospect_log com ficheiro real temporário."""

    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp())
        self._log_file = self._tmp_dir / "prospect_log.jsonl"

        import app.session as s
        self._orig_log = s._PROSPECT_LOG
        self._orig_dir = s._SESSION_DIR
        s._PROSPECT_LOG = self._log_file
        s._SESSION_DIR = self._tmp_dir

    def tearDown(self):
        import app.session as s
        s._PROSPECT_LOG = self._orig_log
        s._SESSION_DIR = self._orig_dir

    def _s(self):
        import app.session as s
        return s

    def test_append_creates_file(self):
        s = self._s()
        self.assertFalse(self._log_file.exists())
        s.append_prospect_log({"ts": "2026-06-05T10:00:00", "name": "A", "phone": "111", "status": "sent", "reason": ""})
        self.assertTrue(self._log_file.exists())

    def test_append_writes_valid_jsonl(self):
        s = self._s()
        s.append_prospect_log({"ts": "2026-06-05T10:00:00", "name": "A", "phone": "111", "status": "sent", "reason": ""})
        lines = self._log_file.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["name"], "A")

    def test_get_returns_most_recent_first(self):
        s = self._s()
        s.append_prospect_log({"ts": "2026-06-05T09:00:00", "name": "First", "phone": "111", "status": "sent", "reason": ""})
        s.append_prospect_log({"ts": "2026-06-05T10:00:00", "name": "Second", "phone": "222", "status": "failed", "reason": "err"})
        result = s.get_prospect_log(10)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Second")  # mais recente primeiro

    def test_get_respects_limit(self):
        s = self._s()
        for i in range(10):
            s.append_prospect_log({"ts": f"2026-06-05T{i:02d}:00:00", "name": f"Lead{i}", "phone": str(i), "status": "sent", "reason": ""})
        result = s.get_prospect_log(5)
        self.assertEqual(len(result), 5)

    def test_get_returns_empty_if_no_file(self):
        s = self._s()
        self.assertFalse(self._log_file.exists())
        result = s.get_prospect_log()
        self.assertEqual(result, [])

    def test_append_noop_on_dir_error(self):
        """Erros ao escrever (e.g. permissões) não devem lançar excepção."""
        import app.session as s
        s._PROSPECT_LOG = Path("/invalid_path/prospect_log.jsonl")
        try:
            s.append_prospect_log({"ts": "x", "name": "Y", "phone": "0", "status": "sent", "reason": ""})
        except Exception as exc:
            self.fail(f"append_prospect_log raised {exc}")


class TestGetProspectHistory(unittest.TestCase):
    """Testa crm_client.get_prospect_history com mock de requests."""

    SESSION = {"access_token": "jwt-token"}

    def _mock_get(self, json_data, status=200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.ok = status < 400
        resp.json.return_value = json_data
        resp.raise_for_status = MagicMock(side_effect=None if status < 400 else Exception(f"HTTP {status}"))
        return resp

    @patch("app.crm_client.requests.get")
    def test_returns_list(self, mock_get):
        mock_get.return_value = self._mock_get([
            {"id": 1, "lead_name": "Empresa A", "phone": "351911", "action": "sent", "notes": "", "created_at": "2026-06-05T10:00:00"},
        ])
        from app.crm_client import get_prospect_history
        result = get_prospect_history(self.SESSION, limit=50)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["lead_name"], "Empresa A")

    @patch("app.crm_client.requests.get")
    def test_calls_correct_endpoint(self, mock_get):
        mock_get.return_value = self._mock_get([])
        from app.crm_client import get_prospect_history
        get_prospect_history(self.SESSION, limit=25)
        url = mock_get.call_args[0][0]
        self.assertIn("/api/prospeccao/history", url)
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["limit"], 25)

    @patch("app.crm_client.requests.get")
    def test_raises_on_http_error(self, mock_get):
        import requests as req_lib
        resp = self._mock_get({}, status=401)
        resp.raise_for_status.side_effect = req_lib.HTTPError("401")
        mock_get.return_value = resp
        from app.crm_client import get_prospect_history
        with self.assertRaises(req_lib.HTTPError):
            get_prospect_history(self.SESSION)

    @patch("app.crm_client.requests.get")
    def test_non_list_response_returns_empty(self, mock_get):
        mock_get.return_value = self._mock_get({"error": "unexpected"})
        from app.crm_client import get_prospect_history
        result = get_prospect_history(self.SESSION)
        self.assertEqual(result, [])


class TestGenerateCopy(unittest.TestCase):
    """Testa crm_client.generate_copy com mock de requests."""

    SESSION = {"access_token": "jwt-token"}

    @patch("app.crm_client.requests.post")
    def test_returns_message_string(self, mock_post):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"message": "Olá, somos a Digital Pro!"}
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        from app.crm_client import generate_copy
        result = generate_copy(self.SESSION, company_name="Empresa X", sector="Dentistas")
        self.assertEqual(result, "Olá, somos a Digital Pro!")

    @patch("app.crm_client.requests.post")
    def test_sends_correct_payload(self, mock_post):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"message": "msg"}
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        from app.crm_client import generate_copy
        generate_copy(self.SESSION, company_name="X", sector="Tech", channel="email", tone="formal")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["company_name"], "X")
        self.assertEqual(payload["sector"], "Tech")
        self.assertEqual(payload["channel"], "email")
        self.assertEqual(payload["tone"], "formal")


if __name__ == "__main__":
    unittest.main()
