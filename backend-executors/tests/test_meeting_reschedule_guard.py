"""Gestão pós-marcação: só se remarca para um horário que o lead pediu ou aceitou, livre e dentro
do horário do profissional."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.schemas.decision import DecisionOutput
from app.services import meeting_date_guard as mdg
from app.services import meeting_proposal as mp
from app.services import professional_hours
from app.services.decision_engine import _apply_meeting_reschedule_guard

TZ = "Europe/Lisbon"
_TODAY = mdg.local_today(TZ, datetime.now(timezone.utc))
ORIGINAL_DAY = _TODAY + timedelta(days=1)
DAY = _TODAY + timedelta(days=3)  # nunca hoje: as horas propostas estão sempre no futuro
DAY_WORD = mdg.WEEKDAY_NAMES_PT[DAY.weekday()]


def _at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo(TZ))


def _utc(dt):
    return dt.astimezone(timezone.utc).isoformat()


def _iso(day, hour, minute=0):
    return _at(day, hour, minute).strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture(autouse=True)
def _val_hours(monkeypatch):
    # Val atende das 11h às 17h no dia da remarcação e no dia da sessão original
    hours = {"Val": {DAY.weekday(): [(11 * 60, 17 * 60)], ORIGINAL_DAY.weekday(): [(11 * 60, 17 * 60)]}}
    monkeypatch.setattr(professional_hours, "get_hours", lambda *_a, **_k: hours)


def _context(inbound, history=()):
    return {
        "lead": {"id": 1, "user_id": 10},
        "ai_profile": {"timezone": TZ, "custom_instructions": "A Val atende das 11h às 17h."},
        "metadata": {"inbound_message_text": inbound},
        "history": [{"model": "inbound", "body": "Queria marcar com a Val"}, *history],
        "calendar_busy_slots": [
            {"id": 42, "lead_id": 1, "start_at": _utc(_at(ORIGINAL_DAY, 14)), "end_at": _utc(_at(ORIGINAL_DAY, 15))},
            {"id": None, "lead_id": None, "start_at": _utc(_at(DAY, 15)), "end_at": _utc(_at(DAY, 16))},
        ],
    }


def _decision(candidate, text):
    return DecisionOutput(
        next_action="reply",
        message_text=text,
        questions=[],
        reason="post_meeting_management",
        decision_trace={
            "effective_route_to": "meeting_management",
            "child_signals_structured": {
                "meeting_cancel_requested": False,
                "meeting_reschedule_requested": True,
                "meeting_datetime_candidate": candidate,
            },
        },
    )


def _run(inbound, candidate, text, history=()):
    decision = _decision(candidate, text)
    _apply_meeting_reschedule_guard(decision, _context(inbound, history))
    signals = decision.decision_trace["child_signals_structured"]
    return decision, signals, decision.decision_trace["meeting_reschedule_guard"]


PEDE_15H = f"Afinal preciso de remarcar para {DAY_WORD} às 15h"
CONTRAPROPOSTA = f"Esse horário já está ocupado. Podemos marcar a sessão para {DAY_WORD} às 16h? Que acha?"


def test_contraproposta_da_lara_nao_remarca_e_o_texto_segue():
    decision, signals, trace = _run(PEDE_15H, _iso(DAY, 16), CONTRAPROPOSTA)
    assert trace["origin"] == "counter_proposal"
    assert trace["blocked"] == "counter_proposal"
    assert signals["meeting_reschedule_requested"] is False
    assert signals["meeting_datetime_candidate"] is None
    assert decision.message_text == CONTRAPROPOSTA


def test_contraproposta_fora_do_horario_do_profissional_nao_remarca():
    text = CONTRAPROPOSTA.replace("16h", "16h15")
    _decision_, signals, trace = _run(PEDE_15H, _iso(DAY, 16, 15), text)
    assert trace["blocked"] == "outside_hours"
    assert signals["meeting_reschedule_requested"] is False


def test_horario_pedido_ocupado_nao_remarca_e_nao_chega_ao_crm():
    decision, signals, trace = _run(PEDE_15H, _iso(DAY, 15), CONTRAPROPOSTA)
    assert trace["origin"] == "lead_stated"
    assert trace["blocked"] == "busy"
    assert signals["meeting_reschedule_requested"] is False
    assert decision.message_text == CONTRAPROPOSTA


def test_lead_aceita_a_contraproposta_e_remarca():
    history = [{"model": "inbound", "body": PEDE_15H}, {"model": "outbound", "body": CONTRAPROPOSTA}]
    _decision_, signals, trace = _run("Pode ser", _iso(DAY, 16), "Remarcado!", history)
    assert trace["origin"] == "accepted"
    assert trace["blocked"] is None
    assert signals["meeting_reschedule_requested"] is True
    assert signals["meeting_datetime_candidate"] == _iso(DAY, 16)


def test_lead_pede_horario_livre_dentro_do_horario_remarca():
    _decision_, signals, trace = _run(f"Pode ser {DAY_WORD} às 12h?", _iso(DAY, 12), "Remarquei para as 12h.")
    assert trace["origin"] == "lead_stated"
    assert trace["blocked"] is None
    assert signals["meeting_reschedule_requested"] is True


def test_contraproposta_dada_como_feita_passa_a_pergunta():
    decision, signals, _trace = _run(PEDE_15H, _iso(DAY, 16), f"Remarquei a sua sessão para {DAY_WORD} às 16h.")
    assert signals["meeting_reschedule_requested"] is False
    assert decision.message_text.startswith("Posso remarcar a sua sessão para ")
    assert "16h" in decision.message_text
    assert "14h" in decision.message_text  # a sessão original mantém-se até confirmar


def test_horario_ocupado_dado_como_feito_passa_a_indisponivel():
    decision, signals, trace = _run(PEDE_15H, _iso(DAY, 15), f"Fica remarcado para {DAY_WORD} às 15h!")
    assert trace["blocked"] == "busy"
    assert signals["meeting_reschedule_requested"] is False
    assert decision.message_text.startswith("Peço desculpa, esse horário já não está disponível.")
    assert "mantém-se" in decision.message_text and "14h" in decision.message_text


def test_sem_pedido_de_remarcacao_nao_mexe():
    decision = _decision(None, "De nada!")
    decision.decision_trace["child_signals_structured"]["meeting_reschedule_requested"] = False
    _apply_meeting_reschedule_guard(decision, _context("Obrigada"))
    assert "meeting_reschedule_guard" not in decision.decision_trace


def test_announces_reschedule():
    assert mp.announces_reschedule("Remarquei para quinta")
    assert mp.announces_reschedule("A sessão fica marcada para quinta às 16h")
    assert not mp.announces_reschedule("Podemos marcar a sessão para quinta às 16h? Que acha?")


MANTEM = f"A sua sessão de {mdg.WEEKDAY_NAMES_PT[ORIGINAL_DAY.weekday()]} às 14h mantém-se até me dizer."
PROPOSTA_E_MANTEM = [
    {"model": "inbound", "body": PEDE_15H},
    {"model": "outbound", "body": f"{DAY_WORD} às 15h já está ocupado."},
    {"model": "outbound", "body": "Pode ser às 16h com a Val?"},
    {"model": "outbound", "body": MANTEM},
]


def test_aceita_a_hora_proposta_e_o_dia_e_o_da_proposta_nao_o_da_sessao_antiga():
    # a Filha juntou "16h" ao dia da sessão antiga; o lead aceitou a proposta de DAY às 16h
    decision, signals, trace = _run(
        "Pode ser às 16h", _iso(ORIGINAL_DAY, 16), "Fica então para as 16h. Posso confirmar?", PROPOSTA_E_MANTEM
    )
    assert trace["corrected_to"] == _iso(DAY, 16)
    assert trace["origin"] == "accepted"
    assert trace["blocked"] is None
    assert signals["meeting_reschedule_requested"] is True
    assert signals["meeting_datetime_candidate"] == _iso(DAY, 16)
    assert decision.message_text == mp.reschedule_done_text(
        mp.ProposedOption(start=_at(DAY, 16), professional="Val")
    )


def test_pode_ser_sozinho_nao_fica_ambiguo_com_a_sessao_que_se_mantem():
    _decision_, signals, trace = _run("Pode ser", _iso(DAY, 16), "Remarcado!", PROPOSTA_E_MANTEM)
    assert trace["origin"] == "accepted"
    assert trace["blocked"] is None
    assert signals["meeting_datetime_candidate"] == _iso(DAY, 16)


def test_remarcacao_que_segue_com_texto_a_pedir_confirmacao_passa_a_feita():
    decision, signals, _trace = _run(
        f"Pode ser {DAY_WORD} às 12h?", _iso(DAY, 12), "Fica então às 12h. Posso confirmar?"
    )
    assert signals["meeting_reschedule_requested"] is True
    assert decision.message_text.startswith("Combinado! A sua sessão fica remarcada para ")
