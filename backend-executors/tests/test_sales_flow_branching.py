import pytest

from app.services.decision_engine import (
    _collect_branch_nodes_for_lead_phase,
    _evaluate_sales_flow_phases,
    _load_branches_selected_map,
)
from app.services.orchestrator_models import MotherDecision


def _sales_flow_two_branches_simple(phase_id: str, sticky: bool) -> dict:
    """Nó de ramificação com 2 caminhos, cada um com blocos simples (sem gatilho próprio)
    — isola o teste de "escopo de ramo" do teste de "gating sequencial dentro de um ramo"."""
    return {
        "enabled": True,
        "phases": [
            {
                "id": phase_id,
                "blocks": [
                    {
                        "id": "cond-1",
                        "typeId": "condicao",
                        "label": "Preço vs objeção de valor",
                        "sticky": sticky,
                        "branches": [
                            {"id": "branch-a", "label": "Caminho A", "criteria": "lead perguntou preço"},
                            {"id": "branch-b", "label": "Caminho B", "criteria": "lead fez objeção de valor"},
                        ],
                    },
                    {
                        "id": "orient-a", "typeId": "orientacao",
                        "branch_group_id": "cond-1", "branch_id": "branch-a",
                        "content": "CONTEUDO EXCLUSIVO A", "priority": "normal",
                    },
                    {
                        "id": "msg-a", "typeId": "mensagem",
                        "branch_group_id": "cond-1", "branch_id": "branch-a",
                        "content": "mensagem do caminho A",
                    },
                    {
                        "id": "orient-b", "typeId": "orientacao",
                        "branch_group_id": "cond-1", "branch_id": "branch-b",
                        "content": "CONTEUDO EXCLUSIVO B", "priority": "normal",
                    },
                    {
                        "id": "msg-b", "typeId": "mensagem",
                        "branch_group_id": "cond-1", "branch_id": "branch-b",
                        "content": "mensagem do caminho B",
                    },
                ],
            },
        ],
    }


def _sales_flow_branch_with_internal_sequence(phase_id: str) -> dict:
    """Caminho A com dois gatilhos sequenciais (fire_once) — testa se o gating sequencial
    continua funcionando DENTRO de um ramo, isolado do escopo raiz/outros ramos."""
    return {
        "enabled": True,
        "phases": [
            {
                "id": phase_id,
                "blocks": [
                    {
                        "id": "cond-1", "typeId": "condicao", "label": "Interesse", "sticky": False,
                        "branches": [
                            {"id": "branch-a", "label": "A", "criteria": "x"},
                            {"id": "branch-b", "label": "B", "criteria": "y"},
                        ],
                    },
                    {
                        "id": "trig-a1", "typeId": "kw_trigger",
                        "branch_group_id": "cond-1", "branch_id": "branch-a",
                        "keywords": "aceito", "fire_once": True,
                    },
                    {
                        "id": "trig-a2", "typeId": "intent_trigger",
                        "branch_group_id": "cond-1", "branch_id": "branch-a",
                        "intent": "confirmou horario", "fire_once": True,
                    },
                    {
                        "id": "orient-a2", "typeId": "orientacao",
                        "branch_group_id": "cond-1", "branch_id": "branch-a",
                        "content": "SO DEPOIS DO SEGUNDO GATILHO A", "priority": "normal",
                    },
                ],
            },
        ],
    }


def _context(category: str, sales_flow: dict, branches_selected: str = "{}") -> dict:
    return {
        "lead": {"category": category, "triggers_fired": "[]", "branches_selected": branches_selected},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }


# ── Escopo de ramo: só o ramo escolhido entra no prompt/system_actions ──────────────────


def test_only_chosen_branch_appears_sibling_fully_absent():
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=False)
    context = _context("apresentation", sales_flow)

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="quanto custa?",
        branch_selections={"cond-1": "branch-a"},
    )

    injections = "\n".join(result["prompt_injections"])
    assert "CONTEUDO EXCLUSIVO A" in injections
    assert "CONTEUDO EXCLUSIVO B" not in injections
    assert any(a.get("content") == "mensagem do caminho A" for a in result["system_actions"])
    assert not any(a.get("content") == "mensagem do caminho B" for a in result["system_actions"])


def test_unresolved_branch_no_children_execute():
    """Sem escolha da mãe nem valor persistido: nenhum dos dois ramos executa — é o
    default seguro (não inventar caminho sem sinal)."""
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=False)
    context = _context("apresentation", sales_flow)

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="ola",
        branch_selections={},
    )

    injections = "\n".join(result["prompt_injections"])
    assert "CONTEUDO EXCLUSIVO A" not in injections
    assert "CONTEUDO EXCLUSIVO B" not in injections
    assert result["system_actions"] == []


def test_invalid_branch_id_from_mother_ignored():
    """Se a mãe devolver um branch_id que não existe no nó, é tratado como não resolvido
    — não crasha, não escolhe um ramo por engano."""
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=False)
    context = _context("apresentation", sales_flow)

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="ola",
        branch_selections={"cond-1": "branch-inexistente"},
    )

    injections = "\n".join(result["prompt_injections"])
    assert "CONTEUDO EXCLUSIVO A" not in injections
    assert "CONTEUDO EXCLUSIVO B" not in injections


def test_non_sticky_branch_reevaluated_each_turn_no_persistence():
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=False)

    result_a = _evaluate_sales_flow_phases(
        _context("apresentation", sales_flow), effective_route_to="apresentation",
        message_text="quanto custa?", branch_selections={"cond-1": "branch-a"},
    )
    assert not any(a["type"] == "mark_branch_selected" for a in result_a["system_actions"])

    result_b = _evaluate_sales_flow_phases(
        _context("apresentation", sales_flow), effective_route_to="apresentation",
        message_text="ta caro", branch_selections={"cond-1": "branch-b"},
    )
    injections_b = "\n".join(result_b["prompt_injections"])
    assert "CONTEUDO EXCLUSIVO B" in injections_b
    assert "CONTEUDO EXCLUSIVO A" not in injections_b
    assert not any(a["type"] == "mark_branch_selected" for a in result_b["system_actions"])


# ── sticky: persiste, deixa de reperguntar à mãe ─────────────────────────────────────────


def test_sticky_branch_persists_across_turns_without_requerying_mother():
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=True)

    # Turno 1 — mãe resolve pela primeira vez.
    result1 = _evaluate_sales_flow_phases(
        _context("apresentation", sales_flow), effective_route_to="apresentation",
        message_text="quanto custa?", branch_selections={"cond-1": "branch-a"},
    )
    assert any(
        a["type"] == "mark_branch_selected" and a["block_id"] == "cond-1" and a["branch_id"] == "branch-a"
        for a in result1["system_actions"]
    )
    assert "CONTEUDO EXCLUSIVO A" in "\n".join(result1["prompt_injections"])

    # Turno 2 — já persistido (simula o que _dispatch_system_actions gravaria); sem
    # branch_selections da mãe (o nó nem seria listado no prompt dela) continua no ramo A.
    result2 = _evaluate_sales_flow_phases(
        _context("apresentation", sales_flow, branches_selected='{"cond-1": "branch-a"}'),
        effective_route_to="apresentation", message_text="e tem desconto?", branch_selections=None,
    )
    assert "CONTEUDO EXCLUSIVO A" in "\n".join(result2["prompt_injections"])
    assert not any(a["type"] == "mark_branch_selected" for a in result2["system_actions"])


# ── gating sequencial isolado por escopo de ramo ─────────────────────────────────────────


def test_sequential_gating_isolated_per_branch_later_trigger_blocked():
    """O mesmo comportamento de encadeamento sequencial (Fase 1) continua a funcionar
    DENTRO de um ramo: um gatilho fire_once mais à frente não dispara antes do anterior,
    mesmo que a mãe já tenha detectado a intenção do segundo."""
    sales_flow = _sales_flow_branch_with_internal_sequence("p2")
    context = _context("apresentation", sales_flow)

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="ola",
        detected_intents=["confirmou horario"],
        branch_selections={"cond-1": "branch-a"},
    )

    assert not any("SO DEPOIS DO SEGUNDO GATILHO A" in i for i in result["prompt_injections"])
    assert not any(a.get("block_id") == "trig-a2" for a in result["system_actions"])


# ── zero regressão sem nenhum bloco `condicao` configurado ───────────────────────────────


def test_zero_regression_when_no_branch_nodes_configured():
    sales_flow = {
        "enabled": True,
        "phases": [
            {
                "id": "p2",
                "blocks": [
                    {"id": "pt", "typeId": "phase_trigger", "content": "Instrucao de entrada", "priority": "normal"},
                    {"id": "orient-1", "typeId": "orientacao", "content": "Sempre presente", "priority": "normal"},
                ],
            },
        ],
    }
    context = {
        "lead": {"category": "qualification", "triggers_fired": "[]", "phases_triggered": "[]"},
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="oi", is_phase_entry=True,
    )

    assert any("Sempre presente" in i for i in result["prompt_injections"])
    assert result["phase_trigger_fired"] is True


# ── _collect_branch_nodes_for_lead_phase ─────────────────────────────────────────────────


def test_collect_branch_nodes_returns_current_phase_nodes_with_branches():
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=False)
    context = {"lead": {"category": "apresentation", "branches_selected": "{}"}, "ai_profile": {"sales_flow": sales_flow}}

    nodes = _collect_branch_nodes_for_lead_phase(context)

    assert [n["id"] for n in nodes] == ["cond-1"]


def test_collect_branch_nodes_excludes_sticky_already_resolved():
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=True)
    context = {
        "lead": {"category": "apresentation", "branches_selected": '{"cond-1": "branch-a"}'},
        "ai_profile": {"sales_flow": sales_flow},
    }

    nodes = _collect_branch_nodes_for_lead_phase(context)

    assert nodes == []


def test_collect_branch_nodes_includes_non_sticky_even_if_previously_resolved():
    sales_flow = _sales_flow_two_branches_simple("p2", sticky=False)
    context = {
        "lead": {"category": "apresentation", "branches_selected": '{"cond-1": "branch-a"}'},
        "ai_profile": {"sales_flow": sales_flow},
    }

    nodes = _collect_branch_nodes_for_lead_phase(context)

    assert [n["id"] for n in nodes] == ["cond-1"]


# ── _load_branches_selected_map ──────────────────────────────────────────────────────────


def test_load_branches_selected_map_parses_json():
    context = {"lead": {"branches_selected": '{"cond-1": "branch-a"}'}}
    assert _load_branches_selected_map(context) == {"cond-1": "branch-a"}


def test_load_branches_selected_map_invalid_json_returns_empty():
    context = {"lead": {"branches_selected": "not json"}}
    assert _load_branches_selected_map(context) == {}


def test_load_branches_selected_map_missing_returns_empty():
    assert _load_branches_selected_map({"lead": {}}) == {}


# ── MotherDecision.branch_selections ─────────────────────────────────────────────────────


def test_mother_decision_branch_selections_default_empty():
    decision = MotherDecision(route_to="apresentation", confidence=0.9, reason="x")
    assert decision.branch_selections == {}


def test_mother_decision_branch_selections_accepts_mapping():
    decision = MotherDecision(
        route_to="apresentation", confidence=0.9, reason="x",
        branch_selections={"cond-1": "branch-a"},
    )
    assert decision.branch_selections == {"cond-1": "branch-a"}
