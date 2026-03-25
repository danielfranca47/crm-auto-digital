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
    _install_fake_module("app.services.meeting_scheduler")

    settings_module = sys.modules["app.core.config"]
    settings_module.settings = types.SimpleNamespace()

    logging_module = sys.modules["app.core.logging"]
    logging_module.log_ctx = lambda logger, **kwargs: logger
    logging_module.setup_logging = lambda: None

    meeting_scheduler_module = sys.modules["app.services.meeting_scheduler"]
    meeting_scheduler_module.handle_meeting_scheduled = lambda *args, **kwargs: None

    decision_engine_module = sys.modules["app.services.decision_engine"]

    class DecisionOutput:
        def __init__(self, **kwargs):
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


def test_confirm_turn_no_link_append():
    _install_fake_app_modules()
    whatsapp = _load_whatsapp_runner()

    decision = whatsapp.decision_engine.DecisionOutput(
        next_action="reply",
        message_text="Plano Starter com suporte premium. Quer seguir?",
        questions=[],
        reason="test",
        suggested_category="apresentation",
        category_reason=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        confidence=0.9,
        decision_trace={
            "presentation_variant": "sales",
            "child_signals_structured": {"offer_presented": True, "checkout_sent": False},
        },
    )
    context = {
        "ai_profile": {
            "offer_pack": {
                "items": [{"name": "Plano Starter", "checkout_link": "https://exemplo.com/checkout-starter"}]
            }
        },
        "playbook": {},
        "metadata": {"presentation_variant": "sales"},
    }

    whatsapp._enforce_checkout_link_guardrail(decision=decision, context=context)
    assert "https://exemplo.com/checkout-starter" not in decision.message_text


def test_send_link_turn_appends_real_url():
    _install_fake_app_modules()
    whatsapp = _load_whatsapp_runner()

    decision = whatsapp.decision_engine.DecisionOutput(
        next_action="reply",
        message_text="Perfeito, vamos finalizar agora.",
        questions=[],
        reason="test",
        suggested_category="apresentation",
        category_reason=None,
        outcome=None,
        kanban_highlight=None,
        signals=[],
        confidence=0.9,
        decision_trace={
            "presentation_variant": "sales",
            "child_signals_structured": {"offer_presented": True, "checkout_sent": True},
        },
    )
    context = {
        "ai_profile": {
            "offer_pack": {
                "items": [{"name": "Plano Starter", "checkout_link": "https://exemplo.com/checkout-starter"}]
            }
        },
        "playbook": {},
        "metadata": {"presentation_variant": "sales"},
    }

    whatsapp._enforce_checkout_link_guardrail(decision=decision, context=context)
    assert "https://exemplo.com/checkout-starter" in decision.message_text


if __name__ == "__main__":
    test_confirm_turn_no_link_append()
    test_send_link_turn_appends_real_url()
    print("OK: checkout guardrail turn split")
