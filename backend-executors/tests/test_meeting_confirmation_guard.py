"""Turno da confirmação: o candidato gravado tem de ser o horário que o lead aceitou."""
from datetime import date, datetime, timedelta, timezone

from app.schemas.decision import DecisionOutput
from app.services import meeting_proposal as mp
from app.services.decision_engine import (
    _apply_meeting_confirmation_guard,
    _build_child_prompt_pre_agendamento,
)
from app.services.orchestrator_models import MotherDecision

NOW = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)  # segunda-feira
TZ = "Europe/Lisbon"
PROS = ["Val", "Daniel"]

RECIBO = (
    "Experiência Agendada ✨\nMassagem Terapêutica - 60 min\nHorário: 18h30\n"
    "Dia: 29/10 (quinta-feira)\nTerapeuta Daniel"
)


def _accepted(history, inbound):
    proposal = mp.last_proposal(history, inbound, tz_name=TZ, now_utc=NOW, professionals=PROS)
    return mp.accepted_slot(inbound, proposal, tz_name=TZ, now_utc=NOW, professionals=PROS)


def _reconcile(candidate, text, accepted):
    return mp.reconcile_confirmation(candidate, text, accepted, tz_name=TZ, now_utc=NOW, professionals=PROS)


SEGUNDA_PROPOSTA = [
    {"model": "outbound", "body": "Posso agendar quinta-feira às 18h30 com o Daniel?"},
    {"model": "inbound", "body": "Epa, não dá. Pode ser na sexta às 9h?"},
    {"model": "outbound", "body": "O primeiro horário disponível é na sexta-feira às 11h com a Val. Pode ser esse?"},
]


def test_candidato_da_proposta_recusada_e_corrigido_com_o_texto():
    result = _reconcile("2026-10-29T18:30:00", RECIBO, _accepted(SEGUNDA_PROPOSTA, "Pode ser sim, marca aí!"))
    assert result.candidate == "2026-10-30T11:00:00"
    assert "Horário: 11h" in result.message_text
    assert "Dia: 30/10 (sexta-feira)" in result.message_text
    assert "Terapeuta Val" in result.message_text
    assert result.trace["action"] == "corrected"
    assert not result.blocked


def test_candidato_em_falta_e_preenchido_com_o_aceite():
    result = _reconcile(None, "Experiência Agendada ✨", _accepted(SEGUNDA_PROPOSTA, "Sim, pode confirmar!"))
    assert result.candidate == "2026-10-30T11:00:00"
    assert result.trace["action"] == "filled"


def test_candidato_certo_fica_igual():
    result = _reconcile("2026-10-30T11:00:00", "ok", _accepted(SEGUNDA_PROPOSTA, "Sim"))
    assert result.trace["action"] == "ok"
    assert result.candidate == "2026-10-30T11:00:00"


def test_candidato_com_fuso_tambem_e_comparado_na_hora_local():
    result = _reconcile("2026-10-30T11:00:00+00:00", "ok", _accepted(SEGUNDA_PROPOSTA, "Sim"))
    assert result.trace["action"] == "ok"  # Lisboa = UTC no fim de outubro


DUAS = [{"model": "outbound", "body": "Tenho quinta às 11h com a Val ou às 15h com o Daniel. Qual prefere?"}]


def test_duas_opcoes_sem_escolha_nao_grava_e_pergunta():
    result = _reconcile(None, "Experiência Agendada ✨", _accepted(DUAS, "Pode marcar!"))
    assert result.blocked
    assert result.candidate is None
    assert "Experiência Agendada" not in result.message_text
    assert result.message_text.startswith("Só para confirmar: prefere quinta-feira, 29/10, às 11h com Val ou")


def test_duas_opcoes_candidato_igual_a_uma_delas_segue():
    result = _reconcile("2026-10-29T15:00:00", "ok", _accepted(DUAS, "Pode marcar!"))
    assert result.trace["action"] == "ok"


def test_pedido_novo_do_cliente_nao_e_mexido():
    result = _reconcile("2026-10-29T17:00:00", "ok", _accepted(DUAS, "Não dá, pode ser às 17h?"))
    assert result.trace["action"] == "skip"
    assert result.candidate == "2026-10-29T17:00:00"


# --- integração com o decision_engine -------------------------------------------------------

def _context(category="agendamento", inbound="Pode ser sim, marca aí!"):
    return {
        "lead": {"id": 1, "category": category},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler", "timezone": TZ},
        "playbook": {"template_key": "hybrid_scheduler"},
        "metadata": {"inbound_message_text": inbound},
        "history": [
            {"model": "outbound", "body": "Posso agendar para amanhã às 18h30?"},
            {"model": "inbound", "body": "Não dá, e depois de amanhã às 9h?"},
            {"model": "outbound", "body": "Às 9h está fora do horário. Tenho depois de amanhã às 11h. Pode ser?"},
        ],
    }


def _decision(candidate, *, scheduled=True, phase_entry=False):
    return DecisionOutput(
        next_action="reply",
        message_text="Experiência Agendada ✨",
        questions=[],
        reason="ok",
        decision_trace={
            "meeting_scheduled": scheduled,
            "is_phase_entry": phase_entry,
            "child_signals_structured": {"meeting_datetime_candidate": candidate},
        },
    )


def _iso(days, hour):
    from app.services.meeting_date_guard import local_today

    day = local_today(TZ) + timedelta(days=days)
    return f"{day.isoformat()}T{hour}:00"


def test_guard_corrige_o_candidato_antes_do_meeting_scheduler():
    decision = _decision(_iso(1, "18:30"))
    _apply_meeting_confirmation_guard(decision, _context())
    signals = decision.decision_trace["child_signals_structured"]
    assert signals["meeting_datetime_candidate"] == _iso(2, "11:00")
    assert decision.decision_trace["meeting_confirmation_guard"]["action"] == "corrected"


def test_guard_preenche_candidato_que_a_filha_nao_devolveu():
    decision = _decision(None)
    _apply_meeting_confirmation_guard(decision, _context(category="pre-agendamento"))
    assert decision.decision_trace["child_signals_structured"]["meeting_datetime_candidate"] == _iso(2, "11:00")
    assert decision.decision_trace["meeting_scheduled"] is True


def test_guard_nao_corre_sem_meeting_scheduled_ou_na_entrada_da_fase():
    for decision in (_decision(_iso(1, "18:30"), scheduled=False), _decision(_iso(1, "18:30"), phase_entry=True)):
        _apply_meeting_confirmation_guard(decision, _context())
        assert decision.decision_trace["child_signals_structured"]["meeting_datetime_candidate"] == _iso(1, "18:30")
        assert "meeting_confirmation_guard" not in decision.decision_trace


def test_guard_bloqueia_e_desliga_meeting_scheduled_com_opcoes_em_aberto():
    context = _context(inbound="Pode marcar!")
    context["history"] = [{"model": "outbound", "body": "Tenho amanhã às 11h ou às 15h. Qual prefere?"}]
    decision = _decision(None)
    _apply_meeting_confirmation_guard(decision, context)
    assert decision.decision_trace["meeting_scheduled"] is False
    assert decision.decision_trace["child_signals_structured"]["meeting_datetime_candidate"] is None
    assert decision.message_text.startswith("Só para confirmar: prefere")


# --- prompt de pré-agendamento ----------------------------------------------------------------

_BOOKED = MotherDecision(
    route_to="pre-agendamento", perceived_category="pre-agendamento", confidence=0.9, reason="ok",
    signals={"meeting_scheduled": True},
)


def test_pre_agendamento_confirmacao_recebe_o_horario_aceite_e_o_candidato_no_schema():
    context = _context(category="pre-agendamento")
    prompt = _build_child_prompt_pre_agendamento(context, "Pode ser sim, marca aí!", _BOOKED)
    assert "MARCAÇÃO JÁ GRAVADA NESTE TURNO" in prompt
    assert f'meeting_datetime_candidate="{_iso(2, "11:00")}"' in prompt
    assert "SINAIS DA MARCAÇÃO" in prompt


def test_pre_agendamento_sem_horario_proposto_fica_como_estava():
    context = _context(category="pre-agendamento")
    context["history"] = [{"model": "outbound", "body": "Posso mandar-lhe mensagem na quinta de manhã?"}]
    prompt = _build_child_prompt_pre_agendamento(context, "Sim", _BOOKED)
    assert "MARCAÇÃO JÁ GRAVADA" not in prompt
    assert "SINAIS DA MARCAÇÃO" not in prompt


def test_agendamento_bloco_diz_qual_horario_foi_aceite():
    from app.services.decision_engine import _build_child_prompt_agendamento

    booked = MotherDecision(
        route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok",
        signals={"meeting_scheduled": True},
    )
    prompt = _build_child_prompt_agendamento(_context(), "Pode ser sim, marca aí!", booked)
    assert "O lead aceitou o horário da última proposta:" in prompt
    assert f'meeting_datetime_candidate="{_iso(2, "11:00")}"' in prompt
