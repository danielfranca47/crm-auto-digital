import sqlite3
import sys
import types


if "fastapi" not in sys.modules:
    fastapi_module = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi_module.HTTPException = HTTPException
    sys.modules["fastapi"] = fastapi_module

from services.lead_category_policy import apply_closing_bot_disable_side_effect
from services import jobs_service


def _mk_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            category TEXT,
            bot_disabled INTEGER DEFAULT 0,
            bot_disabled_reason TEXT,
            lastMovement TEXT
        );

        CREATE TABLE prospection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lead_id INTEGER NOT NULL,
            channel TEXT NULL,
            message_id INTEGER NULL,
            action TEXT NOT NULL,
            notes TEXT,
            createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute("INSERT INTO leads (id, user_id, category, bot_disabled) VALUES (1, 7, 'qualification', 0)")
    conn.commit()
    return conn


def test_helper_idempotent() -> None:
    conn = _mk_conn()
    changed = apply_closing_bot_disable_side_effect(
        conn,
        lead_id=1,
        user_id=7,
        old_category="qualification",
        new_category="closing",
    )
    assert changed is True

    changed_again = apply_closing_bot_disable_side_effect(
        conn,
        lead_id=1,
        user_id=7,
        old_category="qualification",
        new_category="closing",
    )
    assert changed_again is False

    lead = conn.execute("SELECT category, bot_disabled FROM leads WHERE id=1").fetchone()
    assert lead["bot_disabled"] == 1
    logs = conn.execute("SELECT action, notes FROM prospection_logs WHERE lead_id=1 ORDER BY id").fetchall()
    assert len(logs) == 1
    assert logs[0]["action"] == "bot_disabled_changed"
    assert 'category_closing' in (logs[0]["notes"] or "")
    conn.close()


def test_apply_suggested_category_triggers_side_effect() -> None:
    conn = _mk_conn()
    ok = jobs_service.apply_suggested_category(
        conn,
        lead_id=1,
        user_id=7,
        suggested_category="closing",
        reason="lead pediu proposta",
        inbound_message_text="quero fechar hoje",
    )
    assert ok is True

    lead = conn.execute("SELECT category, bot_disabled FROM leads WHERE id=1").fetchone()
    assert lead["category"] == "closing"
    assert lead["bot_disabled"] == 1

    logs = conn.execute("SELECT action, notes FROM prospection_logs WHERE lead_id=1 ORDER BY id").fetchall()
    actions = [row["action"] for row in logs]
    assert "moved_stage" in actions
    assert "bot_disabled_changed" in actions
    conn.close()


if __name__ == "__main__":
    test_helper_idempotent()
    test_apply_suggested_category_triggers_side_effect()
    print("OK: category closing side effects")
