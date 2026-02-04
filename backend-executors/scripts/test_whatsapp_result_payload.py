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
    _install_fake_module("app.core")
    _install_fake_module("app.core.config")
    _install_fake_module("app.core.logging")
    _install_fake_module("app.clients")
    _install_fake_module("app.clients.core_client")
    _install_fake_module("app.clients.crm_client")
    _install_fake_module("app.services")
    _install_fake_module("app.services.decision_engine")

    settings_module = sys.modules["app.core.config"]
    settings_module.settings = types.SimpleNamespace()

    logging_module = sys.modules["app.core.logging"]
    logging_module.log_ctx = lambda logger, **kwargs: logger
    logging_module.setup_logging = lambda: None

    decision_engine_module = sys.modules["app.services.decision_engine"]

    class DecisionOutput:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

        def model_dump(self):
            return dict(self.__dict__)

    decision_engine_module.DecisionOutput = DecisionOutput


def _load_whatsapp_runner():
    current_dir = os.path.dirname(__file__)
    module_path = os.path.abspath(os.path.join(current_dir, "..", "app", "runners", "whatsapp.py"))
    spec = importlib.util.spec_from_file_location("whatsapp_runner", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
    return module


def main() -> None:
    _install_fake_app_modules()
    whatsapp = _load_whatsapp_runner()

    decision = whatsapp.decision_engine.DecisionOutput(
        next_action="reply",
        message_text="ok",
        questions=[],
        reason="test",
        suggested_category=None,
        category_reason=None,
        outcome="won",
        kanban_highlight="green",
        signals=["sinal"],
        confidence=0.91,
    )
    payload = whatsapp._build_result_payload(
        decision,
        lead_id=10,
        user_id=7,
        phone="+5511999999999",
        source_job_id=99,
    )
    assert payload["outcome"] == "won"
    assert payload["kanban_highlight"] == "green"
    assert payload["signals"] == ["sinal"]
    assert payload["confidence"] == 0.91
    assert payload["source_job_id"] == 99
    print("OK: result payload includes outcome/highlight fields")


if __name__ == "__main__":
    main()
