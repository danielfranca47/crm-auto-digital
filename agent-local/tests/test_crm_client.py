"""
Testes de crm_client — chamadas ao backend-crm via JWT do utilizador.
Usa unittest.mock para isolar de rede real.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Garantir que o root do agent-local está no path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.crm_client import create_lead, log_outbound


SESSION = {"access_token": "test-jwt-token"}


class TestCreateLead(unittest.TestCase):

    def _mock_response(self, json_data: dict, status_code: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.ok = status_code < 400
        resp.json.return_value = json_data
        resp.raise_for_status = MagicMock(
            side_effect=None if status_code < 400 else Exception(f"HTTP {status_code}")
        )
        return resp

    @patch("app.crm_client.requests.post")
    def test_create_lead_returns_id(self, mock_post):
        mock_post.return_value = self._mock_response({"id": 42, "companyName": "ACME"})
        result = create_lead(SESSION, name="ACME", phone="351912345678")
        self.assertEqual(result["id"], 42)

    @patch("app.crm_client.requests.post")
    def test_create_lead_sends_companyname_and_phone(self, mock_post):
        mock_post.return_value = self._mock_response({"id": 1})
        create_lead(SESSION, name="Dentista Silva", phone="351911111111")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["companyName"], "Dentista Silva")
        self.assertEqual(payload["phone"], "351911111111")

    @patch("app.crm_client.requests.post")
    def test_create_lead_includes_website_in_observations(self, mock_post):
        mock_post.return_value = self._mock_response({"id": 2})
        create_lead(SESSION, name="X", phone="351912345678", website="https://x.pt")
        _, kwargs = mock_post.call_args
        self.assertIn("https://x.pt", kwargs["json"].get("observations", ""))

    @patch("app.crm_client.requests.post")
    def test_create_lead_sends_auth_header(self, mock_post):
        mock_post.return_value = self._mock_response({"id": 3})
        create_lead(SESSION, name="Y", phone="351912345679")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-jwt-token")

    @patch("app.crm_client.requests.post")
    def test_create_lead_existing_phone_returns_existing(self, mock_post):
        """Quando phone já existe, backend devolve status='exists' — não deve lançar erro."""
        mock_post.return_value = self._mock_response(
            {"id": 7, "lead_id": 7, "status": "exists", "companyName": "Já Existe"}
        )
        result = create_lead(SESSION, name="Já Existe", phone="351912345678")
        self.assertEqual(result["status"], "exists")
        self.assertEqual(result["id"], 7)

    @patch("app.crm_client.requests.post")
    def test_create_lead_raises_on_http_error(self, mock_post):
        resp = self._mock_response({}, status_code=500)
        import requests as req_lib
        resp.raise_for_status.side_effect = req_lib.HTTPError("500")
        mock_post.return_value = resp
        with self.assertRaises(req_lib.HTTPError):
            create_lead(SESSION, name="Z", phone="351912345670")


class TestLogOutbound(unittest.TestCase):

    def _mock_patch(self, json_data: dict, status_code: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.ok = status_code < 400
        resp.json.return_value = json_data
        resp.raise_for_status = MagicMock(side_effect=None if status_code < 400 else Exception())
        return resp

    @patch("app.crm_client.requests.patch")
    def test_log_outbound_sends_origin_and_context(self, mock_patch):
        mock_patch.return_value = self._mock_patch({"id": 10})
        log_outbound(SESSION, lead_id=10, message="Olá, tudo bem?")
        _, kwargs = mock_patch.call_args
        self.assertEqual(kwargs["json"]["origin"], "outbound")
        self.assertEqual(kwargs["json"]["prospection_context"], "Olá, tudo bem?")

    @patch("app.crm_client.requests.patch")
    def test_log_outbound_uses_correct_lead_id_in_url(self, mock_patch):
        mock_patch.return_value = self._mock_patch({"id": 99})
        log_outbound(SESSION, lead_id=99, message="msg")
        url = mock_patch.call_args[0][0]
        self.assertIn("/api/leads/99", url)

    @patch("app.crm_client.requests.patch")
    def test_log_outbound_sends_auth_header(self, mock_patch):
        mock_patch.return_value = self._mock_patch({"id": 5})
        log_outbound(SESSION, lead_id=5, message="msg")
        _, kwargs = mock_patch.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-jwt-token")

    @patch("app.crm_client.requests.patch")
    def test_log_outbound_raises_on_http_error(self, mock_patch):
        import requests as req_lib
        resp = self._mock_patch({}, status_code=404)
        resp.raise_for_status.side_effect = req_lib.HTTPError("404")
        mock_patch.return_value = resp
        with self.assertRaises(req_lib.HTTPError):
            log_outbound(SESSION, lead_id=999, message="msg")


if __name__ == "__main__":
    unittest.main()
