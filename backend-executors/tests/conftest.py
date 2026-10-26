import json

import pytest

from app.services import llm_service, professional_hours


@pytest.fixture(autouse=True)
def _no_real_professional_hours_call(monkeypatch):
    """Construir um prompt com um horário pedido lê o horário de atendimento via IA
    (professional_hours.get_hours). Nos testes nunca há chamada real: sem horários, salvo
    quando o teste substitui esta função."""
    monkeypatch.setattr(
        llm_service, "generate_professional_hours", lambda prompt, ai_profile=None: json.dumps({"professionals": []})
    )
    professional_hours._CACHE.clear()
    yield
    professional_hours._CACHE.clear()
