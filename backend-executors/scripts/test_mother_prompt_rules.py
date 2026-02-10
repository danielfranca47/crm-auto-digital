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

    context = {
        "lead": {"id": 1, "category": "qualification"},
        "ai_profile": {"id": "profile-1", "name": "Demo", "template_key": "sdr_padrao"},
        "playbook": {"template_key": "sdr_padrao"},
        "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        "history": [],
    }
    prompt = decision_engine._build_mother_prompt(context, "Amanhã 17h tá confirmado")
    lowered = prompt.lower()

    assert "definição do funil" in lowered
    assert "apresentation" in lowered
    assert "reagendar" in lowered
    assert "confirmar" in lowered
    assert "follow-up" in lowered
    assert "vou pensar" in lowered
    assert "amanhã 17h tá confirmado" in lowered
    assert "pode reagendar pra sexta" in lowered
    assert "vou pensar, me chama mês que vem" in lowered
    print("OK: mother prompt includes funnel definition and examples")


if __name__ == "__main__":
    main()
