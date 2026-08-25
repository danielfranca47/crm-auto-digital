import sqlite3

from services.lead_category_policy import (
    apply_disqualified_bot_disable_side_effect,
    apply_prospect_refused_bot_disable_side_effect,
)


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


def test_disqualified_disables_bot_and_is_idempotent() -> None:
    conn = _mk_conn()
    changed = apply_disqualified_bot_disable_side_effect(
        conn, lead_id=1, user_id=7, old_category="qualification", new_category="disqualified"
    )
    assert changed is True

    changed_again = apply_disqualified_bot_disable_side_effect(
        conn, lead_id=1, user_id=7, old_category="qualification", new_category="disqualified"
    )
    assert changed_again is False

    lead = conn.execute("SELECT bot_disabled, bot_disabled_reason FROM leads WHERE id=1").fetchone()
    assert lead["bot_disabled"] == 1
    assert lead["bot_disabled_reason"] == "category_disqualified"

    logs = conn.execute("SELECT action FROM prospection_logs WHERE lead_id=1").fetchall()
    assert len(logs) == 1
    assert logs[0]["action"] == "bot_disabled_changed"


def test_prospect_refused_disables_bot_and_is_idempotent() -> None:
    conn = _mk_conn()
    changed = apply_prospect_refused_bot_disable_side_effect(
        conn, lead_id=1, user_id=7, old_category="to-prospect", new_category="prospect-refused"
    )
    assert changed is True

    changed_again = apply_prospect_refused_bot_disable_side_effect(
        conn, lead_id=1, user_id=7, old_category="to-prospect", new_category="prospect-refused"
    )
    assert changed_again is False

    lead = conn.execute("SELECT bot_disabled, bot_disabled_reason FROM leads WHERE id=1").fetchone()
    assert lead["bot_disabled"] == 1
    assert lead["bot_disabled_reason"] == "category_prospect_refused"


def test_no_op_when_category_not_target() -> None:
    conn = _mk_conn()
    changed = apply_disqualified_bot_disable_side_effect(
        conn, lead_id=1, user_id=7, old_category="qualification", new_category="apresentation"
    )
    assert changed is False
    changed = apply_prospect_refused_bot_disable_side_effect(
        conn, lead_id=1, user_id=7, old_category="qualification", new_category="apresentation"
    )
    assert changed is False

    lead = conn.execute("SELECT bot_disabled FROM leads WHERE id=1").fetchone()
    assert lead["bot_disabled"] == 0


if __name__ == "__main__":
    test_disqualified_disables_bot_and_is_idempotent()
    test_prospect_refused_disables_bot_and_is_idempotent()
    test_no_op_when_category_not_target()
    print("OK: category_disqualified / category_prospect_refused side effects")
