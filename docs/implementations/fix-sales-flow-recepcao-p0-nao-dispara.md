# Fix: blocos da fase Recepção (p0) do Fluxo de Venda "nunca disparam"

**Branch:** `worktree-fix+sales-flow-recepcao-p0-nao-dispara`
**Status:** Todos os cenários validados (23/08/2026) — sem correção de código; achados laterais documentados abaixo, fora do escopo

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`nome-whatsapp-lead-variaveis-fluxo-venda.md` (achado lateral, confirmado ao
vivo durante o teste da Fase 3 dessa implementação, 20/08/2026): um bloco
`mensagem` configurado na fase Recepção (p0) do Fluxo de Venda apareceu no
Playground com `phase_trigger_fired=false` e `auto_items=[]` — parecendo
nunca disparar, apesar de `docs/architecture/sales-flow.md` documentar p0
como "Sempre ativo? Sim".

**Diagnóstico do Plan Mode (23/08/2026) revisou a causa raiz original.** A
hipótese inicial ("`_ROUTE_TO_PHASE_ID` exclui p0") não se sustenta contra o
código atual — ver "Problemas Identificados" abaixo. Por isso a Fase 1 desta
implementação é puramente diagnóstica (reprodução controlada), antes de
qualquer mudança de código.

---

## Problemas Identificados (estado anterior)

Investigação estática de `backend-executors/app/services/decision_engine.py`
não encontrou nenhum ponto que exclua p0 do disparo real de blocos:

1. **`_ROUTE_TO_PHASE_ID["recepcao"] = "p0"` já existe e está correta** desde
   pelo menos 18/08/2026, consolidada num único lugar em 21/08/2026 (commit
   `9693e1f`, removendo uma duplicação com `_ROUTE_TO_PHASE_ID_MAP` — as duas
   cópias já tinham o mesmo valor para `"recepcao"`, então a duplicação em si
   não explica um bug de disparo).
2. **`_enforce_greeting_first()` força `route_to = "recepcao"`** sempre que
   `outbound_count == 0` no histórico — cobre de forma confiável o(s)
   primeiro(s) turno(s) reais de qualquer lead novo.
3. **O dispatch real de `system_actions`** (o que gera `auto_items` no
   Playground) acontece em `compose_decision_output()` (~linha 5177) via
   `_evaluate_sales_flow_phases(context, effective_route_to, ...)`, com
   `effective_route_to = effective_route_override or mother_decision.route_to`
   — nada nesse caminho trata "recepcao"/p0 de forma diferente das outras
   fases.
4. **Testes unitários de `_evaluate_sales_flow_phases()`**
   (`test_sales_flow_intent_trigger_phase_entry.py`) cobrem o mesmo mecanismo
   para `effective_route_to="apresentation"` (p2) com sucesso — a função é
   genérica, sem tratamento especial por fase.
5. **Gap real encontrado:** não existe hoje nenhum teste — unitário ou de
   integração — que prove que um bloco de ação em p0 dispara (ou não). Os 9
   testes de `test_recepcao_sales_flow_pending.py` (commit `3127f4b`,
   22/08/2026, implementação já graduada `sales-flow-guardrail-p0-recepcao.md`)
   cobrem só o **bloqueio de `route_to`** pelo guardrail — nunca o disparo de
   fato de um bloco `mensagem`/`midia` em p0.

**Conclusão:** o achado de 20/08 pode ter sido (a) um artefacto do teste
daquela sessão específica (ex.: lead de sandbox reaproveitado que já tinha
passado da recepção — nesse caso o bloco corretamente não dispara, não é
bug), ou (b) um bug real já corrigido incidentalmente pelo trabalho de
21–22/08 nesta mesma área. Sem reprodução controlada não dá para saber qual
dos dois.

---

## Abordagem

```
Fase 1 — Reprodução controlada (sem mudança de código de produto)
  → lead de sandbox NOVO (garante outbound_count=0)
  → ai_profile.sales_flow habilitado, bloco "mensagem" em p0
      (testar com e sem phase_trigger explícito)
  → disparar via Playground (browser) ou script direto contra decide()
  → confirmar: system_actions/auto_items contêm o bloco?
       ├─ SIM (reproduziu) → Fase 2a: diagnosticar causa raiz real + corrigir
       └─ NÃO (não reproduziu) → Fase 2b: sem mudança de comportamento;
            só corrige doc (se necessário) + adiciona teste de cobertura
            que faltava + fecha a investigação documentada
```

---

## Plano de Implementação

### Fase 1 — Reprodução controlada

**Objetivo:** confirmar, com um cenário limpo, se um bloco `mensagem`
configurado em p0 realmente não dispara hoje.

| Arquivo | O que muda |
|---|---|
| (nenhum arquivo de produto) | Script de diagnóstico direto contra `decide()`/`_evaluate_sales_flow_phases()`, ou teste manual via Playground com lead de sandbox novo |

### Fase 2a — Se reproduziu: correção real

A definir após o resultado da Fase 1 — escopo exato depende da causa raiz
encontrada.

### Fase 2b — Se não reproduziu: fechamento documentado

| Arquivo | O que muda |
|---|---|
| `backend-executors/tests/test_sales_flow_intent_trigger_phase_entry.py` (ou arquivo novo dedicado) | Novo teste unitário cobrindo dispatch de bloco `mensagem`/`midia` em p0 via `_evaluate_sales_flow_phases(effective_route_to="recepcao", ...)` — cobertura que faltava, independente de haver bug |
| `docs/architecture/sales-flow.md` | Corrigir só se a investigação revelar alguma imprecisão |

---

### Commits Fase 1 + Fase 2b

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1e8a26b` | Testes de dispatch de bloco `mensagem` em p0 (`_evaluate_sales_flow_phases` direto + integração via `decide()`) — resultado: NÃO reproduzido, sem correção de código |

**Detalhes:**
- `backend-executors/tests/test_recepcao_sales_flow_pending.py` — 3 testes novos: 2 chamando `_evaluate_sales_flow_phases(effective_route_to="recepcao", ...)` diretamente (com e sem `phase_trigger` explícito), 1 de integração completa via `decision_engine.decide()` com lead novo (histórico vazio) confirmando que `decision.system_actions` recebe o `send_message` do bloco de p0

### Relatório da Fase 1 — o que foi investigado

**Antes:** o arquivo original suspeitava que blocos de "Recepção" (p0) do Fluxo de Venda nunca disparavam, por um mapa interno (`_ROUTE_TO_PHASE_ID`) supostamente excluir essa fase.

**Agora:** reproduzi o cenário de forma controlada — lead novo, bloco "mensagem" configurado em p0, com e sem gatilho de entrada — chamando diretamente o motor de decisão. **O bloco disparou corretamente nos dois casos.** A causa raiz apontada no arquivo original (mapa excluindo p0) não existe no código atual: o mapa já inclui p0 corretamente, e nada no motor trata a Recepção de forma diferente das demais fases. A explicação mais provável é que o teste original (20/08/2026) tenha usado um lead de sandbox que já tinha passado da fase de recepção naquele momento específico — nesse caso, o bloco corretamente não dispara (a conversa já saiu da recepção), o que não é bug.

**Para validar:** Cenário P1 e P2 abaixo (via suíte automatizada, já executada — ver Fase 2b).

### Relatório da Fase 2b — o que mudou na prática

**Antes:** não havia nenhum teste automatizado (unitário ou de integração) provando que um bloco de "mensagem" ou "mídia" configurado na fase Recepção do Fluxo de Venda realmente chega a ser enviado. Só existiam testes do mecanismo que *bloqueia* a Mãe de pular a recepção cedo demais — um mecanismo diferente.

**Agora:** 3 testes novos cobrem especificamente isso — incluindo um teste de ponta a ponta simulando um lead totalmente novo. Não houve nenhuma mudança de comportamento do sistema (o comportamento já estava correto); só passou a ter rede de segurança automatizada contra uma regressão futura nesse ponto específico.

**Para validar:** já validado nesta sessão — ver "Achado lateral 1" abaixo para os comandos exatos usados.

---

## Checks de Validação

### Cenário P1 — Bloco `mensagem` em p0 dispara (reprodução controlada)
- [x] Chamada direta a `_evaluate_sales_flow_phases(effective_route_to="recepcao", ...)` com bloco `mensagem` em p0, com `phase_trigger` explícito
- [x] Repetir sem `phase_trigger` explícito (dispara por padrão, como qualquer outra fase)
- **Validado em:** 23/08/2026 — script de diagnóstico direto (`diag_p0_dispatch.py`, scratchpad, não commitado) confirmou `system_actions` contendo o `send_message` nos dois casos. Depois formalizado como teste automatizado (ver Fase 2b).

### Cenário P2 — Cobertura de teste automatizada
- [x] Novos testes unitários/integração passam
- [x] Suíte completa `pytest backend-executors/tests/` — sem regressões causadas por esta mudança
- **Validado em:** 23/08/2026 — `test_recepcao_sales_flow_pending.py`: 12 passed (9 originais + 3 novos). Suíte completa: 23 failed / 235 passed — **os 23 failed já existiam antes desta implementação, em `main`, sem relação com p0** (ver Achado lateral 2 abaixo).

---

## Ajustes Possíveis Pós-Implementação

Nenhum ajuste pendente da correção em si (não houve correção — comportamento já estava certo).

**Achado lateral 1 — worktrees novas não herdam `.env`/`.venv` (gitignored):** ao rodar a suíte de testes pela primeira vez nesta worktree (`fix/sales-flow-recepcao-p0-nao-dispara`), 2 testes pré-existentes falharam (`test_p0_trigger_already_fired_advances_normally`, `test_no_sequential_trigger_in_p0_behaves_like_baseline`) — não por bug, mas porque a worktree nasce sem o `backend-executors/.env` real (só `.env.example`), já que `.env` é gitignored e não é copiado automaticamente por `EnterWorktree`. Copiando o `.env` da pasta principal para a worktree, os 2 testes passaram a verde. Vale documentar este passo manual em `docs/ops/` para quem for rodar testes de backend numa worktree nova — sem isso, alguém pode diagnosticar "bug" onde só falta configuração local. `.venv` também não existe na worktree (mesmo motivo); os testes desta sessão rodaram com o Python global do sistema (pacotes já presentes; `pytest` foi instalado nele durante esta sessão) — outra worktree pode precisar criar seu próprio `.venv` se depender de versões pinadas específicas do `requirements.txt`.

**Achado lateral 2 — 23 testes já falhando em `main`, sem relação com p0 (confirmado independentemente da worktree):** rodando a suíte completa tanto na worktree (com `.env` copiado) quanto na pasta principal (`main`, com `.env`/`.venv` reais), o mesmo conjunto de 23 testes falha nos dois lugares — não é causado por esta implementação nem pelo processo de worktree. Concentrados em `test_qualification_contract.py`, `test_qualification_state_loop.py`, `test_mother_qualification_route_guardrail.py`, `test_guardrails_by_mode.py`, `test_phase2_direct_question_reply_priority.py`, `test_followup_tick_*.py`, `test_followup_prompt_contract_context.py`, `test_recepcao_pending_commercial_extraction.py`. Exemplo concreto: `test_compute_missing_fields_direto_minimal` espera que `price_acceptance` seja campo obrigatório do modo `direto` (`compute_missing_fields("direto", ...)`) mas o código hoje retorna lista vazia — ou o requisito mudou sem atualizar o teste, ou é uma regressão real na função `compute_missing_fields` (`backend-executors/app/contracts/qualification_contract.py`). Isto é potencialmente sério (área de qualificação/guardrails, não só follow-up) e está fora do escopo desta implementação — recomendo abrir Plan Mode dedicado para investigar, dado o volume e a área sensível (qualificação/roteamento).
