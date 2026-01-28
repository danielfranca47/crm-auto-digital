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

    fast_path = _install_fake_module("app.services.fast_path")
    fast_path.try_fast_handoff = lambda _: None

    handoff_policy = _install_fake_module("app.services.handoff_policy")
    handoff_policy.apply = lambda _context, decision, logger=None: decision

    llm_service = _install_fake_module("app.services.llm_service")
    llm_service.generate_decision_text = lambda _prompt: "{}"


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
    allowed = ["to-prospect", "closing"]
    context = {
        "metadata": {"allowed_lead_categories": allowed},
        "job": {"id": 99, "payload": {"job_id": 99, "lead_id": 10, "user_id": 7}},
        "lead": {"id": 10, "user_id": 7},
    }

    invalid = decision_engine.DecisionOutput(
        next_action="reply",
        message_text="",
        questions=[],
        reason="test",
        suggested_category="Marketing",
        category_reason="invalid",
    )
    invalid = decision_engine._sanitize_category_decision(invalid, context)
    assert invalid.suggested_category is None
    assert invalid.category_reason is None

    valid = decision_engine.DecisionOutput(
        next_action="reply",
        message_text="",
        questions=[],
        reason="test",
        suggested_category="closing",
        category_reason="ok",
    )
    valid = decision_engine._sanitize_category_decision(valid, context)
    assert valid.suggested_category == "closing"
    assert valid.category_reason == "ok"

    ask = decision_engine.DecisionOutput(
        next_action="ask_qualification",
        message_text="",
        questions=[],
        reason="test",
        suggested_category="closing",
        category_reason="should clear",
    )
    ask = decision_engine._sanitize_category_decision(ask, context)
    assert ask.suggested_category is None
    assert ask.category_reason is None

    print("OK: category validation sanitizes invalid and ask_qualification decisions")


if __name__ == "__main__":
    main()
