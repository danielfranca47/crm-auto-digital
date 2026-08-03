"""Trava as URLs usadas por crm_client para criar/cancelar/reagendar appointments.

Regressão da Fase 2 de docs/implementations/fix-confirm-exact-agenda-vazia.md: essas
3 funções só enviam X-Service-Token (nunca JWT de usuário), então precisam sempre
apontar para as rotas internas de backend-crm (/api/internal/appointments/...),
protegidas por token de serviço — nunca para as rotas públicas /api/appointments/...,
que exigem require_crm_access (JWT de usuário) desde o commit 6aebb6f.
"""
from app.clients import crm_client


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = ""

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._json_data


class _FakeHttpxClient:
    def __init__(self, recorded_calls):
        self._recorded_calls = recorded_calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def request(self, method, url, headers=None, json=None, params=None):
        self._recorded_calls.append({"method": method, "url": url, "json": json})
        return _FakeResponse(200, {"id": 1, "lead_id": json.get("lead_id") if json else None})


def _patch_httpx(monkeypatch, recorded_calls):
    monkeypatch.setattr(crm_client.httpx, "Client", lambda timeout: _FakeHttpxClient(recorded_calls))
    monkeypatch.setattr(crm_client.settings, "crm_api_base", "http://localhost:8000")
    monkeypatch.setattr(crm_client.settings, "crm_service_token", "token-de-teste")


def test_create_lead_appointment_hits_internal_route(monkeypatch):
    calls = []
    _patch_httpx(monkeypatch, calls)

    crm_client.create_lead_appointment(
        lead_id=1,
        title="Sessao",
        description=None,
        appointment_type="meeting",
        start_at="2026-08-10T15:00:00Z",
    )

    assert calls[0]["url"] == "http://localhost:8000/api/internal/appointments"


def test_cancel_appointment_hits_internal_route(monkeypatch):
    calls = []
    _patch_httpx(monkeypatch, calls)

    crm_client.cancel_appointment(42)

    assert calls[0]["url"] == "http://localhost:8000/api/internal/appointments/42/cancel"


def test_reschedule_appointment_hits_internal_route(monkeypatch):
    calls = []
    _patch_httpx(monkeypatch, calls)

    crm_client.reschedule_appointment(42, start_at="2026-08-10T16:00:00Z", end_at="2026-08-10T16:30:00Z")

    assert calls[0]["url"] == "http://localhost:8000/api/internal/appointments/42"
