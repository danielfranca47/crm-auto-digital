import importlib.util
import os
import sqlite3
import sys
import types
from datetime import datetime


def _install_fastapi_stub() -> None:
    if "fastapi" in sys.modules:
        return

    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            def deco(fn):
                return fn

            return deco

        def post(self, *args, **kwargs):
            def deco(fn):
                return fn

            return deco

        def patch(self, *args, **kwargs):
            def deco(fn):
                return fn

            return deco

        def delete(self, *args, **kwargs):
            def deco(fn):
                return fn

            return deco

    def Depends(_dep):
        return None

    fastapi_module = types.ModuleType("fastapi")
    fastapi_module.HTTPException = HTTPException
    fastapi_module.APIRouter = APIRouter
    fastapi_module.Depends = Depends
    sys.modules["fastapi"] = fastapi_module


def _install_security_stub() -> None:
    module = types.ModuleType("security_core")

    class CurrentUser:
        def __init__(self, id: int):
            self.id = id

    def require_crm_access():
        return CurrentUser(1)

    module.CurrentUser = CurrentUser
    module.require_crm_access = require_crm_access
    sys.modules["security_core"] = module


def _install_models_stub() -> None:
    module = types.ModuleType("models")

    class _PayloadBase:
        def __init__(self, **kwargs):
            self._data = kwargs

        def dict(self, exclude_unset: bool = False):
            if exclude_unset:
                return {k: v for k, v in self._data.items() if v is not None}
            return dict(self._data)

    class Lead:
        pass

    class LeadUpdate(_PayloadBase):
        pass

    class AppointmentCreate(_PayloadBase):
        pass

    class AppointmentUpdate(_PayloadBase):
        pass

    class BotDisabledUpdate(_PayloadBase):
        pass

    module.Lead = Lead
    module.LeadUpdate = LeadUpdate
    module.AppointmentCreate = AppointmentCreate
    module.AppointmentUpdate = AppointmentUpdate
    module.BotDisabledUpdate = BotDisabledUpdate
    sys.modules["models"] = module


def _load_module():
    _install_fastapi_stub()
    _install_security_stub()
    _install_models_stub()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    module_path = os.path.join(repo_root, "routes", "leads.py")
    spec = importlib.util.spec_from_file_location("leads_route", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _mk_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            companyName TEXT,
            contactName TEXT,
            phone TEXT,
            email TEXT,
            origin TEXT,
            category TEXT,
            customMessage TEXT,
            observations TEXT,
            priority INTEGER,
            lastMovement TEXT,
            createdAt TEXT,
            bot_disabled INTEGER DEFAULT 0,
            bot_disabled_reason TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY,
            lead_id INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            type TEXT,
            start_at TEXT NOT NULL,
            end_at TEXT,
            status TEXT,
            location TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO leads (id, user_id, companyName, category, createdAt, lastMovement) VALUES (1, 1, 'ACME', 'qualification', '2026-01-01T10:00:00', '2026-01-01T10:00:00')"
    )
    conn.execute(
        "INSERT INTO appointments (id, lead_id, title, start_at, end_at, status, created_at, updated_at) VALUES (10, 1, 'Reunião', '2026-02-11T15:00:00+00:00', '2026-02-11T15:00:00+00:00', 'pending', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
    )
    conn.commit()
    return conn


def test_empty_lead_patch_stays_400(mod):
    conn = _mk_conn()
    mod.get_connection = lambda: conn

    LeadUpdate = sys.modules["models"].LeadUpdate
    CurrentUser = sys.modules["security_core"].CurrentUser

    try:
        mod.atualizar_lead_parcial(1, LeadUpdate(), CurrentUser(1))
        raise AssertionError("Expected HTTPException for empty payload")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400, f"status_code inesperado: {getattr(exc, 'status_code', None)}"
        assert "Nenhum dado" in str(getattr(exc, "detail", ""))
    finally:
        conn.close()


def test_appointment_patch_without_end_sets_end_to_start(mod):
    conn = _mk_conn()
    mod.get_connection = lambda: conn

    AppointmentUpdate = sys.modules["models"].AppointmentUpdate
    CurrentUser = sys.modules["security_core"].CurrentUser

    result = mod.atualizar_compromisso(
        1,
        10,
        AppointmentUpdate(start_at=datetime.fromisoformat("2026-02-12T15:00:00+00:00")),
        CurrentUser(1),
    )

    assert result["start_at"] == result["end_at"], f"start/end incoerentes: {result['start_at']} != {result['end_at']}"
    conn.close()


if __name__ == "__main__":
    module = _load_module()
    test_empty_lead_patch_stays_400(module)
    test_appointment_patch_without_end_sets_end_to_start(module)
    print("OK: leads patch regressions")
