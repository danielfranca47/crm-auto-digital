import os
import sqlite3
import sys
import unittest

# Allow imports from backend-crm package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import ensure_jobs_tables
from services import rate_limit_service
from fastapi import HTTPException


class EnsureMaxAgentsLocalTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_jobs_tables(self.conn)
        self.entitlements = {"limits": {"max_agents_local": 1}}
        self.user_id = 123

    def tearDown(self):
        self.conn.close()

    def _insert_agent(self, agent_id: str, status: str = "offline"):
        self.conn.execute(
            "INSERT INTO agents (id, user_id, name, status) VALUES (?, ?, ?, ?)",
            (agent_id, self.user_id, agent_id, status),
        )
        self.conn.commit()

    def _revoke_agent(self, agent_id: str):
        """Soft delete an agent by setting revoked_at without altering status."""
        self.conn.execute(
            "UPDATE agents SET revoked_at=CURRENT_TIMESTAMP WHERE id=?",
            (agent_id,),
        )
        self.conn.commit()

    def test_revoked_agent_does_not_consume_quota(self):
        # First agent within quota
        rate_limit_service.ensure_max_agents_local(
            user_id=self.user_id,
            entitlements=self.entitlements,
            amount_to_add=1,
            conn=self.conn,
        )
        self._insert_agent("agent-1")

        # Revoke and ensure quota is freed
        self._revoke_agent("agent-1")
        # Status stays untouched (revoked_at alone frees the quota)
        status_row = self.conn.execute(
            "SELECT status FROM agents WHERE id=?",
            ("agent-1",),
        ).fetchone()
        self.assertEqual(status_row["status"], "offline")
        try:
            rate_limit_service.ensure_max_agents_local(
                user_id=self.user_id,
                entitlements=self.entitlements,
                amount_to_add=1,
                conn=self.conn,
            )
        except HTTPException as exc:  # pragma: no cover - clarity
            self.fail(f"Quota should be available after revocation: {exc}")

        # After provisioning replacement, quota should be consumed again
        self._insert_agent("agent-2")
        with self.assertRaises(HTTPException):
            rate_limit_service.ensure_max_agents_local(
                user_id=self.user_id,
                entitlements=self.entitlements,
                amount_to_add=1,
                conn=self.conn,
            )

    def test_limit_blocks_second_active_agent(self):
        self._insert_agent("agent-1")
        with self.assertRaises(HTTPException):
            rate_limit_service.ensure_max_agents_local(
                user_id=self.user_id,
                entitlements=self.entitlements,
                amount_to_add=1,
                conn=self.conn,
            )

    def test_disabled_agent_does_not_consume_quota(self):
        self._insert_agent("agent-1", status="disabled")
        # Disabled agent should not block creating a new one under the quota
        rate_limit_service.ensure_max_agents_local(
            user_id=self.user_id,
            entitlements=self.entitlements,
            amount_to_add=1,
            conn=self.conn,
        )


if __name__ == "__main__":
    unittest.main()
