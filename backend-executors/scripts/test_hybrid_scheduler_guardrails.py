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
    _install_fake_module("app.schemas.decision")
    _install_fake_module("app.services")
    _install_fake_module("app.services.orchestrator_models")
    _install_fake_module("app.contracts")
    _install_fake_module("app.contracts.qualification_contract")
    _install_fake_module("app.clients")
    _install_fake_module("app.clients.crm_client")
    _install_fake_module("app.core")
    _install_fake_module("app.core.config")

    qc = sys.modules["app.contracts.qualification_contract"]
    qc.SIGNALS_SCHEMA = {"offer_presented", "checkout_sent", "presentation_variant", "offer_item_name"}
    qc.compute_missing_fields = lambda *_args, **_kwargs: []
    qc.infer_extracted_fields = lambda *_args, **_kwargs: {}
    qc.required_fields_for_mode = lambda *_args, **_kwargs: []

    decision_module = sys.modules["app.schemas.decision"]

    class DecisionOutput:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        @classmethod
        def model_validate(cls, payload):
            return cls(**payload)

        def model_dump(self):
            return dict(self.__dict__)

    decision_module.DecisionOutput = DecisionOutput

    orch = sys.modules["app.services.orchestrator_models"]

    class MotherDecision:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class ChildResult:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    orch.MotherDecision = MotherDecision
    orch.ChildResult = ChildResult

    _install_fake_module("app.services.fast_path").try_fast_handoff = lambda _t: None
    _install_fake_module("app.services.field_extractor")
    _install_fake_module("app.services.llm_service")
    _install_fake_module("app.services.handoff_policy").apply = lambda _c, d, logger=None: d

    _install_fake_module("app.core.logging").log_ctx = lambda logger, **kwargs: logger
    sys.modules["app.core.logging"].setup_logging = lambda: None
    sys.modules["app.core.config"].settings = types.SimpleNamespace()

    # whatsapp runner deps
    _install_fake_module("app.clients.core_client")
    _install_fake_module("app.clients.crm_client")
    _install_fake_module("app.services.meeting_scheduler").handle_meeting_scheduled = lambda *a, **k: None


def _load_module(rel_path: str, module_name: str):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", rel_path))
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    _install_fake_app_modules()
    de = _load_module("app/services/decision_engine.py", "decision_engine")
    sys.modules["app.services.decision_engine"] = de
    wr = _load_module("app/runners/whatsapp.py", "whatsapp_runner")

    mother = de.MotherDecision(
        route_to="closing",
        perceived_category="closing",
        confidence=0.9,
        reason="teste",
        agent_mode="agenda",
        signals={},
        objective=None,
        next_action_hint=None,
    )
    child = de.ChildResult(
        message_text="vamos fechar",
        question_text=None,
        field=None,
        should_ask=False,
        did_complete_phase=False,
        recommended_next_category=None,
        outcome="won",
        kanban_highlight="green",
        signals=[],
        signals_structured={"offer_presented": True, "checkout_sent": True},
        confidence=0.8,
    )
    context = {
        "lead": {"category": "apresentation"},
        "ai_profile": {"template_key": "hybrid_scheduler", "agent_mode": "agenda"},
        "playbook": {"template_key": "hybrid_scheduler"},
        "metadata": {},
        "history": [],
    }

    decision = de.compose_decision_output(context=context, mother_decision=mother, child_result=child)
    assert decision.suggested_category != "closing"
    assert decision.outcome is None

    decision2 = wr.decision_engine.DecisionOutput(
        next_action="reply",
        message_text="segue o link [link_do_checkout]",
        questions=[],
        reason="test",
        suggested_category="closing",
        category_reason=None,
        outcome="won",
        kanban_highlight=None,
        signals=[],
        confidence=0.9,
        decision_trace={"child_signals_structured": {"checkout_sent": True}},
    )
    wr._enforce_checkout_link_guardrail(
        decision=decision2,
        context={
            "ai_profile": {"template_key": "hybrid_scheduler", "offer_pack": {"items": [{"checkout_link": "https://exemplo.com/checkout"}]}}
        },
    )
    assert "https://exemplo.com/checkout" not in decision2.message_text
    print("OK: hybrid_scheduler guardrails")


if __name__ == "__main__":
    main()
