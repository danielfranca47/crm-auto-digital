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
    _install_fake_module("app.contracts")
    _install_fake_module("app.contracts.qualification_contract")
    _install_fake_module("app.clients")
    _install_fake_module("app.core")
    _install_fake_module("app.core.config")

    qc = sys.modules["app.contracts.qualification_contract"]
    qc.SIGNALS_SCHEMA = set()
    qc.compute_missing_fields = lambda _mode, _extracted: []
    qc.infer_extracted_fields = lambda _context: {}
    qc.required_fields_for_mode = lambda _mode: []

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
    fast_path.try_fast_handoff = lambda _text: None
    _install_fake_module("app.services.field_extractor")

    handoff_policy = _install_fake_module("app.services.handoff_policy")
    handoff_policy.apply = lambda _context, decision, logger=None: decision

    llm_service = _install_fake_module("app.services.llm_service")
    llm_service.generate_mother_route = lambda _prompt: "{}"
    llm_service.generate_child_result = lambda _route, _prompt: "{}"

    crm_client = _install_fake_module("app.clients.crm_client")
    crm_client.get_lead_qualification_state = lambda _lead_id: None
    crm_client.upsert_lead_qualification_state = lambda *_args, **_kwargs: None

    core_config = sys.modules["app.core.config"]
    core_config.settings = types.SimpleNamespace()


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
        "ai_profile": {"agent_mode": "agenda", "presentation_variant": None, "offer_pack": None},
        "metadata": {"presentation_variant": "sales", "force_presentation_variant": False},
    }

    variant, source = decision_engine._resolve_presentation_variant(context, "agenda")
    assert variant == "scheduler"
    assert source == "agent_mode_default"

    mother = decision_engine.MotherDecision(
        route_to="apresentation",
        perceived_category="apresentation",
        confidence=0.9,
        reason="teste",
        signals={},
        objective=None,
        next_action_hint=None,
    )
    prompt = decision_engine._build_child_prompt_apresentation(context, "Quero horário", mother)
    lowered = prompt.lower()
    assert "presentation_variant: scheduler" in lowered
    assert "conduza agendamento" in lowered
    assert "apresente oferta objetiva" in lowered
    print("OK: presentation variant falls back to scheduler for agenda profile")


if __name__ == "__main__":
    main()
