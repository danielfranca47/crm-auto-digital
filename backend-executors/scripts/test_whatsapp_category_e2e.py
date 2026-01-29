import importlib.util
import os
import sqlite3
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


def _load_jobs_service():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    module_path = os.path.join(repo_root, "backend-crm", "services", "jobs_service.py")
    crm_root = os.path.join(repo_root, "backend-crm")
    if crm_root not in sys.path:
        sys.path.insert(0, crm_root)
    if "fastapi" not in sys.modules:
        fastapi_module = _install_fake_module("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code=None, detail=None):
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        fastapi_module.HTTPException = HTTPException

    spec = importlib.util.spec_from_file_location("jobs_service", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
    return module


def _scenario1(decision_engine):
    allowed = [
        "to-prospect",
        "in-progress",
        "qualification",
        "apresentation",
        "follow-up",
        "closing",
        "client-list",
        "prospect-refused",
        "disqualified",
    ]
    context = {
        "metadata": {"allowed_lead_categories": allowed},
        "lead": {"id": 1, "user_id": 7},
        "ai_profile": {},
        "playbook": {},
        "history": [],
    }

    def fake_llm(_prompt: str) -> str:
        return (
            '{"next_action":"ask_qualification","message_text":"Qual é o seu objetivo agora?",'
            '"questions":[],"reason":"precisa de contexto","suggested_category":"closing","category_reason":"x"}'
        )

    decision_engine.llm_service.generate_decision_text = fake_llm
    decision = decision_engine.decide(context)
    assert decision.next_action == "ask_qualification"
    assert decision.suggested_category is None
    assert decision.category_reason is None
    print("OK: scenario1 ask_qualification clears category")


def _scenario2(decision_engine):
    allowed = [
        "to-prospect",
        "in-progress",
        "qualification",
        "apresentation",
        "follow-up",
        "closing",
        "client-list",
        "prospect-refused",
        "disqualified",
    ]
    context = {
        "metadata": {"allowed_lead_categories": allowed},
        "lead": {"id": 2, "user_id": 7},
        "ai_profile": {},
        "playbook": {},
        "history": [],
    }

    def fake_llm(_prompt: str) -> str:
        return (
            '{"next_action":"reply","message_text":"Perfeito, vamos seguir.",'
            '"questions":[],"reason":"intenção forte","suggested_category":"Marketing","category_reason":"x"}'
        )

    decision_engine.llm_service.generate_decision_text = fake_llm
    decision = decision_engine.decide(context)
    assert decision.next_action == "reply"
    assert decision.suggested_category is None
    assert decision.category_reason is None
    print("OK: scenario2 invalid category is sanitized by executor")


def _scenario3(jobs_service):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            category TEXT,
            lastMovement TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE prospection_logs (
            lead_id INTEGER,
            channel TEXT,
            message_id INTEGER,
            action TEXT,
            notes TEXT,
            user_id INTEGER
        )
        """
    )
    cur.execute(
        "INSERT INTO leads (id, user_id, category, lastMovement) VALUES (1, 7, 'to-prospect', NULL)"
    )
    conn.commit()

    result = jobs_service.apply_suggested_category(
        conn,
        lead_id=1,
        user_id=7,
        suggested_category="Marketing",
        reason="x",
        inbound_message_text="quero fechar",
    )
    assert result is False
    lead_row = cur.execute("SELECT category FROM leads WHERE id = 1").fetchone()
    assert lead_row["category"] == "to-prospect"
    moved = cur.execute(
        "SELECT lead_id FROM prospection_logs WHERE lead_id = 1 AND action = 'moved_stage'"
    ).fetchone()
    assert moved is None
    conn.close()
    print("OK: scenario3 CRM refuses invalid category and does not move lead")


def main() -> None:
    _install_fake_app_modules()
    decision_engine = _load_decision_engine()
    _scenario1(decision_engine)
    _scenario2(decision_engine)

    jobs_service = _load_jobs_service()
    _scenario3(jobs_service)


if __name__ == "__main__":
    main()
