from app.services.decision_engine import (
    _build_mother_prompt,
    _collect_intent_triggers_for_lead_phase,
    _evaluate_sales_flow_phases,
)

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
