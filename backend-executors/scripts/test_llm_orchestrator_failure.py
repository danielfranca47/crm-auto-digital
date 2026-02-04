import importlib.util
import logging
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
    fast_path.try_fast_handoff = lambda _text: None

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


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _make_context() -> dict:
    return {
        "metadata": {"allowed_lead_categories": ["qualification", "closing"]},
        "lead": {"id": 1, "user_id": 7, "category": "qualification"},
        "ai_profile": {},
        "playbook": {},
        "history": [],
        "job": {"id": 99, "payload": {"job_id": 99, "lead_id": 1, "user_id": 7, "message_text": "oi"}},
    }


def _assert_stage(records: list[logging.LogRecord], expected: str) -> None:
    messages = [record.getMessage() for record in records]
    if not any(f"event=llm_orchestrator_error stage={expected}" in msg for msg in messages):
        raise AssertionError(f"expected stage {expected} not found in logs: {messages}")


def main() -> None:
    _install_fake_app_modules()
    decision_engine = _load_decision_engine()
    context = _make_context()

    logger = logging.getLogger("orchestrator-test")
    logger.setLevel(logging.INFO)
    handler = _CaptureHandler()
    logger.addHandler(handler)

    def bad_mother(_prompt: str) -> str:
        return "not-json"

    def ok_child(_route: str, _prompt: str) -> str:
        return (
            '{"message_text":"ok","did_complete_phase":false,'
            '"recommended_next_category":null,"outcome":null,'
            '"kanban_highlight":null,"signals":[],"confidence":0.5}'
        )

    decision_engine.llm_service.generate_mother_route = bad_mother
    decision_engine.llm_service.generate_child_result = ok_child
    handler.records.clear()
    decision_engine.decide(context, logger=logger)
    _assert_stage(handler.records, "mother_parse")

    def ok_mother(_prompt: str) -> str:
        return '{"route_to":"qualification","confidence":0.8,"reason":"test"}'

    def bad_child(_route: str, _prompt: str) -> str:
        return "invalid-child-json"

    decision_engine.llm_service.generate_mother_route = ok_mother
    decision_engine.llm_service.generate_child_result = bad_child
    handler.records.clear()
    decision_engine.decide(context, logger=logger)
    _assert_stage(handler.records, "child_parse")

    print("OK: llm_orchestrator_error stages captured")


if __name__ == "__main__":
    main()
