from datetime import datetime, timedelta, timezone
import os
import sys
import importlib.util

CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from database import get_connection, init_db
APPOINTMENT_OUTCOMES_PATH = os.path.join(ROOT_DIR, "services", "appointment_outcomes.py")
spec = importlib.util.spec_from_file_location("appointment_outcomes", APPOINTMENT_OUTCOMES_PATH)
appointment_outcomes = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(appointment_outcomes)
apply_outcome = appointment_outcomes.apply_outcome


class OutcomePayload:
    def __init__(
        self,
        *,
        outcome: str,
        note: str | None = None,
        reschedule_start_at: datetime | None = None,
        reschedule_end_at: datetime | None = None,
        reactivate_bot: bool = True,
        move_lead_to: str | None = None,
    ) -> None:
        self.outcome = outcome
        self.note = note
        self.reschedule_start_at = reschedule_start_at
        self.reschedule_end_at = reschedule_end_at
        self.reactivate_bot = reactivate_bot
        self.move_lead_to = move_lead_to


def _create_lead(conn, user_id: int) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO leads (user_id, companyName, contactName, phone, email, origin, category, customMessage, observations, priority)
        VALUES (?, 'Empresa Teste', 'Contato', '000', 'teste@example.com', 'Manual', 'apresentation', '', '', 1)
        """,
        (user_id,),
    )
    conn.commit()
    return int(cur.lastrowid)


def _create_appointment(conn, lead_id: int, start_at: datetime) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO appointments (lead_id, title, description, type, start_at, end_at, status, created_at, updated_at)
        VALUES (?, 'Reunião', 'Teste', 'meeting', ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (lead_id, start_at.isoformat(), start_at.isoformat()),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_rescheduled_and_no_show() -> None:
    init_db()
    user_id = 999
    with get_connection() as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(appointments)")}
        for required in ("outcome", "outcome_note", "outcome_at"):
            assert required in cols, f"missing column: {required}"
    with get_connection() as conn:
        lead_id = _create_lead(conn, user_id)
        appointment_id = _create_appointment(conn, lead_id, datetime.now(timezone.utc) + timedelta(days=1))

    new_start = datetime.now(timezone.utc) + timedelta(days=3)
    payload = OutcomePayload(
        outcome="rescheduled",
        reschedule_start_at=new_start,
        reactivate_bot=False,
    )
    with get_connection() as conn:
        apply_outcome(conn, appointment_id=appointment_id, user_id=user_id, payload=payload)
        conn.commit()

    with get_connection() as conn:
        row = conn.execute("SELECT status, outcome FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        assert row["status"] == "pending"
        assert row["outcome"] == "rescheduled"

        appointment_id_2 = _create_appointment(
            conn, lead_id, datetime.now(timezone.utc) + timedelta(days=2)
        )

    payload_no_show = OutcomePayload(
        outcome="no_show",
        reactivate_bot=False,
    )
    with get_connection() as conn:
        apply_outcome(conn, appointment_id=appointment_id_2, user_id=user_id, payload=payload_no_show)
        conn.commit()

    with get_connection() as conn:
        row = conn.execute("SELECT status, outcome FROM appointments WHERE id = ?", (appointment_id_2,)).fetchone()
        assert row["status"] == "completed"
        assert row["outcome"] == "no_show"


if __name__ == "__main__":
    test_rescheduled_and_no_show()
    print("ok")
