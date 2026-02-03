import importlib.util
import os
import sqlite3
import sys
import types
from typing import Any, Dict, Optional


ALLOWED_CATEGORIES = [
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


def _install_fake_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _install_fake_app_modules() -> None:
    """
    Instala módulos fake em sys.modules para permitir importar o decision_engine real
    sem precisar subir o pacote inteiro (app.*).
    """
    _install_fake_module("app")
    _install_fake_module("app.schemas")
    _install_fake_module("app.services")
    _install_fake_module("app.services.orchestrator_models")

    decision_module = _install_fake_module("app.schemas.decision")

    class DecisionOutput:
        """
        Fake simples compatível com:
        - DecisionOutput.model_validate(payload)
        - acesso por atributos (decision.next_action, etc)
        - model_dump()
        """
        def __init__(self, **kwargs) -> None:
            # Defaults úteis para evitar AttributeError em cenários
            self.next_action = kwargs.get("next_action")
            self.message_text = kwargs.get("message_text")
            self.questions = kwargs.get("questions", [])
            self.reason = kwargs.get("reason")
            self.suggested_category = kwargs.get("suggested_category")
            self.category_reason = kwargs.get("category_reason")
            self.outcome = kwargs.get("outcome")
            self.kanban_highlight = kwargs.get("kanban_highlight")
            self.signals = kwargs.get("signals", [])
            self.confidence = kwargs.get("confidence")

            # mantém quaisquer extras
            for k, v in kwargs.items():
                setattr(self, k, v)

        @classmethod
        def model_validate(cls, payload):
            if not isinstance(payload, dict):
                raise TypeError("DecisionOutput.model_validate espera dict")
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
            if not isinstance(payload, dict):
                raise TypeError("MotherDecision.model_validate espera dict")
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
            if not isinstance(payload, dict):
                raise TypeError("ChildResult.model_validate espera dict")
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


def _load_module_from_path(module_name: str, module_path: str):
    if not os.path.isfile(module_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {module_path}")

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Falha ao criar spec para {module_name} em {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_decision_engine():
    current_dir = os.path.dirname(__file__)
    module_path = os.path.abspath(
        os.path.join(current_dir, "..", "app", "services", "decision_engine.py")
    )
    return _load_module_from_path("decision_engine", module_path)


def _load_jobs_service():
    """
    Carrega jobs_service real do backend-crm.

    Observação:
    - Coloca backend-crm no sys.path para imports internos funcionarem.
    - Finge fastapi.HTTPException se o módulo fastapi não estiver disponível.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    crm_root = os.path.join(repo_root, "backend-crm")
    module_path = os.path.join(crm_root, "services", "jobs_service.py")

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

    return _load_module_from_path("jobs_service", module_path)


def _make_context(inbound_message_text: str, lead_id: int, lead_category: str = "qualification") -> Dict[str, Any]:
    """
    Context mínimo, mas incluindo um payload de job para aumentar a chance
    do _extract_message_text() do decision_engine achar o texto corretamente.
    """
    return {
        "metadata": {"allowed_lead_categories": list(ALLOWED_CATEGORIES)},
        "lead": {"id": lead_id, "user_id": 7, "category": lead_category},
        "ai_profile": {},
        "playbook": {},
        "history": [],
        # payload comum em execuções reais
        "job": {
            "id": 123,
            "payload": {
                "job_id": 123,
                "lead_id": lead_id,
                "user_id": 7,
                # dependendo do extractor, ele pode buscar por um ou outro:
                "message_text": inbound_message_text,
                "inbound_message_text": inbound_message_text,
            },
        },
    }


def _scenario1(decision_engine):
    """
    inbound "oi": o LLM tenta sugerir categoria indevida, mas como next_action=ask_qualification,
    o sanitize deve zerar suggested_category e category_reason.
    """
    context = _make_context("oi", lead_id=1)

    def fake_mother(_prompt: str) -> str:
        return '{"route_to":"qualification","confidence":0.8,"reason":"precisa de contexto"}'

    def fake_child(_route: str, _prompt: str) -> str:
        return (
            '{"message_text":"Qual é o seu objetivo agora?",'
            '"did_complete_phase":false,'
            '"recommended_next_category":"apresentation",'
            '"outcome":null,'
            '"kanban_highlight":null,'
            '"signals":[],'
            '"confidence":0.9}'
        )

    decision_engine.llm_service.generate_mother_route = fake_mother
    decision_engine.llm_service.generate_child_result = fake_child
    decision = decision_engine.decide(context)

    assert decision.next_action == "ask_qualification"
    assert decision.suggested_category is None
    assert decision.category_reason is None
    print("OK: scenario1 ask_qualification clears category")


def _scenario2(decision_engine):
    """
    inbound com intenção forte, mas categoria inválida ("Marketing"):
    sanitize do executor deve zerar suggested_category e category_reason.
    """
    context = _make_context("quero fechar", lead_id=2, lead_category="apresentation")

    def fake_mother(_prompt: str) -> str:
        return '{"route_to":"apresentation","confidence":0.8,"reason":"intenção forte"}'

    def fake_child(_route: str, _prompt: str) -> str:
        return (
            '{"message_text":"Perfeito, vamos seguir.",'
            '"did_complete_phase":true,'
            '"recommended_next_category":"Marketing",'
            '"outcome":null,'
            '"kanban_highlight":null,'
            '"signals":[],'
            '"confidence":0.9}'
        )

    decision_engine.llm_service.generate_mother_route = fake_mother
    decision_engine.llm_service.generate_child_result = fake_child
    decision = decision_engine.decide(context)

    assert decision.next_action == "reply"
    assert decision.suggested_category is None
    assert decision.category_reason is None
    print("OK: scenario2 invalid category is sanitized by executor")


def _setup_minimal_crm_schema(conn: sqlite3.Connection) -> None:
    """
    Cria um schema mínimo + tolerante para o apply_suggested_category.
    Se o jobs_service tentar registrar logs com colunas extras comuns, o teste não quebra.
    """
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            category TEXT,
            lastMovement TEXT,
            updated_at TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            channel TEXT,
            message_id INTEGER,
            action TEXT,
            notes TEXT,
            user_id INTEGER,
            created_at TEXT,
            meta TEXT,
            instance_id TEXT,
            source TEXT
        )
        """
    )

    cur.execute(
        "INSERT INTO leads (id, user_id, category, lastMovement) VALUES (1, 7, 'to-prospect', NULL)"
    )
    conn.commit()


def _scenario3(jobs_service):
    """
    CRM nunca aplica categoria inválida.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    _setup_minimal_crm_schema(conn)
    cur = conn.cursor()

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
        "SELECT id FROM prospection_logs WHERE lead_id = 1 AND action = 'moved_stage'"
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
