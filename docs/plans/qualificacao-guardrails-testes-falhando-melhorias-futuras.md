# Qualificação/guardrails — 23 testes já falhando em `main`, investigação pendente

> Contexto: item deixado de fora da graduação de
> `docs/implementations/fix-sales-flow-recepcao-p0-nao-dispara.md` (23/08/2026).
> Ao rodar a suíte completa (`pytest backend-executors/tests/`) tanto na
> worktree dessa implementação quanto na pasta principal (`main`), o mesmo
> conjunto de 23 testes falhou nos dois lugares — confirmando que não é
> causado pela implementação nem pelo processo de worktree, e que já é uma
> regressão (ou teste desatualizado) presente em `main` hoje.

---

## M1 — Investigar e corrigir os 23 testes falhando em `main`

**Prioridade: MÉDIA**

Testes concentrados em: `test_qualification_contract.py`,
`test_qualification_state_loop.py`,
`test_mother_qualification_route_guardrail.py`, `test_guardrails_by_mode.py`,
`test_phase2_direct_question_reply_priority.py`, `test_followup_tick_*.py`,
`test_followup_prompt_contract_context.py`,
`test_recepcao_pending_commercial_extraction.py`.

**Exemplo concreto:** `test_compute_missing_fields_direto_minimal` espera que
`price_acceptance` seja campo obrigatório do modo `direto`
(`compute_missing_fields("direto", ...)`), mas o código hoje retorna lista
vazia — ou o requisito mudou sem atualizar o teste, ou é uma regressão real
na função `compute_missing_fields`
(`backend-executors/app/contracts/qualification_contract.py`).

**Por que é MÉDIA e não ALTA/BAIXA:** a área é sensível (qualificação e
roteamento de leads, tocando guardrails que decidem quando um lead avança de
fase), então merece investigação dedicada e não deve ficar esquecida —  mas
não há hoje sinal concreto de que esteja causando um problema visível em
produção (o comportamento observado nos testes reais do Playground, ver
`docs/implementations/sessao-teste-corrente.md`, não apontou nenhuma falha
atribuível a este conjunto específico).

**Medição de 04/10/2026:** a suíte completa, corrida numa worktree sem `.env`
durante a validação de `feat-modo-auto-sem-cliques.md` (implementação que não
toca em código de backend), deu 265 a passar e 73 a falhar. Contagem de linhas
de erro na saída (não de testes — o total passa de 73, logo há testes com mais
de uma): 39 × `'DecisionOutput' object has no attribute 'pre_send_media'`,
17 × `decision_trace`, 16 × `CRM_SERVICE_TOKEN não configurado` (falta de
`.env` na worktree), 10 × `suggested_category`, 2 ×
`FakeCRMClient.create_lead_appointment() got an unexpected keyword argument
'source'`, e 4 asserções isoladas. Ficheiros novos na lista:
`test_qualification_sales_flow_pending.py`, `test_recepcao_sales_flow_pending.py`,
`test_requeue_pending_message_routing.py`, `test_scheduling_agent_no_closing.py`.
Não foi repetido em `main` com `.env` presente — confirmar isso é o primeiro
passo da investigação, porque o conjunto cresceu em relação aos 23 originais.

**Próximo passo sugerido:** abrir Plan Mode dedicado (não é uma correção de
1 linha — precisa decidir, teste a teste, se o teste está desatualizado ou se
o código regrediu) antes de tocar em qualquer um desses arquivos.
