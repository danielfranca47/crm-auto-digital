"""
Testes de crm_client — chamadas ao backend-crm via JWT do utilizador.
Usa unittest.mock para isolar de rede real.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.crm_client import create_lead, log_outbound

SESSION = {"access_token": "test-jwt-token"}


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    import requests as _req
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = _req.HTTPError(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestCreateLead(unittest.TestCase):

    @patch("app.crm_client.requests.request")
    def test_create_lead_returns_id(self, mock_req):
        mock_req.return_value = _mock_response({"id": 42, "companyName": "ACME"})
        result = create_lead(SESSION, name="ACME", phone="351912345678")
        self.assertEqual(result["id"], 42)

    @patch("app.crm_client.requests.request")
    def test_create_lead_sends_companyname_and_phone(self, mock_req):
        mock_req.return_value = _mock_response({"id": 1})
        create_lead(SESSION, name="Dentista Silva", phone="351911111111")
        kwargs = mock_req.call_args[1]
        payload = kwargs["json"]
        self.assertEqual(payload["companyName"], "Dentista Silva")
        self.assertEqual(payload["phone"], "351911111111")

    @patch("app.crm_client.requests.request")
    def test_create_lead_includes_website_in_observations(self, mock_req):
        mock_req.return_value = _mock_response({"id": 2})
        create_lead(SESSION, name="X", phone="351912345678", website="https://x.pt")
        kwargs = mock_req.call_args[1]
        self.assertIn("https://x.pt", kwargs["json"].get("observations", ""))

    @patch("app.crm_client.requests.request")
    def test_create_lead_sends_auth_header(self, mock_req):
        mock_req.return_value = _mock_response({"id": 3})
        create_lead(SESSION, name="Y", phone="351912345679")
        kwargs = mock_req.call_args[1]
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-jwt-token")

    @patch("app.crm_client.requests.request")
    def test_create_lead_existing_phone_returns_existing(self, mock_req):
        """Quando phone já existe, backend devolve status='exists' — não deve lançar erro."""
        mock_req.return_value = _mock_response(
            {"id": 7, "lead_id": 7, "status": "exists", "companyName": "Já Existe"}
        )
        result = create_lead(SESSION, name="Já Existe", phone="351912345678")
        self.assertEqual(result["status"], "exists")
        self.assertEqual(result["id"], 7)

    @patch("app.crm_client.requests.request")
    def test_create_lead_raises_on_http_error(self, mock_req):
        import requests as req_lib
        mock_req.return_value = _mock_response({}, status_code=500)
        with self.assertRaises(req_lib.HTTPError):
            create_lead(SESSION, name="Z", phone="351912345670")

    @patch("app.crm_client.requests.request")
    def test_create_lead_uses_post_method(self, mock_req):
        mock_req.return_value = _mock_response({"id": 10})
        create_lead(SESSION, name="A", phone="351912345671")
        method = mock_req.call_args[0][0]
        self.assertEqual(method, "POST")


class TestLogOutbound(unittest.TestCase):

    @patch("app.crm_client.requests.request")
    def test_log_outbound_sends_origin_and_context(self, mock_req):
        mock_req.return_value = _mock_response({"id": 10})
        log_outbound(SESSION, lead_id=10, message="Olá, tudo bem?")
        kwargs = mock_req.call_args[1]
        self.assertEqual(kwargs["json"]["origin"], "outbound")
        self.assertEqual(kwargs["json"]["prospection_context"], "Olá, tudo bem?")

    @patch("app.crm_client.requests.request")
    def test_log_outbound_uses_correct_lead_id_in_url(self, mock_req):
        mock_req.return_value = _mock_response({"id": 99})
        log_outbound(SESSION, lead_id=99, message="msg")
        url = mock_req.call_args[0][1]
        self.assertIn("/api/leads/99", url)

    @patch("app.crm_client.requests.request")
    def test_log_outbound_sends_auth_header(self, mock_req):
        mock_req.return_value = _mock_response({"id": 5})
        log_outbound(SESSION, lead_id=5, message="msg")
        kwargs = mock_req.call_args[1]
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-jwt-token")

    @patch("app.crm_client.requests.request")
    def test_log_outbound_raises_on_http_error(self, mock_req):
        import requests as req_lib
        mock_req.return_value = _mock_response({}, status_code=404)
        with self.assertRaises(req_lib.HTTPError):
            log_outbound(SESSION, lead_id=999, message="msg")

    @patch("app.crm_client.requests.request")
    def test_log_outbound_uses_patch_method(self, mock_req):
        mock_req.return_value = _mock_response({"id": 5})
        log_outbound(SESSION, lead_id=5, message="msg")
        method = mock_req.call_args[0][0]
        self.assertEqual(method, "PATCH")


if __name__ == "__main__":
    unittest.main()
