from datetime import datetime, timezone

from app.schemas.decision import DecisionOutput
from app.services import meeting_scheduler


def _build_context(tz_name: str):
    return {
        "lead": {"id": 10, "user_id": 20},
        "job": {"id": 30, "payload": {}},
        "ai_profile": {"agent_mode": "agenda", "timezone": tz_name},
        "metadata": {"inbound_message_text": "amanhã às 10"},
        "history": [{"body": "dia 12/12 às 09:00"}],
    }


def _build_decision(candidate: str | None):
    return DecisionOutput(
        next_action="reply",
        message_text="ok",
        reason="meeting_scheduled",
        decision_trace={
            "meeting_scheduled": True,
            "child_signals_structured": {
                "meeting_proposed": True,
                "meeting_datetime_candidate": candidate,
            },
        },
    )


def test_parse_meeting_candidate_naive_europe_lisbon():
    now_utc = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    parsed = meeting_scheduler.parse_meeting_candidate(
        "2026-03-05T17:00:00",
        tz_name="Europe/Lisbon",
        now_utc=now_utc,
    )

    assert parsed == datetime(2026, 3, 5, 17, 0, tzinfo=timezone.utc)


def test_parse_meeting_candidate_naive_america_sao_paulo():
    now_utc = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    parsed = meeting_scheduler.parse_meeting_candidate(
        "2026-03-05T17:00:00",
        tz_name="America/Sao_Paulo",
        now_utc=now_utc,
    )

    assert parsed == datetime(2026, 3, 5, 20, 0, tzinfo=timezone.utc)


def test_parse_meeting_candidate_aware_offset_is_respected():
    now_utc = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    parsed = meeting_scheduler.parse_meeting_candidate(
        "2026-03-05T17:00:00+01:00",
        tz_name="Asia/Tokyo",
        now_utc=now_utc,
    )

    assert parsed == datetime(2026, 3, 5, 16, 0, tzinfo=timezone.utc)


def test_extract_meeting_signal_invalid_candidate_falls_back(monkeypatch):
    context = _build_context("Europe/Lisbon")
    decision = _build_decision("not-a-date")

    def fake_extract_start_at(metadata, history, *, tz_name=None, now_utc=None):
        assert tz_name == "Europe/Lisbon"
        assert now_utc is not None
        return datetime(2026, 3, 5, 13, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(meeting_scheduler, "extract_start_at", fake_extract_start_at)

    signal = meeting_scheduler._extract_meeting_signal(context, decision)

    assert signal.start_at == datetime(2026, 3, 5, 13, 0, tzinfo=timezone.utc)


def test_extract_meeting_signal_past_candidate_falls_back(monkeypatch):
    context = _build_context("Europe/Lisbon")
    decision = _build_decision("2020-03-05T10:00:00Z")

    monkeypatch.setattr(
        meeting_scheduler,
        "extract_start_at",
        lambda *args, **kwargs: datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc),
    )
    signal = meeting_scheduler._extract_meeting_signal(context, decision)

    assert signal.start_at == datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc)


def test_extract_meeting_signal_uses_candidate_without_fallback(monkeypatch):
    context = _build_context("Europe/Lisbon")
    decision = _build_decision("2099-03-05T17:00:00")

    def fail_extract_start_at(*args, **kwargs):
        raise AssertionError("fallback should not be called when candidate is valid")

    monkeypatch.setattr(meeting_scheduler, "extract_start_at", fail_extract_start_at)
    signal = meeting_scheduler._extract_meeting_signal(context, decision)

    assert signal.start_at == datetime(2099, 3, 5, 17, 0, tzinfo=timezone.utc)


def test_extract_meeting_signal_missing_candidate_does_not_fallback(monkeypatch):
    """Filha não confirmou nenhum horário (ex.: negou o horário pedido) — não deve adivinhar
    via heurística de texto. Ver docs/implementations/fix-compromisso-fantasma-negacao-horario-disponivel.md."""
    context = _build_context("Europe/Lisbon")
    decision = _build_decision(None)

    def fail_extract_start_at(*args, **kwargs):
        raise AssertionError("fallback should not be called when candidate is absent")

    monkeypatch.setattr(meeting_scheduler, "extract_start_at", fail_extract_start_at)
    signal = meeting_scheduler._extract_meeting_signal(context, decision)

    assert signal.start_at is None
