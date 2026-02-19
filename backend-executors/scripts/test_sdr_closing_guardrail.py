import importlib.util
import os
import sys
import types


def _install_fake_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _install_fake_app_modules() -> None:
    _install_fake_module("app")
    _install_fake_module("app.schemas")
    _install_fake_module("app.services")
    _install_fake_module("app.services.orchestrator_models")

    decision_module = _install_fake_module("app.schemas.decision")

    class DecisionOutput:
        def __init__(self, **kwargs) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.questions = getattr(self, "questions", [])

    decision_module.DecisionOutput = DecisionOutput

    orchestrator_module = sys.modules["app.services.orchestrator_models"]

    class MotherDecision:
        def __init__(self, **kwargs) -> None:
            self.route_to = kwargs.get("route_to")
            self.perceived_category = kwargs.get("perceived_category")
            self.confidence = kwargs.get("confidence")
            self.reason = kwargs.get("reason")
            self.agent_mode = kwargs.get("agent_mode")
            self.signals = kwargs.get("signals")
            self.objective = kwargs.get("objective")
            self.next_action_hint = kwargs.get("next_action_hint")

        @classmethod
        def model_validate(cls, payload):
            return cls(**payload)

    class ChildResult:
        def __init__(self, **kwargs) -> None:
            self.message_text = kwargs.get("message_text")
            self.did_complete_phase = kwargs.get("did_complete_phase", False)
            self.recommended_next_category = kwargs.get("recommended_next_category")
            self.outcome = kwargs.get("outcome")
            self.kanban_highlight = kwargs.get("kanban_highlight")
            self.signals = kwargs.get("signals", [])
            self.confidence = kwargs.get("confidence", 0.0)

        @classmethod
        def model_validate(cls, payload):
            return cls(**payload)

    orchestrator_module.MotherDecision = MotherDecision
    orchestrator_module.ChildResult = ChildResult

    fast_path = _install_fake_module("app.services.fast_path")
    fast_path.try_fast_handoff = lambda _text: None

    handoff_policy = _install_fake_module("app.services.handoff_policy")
    handoff_policy.apply = lambda _context, decision, logger=None: decision

    llm_service = _install_fake_module("app.services.llm_service")
    llm_service.generate_mother_route = lambda _prompt: '{}'
    llm_service.generate_child_result = lambda _route, _prompt: '{}'


def _load_decision_engine():
    _install_fake_app_modules()
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "services", "decision_engine.py"))
    spec = importlib.util.spec_from_file_location("decision_engine", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_sdr_closing_escalates_and_suppresses_reply() -> None:
    mod = _load_decision_engine()

    routes = {"called": None}

    mod.llm_service.generate_mother_route = lambda _prompt: (
        '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"intenção"}'
    )

    def fake_child(route: str, _prompt: str) -> str:
        routes["called"] = route
        return '{"message_text":"ok","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    mod.llm_service.generate_child_result = fake_child

    ctx = {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {"agent_mode": "sdr_scheduler"},
        "metadata": {"inbound_message_text": "vamos falar depois"},
        "history": [{"model": "inbound", "body": "talvez mais pra frente"}],
    }
    decision = mod.decide(ctx)
    assert routes["called"] is None
    assert decision.next_action == "ignore"
    assert decision.suggested_category == "closing"
    assert "guardrail_sdr_escalate_closing" in (decision.reason or "")
    trace = decision.decision_trace or {}
    assert trace.get("guardrail_sdr_escalate_closing") is True
    assert trace.get("suppressed_reply") is True


def test_closer_keeps_closing() -> None:
    mod = _load_decision_engine()
    routes = {"called": None}
    mod.llm_service.generate_mother_route = lambda _prompt: (
        '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"intenção"}'
    )

    def fake_child(route: str, _prompt: str) -> str:
        routes["called"] = route
        return '{"message_text":"ok","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    mod.llm_service.generate_child_result = fake_child

    ctx = {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {"agent_mode": "closer"},
        "metadata": {"inbound_message_text": "quero fechar"},
        "history": [],
    }
    mod.decide(ctx)
    assert routes["called"] == "closing"


def test_agenda_with_handoff_indicator_blocks_closing() -> None:
    mod = _load_decision_engine()
    routes = {"called": None}
    mod.llm_service.generate_mother_route = lambda _prompt: (
        '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"intenção"}'
    )

    def fake_child(route: str, _prompt: str) -> str:
        routes["called"] = route
        return '{"message_text":"ok","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    mod.llm_service.generate_child_result = fake_child

    ctx = {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {"requires_handoff": True},
        "metadata": {"inbound_message_text": "vamos falar depois"},
        "history": [],
    }
    decision = mod.decide(ctx)
    assert routes["called"] is None
    assert decision.next_action == "ignore"
    assert "guardrail_sdr_escalate_closing" in (decision.reason or "")


def test_agenda_without_indicators_allows_closing() -> None:
    mod = _load_decision_engine()
    routes = {"called": None}
    mod.llm_service.generate_mother_route = lambda _prompt: (
        '{"route_to":"closing","perceived_category":"closing","confidence":0.9,"reason":"intenção"}'
    )

    def fake_child(route: str, _prompt: str) -> str:
        routes["called"] = route
        return '{"message_text":"ok","did_complete_phase":false,"recommended_next_category":null,"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'

    mod.llm_service.generate_child_result = fake_child

    ctx = {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {"agent_mode": "agenda"},
        "metadata": {"inbound_message_text": "quero fechar"},
        "history": [],
    }
    mod.decide(ctx)
    assert routes["called"] == "closing"


if __name__ == "__main__":
    test_sdr_closing_escalates_and_suppresses_reply()
    test_agenda_with_handoff_indicator_blocks_closing()
    test_agenda_without_indicators_allows_closing()
    test_closer_keeps_closing()
    print("OK: sdr closing guardrail")
