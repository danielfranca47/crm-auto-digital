"""Horário de atendimento da Sensi Vitae (instruções da conta): Val seg–sáb 11h–17h, Daniel
seg–sex 11h–19h30; 17h / 19h30 são as horas em que as sessões têm de ACABAR."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services import llm_service, professional_hours
from app.services.requested_slot import RequestedSlot, build_agenda_fact_block

TZ = ZoneInfo("Europe/Lisbon")
SENSI = {
    "professionals": [
        {"name": "Val", "days": {d: [["11:00", "17:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat")}},
        {"name": "Daniel", "days": {d: [["11:00", "19:30"]] for d in ("mon", "tue", "wed", "thu", "fri")}},
    ]
}
HOURS = professional_hours.parse_hours(SENSI)


def _at(day, hour, minute=0, duration=60):
    start = datetime(2026, 10, day, hour, minute, tzinfo=TZ)
    return start, start + timedelta(minutes=duration)


def test_parse_hours():
    assert HOURS["Val"][5] == [(660, 1020)]  # sábado 11h–17h
    assert 5 not in HOURS["Daniel"]
    assert 6 not in HOURS["Val"]


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"professionals": "x"}, {"professionals": [{"name": "Val", "days": {"mon": [["17:00", "11:00"]]}}]},
     {"professionals": [{"name": "Val", "days": {"segunda": [["11:00", "17:00"]]}}]}],
)
def test_parse_hours_invalido(payload):
    assert professional_hours.parse_hours(payload) is None


def test_sabado_11h_cabe_com_a_val():
    v = professional_hours.check(HOURS, *_at(31, 11))
    assert v.fits and v.fitting == ["Val"]


def test_val_17h_para_1h_nao_cabe_e_sugere_16h():
    v = professional_hours.check(HOURS, *_at(29, 17), professional="Val")
    assert not v.fits
    assert v.suggestion.strftime("%H:%M") == "16:00" and v.suggestion_for == "Val"


def test_quinta_17h_sem_nomear_cabe_com_o_daniel():
    v = professional_hours.check(HOURS, *_at(29, 17))
    assert v.fits and v.fitting == ["Daniel"]


def test_lomi_90_terca_14h_cabe():
    assert professional_hours.check(HOURS, *_at(27, 14, duration=90), professional="Val").fits


def test_21h_nao_cabe_e_sugere_o_ultimo_inicio():
    v = professional_hours.check(HOURS, *_at(29, 21))
    assert not v.fits
    assert v.suggestion.strftime("%H:%M") == "18:30" and v.suggestion_for == "Daniel"


def test_9h_nao_cabe_e_sugere_11h():
    v = professional_hours.check(HOURS, *_at(30, 9))
    assert not v.fits and v.suggestion.strftime("%H:%M") == "11:00"


def test_domingo_sem_atendimento():
    v = professional_hours.check(HOURS, *_at(25, 11))
    assert not v.fits and v.suggestion is None


def test_profissional_nomeado():
    assert professional_hours.mentioned_professional(HOURS, ["Pode ser às 15h?", "Quero com a Val"]) == "Val"
    assert professional_hours.mentioned_professional(HOURS, ["Pode ser às 15h?"]) is None


def test_get_hours_le_uma_vez_por_texto(monkeypatch):
    calls = []

    def fake(prompt, ai_profile=None):
        calls.append(prompt)
        return json.dumps(SENSI)

    monkeypatch.setattr(llm_service, "generate_professional_hours", fake)
    profile = {"custom_instructions": "Val seg–sáb 11h–17h; Daniel seg–sex 11h–19h30."}
    assert professional_hours.get_hours(profile) == HOURS
    assert professional_hours.get_hours(profile) == HOURS
    assert len(calls) == 1
    professional_hours.get_hours({"custom_instructions": "texto diferente"})
    assert len(calls) == 2


def test_get_hours_falha_fica_sem_tabela(monkeypatch):
    def boom(prompt, ai_profile=None):
        raise RuntimeError("rede")

    monkeypatch.setattr(llm_service, "generate_professional_hours", boom)
    assert professional_hours.get_hours({"custom_instructions": "Val 11h–17h"}) is None


def test_get_hours_sem_texto_nao_chama():
    assert professional_hours.get_hours({}) is None


def _slot(day, hour, duration=60):
    start, end = _at(day, hour, duration=duration)
    return RequestedSlot(start=start, end=end, free=True, duration_known=True)


def test_bloco_livre_e_dentro_do_horario():
    slot = _slot(31, 11)
    block = build_agenda_fact_block(slot, professional_hours.check(HOURS, slot.start, slot.end))
    assert "Horário de atendimento: a sessão cabe (Val: sábado 11h–17h)" in block
    assert "O horário está LIVRE com Val. Aceite-o" in block


def test_bloco_fora_do_horario():
    slot = _slot(29, 17)
    block = build_agenda_fact_block(slot, professional_hours.check(HOURS, slot.start, slot.end, "Val"))
    assert "FORA — Val atende quinta-feira 11h–17h, e esta sessão não cabe nesse horário" in block
    assert "proponha 16h com Val" in block
    assert "Não diga que está ocupado" in block


def test_prompt_de_agendamento_traz_o_veredicto(monkeypatch):
    from app.services.decision_engine import _build_child_prompt_agendamento
    from app.services.orchestrator_models import MotherDecision

    monkeypatch.setattr(llm_service, "generate_professional_hours", lambda prompt, ai_profile=None: json.dumps(SENSI))
    inbound = "Queria uma massagem relaxante clássica de 1h com a Val na quinta às 17h."
    context = {
        "lead": {"id": 1, "category": "agendamento"},
        "ai_profile": {"agent_mode": "agenda", "timezone": "Europe/Lisbon", "custom_instructions": "Val seg–sáb 11h–17h"},
        "playbook": {}, "metadata": {"inbound_message_text": inbound}, "history": [], "calendar_busy_slots": [],
    }
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    prompt = _build_child_prompt_agendamento(context, inbound, mother)
    assert "Horário de atendimento: FORA — Val atende quinta-feira 11h–17h" in prompt
    assert "proponha 16h com Val" in prompt


def test_bloco_dia_sem_atendimento():
    slot = _slot(25, 11)
    block = build_agenda_fact_block(slot, professional_hours.check(HOURS, slot.start, slot.end))
    assert "domingo não há atendimento (Val nem Daniel)" in block
    assert "proponha outro dia" in block
