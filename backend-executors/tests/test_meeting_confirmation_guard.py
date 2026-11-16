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


# --- Fase 2: duração por saber ------------------------------------------------------------------

# formato em que o orchestrator do CRM entrega a tabela (structured_v1 já renderizado)
TABELA = "- Massagem Relaxante — 60min: 75 €\n- Massagem Relaxante — 90min: 95 €\n- Massagem Terapêutica — 60min: 75 €"
FORA_HORARIO = [
    {"model": "outbound", "body": "A Val atende das 11h às 17h. Posso agendar para segunda-feira às 11h?"},
]


def test_missing_duration_so_quando_a_tabela_tem_varias_e_ninguem_disse():
    assert mp.missing_duration(["11h na segunda tá bom!"], "Posso agendar para segunda às 11h?", TABELA) == [60, 90]
    assert mp.missing_duration(["Quero terapêutica de 1h"], "", TABELA) is None
    assert mp.missing_duration(["Sim"], "Posso agendar a massagem de 90 min na segunda às 11h?", TABELA) is None
    assert mp.missing_duration(["Sim"], "", "Massagem — 60 min 75€") is None
    assert mp.missing_duration(["Sim"], "", "") is None


def test_duracao_por_saber_nao_grava_e_pergunta_quando_a_filha_confirmou():
    accepted = _accepted(FORA_HORARIO, "Ok, 11h na segunda tá bom! Pode marcar.")
    result = mp.reconcile_confirmation(
        "2026-11-02T11:00:00", "Experiência Agendada ✨\nMassagem Relaxante - 60 min", accepted,
        tz_name=TZ, now_utc=NOW, professionals=PROS, missing_durations=[60, 90],
    )
    assert result.blocked and result.candidate is None
    assert result.trace["action"] == "blocked_duration"
    assert result.message_text == (
        "Para fechar a marcação de segunda-feira, 02/11, às 11h: que serviço e que duração "
        "prefere (60 ou 90 min)?"
    )


def test_duracao_por_saber_mantem_a_pergunta_da_filha():
    accepted = _accepted(FORA_HORARIO, "Pode marcar.")
    pergunta = "Ótimo! Prefere a relaxante ou a terapêutica, e de 60 ou 90 minutos?"
    result = mp.reconcile_confirmation(
        None, pergunta, accepted, tz_name=TZ, now_utc=NOW, professionals=PROS, missing_durations=[60, 90]
    )
    assert result.blocked
    assert result.message_text == pergunta


def _context_tabela():
    context = _context(inbound="Pode ser sim, marca aí!")
    context["history"] = [{"model": "outbound", "body": "Tenho depois de amanhã às 11h. Pode ser?"}]
    context["knowledge_items"] = {"service_pricing_table": TABELA}
    return context


def test_guard_com_tabela_de_varias_duracoes_desliga_meeting_scheduled():
    decision = _decision(_iso(2, "11:00"))
    _apply_meeting_confirmation_guard(decision, _context_tabela())
    assert decision.decision_trace["meeting_scheduled"] is False
    assert decision.decision_trace["meeting_scheduled_blocked"] == "missing_duration"
    assert decision.decision_trace["child_signals_structured"]["meeting_datetime_candidate"] is None


def test_bloco_pede_servico_e_duracao_em_vez_de_confirmar():
    from app.services.decision_engine import _build_child_prompt_agendamento

    booked = MotherDecision(
        route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok",
        signals={"meeting_scheduled": True},
    )
    prompt = _build_child_prompt_agendamento(_context_tabela(), "Pode ser sim, marca aí!", booked)
    assert "FALTA SABER O SERVIÇO E A DURAÇÃO" in prompt
    assert "MARCAÇÃO JÁ GRAVADA NESTE TURNO" not in prompt


# --- duração já conhecida passa para a marcação ------------------------------------------

def test_known_duration_le_o_lead_a_proposta_e_ignora_o_que_nao_esta_na_tabela():
    assert mp.known_duration(["Sim, pode confirmar", "Quero a de 90 minutos"], "", TABELA) == (90, "lead_earlier")
    assert mp.known_duration(["Sim"], "Posso marcar a relaxante de 90 min às 14h?", TABELA) == (90, "proposal")
    assert mp.known_duration(["Afinal 60 min", "Quero 90 minutos"], "", TABELA) == (60, "lead_now")
    assert mp.known_duration(["Sim, chego 10 min antes"], "", TABELA) == (None, None)
    assert mp.known_duration(["Sim"], "Tenho a de 60 min ou a de 90 min às 14h", TABELA) == (None, None)
    assert mp.known_duration(["Quero 45 min"], "", "") == (45, "lead_now")


def _context_90(inbound="Sim, pode confirmar"):
    context = _context(inbound=inbound)
    context["history"] = [
        {"model": "inbound", "body": "Olá, queria uma massagem relaxante de 90 minutos"},
        {"model": "outbound", "body": "Tenho depois de amanhã às 11h. Pode ser?"},
    ]
    context["knowledge_items"] = {"service_pricing_table": TABELA}
    return context


def test_guard_preenche_a_duracao_que_o_lead_disse_e_a_filha_nao_devolveu():
    decision = _decision(_iso(2, "11:00"))
    _apply_meeting_confirmation_guard(decision, _context_90())
    trace = decision.decision_trace
    assert trace["meeting_scheduled"] is True
    assert trace["child_signals_structured"]["meeting_duration_minutes"] == 90
    assert trace["meeting_confirmation_guard"]["duration_filled"] == 90
    assert trace["meeting_confirmation_guard"]["duration_source"] == "lead_earlier"


def test_guard_mantem_a_duracao_da_filha_e_regista_a_do_lead():
    decision = _decision(_iso(2, "11:00"))
    decision.decision_trace["child_signals_structured"]["meeting_duration_minutes"] = 60
    _apply_meeting_confirmation_guard(decision, _context_90())
    trace = decision.decision_trace
    assert trace["child_signals_structured"]["meeting_duration_minutes"] == 60
    assert trace["meeting_confirmation_guard"]["duration_lead"] == 90
    assert "duration_filled" not in trace["meeting_confirmation_guard"]


def test_guard_sem_duracao_dita_deixa_a_por_omissao():
    decision = _decision(_iso(2, "11:00"))
    _apply_meeting_confirmation_guard(decision, _context())
    assert "meeting_duration_minutes" not in decision.decision_trace["child_signals_structured"]


def test_known_duration_le_primeiro_o_recibo_da_filha():
    recibo = "Experiência Agendada ✨\nMassagem Relaxante - 90 min\nHorário: 11h"
    assert mp.known_duration(["Sim, pode confirmar", "Quero a de 60 min"], "", TABELA, recibo) == (90, "reply")
    assert mp.known_duration(["Quero a de 60 min"], "", TABELA, "Chegue 10 min antes") == (60, "lead_now")


# --- serviço + duração fora da tabela → handoff -------------------------------------------

TABELA_SENSI = (
    "## Massagens\n"
    "- Massagem Clássica, Desportiva ou Terapêutica — 20min: 45 € (Sessão localizada)\n"
    "- Massagem Clássica, Desportiva ou Terapêutica — 30min: 55 €\n"
    "- Massagem Clássica, Desportiva ou Terapêutica — 45min: 65 €\n"
    "- Massagem Clássica, Desportiva ou Terapêutica — 60min: 75 €\n"
    "- Massagem Relaxante Exótica (Lomi Lomi) — 45min: 75 €\n"
    "- Massagem Relaxante Exótica (Lomi Lomi) — 60min: 85 €\n"
    "- Massagem Relaxante Exótica (Lomi Lomi) — 90min: 110 €"
)


def test_service_fits_confere_a_linha_e_a_duracao():
    rows = mp.pricing_rows(TABELA_SENSI)
    assert rows["Massagem Relaxante Exótica (Lomi Lomi)"] == [45, 60, 90]
    assert mp.service_fits(rows, "Massagem Clássica, Desportiva ou Terapêutica", 90) == "off_table"
    assert mp.service_fits(rows, "Massagem Clássica, Desportiva ou Terapêutica", 60) == "ok"
    assert mp.service_fits(rows, "Massagem Terapêutica", 60) == "ok"
    assert mp.service_fits(rows, "Lomi Lomi", 90) == "ok"
    assert mp.service_fits(rows, "fora_da_tabela", None) == "off_table"
    assert mp.service_fits(rows, None, 90) is None
    assert mp.service_fits({}, "Lomi Lomi", 90) is None


def test_service_fits_pelo_numero_da_linha():
    rows = mp.pricing_rows(TABELA_SENSI)
    assert mp.service_fits(rows, 1, 90) == "off_table"
    assert mp.service_fits(rows, 1, 60) == "ok"
    assert mp.service_fits(rows, "2", 90) == "ok"
    assert mp.service_fits(rows, 5, 60) is None
    assert mp.service_fits(rows, True, 60) is None


def test_service_fits_nome_proprio_da_conta_nao_faz_handoff_errado():
    # a conta chama "Relaxante Clássica" à Clássica: bate nas duas linhas — só a duração decide
    rows = mp.pricing_rows(TABELA_SENSI)
    assert mp.service_fits(rows, "Massagem Relaxante Clássica", 60) == "ok"
    assert mp.service_fits(rows, "Massagem Relaxante Clássica", 120) == "off_table"
    assert mp.service_fits(rows, "Massagem Tailandesa", 60) == "off_table"
    assert mp.service_fits(rows, "Massagem", 60) == "ok"


def _context_sensi(service_text):
    context = _context(inbound="Sim, pode confirmar")
    context["history"] = [
        {"model": "inbound", "body": f"Queria uma {service_text} de 90 minutos"},
        {"model": "outbound", "body": "Tenho depois de amanhã às 11h. Pode ser?"},
    ]
    context["knowledge_items"] = {"service_pricing_table": TABELA_SENSI}
    return context


def test_guard_classica_de_90_min_nao_grava_e_passa_para_a_equipa():
    decision = _decision(_iso(2, "11:00"))
    decision.decision_trace["child_signals_structured"]["meeting_service"] = (
        "Massagem Clássica, Desportiva ou Terapêutica"
    )
    _apply_meeting_confirmation_guard(decision, _context_sensi("massagem clássica"))
    trace = decision.decision_trace
    assert decision.next_action == "handoff"
    assert decision.reason == "service_not_in_table"
    assert trace["meeting_scheduled"] is False
    assert trace["meeting_scheduled_blocked"] == "service_not_in_table"
    assert trace["meeting_confirmation_guard"]["service_check"] == "off_table"


def test_guard_lomi_lomi_de_90_min_grava():
    decision = _decision(_iso(2, "11:00"))
    decision.decision_trace["child_signals_structured"]["meeting_service"] = 2
    _apply_meeting_confirmation_guard(decision, _context_sensi("Lomi Lomi"))
    trace = decision.decision_trace
    assert decision.next_action == "reply"
    assert trace["meeting_scheduled"] is True
    assert trace["child_signals_structured"]["meeting_duration_minutes"] == 90
    assert trace["meeting_confirmation_guard"]["service_check"] == "ok"


def test_service_in_text_so_com_uma_linha_nomeada():
    rows = mp.pricing_rows(TABELA_SENSI)
    assert mp.service_in_text(rows, "Experiência Agendada ✨\nMassagem Clássica - 90 min") == (
        "Massagem Clássica, Desportiva ou Terapêutica"
    )
    assert mp.service_in_text(rows, "Massagem Relaxante Exótica - 90 min\nTerapeuta Val") == (
        "Massagem Relaxante Exótica (Lomi Lomi)"
    )
    assert mp.service_in_text(rows, "Massagem Relaxante Clássica - 60 min") is None
    assert mp.service_in_text(rows, "Experiência Agendada ✨") is None


def test_guard_sem_meeting_service_le_o_recibo_e_passa_para_a_equipa():
    decision = _decision(_iso(2, "11:00"))
    decision.message_text = "Experiência Agendada ✨\nMassagem Clássica - 90 min\nHorário: 11h"
    _apply_meeting_confirmation_guard(decision, _context_sensi("massagem clássica"))
    guard = decision.decision_trace["meeting_confirmation_guard"]
    assert decision.next_action == "handoff"
    assert guard["service_source"] == "reply"
    assert guard["service_check"] == "off_table"


def test_guard_recibo_ambiguo_nao_decide_e_grava():
    decision = _decision(_iso(2, "11:00"))
    decision.message_text = "Experiência Agendada ✨\nMassagem Relaxante Clássica - 60 min"
    _apply_meeting_confirmation_guard(decision, _context_sensi("massagem relaxante"))
    assert decision.next_action == "reply"
    assert decision.decision_trace["meeting_scheduled"] is True


def test_off_table_request():
    rows = mp.pricing_rows(TABELA_SENSI)
    assert mp.off_table_request(rows, "Quero a clássica de 90 minutos, por favor. Marca assim!")
    assert not mp.off_table_request(rows, "Quero a clássica de 60 minutos")
    assert not mp.off_table_request(rows, "Quero uma relaxante de 90 minutos")
    assert not mp.off_table_request(rows, "Quero a relaxante clássica de 90 minutos")  # ambíguo


def _reply(text="A Clássica vai só até 1h. Pode ser a Lomi Lomi de 90 min?"):
    return DecisionOutput(next_action="reply", message_text=text, questions=[], reason="ok", decision_trace={})


def _context_insiste(inbound, earlier):
    context = _context(inbound=inbound)
    context["history"] = [{"model": "inbound", "body": earlier}, {"model": "outbound", "body": "A Clássica vai só até 1h."}]
    context["knowledge_items"] = {"service_pricing_table": TABELA_SENSI}
    return context


def test_lead_que_insiste_fora_da_tabela_passa_para_a_equipa():
    from app.services.decision_engine import _apply_off_table_insistence_guard

    decision = _reply()
    _apply_off_table_insistence_guard(
        decision, _context_insiste("Quero mesmo a clássica de 90 minutos!", "Queria uma massagem clássica de 90 minutos")
    )
    assert decision.next_action == "handoff"
    assert decision.reason == "service_not_in_table_insisted"
    assert decision.decision_trace["meeting_scheduled"] is False


def test_primeiro_pedido_fora_da_tabela_ou_aceitar_a_alternativa_nao_passa():
    from app.services.decision_engine import _apply_off_table_insistence_guard

    primeira = _reply()
    context = _context_insiste("Queria uma massagem clássica de 90 minutos", "Olá")
    _apply_off_table_insistence_guard(primeira, context)
    assert primeira.next_action == "reply"

    aceita = _reply("Ótimo!")
    _apply_off_table_insistence_guard(
        aceita, _context_insiste("Então a Lomi Lomi de 90 minutos", "Queria uma massagem clássica de 90 minutos")
    )
    assert aceita.next_action == "reply"

    # o histórico com a própria mensagem atual não conta como "já tinha pedido"
    repetida = _reply()
    _apply_off_table_insistence_guard(
        repetida, _context_insiste("Queria uma massagem clássica de 90 minutos", "Queria uma massagem clássica de 90 minutos")
    )
    assert repetida.next_action == "reply"

    # nem o pedaço do pedido original que a 2.ª decisão da Recepção repõe (requeue)
    requeue = _reply()
    _apply_off_table_insistence_guard(
        requeue,
        _context_insiste(
            "queria marcar uma massagem clássica de 90 minutos para quinta às 15h.",
            "Olá, queria marcar uma massagem clássica de 90 minutos para quinta às 15h.",
        ),
    )
    assert requeue.next_action == "reply"


def test_bloco_da_confirmacao_pede_a_linha_da_tabela():
    from app.services.decision_engine import _confirmation_block

    block = _confirmation_block(_context_sensi("Lomi Lomi"))
    assert "MARCAÇÃO JÁ GRAVADA NESTE TURNO" in block
    assert "meeting_service" in block
    assert "2. Massagem Relaxante Exótica (Lomi Lomi): 45, 60 ou 90 min" in block
    assert "meeting_service" not in _confirmation_block(_context())
