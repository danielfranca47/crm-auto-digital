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
            self.route_to = kwargs.get("route_to")
            self.perceived_category = kwargs.get("perceived_category")
            self.confidence = kwargs.get("confidence")
            self.reason = kwargs.get("reason")

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


def main() -> None:
    _install_fake_app_modules()
    decision_engine = _load_decision_engine()

    mother = decision_engine.MotherDecision(
        route_to="qualification",
        perceived_category="apresentation",
        confidence=0.8,
        reason="context",
    )
    child = decision_engine.ChildResult(
        message_text="Pergunta?",
        did_complete_phase=False,
        recommended_next_category="apresentation",
        outcome=None,
        kanban_highlight=None,
        signals=[],
        confidence=0.7,
    )
    child.kanban_highlight = "orange"
    child.outcome = "lost"
    suggested, _, guardrail_reason = decision_engine.apply_mother_category_guardrails(
        "qualification",
        mother,
    )
    assert suggested == "apresentation"
    assert guardrail_reason == "ok"
    outcome, highlight = decision_engine.apply_outcome_guardrails("qualification", child)
    assert outcome is None
    assert highlight is None

    mother.perceived_category = "qualification"
    suggested, _, guardrail_reason = decision_engine.apply_mother_category_guardrails(
        "apresentation",
        mother,
    )
    assert suggested is None
    assert guardrail_reason == "backwards_block"

    mother.perceived_category = "closing"
    mother.confidence = 0.6
    suggested, _, guardrail_reason = decision_engine.apply_mother_category_guardrails(
        "qualification",
        mother,
    )
    assert suggested is None
    assert guardrail_reason == "jump_blocked_low_conf"

    mother.confidence = 0.8
    suggested, _, guardrail_reason = decision_engine.apply_mother_category_guardrails(
        "qualification",
        mother,
    )
    assert suggested == "apresentation"
    assert guardrail_reason == "jump_clamped"

    mother.perceived_category = None
    suggested, _, guardrail_reason = decision_engine.apply_mother_category_guardrails(
        "qualification",
        mother,
    )
    assert suggested is None
    assert guardrail_reason == "missing_perceived"

    mother.perceived_category = "marketing"
    suggested, _, guardrail_reason = decision_engine.apply_mother_category_guardrails(
        "qualification",
        mother,
    )
    assert suggested is None
    assert guardrail_reason == "invalid"

    child.outcome = "won"
    child.kanban_highlight = "green"
    outcome, highlight = decision_engine.apply_outcome_guardrails("closing", child)
    assert outcome == "won"
    assert highlight == "green"

    decision = decision_engine.compose_decision_output(
        context={"lead": {"category": "qualification"}},
        mother_decision=mother,
        child_result=child,
    )
    assert decision.outcome is None
    assert decision.kanban_highlight is None
    assert decision.signals == []
    assert decision.confidence == child.confidence

    print("OK: guardrails and decision composition")


if __name__ == "__main__":
    main()
