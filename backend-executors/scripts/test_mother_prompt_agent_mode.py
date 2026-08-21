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


def main() -> None:
    _install_fake_app_modules()
    decision_engine = _load_decision_engine()

    context = {
        "lead": {"id": 1, "category": "qualification"},
        "ai_profile": {
            "id": "profile-1",
            "name": "Demo",
            "template_key": "closer_agressivo",
            "agent_mode": "closer",
        },
        "playbook": {"template_key": "closer_agressivo"},
        "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        "history": [],
    }
    prompt = decision_engine._build_mother_prompt(context, "Quero marcar uma reunião")
    lowered = prompt.lower()

    assert '"agent_mode": "consultivo|agenda|direto|null (opcional)"' in lowered
    assert "política por modo" in lowered
    assert "meeting_scheduled" in lowered
    assert "next_action_hint" in lowered
    assert "agent_mode_normalized" in lowered
    print("OK: mother prompt includes structured optional fields and normalized mode context")


if __name__ == "__main__":
    main()
