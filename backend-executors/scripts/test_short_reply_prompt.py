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
    context = {
        "lead": {"id": 123, "contactName": "Teste", "phone": "+5511999999999"},
        "ai_profile": {"id": "profile-1", "name": "Demo", "template_key": "sdr_padrao"},
        "playbook": {"template_key": "sdr_padrao"},
        "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        "history": [
            {"model": "inbound", "body": "Olá"},
            {"model": "outbound", "body": "Quer agendar uma reunião?"},
        ],
    }
    prompt = decision_engine._build_prompt(context, "sim")
    assert "last_bot_message: Quer agendar uma reunião?" in prompt
    assert "short_reply_hint: message_text é resposta direta ao last_bot_message" in prompt

    prompt_new_intent = decision_engine._build_prompt(context, "qual o preço?")
    assert "last_bot_message: " in prompt_new_intent
    assert "last_bot_message: Quer agendar uma reunião?" not in prompt_new_intent
    assert "short_reply_hint: " in prompt_new_intent
    assert (
        "short_reply_hint: message_text é resposta direta ao last_bot_message"
        not in prompt_new_intent
    )
    print("OK: short reply prompt includes last_bot_message and short_reply_hint")


if __name__ == "__main__":
    main()
