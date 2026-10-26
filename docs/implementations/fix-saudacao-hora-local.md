# Saudação pelo período do dia errada ("Boa tarde" às 10h55)

**Branch:** `worktree-fix+saudacao-hora-local`
**Status:** Em andamento
**Autonomia:** manual
**Origem:** bateria PROD07 do agente Sensi Vitae (26/10/2026), problema D — "Boa tarde" às 10h55 em
todos os cenários. Investigação em `.claude/agentes/sensi-vitae/README.md`, secção "PROD07".
**Plano de execução:** [`docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md`](../plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md) — P3

---

## Motivação

A abertura configurada da Sensi Vitae diz "Cumprimente pelo período do dia (bom dia / boa tarde /
boa noite)". Em PROD07 (corrida às 10h55 de Lisboa) a Lara disse "Boa tarde" em todos os cenários,
incluindo os em que o cliente não cumprimentou (`p-micas`, `p-ruben`). Um "boa tarde" de manhã soa a
robô logo na primeira mensagem.

## Causa confirmada (investigação de 26/10/2026) — é código, não configuração

1. **Nenhum prompt recebe a hora local.** Procurado em `backend-executors/app/services/decision_engine.py`:
   não há `datetime.now` nem hora atual em nenhum construtor de prompt. A única referência temporal é a
   tabela de dias `_calendar_lookup_table_pt` (`:1794`), que traz só datas (com `[hoje]`), e só entra em
   apresentação, pré-agendamento, agendamento e gestão pós-marcação — **não na receção**, que é a fase
   que escreve a saudação (todos os 1.os turnos de PROD07 foram `recepcao`, com `greeting_first_enforced`).
2. **Os exemplos fixos do prompt da receção usam todos "Boa tarde!"** (`_build_child_prompt_recepcao`,
   `decision_engine.py:2867-2880`: "Boa tarde! Obrigado pelo contato.", "Boa tarde! Agradeço o contato…").
   Sem saber a hora, a IA copia o exemplo. O cabeçalho de saudação da apresentação tem exemplos com
   "Boa noite!" (`:3330-3334`) — mesmo risco.
3. O fuso da conta está configurado: produção, `ai_profiles` id 3 → `timezone = Europe/Lisbon`.
4. A abertura (`origin_inbound_opener`, lida em `:2804` na receção) é texto livre do dono; pede o período
   do dia mas não tem como o saber.

Configuração sozinha não resolve; o melhor que a config faz é evitar o período ("Olá! Sou a Lara…") até
haver código — proposto para a c14 (ver o plano).

## Opções de solução

| # | Opção | Prós | Contras |
|---|---|---|---|
| 1 | **O código calcula o período no fuso do perfil e diz à Filha**: uma linha "AGORA: segunda-feira, 26/10, 10h55 (manhã → 'Bom dia')" na receção e nos outros cabeçalhos de saudação; exemplos fixos passam a usar o cumprimento calculado (ou um neutro "Olá!") | Determinístico; serve todas as contas; o decision_engine corre no executor para o Playground e para o WhatsApp, por isso a paridade é automática (o fuso já vem no `ai_profile` do ContextBundle) | Instruções da IA (sobe ao utilizador); definir limites (proposta: 05h–12h bom dia, 12h–20h boa tarde, 20h–05h boa noite — confirmar com o utilizador para Portugal/Brasil) |
| 2 | Só trocar os exemplos fixos por "Olá!" | Mínimo | A IA continua sem saber a hora; quem pede "bom dia/boa tarde" na abertura continua a errar |
| 3 | Pós-processar o texto (trocar "Boa tarde" por "Bom dia") | Sem prompt | Frágil; mexe no texto que o dono pode ter escrito de propósito |

**Recomendada:** 1. Deixar a hora local disponível como facto também nas outras fases (pequeno custo de
tokens) ajuda frases como "ainda hoje" e "amanhã de manhã" — a decidir no Plan Mode se entra já ou só na
receção/abertura.

## Área do sistema

- `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_recepcao`, cabeçalho de
  saudação de `_build_child_prompt_apresentation`, eventual helper partilhado ao lado de
  `_calendar_lookup_table_pt`) — **instruções da IA**
- `backend-executors/app/services/meeting_date_guard.py` tem `local_today(tz_name, now)` — reusar o mesmo
  cálculo de fuso
- Docs: `docs/prompts_llms.md` (variável nova nos prompts), `docs/architecture/llm-architecture.md`

## Dependências e sobreposição

- **Worktree `feat+temperatura-respostas-ia`** reescreve partes do mesmo `_build_child_prompt_recepcao`
  (bloco "INSTRUÇÕES DO DONO DO NEGÓCIO", passos e regras de pergunta). Começar depois dessa worktree estar
  em `main`, ou a resolução de conflito vai cair exatamente no prompt da receção.
- Não toca em funções das outras implementações deste lote (B e M14 mexem noutros construtores).

## Riscos

- Instruções da IA → só junta a `main` com o "sim" do utilizador. Ler antes
  `docs/architecture/prompt-engineering-principles.md` e `docs/prompts_llms.md`.
- Testes com relógio: usar `now` injetável (como `local_today` já aceita) para não depender da hora a que
  os testes correm.

## Como validar

- Testes unitários com relógio fixo: 10h55 Lisboa → "Bom dia"; 15h → "Boa tarde"; 21h → "Boa noite";
  conta com fuso `America/Sao_Paulo` às 10h55 UTC → 07h55 locais → "Bom dia".
- Bancada: `python simular.py p-manha D1` antes das 12h de Lisboa (esperado "Bom dia") e outra vez depois
  das 20h (esperado "Boa noite"); `python simular.py p-micas D1` de manhã (o cliente não cumprimenta).
- Depois do deploy: `python simular.py p-manha D1 --prod` de manhã.

---

## Problemas Identificados (estado anterior)

Confirmado em `main` a 26/10/2026, já com `feat-temperatura-respostas-ia` e `fix-recepcao-ignora-pergunta-extra`
(as linhas mudaram desde a investigação):

1. **Nenhum prompt recebe a hora local** — `decision_engine.py` só tem a tabela de dias
   (`_calendar_lookup_table_pt`), sem horas, e ela não entra na receção.
2. **Exemplos da receção só com "Boa tarde!"** — `_build_child_prompt_recepcao`, exemplos ✅ 2 e 3. Em ambos o
   lead também diz "boa tarde"; não havia exemplo de lead que não diz período (`p-micas`, `p-ruben`), e a IA
   preenchia com o "Boa tarde" que via.
3. **Cabeçalho de saudação da apresentação com "Boa noite!" fixo** nos exemplos.
4. Qualificação (abertura de 1.º contacto), follow-up e closing (cabeçalho de saudação) mandam cumprimentar
   sem saber a hora.

## Abordagem

O código calcula o período no fuso do perfil e passa-o à Filha como facto:

```
ai_profile.timezone → meeting_date_guard.local_now() → _greeting_for_hour()
  → linha "AGORA (hora local do negócio): segunda-feira, 26/10, 10h55 — manhã. Ao cumprimentar
     pelo período do dia, use "Bom dia"; se o lead já cumprimentou com um período, devolva o dele."
  ├─ Recepção: sempre + exemplo ✅ 4 (lead sem período → cumprimento calculado)
  ├─ Apresentação: no cabeçalho de saudação (exemplos com o cumprimento calculado) ou na abertura de 1.º contacto
  └─ Qualificação / follow-up / closing: só quando já mandam cumprimentar
```

Decisões aprovadas no Plan Mode (26/10/2026): limites 05h–12h / 12h–20h / 20h–05h, iguais para PT e BR;
se o lead diz um período, devolve-se o dele; a hora fica fora das fases que não cumprimentam.
Paridade Playground ↔ WhatsApp automática: o decision_engine corre no executor nos dois casos e o fuso já vem
no `ai_profile` do ContextBundle.

## Plano de Implementação

### Fase 1 — Hora local nos prompts que cumprimentam

**Objetivo:** a Filha sabe a hora local e cumprimenta pelo período certo.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_date_guard.py` | `local_now(tz_name, now_utc)` novo; `local_today` passa a usá-lo |
| `backend-executors/app/services/decision_engine.py` | `_greeting_for_hour`, `_local_greeting`, `_local_time_fact_line`; linha AGORA na receção, qualificação (abertura), apresentação (saudação/abertura), follow-up e closing (saudação); exemplo ✅ 4 da receção; exemplos do cabeçalho da apresentação com o cumprimento calculado |
| `backend-executors/tests/test_saudacao_hora_local.py` | Testes com relógio fixo (Lisboa manhã/tarde/noite, limites 05h/12h/20h, São Paulo, fuso inválido, prompts) |
| `docs/prompts_llms.md`, `docs/architecture/llm-architecture.md` | Linha AGORA documentada |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f1f14e5` | Hora local do negócio nos prompts que cumprimentam + testes com relógio fixo + docs |

**Relatório da fase (linguagem simples):** a Lara passa a saber que horas são no fuso da conta antes de cumprimentar. De manhã diz "Bom dia", de tarde "Boa tarde" e à noite "Boa noite". Se o cliente já cumprimentou com um período, ela responde com o mesmo. Os exemplos do prompt deixaram de ensinar sempre "Boa tarde"/"Boa noite". Os testes automáticos passam; falta ver a Lara a responder na bancada, de manhã e à noite.

## Checks de Validação

### Cenário T1 — Testes automáticos
- [x] `pytest backend-executors/tests/test_saudacao_hora_local.py` passa (12 testes) — 26/10/2026
- [x] Suite completa sem falhas novas: 488 passam — 26/10/2026 (2 falhas em `test_recepcao_sales_flow_pending.py` já existiam em `main`)

### Cenário P1 — Bancada local `.claude/agentes/sensi-vitae`
- [x] `python simular.py p-manha D1` antes das 12h de Lisboa → "Bom dia" — 26/10/2026, relógio do executor fixo em 27/10 10h55 de Lisboa: "Bom dia! Sou a Lara, do Sensi Vitae." (`tentativas/20261026-2137-hora-local-manha-simulada-p-manha.md`)
- [x] `python simular.py p-manha D1` depois das 20h de Lisboa → "Boa noite" — 26/10/2026 21h27: "Boa noite! Sou a Lara, do Sensi Vitae." (`tentativas/20261026-2128-hora-local-noite-p-manha.md`)
- [x] `python simular.py p-micas D1` de manhã (cliente não cumprimenta) → "Bom dia" — 26/10/2026, mesmo relógio fixo: "Bom dia! Sou a Lara, do Sensi Vitae." + pedido na 2.ª decisão; "quarta-feira" resolvida para 28/10, coerente com o "hoje" simulado (`tentativas/20261026-2139-hora-local-manha-simulada-p-micas.md`)
- [x] Regressão `python simular.py p-ruben D1`: a pergunta junto com o cumprimento continua a seguir para o turno seguinte — 26/10/2026 21h28: "Boa noite! Sou a Lara…" (cliente não cumprimentou) + pedido tratado na 2.ª decisão (`tentativas/20261026-2129-hora-local-noite-p-ruben.md`)

> Corridas de 26/10 numa cópia isolada da bancada (código da worktree, portas 8110–8112, cópia dos bancos),
> porque a bancada partilhada (8100–8102, `ambiente/crm.db`) estava em uso por outra sessão.
> Os checks de manhã correram à noite com o executor arrancado por um script que fixa
> `meeting_date_guard.local_now` em 27/10 10h55 UTC (= Lisboa); o código da implementação não muda.

### Cenário C1 — Produção (depois do "sim" e do deploy)
- [ ] `p-manha D1 --prod` de manhã → "Bom dia"
- [ ] `p-micas D1 --prod` e `p-ruben D1 --prod` sem regressão

## Ajustes Possíveis Pós-Implementação

- Hora local também nas fases que não cumprimentam (ajudaria "ainda hoje", "amanhã de manhã") — ficou fora
  por minimalismo.
- A abertura do dono é texto livre: se escrever literalmente "Boa tarde!", a IA pode mantê-lo apesar da linha AGORA.

---

## Fase 2 — Diagnóstico: promessa na receção em produção (26/10/2026)

### Problema identificado

Merge `52ad519` em `main` + deploy às 21h40. Os testes com `--prod` deram o cumprimento certo ("Boa noite!") em
p-manha, p-micas e p-ruben, mas, quando o cliente não cumprimenta e faz um pedido, a receção passou a juntar uma
promessa ao cumprimento. A seguir, a 2.ª decisão pergunta "Posso enviar a tabela?":

- 3/3 no 1.º turno com "Gostaria de mais informações sobre as Massagens" (Playground de produção, em paralelo):
  "Vou ajudar com as informações que precisa." / "Vou passar as suas perguntas para a nossa equipa." /
  "Vou passar as informações sobre as massagens para você."
- Não aconteceu em nenhuma das 10 corridas anteriores (PROD04–PROD07, B1, B2, PROD-B) nem na bancada local com o
  mesmo código.
- "Vou passar as suas perguntas para a nossa equipa" não foi o fallback de handoff (`FALLBACK_DECISION`): esse
  substitui a resposta inteira e aqui veio depois do cumprimento, por isso foi escrito pela própria Filha.
- Suspeita: o exemplo ✅ 4 novo usa quase a mesma frase do cliente real e mostra uma segunda frase depois do
  cumprimento ("Obrigado pelo contato."); o modelo de produção (OpenRouter / Llama 3.3 70B) preenche essa
  segunda frase com uma resposta ao pedido.

**Ação:** revert `7416c79` em `main` (com o "sim" do utilizador); produção voltou ao comportamento anterior.

### Correção

A definir em Plan Mode. Antes de voltar a juntar, medir 3x em paralelo no Playground de produção, ou
localmente com o mesmo modelo que a produção usa.
