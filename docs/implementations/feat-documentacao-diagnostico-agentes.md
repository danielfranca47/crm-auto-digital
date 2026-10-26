# Documentar o diagnóstico de agentes + skill própria de documentação

**Branch:** `worktree-feat+documentacao-diagnostico-agentes`
**Status:** Em andamento
**Autonomia:** manual

---

## Motivação

Foram criadas 4 skills para diagnosticar e afinar o agente de IA de uma conta de cliente a partir de
conversas reais (`diagnosticar-agente` + uma por agente da página Tipos de Agentes). Vão ser a ferramenta de
onboarding e suporte, mas só existem no PC do utilizador, sem guia para o time, e os factos de cada agente
estão copiados dentro delas. Os docs por agente que já existiam estão desatualizados. O utilizador aprovou
uma arquitetura de documentação com fonte única de verdade, validada com 3 skills de terceiros
(`writing-for-agents`, `documentation-and-adrs`, `claude-md-improver`), e pediu que essas 3 passem a ser
uma única skill nossa, adaptada ao projeto.

---

## Problemas Identificados (estado anterior)

1. **Skills e comandos não versionados:** `.gitignore:42` ignora `.claude/` inteiro (só `settings.json`
   foi forçado). Perdem-se ao trocar de máquina e não chegam ao time nem às sessões na cloud.
2. **Cópias dos comandos na documentação:** `docs/ops/local-dev.md` (secção "Comandos slash locais")
   guarda o conteúdo integral de cada comando para o poder recriar; `docs/discovery/README.md:55` repete
   que não são versionados.
3. **Docs dos agentes desatualizados e fora do sítio:** `docs/agente-1-sdr-alto-ticket.md`,
   `docs/agente-2-closer-agressivo.md`, `docs/agente-3-hibrido.md` (último commit 31/05/2026) — campos
   obrigatórios fixos por modo, nomes diferentes dos da página `/agentes-info`. Já pedido em
   `docs/plans/docs-qualificacao-campos-obrigatorios-melhorias-futuras.md` M2. (Correção ao diagnóstico do
   Plan Mode: `requires_handoff`/`human_in_loop` **são** lidos — `decision_engine._compute_system_agent_mode`
   passa `sdr_scheduler` a `consultivo` quando algum está ligado; o doc antigo estava certo nesse ponto. Mas
   `orchestrator._normalize_agent_mode_for_bundle` normaliza `sdr_scheduler` sempre como `agenda`, sem os ler —
   incoerência a registar no doc do Agente 01.)
4. **Factos do sistema duplicados nas skills:** as skills de agente têm tabelas de fases, campos e
   lembretes que vão desatualizar.
5. **Skills de documentação de terceiros:** atualizam-se sozinhas com `npx skills update`, parte do
   conteúdo contradiz a convenção do projeto (`docs/decisions/` com ADRs numerados) e são 3 descrições
   sempre carregadas.
6. **Sem guia para o time** de onboarding e suporte.

---

## Abordagem

Cada tipo de conhecimento num só sítio:

| Conteúdo | Onde |
|---|---|
| Como o Claude atua (passos, scripts) | `.claude/skills/` — versionado |
| Factos de cada agente (preset, fases, campos, página vs. código) | `docs/architecture/agentes/agente-0X-*.md` |
| Como o time usa | `docs/ops/diagnostico-agentes.md` |
| Porquê das decisões | este ficheiro → graduação |
| Apontador e regra de manutenção | `CLAUDE.md` (2 linhas) |
| Dados de clientes | `.claude/agentes/<cliente>/` — fora do git |

---

## Plano de Implementação

### Fase 1 — Versionar skills e comandos

**Objetivo:** skills e comandos slash no repositório, sem dados de clientes.

| Arquivo | O que muda |
|---|---|
| `.gitignore` | `.claude/` → `.claude/*` + exceções `settings.json`, `skills/`, `commands/` |
| `.claude/skills/**` | as 4 skills de diagnóstico, depois da revisão de privacidade |
| `.claude/commands/*.md` | os comandos slash existentes |
| `docs/ops/local-dev.md` | cópias dos comandos → apontadores para os ficheiros |
| `docs/discovery/README.md` | deixa de dizer que os comandos não são versionados |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `297f834` | `.gitignore` com exceções, `.gitattributes`, 4 skills, 9 comandos, cópias de `local-dev.md` → tabela |

**Detalhes do commit `297f834`:**
- `.gitignore` — `.claude/` → `.claude/*` + `!settings.json`, `!skills/`, `!commands/`
- `.gitattributes` (novo) — `*.sh text eol=lf`: o repositório usa `core.autocrlf=true` e o bash falha com CRLF
  (`aplicar_producao.sh` é o único `.sh`)
- `docs/ops/local-dev.md` — as 9 cópias dos comandos foram comparadas com os ficheiros reais (todas
  idênticas) antes de darem lugar à tabela
- referências a "Comandos slash locais" atualizadas em 5 ficheiros; a de
  `feat-fila-turno-do-dia-avaliador.md` fica (registo histórico de outra implementação)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** as skills de diagnóstico e os comandos `/statusdev`, `/discovery-*` e afins existiam só neste
computador; noutra máquina, outra pessoa ou uma sessão na cloud não os tinha, e o `local-dev.md` guardava
cópias deles para os recriar à mão.
**Agora:** fazem parte do repositório e chegam a qualquer cópia dele; as conversas reais dos clientes
continuam fora.
**Para validar:** P1, P2 (feitos), P6 no fim.

### Fase 2 — Skill `documentacao-projeto`

**Objetivo:** uma skill nossa, em PT-PT, que substitui as 3 de terceiros.

| Arquivo | O que muda |
|---|---|
| `.claude/skills/documentacao-projeto/SKILL.md` | router curto: escrever para agentes · registar decisões · auditar CLAUDE.md |
| `.../references/escrever-para-agentes.md` | de `writing-for-agents` + `SKILL-MECHANICS.md` |
| `.../references/registar-decisoes.md` | de `documentation-and-adrs`, adaptado à convenção do projeto |
| `.../references/auditar-claude-md.md` | de `claude-md-improver`, adaptado às regras do nosso CLAUDE.md |
| `.../CREDITOS.md` | licenças (MIT ×2, Apache-2.0), origem, data, o que mudou |

Fora do repositório: remover as 3 skills globais de terceiros.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(este commit)_ | skill `documentacao-projeto` (router + 3 referências + créditos) |

**Detalhes:**
- `SKILL.md` — router de 3 casos; uma única descrição sempre carregada em vez de 3
- `references/registar-decisoes.md` — sem `docs/decisions/`: o porquê vive em discovery → implementations →
  secção "Porquê está assim" em `docs/architecture/` na graduação, sem histórico
- `references/auditar-claude-md.md` — rubrica de 100 pontos + regras próprias (o CLAUDE.md é índice e regras;
  as secções obrigatórias nunca se cortam sem o utilizador)
- `CREDITOS.md` — MIT (Matt Pocock, Addy Osmani) e Apache-2.0 (Anthropic), com o que mudou em cada ficheiro
- fora do repositório: `npx skills remove … -g` das 3 skills de terceiros (confirmado: só ficam
  `extrair-conversa`, `find-skills`, `fluxo-implementacao` em `~/.claude/skills/`)

### Relatório da Fase 2 — o que mudou na prática

**Antes:** havia 3 skills de terceiros que se podiam atualizar sozinhas e que, numa parte, mandavam
organizar as decisões de forma diferente da do projeto.
**Agora:** há uma só skill nossa, `documentacao-projeto`, em português, que abre a parte certa conforme o
pedido (escrever skills e o CLAUDE.md, registar decisões, auditar o CLAUDE.md) e segue as regras deste
projeto.
**Para validar:** P3.

### Commits Fase 2 — hash

`fad3b6f`

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(este commit)_ | os 3 docs movidos para `docs/architecture/agentes/`; Agente 01 reescrito |

**Detalhes:**
- `git mv` de `docs/agente-1/2/3-*.md` para `docs/architecture/agentes/agente-01-sdr-alto-ticket.md`,
  `agente-02-vendedor-autonomo.md`, `agente-03-assistente-comercial.md` (o 02 e o 03 reescrevem-se nas Fases 4 e 5)
- Agente 01: de 404 para ~100 linhas — os prompts deixam de ser copiados (apontador para
  `docs/prompts_llms.md`); acrescentadas a dupla normalização do modo (executor vs. CRM), os guardrails de
  modo, as etapas da página ↔ sistema e "prometido vs. código"; cada afirmação conferida no código
- referências: `docs/ops/analise-qualificacao-ai-profile.md` (nota com o caminho novo),
  `docs/plans/docs-qualificacao-campos-obrigatorios-melhorias-futuras.md` M2 (os 3 guias dados como tratados)

**Achados para as próximas fases:** existe Filha de closing especializada (`_build_child_prompt_closing`,
`decision_engine.py:4274`) — `pipeline-phases.md` ("usa `_build_child_prompt` genérica") e a skill do Agente 02
estão errados; corrigir nas Fases 4 e 6.

Hash da Fase 3: `e20f793`.

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(este commit)_ | Agente 02 reescrito; `pipeline-phases.md` corrigido (Filha de closing) |

**Detalhes:**
- Agente 02: de 452 para ~90 linhas. Corrigido face ao doc antigo: o bot **continua ativo** em closing
  (`lead_category_policy`), e o carrinho abandonado arranca por "http" no texto da mensagem
  (`routes/executor.py`), não por `checkout_sent`. Acrescentados os gateways reconhecidos (hotmart, kiwify,
  stripe) e a contradição dos prompts sobre o link ("URL real" vs. "real ou placeholder")
- `docs/architecture/pipeline-phases.md` — secção "LLM Filha de Closing" passa a descrever
  `_build_child_prompt_closing`

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o guia do Agente 01 tinha 5 meses, nomes diferentes dos da página e regras que já não existem.
**Agora:** está junto da restante arquitetura, com o nome da página, conferido no código, e diz claramente o
que a página promete e o sistema ainda não faz (Calendly, sequência multicanal, NPS).
**Para validar:** P4.

### Fases 3, 4, 5 — Docs dos agentes (um por fase)

**Objetivo:** cada doc movido para `docs/architecture/agentes/`, com o nome da página, reescrito contra
o código atual e com a tabela "prometido na página vs. código".

### Fase 6 — Guia do time, CLAUDE.md e ligar as skills

**Objetivo:** guia em `docs/ops/`, 2 linhas no CLAUDE.md, skills de agente a apontar para os docs (ficam
só critérios e cenários) e descrições das 4 skills encurtadas.

---

## Checks de Validação

### Cenário P1 — Regras do `.gitignore`
- [x] `git check-ignore -v`: `.claude/skills/**` e `.claude/commands/*` não ignorados
- [x] `.claude/agentes/`, `.claude/worktrees/`, `.claude/settings.local.json` continuam ignorados
- [x] `git status` sem dados de clientes
- **Validado em:** 26/10/2026 — também `.claude/scheduled_tasks.lock` e `__pycache__/` ignorados

### Cenário P2 — Skills chegam a uma cópia nova do repositório
- [x] A árvore do commit tem `.claude/skills/` (4 skills, references, scripts) e `.claude/commands/` (9)
- [x] `grep` sem emails ou telefones de clientes nas skills
- **Validado em:** 26/10/2026 — `git ls-tree -r HEAD -- .claude`; `aplicar_producao.sh` com `eol=lf`; só o nome
  da empresa Sensi Vitae aparece como exemplo (já presente noutros docs versionados)

### Cenário P3 — `documentacao-projeto` abre a parte certa
- [ ] "regista esta decisão" → registar-decisoes
- [ ] "audita o CLAUDE.md" → auditar-claude-md
- [ ] "estou a escrever uma skill" → escrever-para-agentes
- [ ] As 3 skills de terceiros já não aparecem na lista

### Cenário P4 — Docs dos agentes
- [ ] `git grep` sem "campos mínimos" e sem "consultivo" fora de contexto
- [ ] Amostra de 5 afirmações por doc conferida no código
- [ ] Sem referências aos caminhos antigos

### Cenário P5 — Diagnóstico encaminha para os docs
- [ ] Conversa nova com "o agente da conta X não atende como nestas conversas…" aciona
      `diagnosticar-agente`, que encaminha para a skill do agente, e esta aponta para
      `docs/architecture/agentes/…`

### Cenário P6 — Portão da fila
- [ ] `python scripts/fila/categorias_que_sobem.py` → `seguranca_agente` + `instrucoes_ia` (o prompt do
      cliente simulado em `simular.py`) — ambas esperadas → merge com o "sim"

---

### Relatório da Fase 4 — o que mudou na prática

**Antes:** o guia do Agente 02 dizia que o bot se desligava no fecho e que a recuperação de carrinho
começava só depois do link de pagamento.
**Agora:** o guia diz o que o sistema faz: o bot continua a vender no fecho, e qualquer link enviado pelo bot
(até o do site) arranca a recuperação de carrinho; também regista que a página promete PagSeguro, upsell e NPS,
que o sistema não tem.
**Para validar:** P4.

---

## Ajustes Possíveis Pós-Implementação

- **Carrinho abandonado arranca com qualquer link** (`routes/executor.py`, "http" no texto) — devia usar
  `checkout_sent` ou o domínio do checkout configurado.
- **Prompts contraditórios sobre o link de pagamento** — validação "URL real" vs. apresentação "real ou
  placeholder" (`decision_engine.py`); relacionado com `docs/plans/motor-llm-otimizacoes.md` M5.
- **Modo do Agente 01 lido de duas formas** — executor passa `sdr_scheduler` a `consultivo` com
  `human_in_loop`/`requires_handoff`; o orquestrador do CRM não.
- **Promessas da página sem código** (Calendly, PagSeguro, multicanal, upsell, NPS, renovação de pacote) —
  decidir se a página muda ou se viram itens de produto (candidato a `docs/discovery/`).

- Modo de onboarding sem conversas de referência (entrevista ao dono do negócio → bancada) — candidato a
  `docs/discovery/`.
