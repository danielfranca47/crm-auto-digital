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


def main() -> None:
    _install_fake_app_modules()
    decision_engine = _load_decision_engine()

    captured = {"prompt": None}

    def fake_mother(payload):
        return payload

    def fake_child(_route, prompt):
        captured["prompt"] = prompt
        return _fake_child_payload()

    decision_engine.llm_service.generate_child_result = fake_child

    base_context = {
        "lead": {"id": 1, "category": "qualification"},
        "ai_profile": {"id": "profile-1", "name": "Demo", "template_key": "sdr_padrao"},
        "playbook": {"template_key": "sdr_padrao"},
        "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        "history": [],
    }

    decision_engine.llm_service.generate_mother_route = lambda _prompt: fake_mother(
        '{"route_to":"qualification","perceived_category":"qualification","confidence":0.8,"reason":"ok"}'
    )
    decision_engine.decide(dict(base_context))
    assert "FILHA QUALIFICATION" in (captured["prompt"] or "")

    decision_engine.llm_service.generate_mother_route = lambda _prompt: fake_mother(
        '{"route_to":"apresentation","perceived_category":"apresentation","confidence":0.8,"reason":"ok"}'
    )
    decision_engine.decide(dict(base_context))
    assert "FILHA APRESENTATION" in (captured["prompt"] or "")

    decision_engine.llm_service.generate_mother_route = lambda _prompt: fake_mother(
        '{"route_to":"follow-up","perceived_category":"follow-up","confidence":0.8,"reason":"ok"}'
    )
    decision_engine.decide(dict(base_context))
    assert "FILHA FOLLOW-UP" in (captured["prompt"] or "")

    closing_context = dict(base_context)
    closing_context["ai_profile"] = {
        "id": "profile-1",
        "name": "Demo",
        "template_key": "closer_agressivo",
        "agent_mode": "closer",
    }
    decision_engine.llm_service.generate_mother_route = lambda _prompt: fake_mother(
        '{"route_to":"closing","perceived_category":"closing","confidence":0.8,"reason":"ok"}'
    )
    decision_engine.decide(closing_context)
    assert "FILHA CLOSING" in (captured["prompt"] or "")

    print("OK: child prompt selection by route")


if __name__ == "__main__":
    main()
