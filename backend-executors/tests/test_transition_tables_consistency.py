"""Rede de segurança para docs/implementations/unificar-transicoes-fase-sales-flow.md.

`_ALLOWED_ADVANCE` (vocabulário de categoria, usado pelos guardrails de
`apply_mother_category_guardrails`/`_apply_child_micro_adjustment`/
`_enforce_<fase>_sales_flow_pending`) e `_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE`
(vocabulário de phase_id, usado só para "olhar a próxima fase" na coleta de
intent_trigger/nós de condição) descrevem o mesmo conceito — "para onde este
lead pode ir a seguir" — em vocabulários diferentes, mantidos à mão em
paralelo, sem nenhuma relação declarada entre eles.

Este teste não unifica as duas estruturas (decisão do usuário: risco de tocar
um arquivo crítico de guardrails não compensava, dada a boa cobertura de teste
já existente nas bordas relevantes). Em vez disso, garante que toda transição
sequencial `p_i -> p_{i+1}` de qualquer `agent_mode` em
`_SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE` continua permitida em
`_ALLOWED_ADVANCE` — se isso falhar, alguém mudou uma sequência (nova fase,
novo agent_mode, reordenação) sem atualizar a outra tabela.
"""
from app.services.decision_engine import (
    _ALLOWED_ADVANCE,
    _ROUTE_TO_PHASE_ID,
    _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE,
    _STAGE_ORDER,
)

# Duas transições existem em _ALLOWED_ADVANCE hoje que não vêm de nenhum par
# consecutivo de _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE — são "escape valves"
# deliberados, não bordas derivadas da sequência linear por agent_mode:
#   - pre-agendamento -> follow-up: desistência no meio do agendamento (lead
#     não confirma horário, Mãe move para nutrição fora do pipeline estrito).
#   - agendamento -> client-list: "client-list" não tem phase_id nenhum — é um
#     estado fora do funil de fases do Fluxo de Venda (lead virou cliente).
_KNOWN_NON_SEQUENTIAL_EDGES = {
    ("pre-agendamento", "follow-up"),
    ("agendamento", "client-list"),
}


def _build_phase_id_to_category() -> dict:
    """Inverte _ROUTE_TO_PHASE_ID mantendo só a grafia canônica (as mesmas
    chaves usadas em _STAGE_ORDER, mais "recepcao") — _ROUTE_TO_PHASE_ID tem
    entradas duplicadas com underscore (ex.: "pre_agendamento") que mapeiam
    para o mesmo phase_id e não devem "vencer" a grafia com hífen usada em
    _ALLOWED_ADVANCE."""
    canonical_categories = set(_STAGE_ORDER) | {"recepcao"}
    return {
        phase_id: category
        for category, phase_id in _ROUTE_TO_PHASE_ID.items()
        if category in canonical_categories
    }


def test_phase_id_to_category_covers_every_phase_used_in_sequences():
    """Pré-condição do teste principal: toda fase citada em alguma sequência
    de agent_mode precisa ter uma categoria canônica correspondente — senão o
    teste principal ficaria silenciosamente incompleto."""
    phase_id_to_category = _build_phase_id_to_category()
    phases_used = {
        phase_id
        for sequence in _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE.values()
        for phase_id in sequence
    }
    missing = phases_used - phase_id_to_category.keys()
    assert not missing, (
        f"Fases sem categoria canônica mapeada: {sorted(missing)} — "
        f"_ROUTE_TO_PHASE_ID/_STAGE_ORDER precisam cobrir todas as fases "
        f"usadas em _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE."
    )


def test_allowed_advance_covers_every_sequential_edge():
    """Toda transição p_i -> p_{i+1} de qualquer agent_mode precisa estar
    refletida em _ALLOWED_ADVANCE (via a categoria equivalente). Se este
    teste falhar, alguém mudou _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE (nova
    fase, novo agent_mode, reordenação) sem atualizar _ALLOWED_ADVANCE em
    conjunto — adicione a transição faltante na entrada correspondente de
    _ALLOWED_ADVANCE."""
    phase_id_to_category = _build_phase_id_to_category()
    failures = []
    for agent_mode, sequence in _SALES_FLOW_PHASE_SEQUENCE_BY_AGENT_MODE.items():
        for current_phase, next_phase in zip(sequence, sequence[1:]):
            current_category = phase_id_to_category.get(current_phase)
            next_category = phase_id_to_category.get(next_phase)
            if not current_category or not next_category:
                continue
            allowed_next = _ALLOWED_ADVANCE.get(current_category, set())
            if next_category not in allowed_next:
                failures.append(
                    f"agent_mode={agent_mode!r}: {current_phase}({current_category}) -> "
                    f"{next_phase}({next_category}) não está em "
                    f"_ALLOWED_ADVANCE[{current_category!r}]={allowed_next!r}"
                )
    assert not failures, "Transições fora de _ALLOWED_ADVANCE:\n" + "\n".join(failures)


def test_known_non_sequential_edges_still_present():
    """Documenta as 2 exceções conhecidas que não vêm de nenhuma sequência de
    agent_mode — se uma delas for removida de _ALLOWED_ADVANCE, este teste
    avisa que a remoção foi deliberada (atualizar _KNOWN_NON_SEQUENTIAL_EDGES
    acima) ou um acidente (investigar antes de seguir)."""
    for current_category, next_category in _KNOWN_NON_SEQUENTIAL_EDGES:
        allowed_next = _ALLOWED_ADVANCE.get(current_category, set())
        assert next_category in allowed_next, (
            f"Exceção conhecida {current_category!r} -> {next_category!r} não "
            f"está mais em _ALLOWED_ADVANCE — se a remoção foi deliberada, "
            f"atualize _KNOWN_NON_SEQUENTIAL_EDGES neste teste."
        )
