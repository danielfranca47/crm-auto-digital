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
            self.__dict__.update(kwargs)

        @classmethod
        def model_validate(cls, payload):
            return cls(**payload)

        def model_dump(self):
            return dict(self.__dict__)

    decision_module.DecisionOutput = DecisionOutput

    orchestrator_module = sys.modules["app.services.orchestrator_models"]

    class MotherDecision:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

        @classmethod
        def model_validate(cls, payload):
            return cls(**payload)

    class ChildResult:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

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
    llm_service.generate_mother_route = lambda _prompt, **_kwargs: "{}"
    llm_service.generate_child_result = lambda _route, _prompt, **_kwargs: "{}"


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

    decision_engine.llm_service.generate_mother_route = lambda _prompt, **_kwargs: (
        '{"route_to":"apresentation","perceived_category":"apresentation","confidence":0.8,"reason":"meeting_scheduled|ok"}'
    )

    def fake_child(_route, prompt, **_kwargs):
        captured["prompt"] = prompt
        return _fake_child_payload()

    decision_engine.llm_service.generate_child_result = fake_child

    context = {
        "lead": {"id": 1, "category": "apresentation"},
        "ai_profile": {"id": "profile-1", "name": "Demo", "template_key": "sdr_padrao"},
        "playbook": {"template_key": "sdr_padrao"},
        "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        "history": [],
    }

    decision_engine.decide(context)
    prompt = captured["prompt"] or ""
    assert "FILHA APRESENTATION" in prompt
    assert "agenda" in prompt.lower()
    assert "meeting_scheduled" in prompt
    print("OK: apresentation prompt handles scheduling")


if __name__ == "__main__":
    main()
