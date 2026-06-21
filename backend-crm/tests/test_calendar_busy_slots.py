import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai_orchestrator.orchestrator import (
    ContextBundle,
    _load_calendar_busy_slots,
    enrich_context_bundle,
)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            companyName TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            user_id INTEGER,
            start_at TEXT,
            end_at TEXT,
            status TEXT
        );

        CREATE TABLE business_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            field_key TEXT,
            label TEXT,
            value TEXT,
            enabled INTEGER,
            sort_order INTEGER
        );
        """
    )
    conn.commit()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class LoadCalendarBusySlotsTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.conn.close()

    def _insert_lead(self, user_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO leads (user_id, companyName) VALUES (?, 'ACME')", (user_id,))
        self.conn.commit()
        return int(cur.lastrowid)

    def _insert_appointment(self, *, lead_id, user_id, start_at, end_at, status="pending"):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO appointments (lead_id, user_id, start_at, end_at, status) VALUES (?, ?, ?, ?, ?)",
            (lead_id, user_id, _iso(start_at), _iso(end_at), status),
        )
        self.conn.commit()

    def test_crm_sourced_appointment_included(self):
        lead_id = self._insert_lead(user_id=1)
        self._insert_appointment(
            lead_id=lead_id, user_id=None,
            start_at=self.now + timedelta(days=1), end_at=self.now + timedelta(days=1, hours=1),
        )
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            slots = _load_calendar_busy_slots(user_id=1)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["lead_id"], lead_id)

    def test_google_sourced_appointment_included(self):
        self._insert_appointment(
            lead_id=None, user_id=1,
            start_at=self.now + timedelta(days=2), end_at=self.now + timedelta(days=2, hours=1),
        )
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            slots = _load_calendar_busy_slots(user_id=1)
        self.assertEqual(len(slots), 1)
        self.assertIsNone(slots[0]["lead_id"])

    def test_other_user_excluded(self):
        lead_id = self._insert_lead(user_id=2)
        self._insert_appointment(
            lead_id=lead_id, user_id=None,
            start_at=self.now + timedelta(days=1), end_at=self.now + timedelta(days=1, hours=1),
        )
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            slots = _load_calendar_busy_slots(user_id=1)
        self.assertEqual(slots, [])

    def test_canceled_status_excluded(self):
        lead_id = self._insert_lead(user_id=1)
        self._insert_appointment(
            lead_id=lead_id, user_id=None,
            start_at=self.now + timedelta(days=1), end_at=self.now + timedelta(days=1, hours=1),
            status="canceled",
        )
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            slots = _load_calendar_busy_slots(user_id=1)
        self.assertEqual(slots, [])

    def test_outside_window_excluded(self):
        lead_id = self._insert_lead(user_id=1)
        self._insert_appointment(
            lead_id=lead_id, user_id=None,
            start_at=self.now + timedelta(days=60), end_at=self.now + timedelta(days=60, hours=1),
        )
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            slots = _load_calendar_busy_slots(user_id=1, window_days=30)
        self.assertEqual(slots, [])


class EnrichContextBundleCalendarTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _bundle(self, agent_mode: str) -> ContextBundle:
        return ContextBundle(
            user_id=1,
            ai_profile={"agent_mode": agent_mode},
            playbook={},
            lead={},
            history=[],
            metadata={},
        )

    def test_populated_for_agenda_mode(self):
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(self._bundle("agenda"), user_id=1)
        self.assertIsNotNone(enriched.calendar_busy_slots)

    def test_not_populated_for_other_modes(self):
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(self._bundle("direto"), user_id=1)
        self.assertIsNone(enriched.calendar_busy_slots)


class EnrichContextBundleBotDisabledTest(unittest.TestCase):
    """Paridade Playground <-> executor real para bot_disabled_reason='meeting_scheduled'.

    O Playground monta o ContextBundle sem passar por routes/executor.py (que seta
    bot_disabled/bot_disabled_reason no metadata só para o fluxo real) — sem esta
    propagação em enrich_context_bundle, o Playground nunca exercitaria o caminho de
    gestão pós-confirmação (_decide_post_meeting_management em decision_engine.py).
    """

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _bundle(self, lead: dict, ai_profile: Optional[dict] = None) -> ContextBundle:
        return ContextBundle(
            user_id=1,
            ai_profile=ai_profile if ai_profile is not None else {"agent_mode": "agenda"},
            playbook={},
            lead=lead,
            history=[],
            metadata={},
        )

    def test_propagates_when_reason_is_meeting_scheduled(self):
        bundle = self._bundle({"bot_disabled": 1, "bot_disabled_reason": "meeting_scheduled"})
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(bundle, user_id=1)
        self.assertTrue(enriched.metadata.get("bot_disabled"))
        self.assertEqual(enriched.metadata.get("bot_disabled_reason"), "meeting_scheduled")

    def test_does_not_propagate_for_other_reasons(self):
        bundle = self._bundle({"bot_disabled": 1, "bot_disabled_reason": "handoff_requested"})
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(bundle, user_id=1)
        self.assertNotIn("bot_disabled", enriched.metadata)

    def test_does_not_propagate_when_bot_not_disabled(self):
        bundle = self._bundle({"bot_disabled": 0, "bot_disabled_reason": None})
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(bundle, user_id=1)
        self.assertNotIn("bot_disabled", enriched.metadata)

    def test_does_not_propagate_when_meeting_management_disabled(self):
        bundle = self._bundle(
            {"bot_disabled": 1, "bot_disabled_reason": "meeting_scheduled"},
            ai_profile={"agent_mode": "agenda", "meeting_management_enabled": False},
        )
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(bundle, user_id=1)
        self.assertNotIn("bot_disabled", enriched.metadata)

    def test_propagates_when_meeting_management_explicitly_enabled(self):
        bundle = self._bundle(
            {"bot_disabled": 1, "bot_disabled_reason": "meeting_scheduled"},
            ai_profile={"agent_mode": "agenda", "meeting_management_enabled": True},
        )
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(bundle, user_id=1)
        self.assertTrue(enriched.metadata.get("bot_disabled"))
        self.assertEqual(enriched.metadata.get("bot_disabled_reason"), "meeting_scheduled")


if __name__ == "__main__":
    unittest.main()
