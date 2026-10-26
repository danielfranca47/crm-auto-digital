"""Callback OAuth do Google Calendar: só aceita a ligação quando a Google concede calendar.events.

Caso real (25/10/2026): a Google devolveu um token só com email/openid (a página do calendário
foi recusada/fechada) e o CRM mostrou "Conectado" sem acesso ao calendário.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api import auth_google

CAL = "https://www.googleapis.com/auth/calendar.events"


def _token_response(scope: str) -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {
        "access_token": "at",
        "refresh_token": "rt",
        "expires_in": 3600,
        "scope": scope,
    }
    return r


def _userinfo_response() -> MagicMock:
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"email": "dono@example.com"}
    return r


def _fake_client():
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class OAuthCallbackScopeTests(unittest.TestCase):

    def _run(self, scope: str):
        client = _fake_client()
        client.post = AsyncMock(return_value=_token_response(scope))
        client.get = AsyncMock(return_value=_userinfo_response())
        settings = MagicMock(
            GOOGLE_CLIENT_ID="cid",
            GOOGLE_CLIENT_SECRET="sec",
            GOOGLE_REDIRECT_URI="https://core/cb",
            CRM_FRONTEND_URL="https://crm",
        )
        with patch.object(auth_google, "settings", settings), \
             patch.object(auth_google, "_verify_state", return_value=4), \
             patch.object(auth_google.httpx, "AsyncClient", return_value=client), \
             patch.object(auth_google, "_save_google_tokens") as save:
            resp = asyncio.run(auth_google.oauth_callback(code="c", state="s", error=None))
        return resp, save

    def test_token_without_calendar_scope_is_rejected(self):
        resp, save = self._run("email https://www.googleapis.com/auth/userinfo.email openid")
        save.assert_not_called()
        self.assertEqual(resp.headers["location"], "https://crm/?google_error=missing_calendar_scope")

    def test_token_with_calendar_scope_is_saved(self):
        resp, save = self._run(f"email https://www.googleapis.com/auth/userinfo.email openid {CAL}")
        save.assert_called_once()
        self.assertEqual(resp.headers["location"], "https://crm/?google_connected=1")

    def test_user_denied_redirects_with_denied(self):
        settings = MagicMock(
            GOOGLE_CLIENT_ID="cid", GOOGLE_CLIENT_SECRET="sec",
            GOOGLE_REDIRECT_URI="https://core/cb", CRM_FRONTEND_URL="https://crm",
        )
        with patch.object(auth_google, "settings", settings):
            resp = asyncio.run(auth_google.oauth_callback(code=None, state="s", error="access_denied"))
        self.assertEqual(resp.headers["location"], "https://crm/?google_error=denied")


if __name__ == "__main__":
    unittest.main()
