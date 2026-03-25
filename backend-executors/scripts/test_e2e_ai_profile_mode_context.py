"""
E2E mínimo (sem WhatsApp real) com mock explícito de HTTP entre serviços.

Fluxo validado:
1) create/update AI profile no backend-core (mock endpoint)
2) execução de "execution-context" no backend-crm (mock endpoint)
3) decisão no executor via decision_engine.decide(context)
4) assert de decision_trace.agent_mode_normalized para consultivo/agenda
"""

import importlib.util
import json
import os
import sys
import types
from typing import Any, Dict

CORE_PROFILE_STORE: Dict[int, Dict[str, Any]] = {}


def _install_fake_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _install_fake_executor_dependencies() -> None:
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
    llm_service.generate_mother_route = lambda _prompt: "{}"
    llm_service.generate_child_result = lambda _route, _prompt: "{}"


def _load_decision_engine():
    _install_fake_executor_dependencies()
    module_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "app", "services", "decision_engine.py")
    )
    spec = importlib.util.spec_from_file_location("decision_engine", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ===== Mocks explícitos de "endpoint" core/crm =====
def core_create_or_update_ai_profile(user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload)
    record["user_id"] = user_id
    CORE_PROFILE_STORE[user_id] = record
    return record


def crm_get_execution_context(user_id: int, lead_id: int) -> Dict[str, Any]:
    ai_profile = CORE_PROFILE_STORE[user_id]
    return {
        "job": {"id": 777, "payload": {"lead_id": lead_id, "user_id": user_id}},
        "lead": {
            "id": lead_id,
            "user_id": user_id,
            "category": "qualification",
            "contactName": "Lead E2E",
        },
        "history": [],
        "ai_profile": ai_profile,
        "playbook": {"template_key": ai_profile.get("template_key", "sdr_padrao")},
        "metadata": {
            "inbound_message_text": "oi",
            "provider": "uazapi",
            "instance_id": "inst-e2e",
            "message_id": "m-e2e",
            "allowed_lead_categories": [
                "to-prospect",
                "in-progress",
                "qualification",
                "apresentation",
                "follow-up",
                "closing",
                "client-list",
                "prospect-refused",
                "disqualified",
            ],
        },
    }


def _patch_llm(decision_engine_module) -> None:
    decision_engine_module.llm_service.generate_mother_route = lambda _prompt: json.dumps(
        {
            "route_to": "qualification",
            "perceived_category": "qualification",
            "confidence": 0.8,
            "reason": "ok",
        }
    )
    decision_engine_module.llm_service.generate_child_result = lambda _route, _prompt: json.dumps(
        {
            "message_text": "Perfeito, me conta mais.",
            "did_complete_phase": False,
            "recommended_next_category": None,
            "outcome": None,
            "kanban_highlight": None,
            "signals": [],
            "confidence": 0.7,
        }
    )


def run_case(decision_engine_module, *, user_id: int, lead_id: int, agent_mode: str, requires_handoff: bool, human_in_loop: bool, expected_mode: str) -> None:
    payload = {
        "template_key": "sdr_padrao",
        "name": "Agente E2E",
        "brand_name": "AutoDigital",
        "tone_of_voice": "profissional",
        "timezone": "UTC",
        "niche": "serviços",
        "target_audience": "PME",
        "offer_description": "Automação",
        "goals": "- qualificar",
        "agent_mode": agent_mode,
        "requires_handoff": requires_handoff,
        "human_in_loop": human_in_loop,
    }

    saved = core_create_or_update_ai_profile(user_id, payload)
    assert saved["agent_mode"] == agent_mode
    assert saved["requires_handoff"] is requires_handoff
    assert saved["human_in_loop"] is human_in_loop

    context = crm_get_execution_context(user_id, lead_id)
    assert context["ai_profile"]["agent_mode"] == agent_mode
    assert context["ai_profile"]["requires_handoff"] is requires_handoff
    assert context["ai_profile"]["human_in_loop"] is human_in_loop

    decision = decision_engine_module.decide(context)
    trace = decision.decision_trace or {}
    assert trace.get("agent_mode_normalized") == expected_mode

    print(
        f"OK: user={user_id} mode={agent_mode} requires_handoff={requires_handoff} "
        f"human_in_loop={human_in_loop} -> normalized={trace.get('agent_mode_normalized')}"
    )


def main() -> None:
    decision_engine_module = _load_decision_engine()
    _patch_llm(decision_engine_module)

    run_case(
        decision_engine_module,
        user_id=1001,
        lead_id=5001,
        agent_mode="consultivo",
        requires_handoff=True,
        human_in_loop=True,
        expected_mode="consultivo",
    )

    run_case(
        decision_engine_module,
        user_id=1002,
        lead_id=5002,
        agent_mode="agenda",
        requires_handoff=False,
        human_in_loop=False,
        expected_mode="agenda",
    )

    print("OK: E2E mínimo sem WhatsApp real validado (com mocks explícitos de HTTP core/crm)")


if __name__ == "__main__":
    main()
