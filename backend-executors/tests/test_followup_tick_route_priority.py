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

from app.services import decision_engine


def test_followup_tick_forces_followup_child_route(monkeypatch):
    context = {
        "lead": {"id": 10, "user_id": 99, "category": "follow-up"},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {},
        "metadata": {
            "inbound_message_text": "followup_tick_auto_trigger",
            "followup_context": {
                "followup_goal": "reschedule",
                "followup_variant": "hybrid_scheduler",
                "followup_attempts": 1,
            },
        },
        "history": [],
        "job": {"id": 123, "type": "whatsapp.followup.tick", "payload": {"lead_id": 10, "user_id": 99}},
        "qualification_state": {
            "exists": True,
            "data_json": {},
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }

    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _prompt: '{"route_to":"qualification","perceived_category":"follow-up","confidence":0.5,"reason":"faltando localização"}',
    )

    calls = {}

    def _child(route: str, _prompt: str):
        calls["route"] = route
        return '{"message_text":"mensagem follow-up","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", _child)

    decision = decision_engine.decide(context)
    trace = decision.decision_trace or {}

    assert calls["route"] == "follow-up"
    assert trace.get("effective_route_to") == "follow-up"
    assert trace.get("mother_route_to") == "qualification"
    assert trace.get("anti_loop_rule3_applied") is False
    assert decision.next_action == "reply"
