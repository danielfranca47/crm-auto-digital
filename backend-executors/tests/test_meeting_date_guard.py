"""Casos reais das transcrições PROD02/PROD03 da conta Sensi Vitae (25/10/2026, um domingo)."""
from datetime import datetime, timezone

import pytest

from app.services.meeting_date_guard import reconcile_meeting_date

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)  # domingo
TZ = "Europe/Lisbon"

CONFIRMACAO = (
    "Experiência Agendada ✨\nMassagem Terapêutica - 60 min\nHorário: 11h\n"
    "Dia: {dia}\nTerapeuta Val"
)


def _run(candidate, text, reference=None):
    return reconcile_meeting_date(candidate, text, day_reference=reference, tz_name=TZ, now_utc=NOW)


@pytest.mark.parametrize(
    "candidate,dia_escrito,reference,esperado_iso,esperado_dia",
    [
        # sexta → 28/10 (quarta)
        ("2026-10-28T11:00:00", "28/10 (sexta-feira)", "sexta-feira", "2026-10-30T11:00:00", "30/10 (sexta-feira)"),
        # sábado → 29/10 (quinta)
        ("2026-10-29T15:00:00", "29/10 (sábado)", "sábado", "2026-10-31T15:00:00", "31/10 (sábado)"),
        # terça (dita num domingo) → 31/10 (sábado): a terça certa é a próxima, 27/10
        ("2026-10-31T15:00:00", "31/10 (terça-feira)", "terça", "2026-10-27T15:00:00", "27/10 (terça-feira)"),
    ],
)
def test_dia_da_semana_certo_data_errada_corrige_candidato_e_texto(
    candidate, dia_escrito, reference, esperado_iso, esperado_dia
):
    result = _run(candidate, CONFIRMACAO.format(dia=dia_escrito), reference)
    assert result.candidate == esperado_iso
    assert f"Dia: {esperado_dia}" in result.message_text
    assert result.trace["applied"] is True


def test_sem_sinal_usa_dia_da_semana_colado_a_data():
    result = _run("2026-10-28T11:00:00", CONFIRMACAO.format(dia="28/10 (sexta-feira)"))
    assert result.candidate == "2026-10-30T11:00:00"
    assert "Dia: 30/10 (sexta-feira)" in result.message_text
    assert result.trace["reference_source"] == "message_text"


def test_amanha_com_dia_e_data_errados_corrige_os_dois():
    text = "Fica então quarta-feira, 28/10, às 11h, Massagem Relaxante de 60 min com a Val."
    result = _run("2026-10-28T11:00:00", text, "amanhã")
    assert result.candidate == "2026-10-26T11:00:00"
    assert result.message_text == "Fica então segunda-feira, 26/10, às 11h, Massagem Relaxante de 60 min com a Val."


def test_remarcacao_quinta_corrige_para_a_quinta_seguinte():
    text = "Posso confirmar a sua marcação para quinta-feira, 27/10, às 15h?"
    result = _run("2026-10-27T15:00:00", text, "quinta")
    assert result.candidate == "2026-10-29T15:00:00"
    assert "quinta-feira, 29/10" in result.message_text


@pytest.mark.parametrize(
    "candidate,text,reference",
    [
        ("2026-10-31T11:30:00", CONFIRMACAO.format(dia="31/10 (sábado)"), "sábado"),
        ("2026-10-26T11:00:00", "Fica então amanhã, 26/10, às 11h.", "amanhã"),
        ("2026-10-27T14:00:00", CONFIRMACAO.format(dia="27/10 (terça-feira)"), None),
        # "sexta da próxima semana" com a IA a acertar: a data já cai numa sexta → mantém
        ("2026-11-06T11:00:00", "Fica sexta-feira, 06/11, às 11h.", "sexta"),
    ],
)
def test_data_ja_certa_nao_muda(candidate, text, reference):
    result = _run(candidate, text, reference)
    assert result.candidate == candidate
    assert result.message_text == text
    assert result.trace["applied"] is False


def test_data_escrita_explicita_vence():
    result = _run("2026-10-28T11:00:00", "Fica dia 30/10 às 11h.", "30/10")
    assert result.candidate == "2026-10-30T11:00:00"


def test_sem_referencia_nao_mexe():
    text = "Fica marcado às 11h. Até amanhã!"
    result = _run("2026-10-28T11:00:00", text)
    assert result.candidate == "2026-10-28T11:00:00"
    assert result.message_text == text


def test_segunda_opcao_nao_e_dia_da_semana():
    text = "Combinado, fica a segunda opção, às 15h."
    result = _run("2026-10-28T15:00:00", text)
    assert result.candidate == "2026-10-28T15:00:00"


def test_candidato_com_offset_preserva_hora_e_offset():
    result = _run("2026-10-28T11:00:00+00:00", "Dia: 28/10 (sexta-feira)", "sexta")
    assert result.candidate == "2026-10-30T11:00:00+00:00"


def test_sem_candidato_nao_mexe():
    result = _run(None, "Dia: 28/10 (sexta-feira)", "sexta")
    assert result.candidate is None
    assert result.message_text == "Dia: 28/10 (sexta-feira)"


def test_data_por_extenso():
    result = _run("2026-10-28T11:00:00", "Fica sexta-feira, 28 de outubro, às 11h.", "sexta")
    assert result.message_text == "Fica sexta-feira, 30 de outubro, às 11h."


def test_decision_engine_corrige_o_que_o_meeting_scheduler_le(monkeypatch):
    from app.schemas.decision import DecisionOutput
    from app.services import decision_engine, meeting_date_guard

    monkeypatch.setattr(meeting_date_guard, "local_today", lambda tz, now=None: NOW.date())
    decision = DecisionOutput(
        next_action="reply",
        message_text=CONFIRMACAO.format(dia="28/10 (sexta-feira)"),
        questions=[],
        reason="route:agendamento",
        decision_trace={
            "meeting_scheduled": True,
            "child_signals_structured": {
                "meeting_proposed": True,
                "meeting_datetime_candidate": "2026-10-28T11:00:00",
                "meeting_day_reference": "sexta",
            },
        },
    )
    decision_engine._apply_meeting_date_guard(decision, {"ai_profile": {"timezone": TZ}})
    signals = decision.decision_trace["child_signals_structured"]
    assert signals["meeting_datetime_candidate"] == "2026-10-30T11:00:00"
    assert "Dia: 30/10 (sexta-feira)" in decision.message_text
    assert decision.decision_trace["meeting_date_guard"]["applied"] is True
