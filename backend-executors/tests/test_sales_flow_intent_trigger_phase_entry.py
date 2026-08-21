import pytest

from app.services.decision_engine import (
    _build_child_prompt_apresentation,
    _build_daughter_identity_block,
    _build_mother_prompt,
    _collect_intent_triggers_for_lead_phase,
    _enforce_apresentation_sales_flow_pending,
    _evaluate_sales_flow_phases,
)
from app.services.orchestrator_models import MotherDecision

INTENT_LABEL = "Quando o cliente aceita ou diz sim para a tabela de preços"


def _sales_flow_with_intent_trigger_and_media(phase_id: str) -> dict:
    return {
        "enabled": True,
        "phases": [
            {"id": "p0", "blocks": []},
            {"id": "p1", "blocks": []},
            {
                "id": phase_id,
                "blocks": [
                    {
                        "id": "trigger-1",
                        "typeId": "intent_trigger",
                        "intent": INTENT_LABEL,
                        "fire_once": True,
                    },
                    {
                        "id": "media-1",
                        "typeId": "midia",
                        "media_url": "https://example.com/tabela-1.png",
                        "media_type": "image",
                    },
                    {
                        "id": "media-2",
                        "typeId": "midia",
                        "media_url": "https://example.com/tabela-2.png",
                        "media_type": "image",
                    },
                    {
                        "id": "media-3",
                        "typeId": "midia",
                        "media_url": "https://example.com/tabela-3.png",
                        "media_type": "image",
                    },
                ],
            },
        ],
    }


def _context(category: str, sales_flow: dict) -> dict:
    return {
        "lead": {"category": category, "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }


def test_new_lead_no_category_includes_next_phase_p1_intents():
    sales_flow = _sales_flow_with_intent_trigger_and_media("p1")
    context = _context("", sales_flow)

    blocks = _collect_intent_triggers_for_lead_phase(context, "agenda")

    assert [b["id"] for b in blocks] == ["trigger-1"]


def test_lead_in_qualification_includes_next_phase_p2_intents():
    """Reproduz o bug relatado: lead ainda em p1, mensagem que deveria entrar em p2."""
    sales_flow = _sales_flow_with_intent_trigger_and_media("p2")
    context = _context("qualification", sales_flow)

    blocks = _collect_intent_triggers_for_lead_phase(context, "agenda")

    assert [b["id"] for b in blocks] == ["trigger-1"]


def test_direto_mode_next_phase_after_apresentation_is_closing_not_scheduling():
    sales_flow = {
        "enabled": True,
        "phases": [
            {"id": "p2", "blocks": []},
            {
                "id": "p3a",
                "blocks": [
                    {"id": "should-not-appear", "typeId": "intent_trigger", "intent": "irrelevante"},
                ],
            },
            {
                "id": "p5",
                "blocks": [
                    {"id": "trigger-closing", "typeId": "intent_trigger", "intent": "cliente confirmou fechamento"},
                ],
            },
        ],
    }
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "direto", "sales_flow": sales_flow},
    }

    blocks = _collect_intent_triggers_for_lead_phase(context, "direto")

    assert [b["id"] for b in blocks] == ["trigger-closing"]


def test_does_not_look_more_than_one_phase_ahead():
    sales_flow = {
        "enabled": True,
        "phases": [
            {"id": "p1", "blocks": []},
            {"id": "p2", "blocks": []},
            {
                "id": "p5",
                "blocks": [
                    {"id": "too-far-ahead", "typeId": "intent_trigger", "intent": "não deveria aparecer aqui"},
                ],
            },
        ],
    }
    context = {
        "lead": {"category": "qualification", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "direto", "sales_flow": sales_flow},
    }

    blocks = _collect_intent_triggers_for_lead_phase(context, "direto")

    assert blocks == []


def test_current_phase_intents_still_included_backwards_compat():
    sales_flow = _sales_flow_with_intent_trigger_and_media("p2")
    context = _context("apresentation", sales_flow)

    blocks = _collect_intent_triggers_for_lead_phase(context, "agenda")

    assert [b["id"] for b in blocks] == ["trigger-1"]


def test_end_to_end_intent_trigger_fires_media_on_phase_entry_message():
    """Reproduz o cenário completo relatado: lead em p1 diz 'sim, pode enviar' e a
    mãe classifica corretamente a intenção — agora os 3 blocos de mídia disparam."""
    sales_flow = _sales_flow_with_intent_trigger_and_media("p2")
    context = _context("qualification", sales_flow)

    active_triggers = _collect_intent_triggers_for_lead_phase(context, "agenda")
    assert [b["id"] for b in active_triggers] == ["trigger-1"]

    detected_intents = [INTENT_LABEL]

    result = _evaluate_sales_flow_phases(
        context,
        effective_route_to="apresentation",
        message_text="sim, pode enviar",
        detected_intents=detected_intents,
    )

    send_media_actions = [a for a in result["system_actions"] if a["type"] == "send_media"]
    assert [a["media_url"] for a in send_media_actions] == [
        "https://example.com/tabela-1.png",
        "https://example.com/tabela-2.png",
        "https://example.com/tabela-3.png",
    ]


def test_end_to_end_intent_trigger_does_not_fire_without_detection():
    """Sem o fix, este é o comportamento observado: detected_intents vazio (porque a
    mãe nunca viu o trigger) faz os blocos de mídia não disparar."""
    sales_flow = _sales_flow_with_intent_trigger_and_media("p2")
    context = _context("qualification", sales_flow)

    result = _evaluate_sales_flow_phases(
        context,
        effective_route_to="apresentation",
        message_text="sim, pode enviar",
        detected_intents=[],
    )

    send_media_actions = [a for a in result["system_actions"] if a["type"] == "send_media"]
    assert send_media_actions == []


def test_mother_prompt_reinforces_detected_intents_consistency_with_reason():
    """Fase 2: testes ao vivo mostraram a mãe reconhecendo a intenção em `reason` mas
    devolvendo detected_intents=[] mesmo vendo o trigger listado. O prompt precisa
    conter o reforço explícito que nomeia essa inconsistência como inválida."""
    sales_flow = _sales_flow_with_intent_trigger_and_media("p2")
    context = _context("qualification", sales_flow)

    prompt = _build_mother_prompt(context, "sim, pode enviar")

    assert "[DETECÇÃO DE INTENÇÃO]" in prompt
    assert INTENT_LABEL in prompt
    assert "INCONSISTENTE" in prompt
    assert "detected_intents" in prompt.split("OBRIGATÓRIO")[-1]


def test_daughter_identity_block_forbids_repeated_greetings():
    """Testes ao vivo mostraram a LLM filha repetindo 'Boa tarde!' mesmo com a
    saudação anterior já visível no histórico. A regra anti-repetição precisa
    nomear saudações explicitamente, não só 'conteúdo/informações' em geral."""
    context = {
        "lead": {},
        "ai_profile": {"name": "Daniel", "brand_name": "Sensi Vitae", "template_key": "hybrid_scheduler"},
        "playbook": {},
    }

    block = _build_daughter_identity_block(context, "apresentation")

    assert "REGRA ANTI-REPETIÇÃO" in block
    assert "saudaç" in block.lower()
    assert "Boa tarde" in block


def test_deferred_media_note_when_intent_trigger_fires_media():
    """A ordem de despacho real (whatsapp.py) envia a mídia de um intent_trigger
    DEPOIS do texto da LLM. Sem aviso, a LLM escreve como se a mídia já tivesse
    sido entregue ('aqui está'). O prompt precisa avisar que o envio é pendente."""
    sales_flow = _sales_flow_with_intent_trigger_and_media("p2")
    context = _context("qualification", sales_flow)

    result = _evaluate_sales_flow_phases(
        context,
        effective_route_to="apresentation",
        message_text="sim, pode enviar",
        detected_intents=[INTENT_LABEL],
    )

    pending_notes = [i for i in result["prompt_injections"] if "envio automático pendente" in i]
    assert len(pending_notes) == 1
    note = pending_notes[0]
    assert note.count("image") == 3
    assert "ainda NÃO foi enviado" in note
    assert "aqui está" in note.lower()


def test_no_deferred_media_note_when_phase_trigger_fires_media():
    """Regressão: phase_trigger continua usando o aviso "enviada automaticamente"
    (passado) — só o caminho sem phase_trigger precisa do aviso no futuro."""
    sales_flow = {
        "enabled": True,
        "phases": [
            {
                "id": "p2",
                "blocks": [
                    {"id": "trigger-1", "typeId": "phase_trigger"},
                    {
                        "id": "media-1",
                        "typeId": "midia",
                        "media_url": "https://example.com/tabela-1.png",
                        "media_type": "image",
                    },
                ],
            },
        ],
    }
    context = _context("qualification", sales_flow)

    result = _evaluate_sales_flow_phases(
        context,
        effective_route_to="apresentation",
        message_text="oi",
        detected_intents=[],
        is_phase_entry=True,
    )

    assert not any("envio automático pendente" in i for i in result["prompt_injections"])
    assert any("Mídia enviada automaticamente ao lead" in i for i in result["prompt_injections"])


CRITICAL_GUARD_TEXT = "Não pergunte disponibilidade antes de o lead aceitar a tabela."


def _sales_flow_sequential_critical_guard() -> dict:
    """Reproduz o desenho do agente 'Daniel' (Sensi Vitae) relatado no bug: apresentação
    -> orientação crítica ('não pergunte disponibilidade ainda') -> gatilho (aceitar
    tabela) -> mídia -> gatilho (escolheu serviço) -> orientação (pergunte disponibilidade)."""
    return {
        "enabled": True,
        "phases": [
            {"id": "p0", "blocks": []},
            {"id": "p1", "blocks": []},
            {
                "id": "p2",
                "blocks": [
                    {"id": "phase-entry-p2", "typeId": "phase_trigger"},
                    {
                        "id": "critical-no-schedule-yet",
                        "typeId": "orientacao",
                        "content": CRITICAL_GUARD_TEXT,
                        "priority": "critical",
                    },
                    {
                        "id": "intent-accept-table",
                        "typeId": "intent_trigger",
                        "intent": "Cliente aceitou ver a tabela de preços",
                        "fire_once": True,
                    },
                    {
                        "id": "media-table",
                        "typeId": "midia",
                        "media_url": "https://example.com/tabela.png",
                        "media_type": "image",
                    },
                    {
                        "id": "intent-picked-service",
                        "typeId": "intent_trigger",
                        "intent": "Cliente indicou qual serviço quer",
                        "fire_once": True,
                    },
                    {
                        "id": "ask-availability",
                        "typeId": "orientacao",
                        "content": "Pergunte a disponibilidade do cliente.",
                        "priority": "normal",
                    },
                ],
            },
        ],
    }


def test_later_intent_trigger_blocked_until_earlier_one_fires():
    """Trava estrutural pedida pelo utilizador: um intent_trigger mais à frente não pode
    disparar antes de o intent_trigger anterior (fire_once) já ter disparado — mesmo que a
    LLM Mãe tenha classificado (erroneamente ou não) a intenção mais à frente neste turno.
    Sem o fix, 'intent-picked-service' dispararia e 'ask-availability' seria injectado."""
    sales_flow = _sales_flow_sequential_critical_guard()
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]", "phases_triggered": '["p2"]'},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }

    result = _evaluate_sales_flow_phases(
        context,
        effective_route_to="apresentation",
        message_text="quero a massagem relaxante",
        detected_intents=["Cliente indicou qual serviço quer"],
        is_phase_entry=False,
    )

    assert not any(
        a["type"] == "mark_trigger_fired" and a.get("block_id") == "intent-picked-service"
        for a in result["system_actions"]
    )
    assert not any("Pergunte a disponibilidade" in i for i in result["prompt_injections"])


def test_critical_orientation_persists_until_next_trigger_fires():
    """A instrução crítica ('não pergunte disponibilidade ainda') deve continuar a
    aparecer no prompt em turnos seguintes da mesma fase — não só no turno de entrada —
    até o próximo gatilho da sequência (aceitar a tabela) disparar. Reproduz o bug
    relatado: no turno 2 (sem phase_trigger disparar de novo), a instrução sumia."""
    sales_flow = _sales_flow_sequential_critical_guard()

    # Turno 1 — entrada na fase: a orientação crítica aparece via a passagem principal.
    entry_context = {
        "lead": {"category": "qualification", "triggers_fired": "[]", "phases_triggered": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    entry_result = _evaluate_sales_flow_phases(
        entry_context,
        effective_route_to="apresentation",
        message_text="oi",
        detected_intents=[],
        is_phase_entry=True,
    )
    assert any(CRITICAL_GUARD_TEXT in i for i in entry_result["prompt_injections"])

    # Turno 2 — mesma fase, sem phase_trigger disparar de novo, gatilho seguinte (aceitar
    # tabela) ainda não satisfeito: a instrução crítica deve continuar presente.
    mid_context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]", "phases_triggered": '["p2"]'},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    mid_result = _evaluate_sales_flow_phases(
        mid_context,
        effective_route_to="apresentation",
        message_text="e tens espaço noutra cidade?",
        detected_intents=[],
        is_phase_entry=False,
    )
    assert any(CRITICAL_GUARD_TEXT in i for i in mid_result["prompt_injections"])

    # Turno 3 — o gatilho seguinte já foi satisfeito (persistido): a instrução crítica já
    # foi superada e não deve mais aparecer.
    late_context = {
        "lead": {
            "category": "apresentation",
            "triggers_fired": '["intent-accept-table"]',
            "phases_triggered": '["p2"]',
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    late_result = _evaluate_sales_flow_phases(
        late_context,
        effective_route_to="apresentation",
        message_text="quero a relaxante",
        detected_intents=[],
        is_phase_entry=False,
    )
    assert not any(CRITICAL_GUARD_TEXT in i for i in late_result["prompt_injections"])


def _mother_decision(route_to: str, reason: str = "mother chose it") -> MotherDecision:
    return MotherDecision(route_to=route_to, confidence=0.8, reason=reason)


def test_enforce_apresentation_pending_blocks_mother_route_jump():
    """Reproduz o cenário relatado ao vivo: lead diz apenas 'ok' e a Mãe decide sozinha
    route_to='pre-agendamento', pulando toda a fase p2 (e a sua instrução crítica) num
    único turno. O guardrail deve forçar a rota de volta para 'apresentation' enquanto
    o intent_trigger sequencial de p2 ainda não tiver disparado para este lead."""
    sales_flow = _sales_flow_sequential_critical_guard()
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    mother_decision = _mother_decision("pre-agendamento")

    result = _enforce_apresentation_sales_flow_pending(mother_decision, context)

    assert result.route_to == "apresentation"
    assert "sales_flow_apresentation_pending_forced_route" in result.reason
    assert "intent-accept-table" in result.reason


@pytest.mark.parametrize("target_route", ["pre-agendamento", "closing", "follow-up"])
def test_enforce_apresentation_pending_blocks_any_allowed_advance_target(target_route):
    """O guardrail cobre qualquer salto permitido a partir de 'apresentation'
    (_ALLOWED_ADVANCE), não só pre-agendamento."""
    sales_flow = _sales_flow_sequential_critical_guard()
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    mother_decision = _mother_decision(target_route)

    result = _enforce_apresentation_sales_flow_pending(mother_decision, context)

    assert result.route_to == "apresentation"


def test_enforce_apresentation_pending_allows_jump_once_all_sequential_triggers_fired():
    """Depois de todos os gatilhos sequenciais de p2 já terem disparado (persistidos em
    triggers_fired), o salto de rota da Mãe deixa de ser bloqueado — comportamento normal."""
    sales_flow = _sales_flow_sequential_critical_guard()
    context = {
        "lead": {
            "category": "apresentation",
            "triggers_fired": '["intent-accept-table", "intent-picked-service"]',
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    mother_decision = _mother_decision("pre-agendamento")

    result = _enforce_apresentation_sales_flow_pending(mother_decision, context)

    assert result.route_to == "pre-agendamento"


def test_enforce_apresentation_pending_ignores_other_current_categories():
    """Só age quando o lead está atualmente em 'apresentation' — outras fases não são
    afetadas por este guardrail (cada uma tem o seu próprio mecanismo, se precisar)."""
    sales_flow = _sales_flow_sequential_critical_guard()
    context = {
        "lead": {"category": "qualification", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    mother_decision = _mother_decision("apresentation")

    result = _enforce_apresentation_sales_flow_pending(mother_decision, context)

    assert result.route_to == "apresentation"


def test_enforce_apresentation_pending_noop_without_sales_flow_configured():
    """Sem Fluxo de Venda configurado (ou sem gatilhos sequenciais em p2), o guardrail
    não interfere — comportamento idêntico ao de antes desta fase, sem regressão para
    agentes que não usam o Fluxo de Venda avançado."""
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": {"enabled": False, "phases": []}},
    }
    mother_decision = _mother_decision("pre-agendamento")

    result = _enforce_apresentation_sales_flow_pending(mother_decision, context)

    assert result.route_to == "pre-agendamento"


def test_enforce_apresentation_pending_uses_phases_triggered_when_category_lags():
    """Reproduz o comportamento visto ao vivo: leads.category ficou em 'qualification'
    (não atualizado) mesmo com phases_triggered já contendo 'p2' — a Mãe tinha gerado
    conteúdo de apresentation via route_to num turno anterior sem a categoria persistida
    acompanhar. O guardrail deve usar phases_triggered como sinal de "já entrou em p2",
    não depender só de lead.category."""
    sales_flow = _sales_flow_sequential_critical_guard()
    context = {
        "lead": {
            "category": "qualification",
            "triggers_fired": "[]",
            "phases_triggered": '["p2"]',
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }
    mother_decision = _mother_decision("pre-agendamento")

    result = _enforce_apresentation_sales_flow_pending(mother_decision, context)

    assert result.route_to == "apresentation"
    assert "sales_flow_apresentation_pending_forced_route" in result.reason


def test_is_phase_entry_threaded_correctly_to_apresentation_prompt():
    """Fase 3: antes desta fase, _build_child_prompt_apresentation chamava
    _evaluate_sales_flow_phases sem passar is_phase_entry, usando sempre o default
    True — reapresentando 'ATENÇÃO: mensagens enviadas automaticamente' como se fosse
    novo em todo turno da fase, mesmo fora do turno de entrada real."""
    sales_flow = _sales_flow_sequential_critical_guard()
    context = {
        "lead": {
            "id": 1,
            "category": "apresentation",
            "triggers_fired": "[]",
            "phases_triggered": '["p2"]',
        },
        "ai_profile": {"agent_mode": "agenda", "template_key": "sdr_padrao", "sales_flow": sales_flow},
        "playbook": {"template_key": "sdr_padrao"},
        "metadata": {"inbound_message_text": "oi"},
        "history": [{"model": "outbound", "text": "Oi!"}, {"model": "inbound", "text": "oi"}],
        "knowledge_items": {},
        "knowledge_media": {},
        "lead_detected_language": "pt",
    }
    mother = MotherDecision(
        route_to="apresentation", perceived_category="apresentation", confidence=0.9, reason="turno 2"
    )
    ATENCAO = "ATENÇÃO: As mensagens listadas abaixo foram enviadas AUTOMATICAMENTE"

    entry_prompt = _build_child_prompt_apresentation(context, "oi", mother, is_phase_entry=True)
    mid_prompt = _build_child_prompt_apresentation(context, "oi", mother, is_phase_entry=False)

    assert ATENCAO in entry_prompt
    assert ATENCAO not in mid_prompt
