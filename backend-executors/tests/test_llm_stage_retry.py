"""Novas tentativas da Mãe/Filha antes do handoff por llm_failure.

Cada etapa (Mãe ou Filha) repete só a si mesma até 4 tentativas no total — falha de
rede/timeout/429/5xx, JSON inválido ou ValidationError — e só a 4.ª falha leva ao
handoff. Ver docs/architecture/llm-architecture.md, secção "Falhas da IA e novas tentativas".
"""

import logging

import httpx
import pytest

from app.services import decision_engine

MOTHER_OK = '{"route_to":"apresentation","perceived_category":"qualification","confidence":0.9,"reason":"agendamento"}'
CHILD_OK = '{"message_text":"Perfeito, vamos agendar.","did_complete_phase":false,"recommended_next_category":"apresentation","outcome":null,"kanban_highlight":null,"signals":[],"confidence":0.8}'
# As duas formas de ValidationError vistas no Playground em 26/10/2026.
MOTHER_BAD_ROUTE = '{"route_to":"recepcao_x","confidence":0.9,"reason":"x"}'
CHILD_NO_CONFIDENCE = '{"message_text":"O horário fica para amanhã."}'

AGENDA_REQUIRED_FIELDS = [
    {"key": "service_interest", "mode": "required"},
    {"key": "availability_window", "mode": "required"},
    {"key": "price_acceptance", "mode": "required"},
]


def _context():
    return {
        "lead": {"category": "qualification"},
        "ai_profile": {"agent_mode": "agenda", "qualification_fields": AGENDA_REQUIRED_FIELDS},
        "playbook": {},
        "metadata": {"inbound_message_text": "podemos agendar"},
        "history": [{"model": "outbound", "body": "Oi! Tudo bem?"}],
        "qualification_state": {
            "exists": True,
            "data_json": {
                "service_interest": "botox",
                "availability_window": "amanhã 10h",
                "location_preference": "presencial",
                "price_acceptance": "yes",
            },
            "attempts_json": {},
            "last_questioned_field": None,
        },
    }


def _status_error(code):
    request = httpx.Request("POST", "https://llm.test")
    return httpx.HTTPStatusError("error", request=request, response=httpx.Response(code, request=request))


class _FakeLlm:
    """Devolve (ou levanta) os itens da lista por ordem; o último repete-se."""

    def __init__(self, items):
        self.items = list(items)
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(kwargs)
        item = self.items[min(len(self.calls), len(self.items)) - 1]
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(decision_engine.time, "sleep", lambda _seconds: None)


def _patch(monkeypatch, mother_items, child_items):
    mother = _FakeLlm(mother_items)
    child = _FakeLlm(child_items)
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", lambda _p, **kw: mother(**kw))
    monkeypatch.setattr(decision_engine.llm_service, "generate_child_result", lambda _r, _p, **kw: child(**kw))
    return mother, child


@pytest.mark.parametrize("failures", [1, 2, 3])
def test_mother_recovers_after_n_failures(monkeypatch, failures):
    mother, child = _patch(monkeypatch, ["not json"] * failures + [MOTHER_OK], [CHILD_OK])

    decision = decision_engine.decide(_context())

    assert decision.next_action == "reply"
    assert len(mother.calls) == failures + 1
    assert len(child.calls) == 1


def test_mother_fourth_failure_goes_to_handoff(monkeypatch):
    mother, child = _patch(monkeypatch, ["not json"] * 4 + [MOTHER_OK], [CHILD_OK])

    decision = decision_engine.decide(_context())

    assert decision.next_action == "handoff"
    assert decision.reason == "llm_failure"
    assert len(mother.calls) == 4
    assert child.calls == []


@pytest.mark.parametrize("failures", [1, 2, 3])
def test_child_recovers_after_n_failures_without_calling_mother_again(monkeypatch, failures):
    mother, child = _patch(monkeypatch, [MOTHER_OK], [CHILD_NO_CONFIDENCE] * failures + [CHILD_OK])

    decision = decision_engine.decide(_context())

    assert decision.next_action == "reply"
    assert len(child.calls) == failures + 1
    assert len(mother.calls) == 1


def test_child_fourth_failure_goes_to_handoff(monkeypatch):
    mother, child = _patch(monkeypatch, [MOTHER_OK], [CHILD_NO_CONFIDENCE] * 4 + [CHILD_OK])

    decision = decision_engine.decide(_context())

    assert decision.next_action == "handoff"
    assert decision.reason == "llm_failure"
    assert len(child.calls) == 4
    assert len(mother.calls) == 1


def test_mixed_failure_types_share_one_counter(monkeypatch):
    mother, _child = _patch(
        monkeypatch,
        [httpx.ReadTimeout("timed out"), _status_error(503), MOTHER_BAD_ROUTE, MOTHER_OK],
        [CHILD_OK],
    )

    decision = decision_engine.decide(_context())

    assert decision.next_action == "reply"
    assert len(mother.calls) == 4


def test_non_retryable_status_goes_to_handoff_without_retry(monkeypatch):
    mother, _child = _patch(monkeypatch, [_status_error(400), MOTHER_OK], [CHILD_OK])

    decision = decision_engine.decide(_context())

    assert decision.next_action == "handoff"
    assert len(mother.calls) == 1


def test_stage_calls_disable_inner_http_retry(monkeypatch):
    mother, child = _patch(monkeypatch, [MOTHER_OK], [CHILD_OK])

    decision_engine.decide(_context())

    assert mother.calls[0]["max_attempts"] == 1
    assert child.calls[0]["max_attempts"] == 1


def test_budget_caps_call_timeout_and_stops_retries(monkeypatch):
    monkeypatch.setattr(decision_engine.settings, "llm_decision_budget_seconds", 4)
    mother, _child = _patch(monkeypatch, ["not json", MOTHER_OK], [CHILD_OK])

    decision = decision_engine.decide(_context())

    # 4s de orçamento: a chamada não pode esperar os 20s normais, e depois da 1.ª falha
    # não sobra tempo para outra (mínimo de 5s por chamada) — handoff.
    assert mother.calls[0]["timeout_seconds"] <= 4
    assert decision.next_action == "handoff"
    assert len(mother.calls) == 1


def test_retry_and_exhausted_events_are_logged(monkeypatch, caplog):
    _patch(monkeypatch, ["not json"] * 4, [CHILD_OK])
    test_logger = logging.getLogger("test_llm_stage_retry")

    with caplog.at_level(logging.WARNING, logger="test_llm_stage_retry"):
        decision_engine.decide(_context(), logger=test_logger)

    messages = [record.getMessage() for record in caplog.records]
    assert sum("event=llm_stage_retry stage=mother" in m for m in messages) == 3
    assert any("event=llm_stage_exhausted stage=mother attempts=4/4 reason=invalid_json limit=max_attempts" in m for m in messages)
    assert any("event=llm_orchestrator_error stage=mother_parse" in m for m in messages)


def test_route_to_apresentacao_alias_is_accepted(monkeypatch):
    mother, _child = _patch(
        monkeypatch,
        ['{"route_to":"apresentacao","perceived_category":"qualification","confidence":0.9,"reason":"x"}'],
        [CHILD_OK],
    )

    decision = decision_engine.decide(_context())

    assert decision.next_action == "reply"
    assert len(mother.calls) == 1
