from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.clients import crm_client
from app.runners import whatsapp as runner


@dataclass
class _DummyDecision:
    next_action: str = "reply"
    reason: str = "ok"
    message_text: str = "Mensagem de follow-up"
    suggested_category: str | None = None
    category_reason: str | None = None
    outcome: str | None = None
    kanban_highlight: str | None = None
    signals: List[str] = field(default_factory=list)
    confidence: float = 0.9
    decision_trace: Dict[str, Any] = field(default_factory=dict)
    questions: List[str] = field(default_factory=list)

    def model_dump(self) -> Dict[str, Any]:
        return {
            "next_action": self.next_action,
            "reason": self.reason,
            "message_text": self.message_text,
            "suggested_category": self.suggested_category,
            "category_reason": self.category_reason,
            "outcome": self.outcome,
            "kanban_highlight": self.kanban_highlight,
            "signals": self.signals,
            "confidence": self.confidence,
            "decision_trace": self.decision_trace,
            "questions": self.questions,
        }


def test_followup_tick_job_uses_synthetic_in_reply_and_completes(monkeypatch):
    calls: Dict[str, Any] = {}

    def _claim_job(job_id: str, lease_owner: str, ttl_seconds: int):
        return {"job": {"id": int(job_id), "attempts": 1}, "normalized": {"attempts": 1}}

    def _get_job(job_id: str):
        return {
            "id": int(job_id),
            "type": "whatsapp.followup.tick",
            "status": "pending",
            "payload": {"lead_id": 10, "user_id": 99, "due_at": "2026-01-01T10:00:00Z"},
            "attempts": 1,
        }

    def _get_ctx(job_id: str):
        return {
            "job": {"id": int(job_id), "payload": {"lead_id": 10, "user_id": 99}},
            "lead": {"id": 10, "user_id": 99, "phone": "+5511999999999", "contactName": "Maria"},
            "history": [],
            "ai_profile": {},
            "playbook": {},
            "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        }

    def _register_outbound(payload: Dict[str, Any]):
        calls["outbound_payload"] = payload
        return {
            "status": "already_sent",
            "outbound_event_status": "sent",
            "provider_message_id": "pmid-1",
            "outbound_event_id": 1,
            "message_id": 12,
        }

    monkeypatch.setattr(runner.crm_client, "claim_job", _claim_job)
    monkeypatch.setattr(runner.crm_client, "get_job", _get_job)
    monkeypatch.setattr(runner.crm_client, "get_whatsapp_execution_context", _get_ctx)
    monkeypatch.setattr(runner.decision_engine, "decide", lambda context, logger=None: _DummyDecision())
    monkeypatch.setattr(runner.meeting_scheduler, "handle_meeting_scheduled", lambda context, decision, logger=None: None)
    monkeypatch.setattr(runner.crm_client, "register_whatsapp_outbound", _register_outbound)
    monkeypatch.setattr(runner.crm_client, "complete_job", lambda job_id, result: {"ok": True})

    rc = runner.execute_job("123", runner.logging.getLogger("test"))
    assert rc == 0
    assert calls["outbound_payload"]["in_reply_to_message_id"] == "followup:123:2026-01-01T10:00:00Z"


def test_followup_tick_job_fail_reports_retryable(monkeypatch):
    fail_calls: Dict[str, Any] = {}

    monkeypatch.setattr(
        runner.crm_client,
        "claim_job",
        lambda job_id, lease_owner, ttl_seconds: {"job": {"id": int(job_id), "attempts": 1}, "normalized": {"attempts": 1}},
    )
    monkeypatch.setattr(
        runner.crm_client,
        "get_job",
        lambda job_id: {
            "id": int(job_id),
            "type": "whatsapp.followup.tick",
            "status": "pending",
            "payload": {"lead_id": 10, "user_id": 99, "due_at": "2026-01-01T10:00:00Z"},
            "attempts": 1,
        },
    )
    monkeypatch.setattr(
        runner.crm_client,
        "get_whatsapp_execution_context",
        lambda job_id: {
            "job": {"id": int(job_id), "payload": {"lead_id": 10, "user_id": 99}},
            "lead": {"id": 10, "user_id": 99, "phone": "+5511999999999"},
            "history": [],
            "ai_profile": {},
            "playbook": {},
            "metadata": {"provider": "uazapi", "instance_id": "inst-1"},
        },
    )
    monkeypatch.setattr(runner.decision_engine, "decide", lambda context, logger=None: _DummyDecision())
    monkeypatch.setattr(runner.meeting_scheduler, "handle_meeting_scheduled", lambda context, decision, logger=None: None)

    def _raise_reserve(payload: Dict[str, Any]):
        raise crm_client.CRMClientError("transient", status_code=503, error_type="network")

    monkeypatch.setattr(runner.crm_client, "register_whatsapp_outbound", _raise_reserve)

    def _fail_job(job_id: str, error: str, details: Dict[str, Any] | None = None):
        fail_calls["details"] = details
        return {"ok": True}

    monkeypatch.setattr(runner.crm_client, "fail_job", _fail_job)

    rc = runner.execute_job("123", runner.logging.getLogger("test"))
    assert rc == 1
    assert fail_calls["details"]["retryable"] is True
