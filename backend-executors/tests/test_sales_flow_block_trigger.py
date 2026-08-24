"""block_trigger — gatilho leve sem condição de conteúdo, criado implicitamente pelo
frontend quando o utilizador escolhe "Sem gatilho" e define uma dependência (requires_block_id).
Dispara exatamente uma vez por lead, assim que a dependência já tiver disparado num turno
anterior — reaproveita toda a infraestrutura de requires_block_id/gating sequencial já
existente para kw_trigger/intent_trigger. Ver docs/architecture/sales-flow.md."""
from app.services.decision_engine import _evaluate_sales_flow_phases, _phase_pending_sequential_triggers


def _sales_flow_block_trigger() -> dict:
    """Fase p2: phase_trigger "opener" seguido de um block_trigger "follow" que depende
    dele, seguido de uma orientação observável só quando "follow" dispara."""
    return {
        "enabled": True,
        "phases": [
            {"id": "p0", "blocks": []},
            {"id": "p1", "blocks": []},
            {
                "id": "p2",
                "blocks": [
                    {"id": "opener", "typeId": "phase_trigger"},
                    {"id": "follow", "typeId": "block_trigger", "requires_block_id": "opener"},
                    {"id": "guard", "typeId": "orientacao", "content": "ORIENTACAO_APOS_FOLLOW"},
                ],
            },
        ],
    }


def _context(*, triggers_fired: str = "[]", phases_triggered: str = "[]") -> dict:
    return {
        "lead": {
            "category": "apresentation",
            "triggers_fired": triggers_fired,
            "phases_triggered": phases_triggered,
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": _sales_flow_block_trigger()},
    }


def test_block_trigger_blocked_until_dependency_persisted():
    """Turno 1 — mesmo que a dependência (phase_trigger) dispare NESTE turno, o block_trigger
    não dispara: requires_block_id só reconhece satisfação persistida de um turno anterior."""
    context = _context(phases_triggered="[]")

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="oi",
        is_phase_entry=True,
    )

    assert not any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "follow"
        for a in result["system_actions"]
    )
    assert not any("ORIENTACAO_APOS_FOLLOW" in i for i in result["prompt_injections"])


def test_block_trigger_fires_once_dependency_persisted():
    """Turno 2 — dependência já persistida (phases_triggered contém "p2", vindo do
    mark_phase_triggered do turno 1 já processado pelo CRM) — o block_trigger dispara."""
    context = _context(phases_triggered='["p2"]')

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="continuando a conversa",
        is_phase_entry=False,
    )

    assert any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "follow"
        for a in result["system_actions"]
    )
    assert any("ORIENTACAO_APOS_FOLLOW" in i for i in result["prompt_injections"])


def test_block_trigger_does_not_refire_next_turn():
    """Regressão central: diferente de phase_trigger (auto-limitado por is_phase_entry) e de
    kw/intent_trigger (auto-limitados pelo checkbox fire_once), block_trigger não tem nenhum
    outro mecanismo de "uma vez só" — precisa checar triggers_fired explicitamente, senão
    reenviaria a ação em todo turno seguinte para sempre."""
    context = _context(phases_triggered='["p2"]', triggers_fired='["follow"]')

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="mais uma mensagem",
        is_phase_entry=False,
    )

    assert not any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "follow"
        for a in result["system_actions"]
    )
    assert not any("ORIENTACAO_APOS_FOLLOW" in i for i in result["prompt_injections"])


def test_block_trigger_dangling_reference_fails_open():
    """Referência a um id que não existe em nenhum bloco — sem efeito, block_trigger dispara
    normalmente (mesmo comportamento fail-open de kw_trigger/intent_trigger)."""
    sales_flow = _sales_flow_block_trigger()
    sales_flow["phases"][2]["blocks"] = [
        b for b in sales_flow["phases"][2]["blocks"] if b["id"] != "opener"
    ]
    context = {
        "lead": {"category": "apresentation", "triggers_fired": "[]", "phases_triggered": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="oi",
        is_phase_entry=False,
    )

    assert any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "follow"
        for a in result["system_actions"]
    )


def test_block_trigger_counts_as_pending_for_phase_advance_guardrail():
    """_phase_pending_sequential_triggers precisa contar um block_trigger ainda não disparado
    como pendência — senão a Mãe pode avançar a fase pulando a ação configurada (mesmo
    guardrail que já protege kw_trigger/intent_trigger com fire_once=True)."""
    sales_flow = _sales_flow_block_trigger()

    pending_before = _phase_pending_sequential_triggers("p2", {"sales_flow": sales_flow}, triggers_fired=set())
    assert "follow" in pending_before

    pending_after = _phase_pending_sequential_triggers("p2", {"sales_flow": sales_flow}, triggers_fired={"follow"})
    assert "follow" not in pending_after
