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
            self.next_action = kwargs.get("next_action")
            self.message_text = kwargs.get("message_text", "")
            self.questions = kwargs.get("questions", [])
            self.reason = kwargs.get("reason", "")
            self.suggested_category = kwargs.get("suggested_category")
            self.category_reason = kwargs.get("category_reason")
            self.outcome = kwargs.get("outcome")
            self.kanban_highlight = kwargs.get("kanban_highlight")
            self.signals = kwargs.get("signals", [])
            self.confidence = kwargs.get("confidence")
            self.decision_trace = kwargs.get("decision_trace")

        @classmethod
        def model_validate(cls, payload):
            return cls(**payload)

        def model_dump(self):
            return dict(self.__dict__)

    decision_module.DecisionOutput = DecisionOutput

    orchestrator_module = sys.modules["app.services.orchestrator_models"]

    class MotherDecision:
        def __init__(self, **kwargs) -> None:
            self.route_to = kwargs.get("route_to")
            self.perceived_category = kwargs.get("perceived_category")
            self.confidence = kwargs.get("confidence", 0.0)
            self.reason = kwargs.get("reason", "")
            self.agent_mode = kwargs.get("agent_mode")
            self.signals = kwargs.get("signals")
            self.objective = kwargs.get("objective")
            self.next_action_hint = kwargs.get("next_action_hint")

        @classmethod
        def model_validate(cls, payload):
            return cls(**payload)

    class ChildResult:
        def __init__(self, **kwargs) -> None:
            self.message_text = kwargs.get("message_text", "")
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
    fast_path.try_fast_handoff = lambda _: None

    handoff_policy = _install_fake_module("app.services.handoff_policy")
    handoff_policy.apply = lambda _context, decision, logger=None: decision

    llm_service = _install_fake_module("app.services.llm_service")
    llm_service.generate_mother_route = lambda _prompt: "{}"
    llm_service.generate_child_result = lambda _route, _prompt: "{}"


def _load_decision_engine():
    current_dir = os.path.dirname(__file__)
    module_path = os.path.abspath(os.path.join(current_dir, "..", "app", "services", "decision_engine.py"))
    spec = importlib.util.spec_from_file_location("decision_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
    return module


def _fake_child_payload():
    return (
        '{"message_text":"ok","did_complete_phase":false,"recommended_next_category":null,'
        '"outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.6}'
    )


def _base_context():
    return {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {"id": "profile-1", "name": "Demo", "template_key": "sdr_padrao", "agent_mode": "sdr_scheduler"},
        "playbook": {"template_key": "sdr_padrao"},
        "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        "history": [],
    }


def main() -> None:
    _install_fake_app_modules()
    decision_engine = _load_decision_engine()
    decision_engine.llm_service.generate_child_result = lambda _route, _prompt: _fake_child_payload()

    decision_engine.llm_service.generate_mother_route = lambda _prompt: (
        '{"route_to":"apresentation","perceived_category":"apresentation","confidence":0.9,'
        '"reason":"ok","signals":{"meeting_scheduled":true}}'
    )
    decision = decision_engine.decide(_base_context())
    trace = decision.decision_trace or {}
    assert trace.get("meeting_scheduled") is True
    assert trace.get("agent_mode_normalized") == "agenda"

    decision_engine.llm_service.generate_mother_route = lambda _prompt: (
        '{"route_to":"apresentation","perceived_category":"apresentation","confidence":0.8,'
        '"reason":"meeting_scheduled|legacy"}'
    )
    decision_legacy = decision_engine.decide(_base_context())
    trace_legacy = decision_legacy.decision_trace or {}
    assert trace_legacy.get("meeting_scheduled") is True

    print("OK: structured meeting_scheduled preferred with legacy fallback")


if __name__ == "__main__":
    main()
