"""
tests/test_refresh_token.py

Checks I1 e I2 — lógica de refresh token silencioso em crm_client._request().

O que testa:
  I1a — 200 no primeiro try: sem refresh (caminho feliz)
  I1b — 401 com refresh_token: token renovado, sessão actualizada, retry com novo token
  I1c — sessão em memória actualizada com novo access_token após refresh
  I1d — sessão persistida em disco (save_session chamado) após refresh
  I1e — retry usa o novo token (não o expirado)
  I2a — 401 sem refresh_token na sessão: retorna 401 directamente (sem crash)
  I2b — 401 com refresh_token inválido (AuthError): retorna 401 original (sem crash)
  I2c — 401 + refresh bem sucedido mas retry também falha: retorna resposta do retry
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.crm_client import _request, create_lead
from app.auth import AuthError


def _resp(status_code: int, json_data: dict = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.ok = status_code < 400
    r.json.return_value = json_data or {}
    r.raise_for_status.return_value = None
    return r


SESSION_WITH_REFRESH = {
    "access_token": "expired-access-token",
    "refresh_token": "valid-refresh-token-30d",
    "email": "test@example.com",
    "name": "Test",
}

SESSION_NO_REFRESH = {
    "access_token": "expired-access-token",
}


class TestRequestHappyPath(unittest.TestCase):

    @patch("app.crm_client.requests.request")
    def test_I1a_200_no_refresh_triggered(self, mock_req):
        """200 directo: refresh nunca é chamado."""
        mock_req.return_value = _resp(200, {"id": 1})
        resp = _request("GET", "http://localhost/api/test", SESSION_WITH_REFRESH.copy())
        self.assertEqual(resp.status_code, 200)
        mock_req.assert_called_once()


class TestRefreshOnExpiry(unittest.TestCase):

    @patch("app.crm_client.save_session")
    @patch("app.crm_client.refresh_access_token", return_value="new-access-token-fresh")
    @patch("app.crm_client.requests.request")
    def test_I1b_401_triggers_refresh_and_retry(self, mock_req, mock_refresh, mock_save):
        """401 com refresh_token válido: token renovado e chamada repetida."""
        mock_req.side_effect = [
            _resp(401),
            _resp(200, {"id": 42}),
        ]
        session = SESSION_WITH_REFRESH.copy()
        resp = _request("GET", "http://localhost/api/test", session)

        self.assertEqual(resp.status_code, 200)
        mock_refresh.assert_called_once_with("valid-refresh-token-30d")
        self.assertEqual(mock_req.call_count, 2)

    @patch("app.crm_client.save_session")
    @patch("app.crm_client.refresh_access_token", return_value="new-access-token-fresh")
    @patch("app.crm_client.requests.request")
    def test_I1c_session_dict_updated_in_memory(self, mock_req, mock_refresh, mock_save):
        """session['access_token'] actualizado em memória após refresh."""
        mock_req.side_effect = [_resp(401), _resp(200)]
        session = SESSION_WITH_REFRESH.copy()
        _request("GET", "http://localhost/api/test", session)
        self.assertEqual(session["access_token"], "new-access-token-fresh")

    @patch("app.crm_client.save_session")
    @patch("app.crm_client.refresh_access_token", return_value="new-access-token-fresh")
    @patch("app.crm_client.requests.request")
    def test_I1d_save_session_called_after_refresh(self, mock_req, mock_refresh, mock_save):
        """save_session chamado para persistir novo token em disco."""
        mock_req.side_effect = [_resp(401), _resp(200)]
        session = SESSION_WITH_REFRESH.copy()
        _request("GET", "http://localhost/api/test", session)
        mock_save.assert_called_once_with(session)

    @patch("app.crm_client.save_session")
    @patch("app.crm_client.refresh_access_token", return_value="new-access-token-fresh")
    @patch("app.crm_client.requests.request")
    def test_I1e_retry_uses_new_token(self, mock_req, mock_refresh, mock_save):
        """Segundo request (retry) usa novo token no header Authorization."""
        mock_req.side_effect = [_resp(401), _resp(200)]
        session = SESSION_WITH_REFRESH.copy()
        _request("POST", "http://localhost/api/leads", session, json={"x": 1})

        second_call_kwargs = mock_req.call_args_list[1][1]
        self.assertEqual(
            second_call_kwargs["headers"]["Authorization"],
            "Bearer new-access-token-fresh",
        )


class TestNoRefreshToken(unittest.TestCase):

    @patch("app.crm_client.requests.request")
    def test_I2a_401_without_refresh_token_returns_401(self, mock_req):
        """Sem refresh_token na sessão: retorna 401 directamente, sem crash."""
        mock_req.return_value = _resp(401)
        resp = _request("GET", "http://localhost/api/test", SESSION_NO_REFRESH.copy())
        self.assertEqual(resp.status_code, 401)
        mock_req.assert_called_once()


class TestRefreshFails(unittest.TestCase):

    @patch("app.crm_client.save_session")
    @patch("app.crm_client.refresh_access_token", side_effect=AuthError("Sessão expirada."))
    @patch("app.crm_client.requests.request")
    def test_I2b_refresh_raises_autherror_returns_401(self, mock_req, mock_refresh, mock_save):
        """refresh_access_token lança AuthError: retorna 401 original sem crash."""
        mock_req.return_value = _resp(401)
        session = SESSION_WITH_REFRESH.copy()
        resp = _request("GET", "http://localhost/api/test", session)
        self.assertEqual(resp.status_code, 401)
        mock_save.assert_not_called()

    @patch("app.crm_client.save_session")
    @patch("app.crm_client.refresh_access_token", return_value="new-token")
    @patch("app.crm_client.requests.request")
    def test_I2c_retry_also_fails_returns_retry_response(self, mock_req, mock_refresh, mock_save):
        """Refresh bem-sucedido mas recurso continua inacessível (403): retorna resposta do retry."""
        mock_req.side_effect = [_resp(401), _resp(403)]
        session = SESSION_WITH_REFRESH.copy()
        resp = _request("GET", "http://localhost/api/test", session)
        self.assertEqual(resp.status_code, 403)


class TestCreateLeadWithRefresh(unittest.TestCase):
    """Teste end-to-end: create_lead renova token e cria lead com sucesso."""

    @patch("app.crm_client.save_session")
    @patch("app.crm_client.refresh_access_token", return_value="fresh-token")
    @patch("app.crm_client.requests.request")
    def test_create_lead_retries_after_401(self, mock_req, mock_refresh, mock_save):
        mock_req.side_effect = [
            _resp(401),
            _resp(200, {"id": 55, "companyName": "Test Corp"}),
        ]
        session = SESSION_WITH_REFRESH.copy()
        result = create_lead(session, name="Test Corp", phone="351912345678")
        self.assertEqual(result["id"], 55)
        mock_refresh.assert_called_once()


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    unittest.main(verbosity=2)
