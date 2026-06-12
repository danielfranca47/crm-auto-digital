import os
import sqlite3
import sys
import unittest

# Allow imports from backend-crm package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import ensure_jobs_tables
from routes.usage import build_usage_payload
from services import rate_limit_service


class UsageEndpointTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_jobs_tables(self.conn)
        rate_limit_service._ensure_usage_table(self.conn)
        rate_limit_service._ensure_usage_monthly_table(self.conn)

        self.entitlements = {
            "limits": {
                "max_leads": 5,
                "max_agents_local": 3,
                "max_copy_generation_monthly": 10,
                "max_prospects_daily": 4,
                "max_whatsapp_send_daily": 2,
                "max_maps_search_daily": 6,
                "max_maps_enrich_daily": None,
            }
        }
        self.user_id = 42

        # Minimal leads table for counting
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER)"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_leads_usage_counts_total_and_remaining(self):
        # Two leads for the current user and one for another user
        self.conn.executemany(
            "INSERT INTO leads (user_id) VALUES (?)",
            [(self.user_id,), (self.user_id,), (9999,)],
        )
        self.conn.commit()

        usage = build_usage_payload(
            conn=self.conn, entitlements=self.entitlements, user_id=self.user_id
        )

        self.assertEqual(usage["leads"], {"total": 2, "limit": 5, "remaining": 3})

    def test_agents_active_ignores_revoked_and_disabled(self):
        # Active agent
        self.conn.execute(
            "INSERT INTO agents (id, user_id, name, status) VALUES (?, ?, ?, ?)",
            ("a1", self.user_id, "A1", "offline"),
        )
        # Revoked agent
        self.conn.execute(
            "INSERT INTO agents (id, user_id, name, status, revoked_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("a2", self.user_id, "A2", "offline"),
        )
        # Disabled agent
        self.conn.execute(
            "INSERT INTO agents (id, user_id, name, status) VALUES (?, ?, ?, ?)",
            ("a3", self.user_id, "A3", "disabled"),
        )
        self.conn.commit()

        usage = build_usage_payload(
            conn=self.conn, entitlements=self.entitlements, user_id=self.user_id
        )

        self.assertEqual(
            usage["agents"], {"active": 1, "limit": 3, "remaining": 2}
        )

    def test_daily_usage_defaults_to_zero(self):
        usage = build_usage_payload(
            conn=self.conn, entitlements=self.entitlements, user_id=self.user_id
        )

        daily = usage["daily"]
        self.assertEqual(
            daily["max_prospects_daily"], {"used": 0, "limit": 4, "remaining": 4}
        )
        self.assertEqual(
            daily["max_whatsapp_send_daily"], {"used": 0, "limit": 2, "remaining": 2}
        )
        self.assertEqual(
            daily["max_maps_enrich_daily"], {"used": 0, "limit": None, "remaining": None}
        )

    def test_zero_limit_returns_zero_remaining(self):
        entitlements = {"limits": {"max_leads": 0, "max_prospects_daily": 0}}

        usage = build_usage_payload(
            conn=self.conn, entitlements=entitlements, user_id=self.user_id
        )

        self.assertEqual(
            usage["leads"], {"total": 0, "limit": 0, "remaining": 0}
        )
        self.assertEqual(
            usage["daily"]["max_prospects_daily"],
            {"used": 0, "limit": 0, "remaining": 0},
        )


if __name__ == "__main__":
    unittest.main()
