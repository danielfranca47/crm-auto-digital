"""Conversas reais da conta Sensi Vitae (bancada PROD07, 26/10/2026, uma segunda-feira)."""
from datetime import datetime, timezone

import pytest

from app.services import meeting_proposal as mp

NOW = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
TZ = "Europe/Lisbon"
PROS = ["Val", "Daniel"]


def _h(*pairs):
    return [{"model": model, "body": body} for model, body in pairs]


def _read(history, inbound):
    proposal = mp.last_proposal(history, inbound, tz_name=TZ, now_utc=NOW, professionals=PROS)
    accepted = mp.accepted_slot(inbound, proposal, tz_name=TZ, now_utc=NOW, professionals=PROS)
    return proposal, accepted


CEDO_TARDE = _h(
    ("inbound", "Boa tarde, queria marcar uma massagem terapêutica de 1h para quinta às 21h."),
    ("outbound", "Boa tarde! Sou a Lara, do Sensi Vitae Massages."),
    (
        "outbound",
        "O horário que pediu está fora do horário de atendimento. A Val atende até às 17h e o Daniel até "
        "às 19h30. Posso agendar uma massagem terapêutica de 1h quinta-feira às 18h30 com o Daniel?",
    ),
    ("inbound", "Epa, não dá. Pode ser na sexta às 9h?"),
    ("outbound", "Infelizmente, o horário que pediu está fora do horário de atendimento."),
    ("outbound", "O primeiro horário disponível é na sexta-feira às 11h com a Val."),
    ("outbound", "Pode ser esse?"),
)


def test_aceita_a_segunda_proposta_e_nao_a_primeira():
    proposal, accepted = _read(CEDO_TARDE, "Pode ser sim, marca aí!")
    assert proposal.source == "agent"
    assert accepted.source == "single_option"
    assert mp.candidate_iso(accepted.option) == "2026-10-30T11:00:00"
    assert accepted.option.professional == "Val"
    assert mp.describe(accepted.option) == "sexta-feira, 30/10, às 11h com Val"


def test_primeira_proposta_ignora_horario_de_atendimento():
    proposal, _ = _read(CEDO_TARDE[:3], "Epa")
    assert [mp.candidate_iso(o) for o in proposal.options] == ["2026-10-29T18:30:00"]
    assert proposal.options[0].professional == "Daniel"


def test_historico_que_ja_traz_a_mensagem_atual():
    history = CEDO_TARDE + _h(("inbound", "Pode ser sim, marca aí!"))
    _, accepted = _read(history, "Pode ser sim, marca aí!")
    assert mp.candidate_iso(accepted.option) == "2026-10-30T11:00:00"


def test_resumo_com_data_e_dia_da_semana():
    history = _h(
        ("outbound", "Fica então quarta-feira, 28/10, às 15h, Massagem Relaxante Exótica de 60 min com a Val."),
        ("outbound", "Posso confirmar?"),
    )
    _, accepted = _read(history, "Sim, confirma!")
    assert mp.candidate_iso(accepted.option) == "2026-10-28T15:00:00"


def test_data_errada_colada_ao_dia_da_semana_vale_o_dia_da_semana():
    history = _h(("outbound", "Fica então sexta-feira, 28/10, às 11h com a Val. Posso confirmar?"))
    _, accepted = _read(history, "Sim")
    assert mp.candidate_iso(accepted.option) == "2026-10-30T11:00:00"


def test_proposta_e_pedido_do_nome_na_mesma_resposta():
    history = _h(
        ("outbound", "Temos sim, a Lomi Lomi de 60 minutos disponível para sábado às 11h com a Val."),
        ("outbound", "Como se chama?"),
    )
    _, accepted = _read(history, "Ricardo! Obrigado!")
    assert mp.candidate_iso(accepted.option) == "2026-10-31T11:00:00"


def test_hora_recusada_na_frase_negativa_nao_e_proposta():
    history = _h(
        ("outbound", "O horário às 9h na segunda está fora do horário de atendimento, pois a Val atende das 11h às 17h."),
        ("outbound", "Posso agendar para segunda-feira às 11h?"),
    )
    proposal, accepted = _read(history, "Ok, 11h na segunda tá bom! Pode marcar.")
    assert [mp.candidate_iso(o) for o in proposal.options] == ["2026-11-02T11:00:00"]
    assert accepted.source == "matched_option" or accepted.source == "single_option"
    assert mp.candidate_iso(accepted.option) == "2026-11-02T11:00:00"


DUAS = _h(("outbound", "Tenho quinta às 11h com a Val ou às 15h com o Daniel. Qual prefere?"))


def test_duas_opcoes_sem_escolha_e_ambiguo():
    proposal, accepted = _read(DUAS, "Pode ser, marca!")
    assert len(proposal.options) == 2
    assert accepted.source == "ambiguous"
    assert accepted.option is None


@pytest.mark.parametrize("inbound,esperado", [("Às 15h, por favor", "2026-10-29T15:00:00"),
                                               ("Com o Daniel", "2026-10-29T15:00:00"),
                                               ("Prefiro com a Val", "2026-10-29T11:00:00")])
def test_duas_opcoes_cliente_escolhe_uma(inbound, esperado):
    _, accepted = _read(DUAS, inbound)
    assert accepted.source == "matched_option"
    assert mp.candidate_iso(accepted.option) == esperado


def test_hora_nova_do_cliente_nao_e_aceitacao():
    _, accepted = _read(DUAS, "Não dá, pode ser às 17h?")
    assert accepted.source == "lead_stated"


def test_hora_dita_pelo_cliente_e_a_proposta_quando_o_agente_so_pergunta():
    history = _h(("inbound", "Queria quinta às 14h"), ("outbound", "Perfeito! Posso confirmar?"))
    proposal, accepted = _read(history, "Sim")
    assert proposal.source == "lead"
    assert mp.candidate_iso(accepted.option) == "2026-10-29T14:00:00"


def test_sem_horario_nenhum():
    proposal, accepted = _read(_h(("outbound", "Que dia funcionaria melhor?")), "Sim")
    assert proposal.source == "none"
    assert accepted.source == "none"


def test_hora_sem_dia_usa_o_ultimo_dia_falado():
    history = _h(("inbound", "Queria para sábado"), ("outbound", "Tenho às 11h com a Val. Pode ser?"))
    _, accepted = _read(history, "Sim")
    assert mp.candidate_iso(accepted.option) == "2026-10-31T11:00:00"
