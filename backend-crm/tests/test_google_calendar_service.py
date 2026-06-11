"""
Testes unitários para services/google_calendar_service.py

Cobertos:
  - _is_token_expired
  - _refresh_access_token (sucesso, campos em falta, HTTP 4xx)
  - _appointment_to_gcal_event (mapeamento de campos, fallbacks)
  - push_event (sem tokens, sucesso, Google timeout, retry 401)
  - update_event (sem google_event_id, sucesso, falha silenciosa)
  - delete_event (sem google_event_id, sucesso, 404/410 tratados como sucesso)
  - resiliência: push/update/delete nunca lançam excepção ao chamador
"""
import datetime
import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.google_calendar_service as svc

# ── Fixtures ─────────────────────────────────────────────────────────────────

VALID_TOKENS = {
    "access_token": "tok_access",
    "refresh_token": "tok_refresh",
    "token_expiry": (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    ).isoformat(),
    "calendar_id": "primary",
    "client_id": "client_id_x",
    "client_secret": "client_secret_x",
}

EXPIRED_TOKENS = {
    **VALID_TOKENS,
    "token_expiry": (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
    ).isoformat(),
}

APPOINTMENT = {
    "title": "Demo Call",
    "description": "Apresentação do produto",
    "start_at": "2026-06-15T10:00:00+00:00",
    "end_at": "2026-06-15T11:00:00+00:00",
    "location": "Sala A",
}


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        r.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    return r


# ── _is_token_expired ─────────────────────────────────────────────────────────

class TestIsTokenExpired(unittest.TestCase):

    def test_valid_token_not_expired(self):
        self.assertFalse(svc._is_token_expired(VALID_TOKENS))

    def test_expired_token(self):
        self.assertTrue(svc._is_token_expired(EXPIRED_TOKENS))

    def test_token_within_5min_buffer_is_expired(self):
        near_expiry = {
            **VALID_TOKENS,
            "token_expiry": (
                datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=3)
            ).isoformat(),
        }
        self.assertTrue(svc._is_token_expired(near_expiry))

    def test_no_expiry_field_returns_false(self):
        self.assertFalse(svc._is_token_expired({"access_token": "tok"}))

    def test_invalid_expiry_string_returns_false(self):
        self.assertFalse(svc._is_token_expired({"token_expiry": "not-a-date"}))


# ── _refresh_access_token ─────────────────────────────────────────────────────

class TestRefreshAccessToken(unittest.TestCase):

    @patch("services.google_calendar_service.httpx.post")
    def test_successful_refresh_returns_tuple(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            "access_token": "new_tok",
            "expires_in": 3600,
        })
        result = svc._refresh_access_token(VALID_TOKENS)
        self.assertIsNotNone(result)
        token, expiry = result
        self.assertEqual(token, "new_tok")
        self.assertIn("T", expiry)  # ISO format

    @patch("services.google_calendar_service.httpx.post")
    def test_refresh_uses_default_expires_in_when_missing(self, mock_post):
        mock_post.return_value = _mock_response(200, {"access_token": "new_tok"})
        result = svc._refresh_access_token(VALID_TOKENS)
        self.assertIsNotNone(result)
        token, expiry = result
        exp_dt = datetime.datetime.fromisoformat(expiry)
        now = datetime.datetime.now(datetime.timezone.utc)
        # expiry deve ser ~3600s no futuro (tolerância ±10s)
        delta = (exp_dt - now).total_seconds()
        self.assertGreater(delta, 3590)
        self.assertLess(delta, 3610)

    def test_missing_refresh_token_returns_none(self):
        tokens = {**VALID_TOKENS, "refresh_token": None}
        self.assertIsNone(svc._refresh_access_token(tokens))

    def test_missing_client_id_returns_none(self):
        tokens = {**VALID_TOKENS, "client_id": None}
        self.assertIsNone(svc._refresh_access_token(tokens))

    @patch("services.google_calendar_service.httpx.post")
    def test_http_error_returns_none(self, mock_post):
        mock_post.side_effect = Exception("network error")
        self.assertIsNone(svc._refresh_access_token(VALID_TOKENS))


# ── _appointment_to_gcal_event ────────────────────────────────────────────────

class TestAppointmentToGcalEvent(unittest.TestCase):

    def test_maps_basic_fields(self):
        event = svc._appointment_to_gcal_event(APPOINTMENT)
        self.assertEqual(event["summary"], "Demo Call")
        self.assertEqual(event["description"], "Apresentação do produto")
        self.assertEqual(event["location"], "Sala A")
        self.assertIn("dateTime", event["start"])
        self.assertIn("dateTime", event["end"])

    def test_falls_back_to_startTime_key(self):
        appt = {"startTime": "2026-06-15T09:00:00+00:00", "endTime": "2026-06-15T10:00:00+00:00"}
        event = svc._appointment_to_gcal_event(appt)
        self.assertIn("2026-06-15", event["start"]["dateTime"])

    def test_missing_title_uses_default(self):
        appt = {**APPOINTMENT, "title": None}
        event = svc._appointment_to_gcal_event(appt)
        self.assertEqual(event["summary"], "Compromisso")

    def test_no_description_key_absent(self):
        appt = {**APPOINTMENT, "description": None}
        event = svc._appointment_to_gcal_event(appt)
        self.assertNotIn("description", event)

    def test_no_location_key_absent(self):
        appt = {**APPOINTMENT, "location": None}
        event = svc._appointment_to_gcal_event(appt)
        self.assertNotIn("location", event)

    def test_end_falls_back_to_start_when_missing(self):
        appt = {"title": "X", "start_at": "2026-06-15T10:00:00+00:00"}
        event = svc._appointment_to_gcal_event(appt)
        self.assertEqual(event["start"]["dateTime"], event["end"]["dateTime"])


# ── push_event ────────────────────────────────────────────────────────────────

class TestPushEvent(unittest.TestCase):

    @patch("services.google_calendar_service._get_tokens", return_value=None)
    def test_no_tokens_returns_none(self, _):
        result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        self.assertIsNone(result)

    @patch("services.google_calendar_service.httpx.post")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_success_returns_event_id(self, _mock_tokens, mock_post):
        mock_post.return_value = _mock_response(201, {"id": "gcal_evt_123"})
        result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        self.assertEqual(result, "gcal_evt_123")

    @patch("services.google_calendar_service.httpx.post")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_google_timeout_returns_none(self, _mock_tokens, mock_post):
        import httpx
        mock_post.side_effect = httpx.TimeoutException("timeout")
        result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        self.assertIsNone(result)

    @patch("services.google_calendar_service.httpx.post")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_google_500_returns_none(self, _mock_tokens, mock_post):
        mock_post.return_value = _mock_response(500)
        result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        self.assertIsNone(result)

    @patch("services.google_calendar_service._save_refreshed_token")
    @patch("services.google_calendar_service._refresh_access_token",
           return_value=("new_tok", "2026-06-15T12:00:00+00:00"))
    @patch("services.google_calendar_service.httpx.post")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_retries_on_401_and_succeeds(self, _tokens, mock_post, _refresh, _save):
        # primeira chamada: 401; segunda: 201 com id
        mock_post.side_effect = [
            _mock_response(401),
            _mock_response(201, {"id": "gcal_retry_ok"}),
        ]
        result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        self.assertEqual(result, "gcal_retry_ok")
        self.assertEqual(mock_post.call_count, 2)
        _save.assert_called_once_with(1, "new_tok", "2026-06-15T12:00:00+00:00")

    @patch("services.google_calendar_service._refresh_access_token", return_value=None)
    @patch("services.google_calendar_service.httpx.post")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_401_refresh_fails_returns_none(self, _tokens, mock_post, _refresh):
        mock_post.return_value = _mock_response(401)
        result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        self.assertIsNone(result)

    @patch("services.google_calendar_service._get_tokens", return_value=EXPIRED_TOKENS)
    @patch("services.google_calendar_service._refresh_access_token", return_value=None)
    def test_expired_token_with_failed_refresh_returns_none(self, _refresh, _tokens):
        result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        self.assertIsNone(result)

    @patch("services.google_calendar_service.httpx.post")
    @patch("services.google_calendar_service._get_tokens",
           side_effect=Exception("core_unreachable"))
    def test_push_never_raises(self, _tokens, mock_post):
        # push_event deve ser fail-silent mesmo com excepção inesperada
        try:
            result = svc.push_event(user_id=1, appointment=APPOINTMENT)
        except Exception as e:
            self.fail(f"push_event lançou excepção: {e}")


# ── update_event ──────────────────────────────────────────────────────────────

class TestUpdateEvent(unittest.TestCase):

    def test_empty_google_event_id_is_noop(self):
        # não deve chamar nenhuma rede
        with patch("services.google_calendar_service._get_tokens") as mock_tokens:
            svc.update_event(user_id=1, google_event_id="", appointment=APPOINTMENT)
            mock_tokens.assert_not_called()

    @patch("services.google_calendar_service._get_tokens", return_value=None)
    def test_no_tokens_returns_silently(self, _):
        svc.update_event(user_id=1, google_event_id="evt_1", appointment=APPOINTMENT)

    @patch("services.google_calendar_service.httpx.put")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_success(self, _tokens, mock_put):
        mock_put.return_value = _mock_response(200)
        svc.update_event(user_id=1, google_event_id="evt_1", appointment=APPOINTMENT)
        mock_put.assert_called_once()

    @patch("services.google_calendar_service.httpx.put")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_google_error_does_not_raise(self, _tokens, mock_put):
        import httpx
        mock_put.side_effect = httpx.ConnectError("unreachable")
        try:
            svc.update_event(user_id=1, google_event_id="evt_1", appointment=APPOINTMENT)
        except Exception as e:
            self.fail(f"update_event lançou excepção: {e}")


# ── delete_event ──────────────────────────────────────────────────────────────

class TestDeleteEvent(unittest.TestCase):

    def test_empty_google_event_id_is_noop(self):
        with patch("services.google_calendar_service._get_tokens") as mock_tokens:
            svc.delete_event(user_id=1, google_event_id="")
            mock_tokens.assert_not_called()

    @patch("services.google_calendar_service._get_tokens", return_value=None)
    def test_no_tokens_returns_silently(self, _):
        svc.delete_event(user_id=1, google_event_id="evt_1")

    @patch("services.google_calendar_service.httpx.delete")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_success_204(self, _tokens, mock_del):
        mock_del.return_value = _mock_response(204)
        svc.delete_event(user_id=1, google_event_id="evt_1")
        mock_del.assert_called_once()

    @patch("services.google_calendar_service.httpx.delete")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_404_treated_as_success(self, _tokens, mock_del):
        mock_del.return_value = _mock_response(404)
        try:
            svc.delete_event(user_id=1, google_event_id="evt_already_gone")
        except Exception as e:
            self.fail(f"delete_event lançou excepção em 404: {e}")

    @patch("services.google_calendar_service.httpx.delete")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_410_treated_as_success(self, _tokens, mock_del):
        mock_del.return_value = _mock_response(410)
        svc.delete_event(user_id=1, google_event_id="evt_gone")

    @patch("services.google_calendar_service.httpx.delete")
    @patch("services.google_calendar_service._get_tokens", return_value=VALID_TOKENS)
    def test_network_error_does_not_raise(self, _tokens, mock_del):
        import httpx
        mock_del.side_effect = httpx.TimeoutException("timeout")
        try:
            svc.delete_event(user_id=1, google_event_id="evt_1")
        except Exception as e:
            self.fail(f"delete_event lançou excepção: {e}")


# ── _save_refreshed_token — verifica payload ─────────────────────────────────

class TestSaveRefreshedToken(unittest.TestCase):

    @patch("services.google_calendar_service.httpx.put")
    def test_sends_both_access_token_and_expiry(self, mock_put):
        mock_put.return_value = _mock_response(200, {"updated": True})
        svc._save_refreshed_token(42, "new_tok_xyz", "2026-06-15T12:00:00+00:00")
        args, kwargs = mock_put.call_args
        body = kwargs.get("json") or args[1] if len(args) > 1 else kwargs["json"]
        self.assertEqual(body["access_token"], "new_tok_xyz")
        self.assertEqual(body["token_expiry"], "2026-06-15T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
