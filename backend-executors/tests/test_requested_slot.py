"""Frases reais das transcrições PROD05/PROD06 da conta Sensi Vitae (26/10/2026, uma segunda)."""
from datetime import datetime, timezone

import pytest

from app.services.requested_slot import build_agenda_fact_block, find_requested_slot, requested_time

NOW = datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)  # segunda, 8h em Lisboa
TZ = "Europe/Lisbon"


def _slot(text, earlier=None, busy=None, duration=60):
    return find_requested_slot(
        text, earlier or [], tz_name=TZ, busy_slots=busy or [], duration_minutes=duration, now_utc=NOW
    )


@pytest.mark.parametrize(
    "text,esperado",
    [
        ("Quero a Lomi Lomi de 60 minutos, por favor! Pode marcar para sábado de manhã às 11h?", "2026-10-31 11:00"),
        ("Quero a Lomi Lomi de 90 minutos! Podemos marcar para terça-feira às 14h com a Val?", "2026-10-27 14:00"),
        ("Afinal preciso de remarcar para quinta às 15h", "2026-10-29 15:00"),
        # "de 1h" é a duração, não a hora
        ("Queria marcar uma massagem relaxante clássica de 1h com a Val na quinta às 17h.", "2026-10-29 17:00"),
        ("Boa tarde, queria marcar uma massagem terapêutica de 1h para quinta às 21h.", "2026-10-29 21:00"),
        ("Quero marcar a massagem relaxante clássica de 1 hora para amanhã às 11h. Pode confirmar?", "2026-10-27 11:00"),
        ("Pode ser sexta às 14h30?", "2026-10-30 14:30"),
        ("Dá para dia 30/10 às 15:00?", "2026-10-30 15:00"),
    ],
)
def test_le_dia_e_hora_pedidos(text, esperado):
    slot = _slot(text)
    assert slot is not None
    assert slot.start.strftime("%Y-%m-%d %H:%M") == esperado
    assert slot.free is True


@pytest.mark.parametrize(
    "text",
    [
        "E a Val tá disponível hoje depois das 19h? Tem final feliz?",  # limite, não horário
        "Quinta às 17h não dá mesmo? Se não, pode ser na quarta às 16h sim.",  # duas horas
        "Gostei da Lomi Lomi de 60 minutos.",  # sem hora
        "Quero uma massagem relaxante de 90 minutos.",
        "Tem vaga a partir das 15h na sexta?",
        "Pode ser hoje às 7h?",  # já passou (são 8h)
    ],
)
def test_sem_horario_inequivoco_nao_ha_facto(text):
    assert _slot(text) is None


def test_hora_sem_dia_usa_o_ultimo_dia_falado():
    earlier = [
        "Infelizmente sábado às 11h não dá, mas posso sugerir sábado às 11h30 ou às 15h.",
        "Quero a Lomi Lomi de 60 minutos. Pode ser sábado às 11h?",
    ]
    slot = _slot("Pode ser às 15h então!", earlier)
    assert slot.start.strftime("%Y-%m-%d %H:%M") == "2026-10-31 15:00"


def test_hora_sem_dia_nenhum_na_conversa_nao_ha_facto():
    assert _slot("Pode ser às 15h?", ["Olá, quero uma massagem"]) is None


def test_compromisso_que_colide_marca_ocupado():
    busy = [{"start_at": "2026-10-31T10:30:00+00:00", "end_at": "2026-10-31T11:30:00+00:00", "lead_id": 99}]
    slot = _slot("Pode ser sábado às 11h?", busy=busy)
    assert slot.free is False
    block = build_agenda_fact_block(slot)
    assert "colide com um compromisso já marcado (10h30–11h30)" in block


def test_compromisso_do_proprio_lead_nao_conta():
    busy = [{"start_at": "2026-10-29T15:00:00+00:00", "end_at": "2026-10-29T16:00:00+00:00", "lead_id": 7}]
    slot = find_requested_slot(
        "Afinal preciso de remarcar para quinta às 15h", [], tz_name=TZ, busy_slots=busy,
        duration_minutes=60, exclude_lead_id=7, now_utc=NOW,
    )
    assert slot.free is True


def test_bloco_livre_diz_o_facto_e_a_unica_razao_para_recusar():
    block = build_agenda_fact_block(_slot("Pode marcar para sábado de manhã às 11h?"))
    assert "O lead pediu sábado, 31/10, às 11h;" in block
    assert "NÃO há nenhum compromisso nesse intervalo" in block
    assert "diga que está fora do horário de atendimento" in block


def test_sem_slot_sem_bloco():
    assert build_agenda_fact_block(None) == ""


def _context(inbound, category="agendamento"):
    return {
        "lead": {"id": 1, "category": category},
        "ai_profile": {"agent_mode": "agenda", "timezone": TZ, "custom_instructions": "Val: seg–sáb 11h–17h."},
        "playbook": {},
        "metadata": {"inbound_message_text": inbound},
        "history": [],
        "calendar_busy_slots": [],
    }


def test_prompt_de_agendamento_traz_o_facto_no_fim():
    from app.services.decision_engine import _build_child_prompt_agendamento
    from app.services.orchestrator_models import MotherDecision

    inbound = "Quero a Lomi Lomi de 60 minutos. Pode marcar para sábado de manhã às 11h?"
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    prompt = _build_child_prompt_agendamento(_context(inbound), inbound, mother)
    assert "VERIFICAÇÃO DO HORÁRIO PEDIDO" in prompt
    # depois das instruções da conta, para não ser vencido por elas
    assert prompt.rindex("VERIFICAÇÃO DO HORÁRIO PEDIDO") > prompt.rindex("INSTRUÇÕES PERSONALIZADAS DO OPERADOR")


def test_prompt_de_agendamento_sem_hora_nao_traz_facto():
    from app.services.decision_engine import _build_child_prompt_agendamento
    from app.services.orchestrator_models import MotherDecision

    inbound = "Quero a Lomi Lomi de 60 minutos."
    mother = MotherDecision(route_to="agendamento", perceived_category="agendamento", confidence=0.9, reason="ok")
    assert "VERIFICAÇÃO DO HORÁRIO PEDIDO" not in _build_child_prompt_agendamento(_context(inbound), inbound, mother)


def test_prompt_de_remarcacao_traz_o_facto():
    from app.services.decision_engine import _build_child_prompt_meeting_management

    inbound = "Afinal preciso de remarcar para quinta às 15h"
    prompt = _build_child_prompt_meeting_management(_context(inbound, "client-list"), inbound)
    assert "VERIFICAÇÃO DO HORÁRIO PEDIDO" in prompt


def test_requested_time_ignora_duracoes():
    assert requested_time("massagem de 1h30") is None
    assert requested_time("1h de massagem às 16h") is not None


@pytest.mark.parametrize(
    "texts,esperado",
    [
        (["Queria uma massagem relaxante clássica de 1h com a Val na quinta às 17h."], 60),
        (["Quero a Lomi Lomi de 90 minutos! Terça às 14h?"], 90),
        (["Pode ser de 1h30, sábado às 11h"], 90),
        (["Pode ser às 15h então!", "Quero a Lomi Lomi de 60 minutos."], 60),
        (["Sábado às 11h?"], None),
    ],
)
def test_requested_duration(texts, esperado):
    from app.services.requested_slot import requested_duration

    assert requested_duration(texts) == esperado


def test_bloco_diz_a_hora_a_que_a_sessao_acaba():
    # Bancada M12a: com só "a agenda está livre", a IA aceitou Val às 17h para 1h (acaba às 18h).
    slot = _slot("Queria uma massagem relaxante clássica de 1h com a Val na quinta às 17h.")
    block = build_agenda_fact_block(slot)
    assert "O lead pediu quinta-feira, 29/10, às 17h; a sessão de 60 min terminaria às 18h." in block
    assert block.index("Horário de atendimento") < block.index("Agenda —")


def test_sem_duracao_dita_usa_a_do_perfil_e_avisa():
    block = build_agenda_fact_block(_slot("Pode marcar para sábado às 11h?", duration=60))
    assert "com 60 min (duração ainda por confirmar) a sessão terminaria às 12h" in block


def test_duracao_dita_antes_conta_para_o_conflito():
    busy = [{"start_at": "2026-10-31T12:00:00+00:00", "end_at": "2026-10-31T13:00:00+00:00", "lead_id": 9}]
    slot = find_requested_slot(
        "Pode ser sábado às 11h?", [], tz_name=TZ, busy_slots=busy, duration_minutes=60, now_utc=NOW,
        lead_messages=["Quero a Lomi Lomi de 90 minutos."],
    )
    assert slot.free is False  # 11h–12h30 colide com 12h–13h


def test_prompt_de_pre_agendamento_traz_o_facto():
    from app.services.decision_engine import _build_child_prompt_pre_agendamento
    from app.services.orchestrator_models import MotherDecision

    inbound = "Olá, queria marcar uma massagem relaxante de 60 minutos com a Val para terça às 14h"
    mother = MotherDecision(route_to="pre-agendamento", perceived_category="pre-agendamento", confidence=0.9, reason="ok")
    prompt = _build_child_prompt_pre_agendamento(_context(inbound, "qualification"), inbound, mother)
    assert "VERIFICAÇÃO DO HORÁRIO PEDIDO" in prompt
