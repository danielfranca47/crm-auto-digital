# Novas tentativas da IA — Melhorias Futuras

> Contexto: itens deixados de fora da implementação
> `docs/implementations/feat-retry-llm-resposta-invalida.md` (graduada em 26/10/2026). Hoje a Mãe e a Filha
> repetem a etapa que falhou até 4 vezes, com o mesmo prompt, antes do handoff — ver
> [`llm-architecture.md`](../architecture/llm-architecture.md), secção "Falhas da IA e novas tentativas
> (Mãe/Filha)". Medição de origem: 4 handoffs em 355 turnos no Playground, todos por resposta inválida.

**Gatilho para voltar a isto:** os logs depois do deploy (`llm_stage_exhausted`, `llm_orchestrator_error`)
continuarem a mostrar handoffs por falha da IA.

---

## M1 — Dizer à IA o que estava errado na nova tentativa

**Prioridade: BAIXA**

**Em palavras simples:** a nova tentativa reenvia exatamente o mesmo pedido e conta com a variação natural da IA.
Juntar ao pedido o erro da tentativa anterior (ex.: "faltou o campo `confidence`", "`route_to` tem de ser um
destes valores") deve acertar mais vezes à 2.ª tentativa.

**O que precisaria existir:**
- Em `decision_engine._run_llm_stage`, passar o motivo/mensagem do `ValidationError` para a chamada seguinte
- Texto curto de correção no fim do prompt da Mãe/Filha, como o `VALIDATION_ERRORS` que a Filha `qualification`
  já usa
- Mexe nas instruções da IA: ler `docs/architecture/prompt-engineering-principles.md` antes; o merge sobe ao
  utilizador

---

## M2 — Mesmas novas tentativas no atalho de gestão pós-reunião

**Prioridade: BAIXA**

**Em palavras simples:** quando o lead já tem reunião marcada, `decide()` vai por um atalho
(`_decide_post_meeting_management`) que chama a Filha diretamente e, se ela falhar, cai no seu próprio
fallback (`reason="meeting_management_llm_failure"`) sem nova tentativa.

**O que precisaria existir:**
- Envolver a chamada `generate_child_result` desse atalho com `_run_llm_stage` (com o seu próprio orçamento)
- Teste com a Filha simulada a falhar 1–4 vezes nesse caminho
