"""
Push/update/delete de eventos no Google Calendar do utilizador.
Fail-silent: nunca bloqueia criação/edição de compromissos no CRM.
Os tokens são lidos do backend-core via chamada service-to-service.
"""
import datetime
import logging
import os
from typing import Optional

import httpx

CORE_BASE = os.environ.get("CORE_API_BASE", "http://localhost:8001")
SERVICE_TOKEN = os.environ.get("CORE_SERVICE_TOKEN", "")

logger = logging.getLogger(__name__)


def _get_tokens(user_id: int) -> Optional[dict]:
    try:
        r = httpx.get(
            f"{CORE_BASE}/auth/google/tokens/{user_id}",
            headers={"X-Service-Token": SERVICE_TOKEN},
            timeout=5.0,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.debug("google_tokens_fetch_failed user_id=%s: %s", user_id, exc)
        return None


def _is_token_expired(tokens: dict) -> bool:
    expiry = tokens.get("token_expiry")
    if not expiry:
        return False
    try:
        exp_dt = datetime.datetime.fromisoformat(expiry)
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
        return datetime.datetime.now(datetime.timezone.utc) >= exp_dt - datetime.timedelta(minutes=5)
    except Exception:
        return False


def _refresh_access_token(tokens: dict) -> Optional[tuple]:
    """Returns (access_token, expiry_iso) or None."""
    refresh_token = tokens.get("refresh_token")
    client_id = tokens.get("client_id")
    client_secret = tokens.get("client_secret")
    if not all([refresh_token, client_id, client_secret]):
        return None
    try:
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in") or 3600)
        expiry_iso = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=expires_in)
        ).isoformat()
        return (access_token, expiry_iso)
    except Exception as exc:
        logger.warning("google_token_refresh_failed: %s", exc)
        return None


def _save_refreshed_token(user_id: int, new_access_token: str, new_expiry: str) -> None:
    try:
        httpx.put(
            f"{CORE_BASE}/auth/google/tokens/{user_id}",
            json={"access_token": new_access_token, "token_expiry": new_expiry},
            headers={"X-Service-Token": SERVICE_TOKEN},
            timeout=5.0,
        )
    except Exception as exc:
        logger.debug("google_token_save_failed user_id=%s: %s", user_id, exc)


def _get_valid_token(user_id: int, tokens: dict) -> Optional[str]:
    if _is_token_expired(tokens):
        result = _refresh_access_token(tokens)
        if result:
            new_token, new_expiry = result
            _save_refreshed_token(user_id, new_token, new_expiry)
            return new_token
        return None
    return tokens.get("access_token")


def _to_rfc3339(s: str) -> str:
    if not s:
        return s
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.isoformat()
    except Exception:
        return s


def _appointment_to_gcal_event(appointment: dict) -> dict:
    start = appointment.get("start_at") or appointment.get("startTime", "")
    end = appointment.get("end_at") or appointment.get("endTime") or start
    event: dict = {
        "summary": appointment.get("title") or "Compromisso",
        "start": {"dateTime": _to_rfc3339(start), "timeZone": "UTC"},
        "end": {"dateTime": _to_rfc3339(end) or _to_rfc3339(start), "timeZone": "UTC"},
    }
    if appointment.get("description"):
        event["description"] = appointment["description"]
    if appointment.get("location"):
        event["location"] = appointment["location"]
    return event


def push_event(user_id: int, appointment: dict) -> Optional[str]:
    """Cria evento no Google Calendar. Retorna google_event_id ou None."""
    try:
        tokens = _get_tokens(user_id)
        if not tokens:
            return None

        access_token = _get_valid_token(user_id, tokens)
        if not access_token:
            return None

        calendar_id = tokens.get("calendar_id") or "primary"
        event = _appointment_to_gcal_event(appointment)

        r = httpx.post(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
            json=event,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if r.status_code == 401:
            result = _refresh_access_token(tokens)
            if not result:
                return None
            new_token, new_expiry = result
            _save_refreshed_token(user_id, new_token, new_expiry)
            r = httpx.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                json=event,
                headers={"Authorization": f"Bearer {new_token}"},
                timeout=10.0,
            )
        if r.status_code in (200, 201):
            return r.json().get("id")
        logger.warning("google_push_event_failed user_id=%s status=%s", user_id, r.status_code)
        return None
    except Exception as exc:
        logger.warning("google_push_event_error user_id=%s: %s", user_id, exc)
        return None


def update_event(user_id: int, google_event_id: str, appointment: dict) -> None:
    """Actualiza evento no Google Calendar."""
    if not google_event_id:
        return
    try:
        tokens = _get_tokens(user_id)
        if not tokens:
            return

        access_token = _get_valid_token(user_id, tokens)
        if not access_token:
            return

        calendar_id = tokens.get("calendar_id") or "primary"
        event = _appointment_to_gcal_event(appointment)

        r = httpx.put(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{google_event_id}",
            json=event,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if r.status_code not in (200, 204):
            logger.warning(
                "google_update_event_failed user_id=%s event_id=%s status=%s",
                user_id, google_event_id, r.status_code,
            )
    except Exception as exc:
        logger.warning("google_update_event_error user_id=%s: %s", user_id, exc)


def delete_event(user_id: int, google_event_id: str) -> None:
    """Cancela evento no Google Calendar."""
    if not google_event_id:
        return
    try:
        tokens = _get_tokens(user_id)
        if not tokens:
            return

        access_token = _get_valid_token(user_id, tokens)
        if not access_token:
            return

        calendar_id = tokens.get("calendar_id") or "primary"

        r = httpx.delete(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{google_event_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        if r.status_code not in (200, 204, 404, 410):
            logger.warning(
                "google_delete_event_failed user_id=%s event_id=%s status=%s",
                user_id, google_event_id, r.status_code,
            )
    except Exception as exc:
        logger.warning("google_delete_event_error user_id=%s: %s", user_id, exc)
