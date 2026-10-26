"""
Pull Google → CRM sem esconder falhas.

Cobertos:
  - list_events: sem Google → None; 403 de scope → GoogleCalendarError(missing_calendar_scope)
    e erro reportado ao core; 200 → eventos e erro limpo no core; rede → google_unavailable
  - sync_user_google_events: falha da Google não apaga nada; sucesso faz upsert + limpeza
  - rota google-sync: erro da Google → 409 com code/message
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException

import routes.appointments as appointments_module
import services.google_calendar_service as svc
from security_core import CurrentUser
from services.google_calendar_service import GoogleCalendarError
from services.google_calendar_sync import sync_user_google_events

TOKENS = {
    "access_token": "tok",
    "refresh_token": "ref",
    "token_expiry": None,
    "calendar_id": "primary",
    "client_id": "cid",
    "client_secret": "csec",
}

SCOPE_403_BODY = (
    '{"error": {"code": 403, "message": "Request had insufficient authentication scopes.",'
    ' "errors": [{"reason": "insufficientPermissions"}], "status": "PERMISSION_DENIED",'
    ' "details": [{"reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}]}}'
)


def _response(status_code: int, json_data=None, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.text = text
    return r


class ListEventsTest(unittest.TestCase):

    @patch("services.google_calendar_service._get_tokens", return_value=None)
    def test_without_google_returns_none(self, _):
        self.assertIsNone(svc.list_events(1, "2026-10-01T00:00:00+00:00", "2026-10-31T00:00:00+00:00"))

    @patch("services.google_calendar_service._report_error")
    @patch("services.google_calendar_service.httpx.get")
    @patch("services.google_calendar_service._get_tokens", return_value=TOKENS)
    def test_scope_403_raises_and_reports(self, _tokens, mock_get, mock_report):
        mock_get.return_value = _response(403, text=SCOPE_403_BODY)
        with self.assertRaises(GoogleCalendarError) as ctx:
            svc.list_events(4, "a", "b")
        self.assertEqual(ctx.exception.code, svc.ERROR_MISSING_SCOPE)
        mock_report.assert_called_once_with(4, svc.ERROR_MISSING_SCOPE)

    @patch("services.google_calendar_service._report_error")
    @patch("services.google_calendar_service.httpx.get")
    @patch("services.google_calendar_service._get_tokens", return_value=TOKENS)
    def test_success_returns_items_and_clears_error(self, _tokens, mock_get, mock_report):
        mock_get.return_value = _response(200, {"items": [{"id": "g1"}]})
        self.assertEqual(svc.list_events(4, "a", "b"), [{"id": "g1"}])
        mock_report.assert_called_once_with(4, None)

    @patch("services.google_calendar_service._report_error")
    @patch("services.google_calendar_service.httpx.get", side_effect=httpx.ConnectTimeout("t"))
    @patch("services.google_calendar_service._get_tokens", return_value=TOKENS)
    def test_network_error_is_unavailable_and_not_reported(self, _tokens, _get, mock_report):
        with self.assertRaises(GoogleCalendarError) as ctx:
            svc.list_events(4, "a", "b")
        self.assertEqual(ctx.exception.code, svc.ERROR_UNAVAILABLE)
        mock_report.assert_not_called()

    @patch("services.google_calendar_service._report_error")
    @patch("services.google_calendar_service.httpx.get")
    @patch("services.google_calendar_service._get_tokens", return_value=TOKENS)
    def test_other_500_is_unavailable_and_not_reported(self, _tokens, mock_get, mock_report):
        mock_get.return_value = _response(500, text="boom")
        with self.assertRaises(GoogleCalendarError) as ctx:
            svc.list_events(4, "a", "b")
        self.assertEqual(ctx.exception.code, svc.ERROR_UNAVAILABLE)
        mock_report.assert_not_called()


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT,
            contactName TEXT
        );
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            type TEXT,
            start_at TEXT,
            end_at TEXT,
            status TEXT DEFAULT 'pending',
            outcome TEXT,
            outcome_note TEXT,
            outcome_at TEXT,
            location TEXT,
            google_event_id TEXT,
            source TEXT DEFAULT 'crm',
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    conn.commit()


START = "2026-11-01T00:00:00+00:00"
END = "2026-11-30T23:59:59+00:00"


class SyncUserGoogleEventsTest(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = self._open()
        _create_schema(conn)
        conn.execute(
            "INSERT INTO appointments (user_id, lead_id, title, start_at, end_at, source, google_event_id)"
            " VALUES (4, NULL, 'Sessão Val', '2026-11-10T10:00:00+00:00', '2026-11-10T11:00:00+00:00', 'google', 'g-old')"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _google_ids(self):
        conn = self._open()
        try:
            return sorted(r["google_event_id"] for r in conn.execute(
                "SELECT google_event_id FROM appointments WHERE source = 'google' AND user_id = 4"
            ))
        finally:
            conn.close()

    def test_google_failure_keeps_imported_events(self):
        with patch("services.google_calendar_sync.get_connection", side_effect=self._open), \
             patch("services.google_calendar_sync.list_events",
                   side_effect=GoogleCalendarError(svc.ERROR_MISSING_SCOPE)):
            with self.assertRaises(GoogleCalendarError):
                sync_user_google_events(4, START, END)
        self.assertEqual(self._google_ids(), ["g-old"])

    def test_without_google_does_nothing(self):
        with patch("services.google_calendar_sync.get_connection", side_effect=self._open), \
             patch("services.google_calendar_sync.list_events", return_value=None):
            self.assertIsNone(sync_user_google_events(4, START, END))
        self.assertEqual(self._google_ids(), ["g-old"])

    def test_success_upserts_and_removes_missing(self):
        events = [{
            "id": "g-new",
            "summary": "Massagem",
            "start": {"dateTime": "2026-11-12T15:00:00+00:00"},
            "end": {"dateTime": "2026-11-12T16:00:00+00:00"},
        }]
        with patch("services.google_calendar_sync.get_connection", side_effect=self._open), \
             patch("services.google_calendar_sync.list_events", return_value=events):
            self.assertEqual(sync_user_google_events(4, START, END), 1)
        self.assertEqual(self._google_ids(), ["g-new"])

    def test_empty_google_removes_period_events(self):
        with patch("services.google_calendar_sync.get_connection", side_effect=self._open), \
             patch("services.google_calendar_sync.list_events", return_value=[]):
            self.assertEqual(sync_user_google_events(4, START, END), 0)
        self.assertEqual(self._google_ids(), [])


class GoogleSyncRouteTest(unittest.TestCase):

    def test_google_error_returns_409_with_message(self):
        user = CurrentUser(id=4, email="dono@teste.com")
        with patch("routes.appointments.sync_user_google_events",
                   side_effect=GoogleCalendarError(svc.ERROR_MISSING_SCOPE)):
            with self.assertRaises(HTTPException) as ctx:
                appointments_module.google_sync(start=START, end=END, current_user=user)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["code"], svc.ERROR_MISSING_SCOPE)
        self.assertIn("Minha Conta", ctx.exception.detail["message"])


if __name__ == "__main__":
    unittest.main()
