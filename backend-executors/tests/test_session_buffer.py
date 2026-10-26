"""Margem entre sessões: o CRM manda os ocupados de outros já alargados (orchestrator.py::
_apply_session_buffer). Aqui confirma-se que a verificação do horário pedido respeita isso.

Ocupado real 15h–16h com margem de 15 min → chega como 14h45–16h15 (Lisboa = UTC em 29/10/2026).
"""
from datetime import datetime, timezone

import pytest

from app.services.requested_slot import find_requested_slot

NOW = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)  # segunda
TZ = "Europe/Lisbon"
OTHER_LEAD_WIDENED = {"id": 1, "lead_id": 50, "start_at": "2026-10-29T14:45:00+00:00", "end_at": "2026-10-29T16:15:00+00:00"}
OWN_LEAD_REAL = {"id": 2, "lead_id": 7, "start_at": "2026-10-29T17:00:00+00:00", "end_at": "2026-10-29T18:00:00+00:00"}


def _slot(text, busy, duration=60):
    return find_requested_slot(
        text, [], tz_name=TZ, busy_slots=busy, duration_minutes=duration, exclude_lead_id=7, now_utc=NOW
    )


@pytest.mark.parametrize(
    "text,livre",
    [
        ("Pode ser quinta às 16h?", False),  # colada ao fim — sem tempo para preparar a sala
        ("Pode ser quinta às 16h15?", True),
        ("Pode ser quinta às 14h?", False),  # acabaria às 15h, colada ao início
        ("Pode ser quinta às 13h45?", True),  # acaba às 14h45 — 15 min antes da sessão das 15h
    ],
)
def test_margem_respeitada_antes_e_depois(text, livre):
    slot = _slot(text, [OTHER_LEAD_WIDENED])
    assert slot is not None
    assert slot.free is livre


def test_sessao_do_proprio_lead_nao_bloqueia_a_remarcacao():
    slot = _slot("Pode ser quinta às 17h30?", [OTHER_LEAD_WIDENED, OWN_LEAD_REAL])
    assert slot.free is True
