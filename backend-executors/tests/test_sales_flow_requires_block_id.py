from app.services.decision_engine import _evaluate_sales_flow_phases


def _sales_flow_with_dependency(
    *,
    target_type: str = "phase_trigger",
    target_fire_once: bool = True,
    target_phase_id: str = "p2",
    dependent_phase_id: str = "p2",
) -> dict:
    """Fase p2 com um bloco-alvo sequencial ("target") e um kw_trigger ("dependent") que
    declara `requires_block_id="target"`. `target` fica DEPOIS de `dependent` no array —
    propositalmente, para isolar o teste do gating posicional (_prereqs_satisfied_by_scope),
    que só olha o bloco IMEDIATAMENTE anterior no mesmo escopo. `dependent` tem
    `fire_once=True` só para deixar observável via `mark_trigger_fired` nos system_actions —
    não é isso que o gating desta feature depende (funciona igual sem fire_once no
    dependente, só não haveria como observar o disparo por essa via)."""
    target_block = {"id": "target", "typeId": target_type}
    if target_type in ("kw_trigger", "intent_trigger"):
        target_block["fire_once"] = target_fire_once
        target_block["keywords"] = "tabela"
        if target_type == "intent_trigger":
            target_block["intent"] = "aceitou a tabela"

    dependent_block = {
        "id": "dependent",
        "typeId": "kw_trigger",
        "keywords": "preço",
        "fire_once": True,
        "requires_block_id": "target",
    }

    phases = [{"id": "p0", "blocks": []}, {"id": "p1", "blocks": []}]
    if target_phase_id == dependent_phase_id:
        phases.append({"id": dependent_phase_id, "blocks": [dependent_block, target_block]})
    else:
        phases.append({"id": target_phase_id, "blocks": [target_block]})
        phases.append({"id": dependent_phase_id, "blocks": [dependent_block]})

    return {"enabled": True, "phases": phases}


def _context(sales_flow: dict, *, triggers_fired: str = "[]", phases_triggered: str = "[]") -> dict:
    return {
        "lead": {
            "category": "apresentation",
            "triggers_fired": triggers_fired,
            "phases_triggered": phases_triggered,
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }


def test_requires_block_id_blocks_until_dependency_persisted():
    """Bloco-alvo (phase_trigger) ainda não persistido em phases_triggered — o dependente
    não dispara, mesmo com keyword match na mensagem."""
    sales_flow = _sales_flow_with_dependency()
    context = _context(sales_flow, phases_triggered="[]")

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="quero saber o preço",
        is_phase_entry=False,
    )

    assert not any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "dependent"
        for a in result["system_actions"]
    )


def test_requires_block_id_satisfied_once_dependency_persisted():
    """Bloco-alvo já persistido de um turno anterior — o dependente pode disparar."""
    sales_flow = _sales_flow_with_dependency()
    context = _context(sales_flow, phases_triggered='["p2"]')

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="quero saber o preço",
        is_phase_entry=False,
    )

    assert any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "dependent"
        for a in result["system_actions"]
    )


def test_requires_block_id_never_satisfied_same_turn():
    """Garantia central: mesmo que o bloco-alvo dispare NESTE turno, o dependente não
    dispara — só reconhece satisfação persistida de um turno ANTERIOR.

    `dependent` é deliberadamente um kw_trigger SEM fire_once (não-sequencial), para
    isolar o teste do gating posicional pré-existente (_prereqs_satisfied_by_scope) — só
    o `requires_block_id` pode estar travando aqui. A observação do disparo é indireta:
    uma orientação logo a seguir só é injectada se `dependent` disparou (governa
    last_trigger_active para o próximo bloco de ação)."""
    sales_flow = {
        "enabled": True,
        "phases": [
            {"id": "p0", "blocks": []},
            {"id": "p1", "blocks": []},
            {
                "id": "p2",
                "blocks": [
                    {"id": "target", "typeId": "kw_trigger", "keywords": "tabela", "fire_once": True},
                    {
                        "id": "dependent", "typeId": "kw_trigger", "keywords": "preço",
                        "requires_block_id": "target",
                    },
                    {"id": "guard", "typeId": "orientacao", "content": "ORIENTACAO_APOS_DEPENDENTE"},
                ],
            },
        ],
    }

    # Turno 1 — mensagem contém keyword de AMBOS os blocos: o alvo dispara neste turno,
    # mas o dependente ainda não deve (alvo só persiste DEPOIS deste turno).
    context1 = _context(sales_flow, triggers_fired="[]")
    result1 = _evaluate_sales_flow_phases(
        context1, effective_route_to="apresentation",
        message_text="quero saber o preço da tabela", is_phase_entry=False,
    )
    assert any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "target"
        for a in result1["system_actions"]
    )
    assert not any("ORIENTACAO_APOS_DEPENDENTE" in i for i in result1["prompt_injections"])

    # Turno 2 — alvo já persistido (simulando o mark_trigger_fired do turno 1 já
    # processado pelo CRM) — agora o dependente dispara.
    context2 = _context(sales_flow, triggers_fired='["target"]')
    result2 = _evaluate_sales_flow_phases(
        context2, effective_route_to="apresentation",
        message_text="quero saber o preço", is_phase_entry=False,
    )
    assert any("ORIENTACAO_APOS_DEPENDENTE" in i for i in result2["prompt_injections"])


def test_requires_block_id_dangling_reference_fails_open():
    """Referência a um id que não existe em nenhum bloco — sem efeito, dependente dispara
    normalmente."""
    sales_flow = _sales_flow_with_dependency()
    # Remove o bloco-alvo, deixando a referência pendurada.
    sales_flow["phases"][2]["blocks"] = [
        b for b in sales_flow["phases"][2]["blocks"] if b["id"] != "target"
    ]
    context = _context(sales_flow, phases_triggered="[]")

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="quero saber o preço",
        is_phase_entry=False,
    )

    assert any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "dependent"
        for a in result["system_actions"]
    )


def test_requires_block_id_target_no_longer_sequential_fails_open():
    """Bloco-alvo ainda existe mas deixou de ser sequencial (fire_once=False) — sem
    registo persistido possível; a dependência falha aberto em vez de travar para sempre."""
    sales_flow = _sales_flow_with_dependency(target_type="kw_trigger", target_fire_once=False)
    context = _context(sales_flow, triggers_fired="[]", phases_triggered="[]")

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="quero saber o preço",
        is_phase_entry=False,
    )

    assert any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "dependent"
        for a in result["system_actions"]
    )


def test_requires_block_id_resolves_against_referenced_blocks_own_phase():
    """Regressão do refinamento crítico: um phase_trigger referenciado vive em OUTRA fase
    (p1) — a checagem tem de usar o phase_id do bloco referenciado, não o da fase p2 que
    está a ser avaliada agora."""
    sales_flow = _sales_flow_with_dependency(target_phase_id="p1", dependent_phase_id="p2")

    # phases_triggered contém "p1" (o alvo já disparou lá) mas não "p2" — deve satisfazer.
    context_satisfied = _context(sales_flow, phases_triggered='["p1"]')
    result_satisfied = _evaluate_sales_flow_phases(
        context_satisfied, effective_route_to="apresentation",
        message_text="quero saber o preço", is_phase_entry=False,
    )
    assert any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "dependent"
        for a in result_satisfied["system_actions"]
    )

    # phases_triggered contém "p2" (a fase sendo avaliada) mas NÃO "p1" (a fase real do
    # alvo) — não deve satisfazer; prova que o phase_id certo é usado, não o da fase corrente.
    context_not_satisfied = _context(sales_flow, phases_triggered='["p2"]')
    result_not_satisfied = _evaluate_sales_flow_phases(
        context_not_satisfied, effective_route_to="apresentation",
        message_text="quero saber o preço", is_phase_entry=False,
    )
    assert not any(
        a.get("type") == "mark_trigger_fired" and a.get("block_id") == "dependent"
        for a in result_not_satisfied["system_actions"]
    )


def test_no_requires_block_id_behaves_exactly_as_before():
    """Regressão: um kw_trigger sem `requires_block_id` continua a disparar normalmente,
    liberando a orientação seguinte — sem qualquer trava nova."""
    sales_flow = {
        "enabled": True,
        "phases": [
            {"id": "p0", "blocks": []},
            {"id": "p1", "blocks": []},
            {
                "id": "p2",
                "blocks": [
                    {"id": "plain", "typeId": "kw_trigger", "keywords": "preço"},
                    {"id": "orientacao-1", "typeId": "orientacao", "content": "Explique os planos."},
                ],
            },
        ],
    }
    context = _context(sales_flow)

    result = _evaluate_sales_flow_phases(
        context, effective_route_to="apresentation", message_text="quero saber o preço",
        is_phase_entry=False,
    )

    assert any("Explique os planos." in i for i in result["prompt_injections"])
