import os
import sys
import types

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")

    class RequestError(Exception):
        pass

    class _Resp:
        status_code = 500
        text = ""

        def __init__(self, status_code: int = 500, text: str = "", json_data=None):
            self.status_code = status_code
            self.text = text
            self._json_data = json_data or {}

        @property
        def is_success(self) -> bool:
            return 200 <= self.status_code < 300

        def json(self):
            return self._json_data

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, *args, **kwargs):
            return _Resp()

    httpx_stub.RequestError = RequestError
    httpx_stub.Client = Client
    httpx_stub.Response = _Resp
    sys.modules["httpx"] = httpx_stub

if "pydantic_settings" not in sys.modules:
    pydantic_settings_stub = types.ModuleType("pydantic_settings")

    class BaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def SettingsConfigDict(**kwargs):
        return dict(**kwargs)

    pydantic_settings_stub.BaseSettings = BaseSettings
    pydantic_settings_stub.SettingsConfigDict = SettingsConfigDict
    sys.modules["pydantic_settings"] = pydantic_settings_stub

from app.services.decision_engine import _build_child_prompt_follow_up
from app.services.orchestrator_models import MotherDecision


def test_followup_prompt_includes_contract_signals_and_variant_rule():
    context = {
        "lead": {"id": 7, "category": "follow-up", "contactName": "Maria"},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {"template_key": "hybrid_scheduler", "max_chars": 280},
        "metadata": {
            "provider": "uazapi",
            "instance_id": "inst-1",
            "followup_context": {
                "followup_goal": "reschedule",
                "followup_outcome": "warm",
                "followup_variant": "hybrid_scheduler",
                "followup_attempts": 1,
                "followup_max_attempts": 3,
                "followup_meeting_happened": False,
                "followup_meeting_or_session_happened": "no_show",
                "followup_proposal_sent": False,
                "followup_operator_note": "cliente pediu novo horário",
                "followup_status": "active",
                "followup_next_followup_at": "2026-01-01T10:00:00Z",
            },
        },
        "history": [{"model": "outbound", "body": "Oi"}],
    }
    mother = MotherDecision(route_to="follow-up", perceived_category="follow-up", confidence=0.9, reason="ok")

    prompt = _build_child_prompt_follow_up(context, "followup_tick_auto_trigger", mother)

    assert "followup_contract_signals" in prompt
    assert "hybrid_scheduler" in prompt
    assert "no-show" in prompt or "no_show" in prompt
    # Regra de retomada de no-show/remarcação continua no prompt, só a redação mudou.
    assert "no-show/remarcação" in prompt
    assert "CONTEXTO PRIORITÁRIO (follow-up tick)" in prompt
    assert "não reabra qualificação antiga por padrão" in prompt
    assert "histórico é memória contextual; ele NÃO é backlog" in prompt
    assert "pergunta antiga sem resposta" in prompt
    assert "não repita por padrão" in prompt
    assert "SOMENTE memória auxiliar (read-only)" in prompt
    assert "proibido usar missing_fields de qualification como alvo de coleta/pergunta" in prompt
    assert "qualification_context_read_only" in prompt
    assert "Required fields:" not in prompt
    assert "Missing fields:" not in prompt
    assert "priorize o próximo missing_field" not in prompt


def test_followup_prompt_keeps_missing_field_guidance_outside_tick_context():
    context = {
        "lead": {"id": 7, "category": "follow-up", "contactName": "Maria"},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {"template_key": "hybrid_scheduler", "max_chars": 280},
        "metadata": {
            "provider": "uazapi",
            "instance_id": "inst-1",
            "followup_context": {},
        },
        "history": [{"model": "outbound", "body": "Oi"}],
    }
    mother = MotherDecision(route_to="follow-up", perceived_category="follow-up", confidence=0.9, reason="ok")

    prompt = _build_child_prompt_follow_up(context, "mensagem inbound real", mother)

    assert "priorize o próximo missing_field" in prompt
    assert "CONTEXTO PRIORITÁRIO (follow-up tick)" not in prompt
    assert "Required fields:" in prompt
    assert "Missing fields:" in prompt
