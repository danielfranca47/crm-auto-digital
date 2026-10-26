# Saudação pelo período do dia errada ("Boa tarde" às 10h55)

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
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
