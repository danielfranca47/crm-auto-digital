# Plano de Sprint — Agenda do agente Sensi Vitae depois da bateria PROD07

> Gerado em 26/10/2026 a partir da investigação dos 4 problemas da bateria PROD07
> (`.claude/agentes/sensi-vitae/README.md`, secção "PROD07"; transcrições em
> `.claude/agentes/sensi-vitae/tentativas/*PROD07*`). Só leitura de código e de produção.

**Data de geração:** 26/10/2026
**Status:** Aguardando decisão do utilizador sobre a ordem e a c14
**Conta:** Sensi Vitae — produção user_id 4, ai_profile 3 (`Europe/Lisbon`, `agent_mode=agenda`, `confirm_exact`)

---

## Diagnóstico — os 4 problemas

| # | Problema | Onde está a causa | Destino |
|---|---|---|---|
| A | Sessão que começa quando outra acaba = "conflito"; 409 não tratado → 502 no Playground e queda do worker no WhatsApp real | Código: comparação de datas como texto em 6 sítios do backend-crm; `handle_meeting_scheduled` sem tratamento do 409 | [`fix-conflito-horario-comparado-como-texto.md`](../implementations/fix-conflito-horario-comparado-como-texto.md) |
| A2 | Margem entre sessões (preparar a sala) | Não existe | [`feat-margem-entre-sessoes.md`](../implementations/feat-margem-entre-sessoes.md) — depois de A |
| B | Na confirmação grava uma proposta antiga | Código: a Filha escolhe o horário sozinha; nada guarda a última proposta; a proteção de datas só confere "dia já falado" | [`fix-confirmacao-grava-proposta-antiga.md`](../implementations/fix-confirmacao-grava-proposta-antiga.md) (inclui "grava sem tipo/duração/nome") |
| C | Assume o tipo de massagem, "relaxante só 60 min", ignora perguntas múltiplas | Metade configuração (c14, abaixo); metade código: pré-agendamento/agendamento não leem o Fluxo de Venda (M14) e o roteiro fixo do pré-agendamento compete com as instruções | c14 + [`fix-agendamento-le-fluxo-de-venda.md`](../implementations/fix-agendamento-le-fluxo-de-venda.md) |
| D | "Boa tarde" às 10h55 | Código: nenhum prompt recebe a hora local; os exemplos fixos da receção dizem todos "Boa tarde!" | [`fix-saudacao-hora-local.md`](../implementations/fix-saudacao-hora-local.md) (+ paliativo na c14) |

---

## Quadro de sobreposição

Trabalho já existente que entra no quadro:
- **W1 — worktree `fix+disponibilidade-campo-duplo-sentido`** (Em andamento desde 04/10, 92 commits atrás
  de `main`; junta sem conflito de código — só o próprio `.md`; falta o check C1, que só se faz em produção).
- **W2 — worktree `feat+temperatura-respostas-ia`** (Em andamento, 3 checks por validar; junta com conflito
  só em `docs/architecture/sales-flow.md`).
- **M12 em `main`** (`fix-horario-livre-recusado`: `professional_hours.py`, `requested_slot.py`,
  `_build_agenda_fact_block`) e **M11 em `main`** (`fix-data-dia-semana-agendamento`: `meeting_date_guard.py`).

| Ficheiro / função | A | A2 | B | C (M14) | D | W1 | W2 | M11/M12 (main) |
|---|---|---|---|---|---|---|---|---|
| `backend-crm/routes/appointments.py::_check_conflict`, listas | ✏️ | (lê) | | | | | | |
| `backend-crm/.../orchestrator.py::_load_calendar_busy_slots` | ✏️ query | ✏️ alarga ocupados | | | | | | |
| `backend-crm/services/google_calendar_sync.py` | ✏️ | | | | | | | |
| `backend-crm/services/appointment_outcomes.py` | ✏️ | | | | | | | |
| `executors/meeting_scheduler.py::handle_meeting_scheduled` | ✏️ 409 | | | | | | | |
| `executors/meeting_scheduler.py::_has_conflict` | | (lê) | | | | | | usado por `requested_slot` |
| `executors/runners/whatsapp.py` (~l. 793) | ✏️ proteção | | | | | | | |
| `executors/meeting_date_guard.py` | | | ✏️ (ou módulo novo) | | (reusa `local_today`) | | | ✏️ M11 |
| `executors/requested_slot.py` | | (lê ocupados) | (reusa leitura de horas) | | | | | ✏️ M12 |
| `decision_engine._build_meeting_already_booked_block` + conferência pós-Filha | | | ✏️ | | | | | |
| `decision_engine._build_child_prompt_agendamento` | | | ✏️ (bloco marcação) | ✏️ (Fluxo) | | ✏️ (disponibilidade) | | ✏️ M12 (`_build_agenda_fact_block`) |
| `decision_engine._build_child_prompt_pre_agendamento` | | | | ✏️ | | | | |
| `decision_engine._build_child_prompt_recepcao` | | | | | ✏️ | | ✏️ | |
| `decision_engine.decide()` / `_SALES_FLOW_INJECTING_CHILD_ROUTES` | | | | ✏️ | | | ✏️ | |
| `backend-core` AI profile (modelo, `db.py`, API) | | ✏️ coluna | | | | ✏️ coluna | ✏️ coluna | |
| `frontend-crm` ecrãs do agente / `AdminAgents.tsx` | | ✏️ | | | | ✏️ | ✏️ | |

**Onde duas soluções podem chocar e o que se decidiu:**
1. **A ↔ A2** — mesmas consultas de ocupados → A2 só começa depois de A estar em `main`.
2. **B ↔ C (M14) ↔ W1** — os três mexem em `_build_child_prompt_agendamento` (blocos diferentes). Não
   se juntaram num só ficheiro porque resolvem coisas independentes e B é urgente; a ordem fica fixa:
   **W1 → B → M14**.
3. **C (M14) ↔ W2** — W2 cria a lista das fases que injetam o Fluxo de Venda e lê-a em `decide()`; o M14
   tem de acrescentar pré-agendamento/agendamento a essa lista → **W2 antes do M14**.
4. **D ↔ W2** — ambos reescrevem o prompt da receção → **W2 antes do D**.
5. **A2 ↔ W1 ↔ W2** — todos acrescentam uma coluna ao AI profile e mexem nos ecrãs do agente: conflitos
   só mecânicos (linhas vizinhas), resolvidos no merge; A2 é o último.
6. **B ↔ M11** — B reutiliza/estende `meeting_date_guard.py`; M11 já está em `main`, por isso não há
   choque — só cuidado para não alterar o comportamento da correção de datas (os testes do M11 têm de
   continuar a passar).
7. **A ↔ M12** — A não altera o `_has_conflict` do executor (que já compara bem), só o lado do CRM;
   sem choque.

---

## Ordem recomendada

| Passo | O quê | Porquê nesta posição | Pode correr em paralelo com |
|---|---|---|---|
| 0a | Fechar **W1** (disponibilidade) — validar o C1 em produção e juntar | Destrava a c14 (horários dos terapeutas no campo próprio, sem o truque "ignore o bloco 08–22") e tem de entrar antes de B e M14 | A, D-preparação |
| 0b | Fechar **W2** (temperatura) — validar os 3 checks e juntar | Tem de entrar antes de D e M14 | A, B |
| 1 | **A** — conflito comparado como texto + 409 | O mais urgente: bloqueia sessões seguidas e, no WhatsApp real, derruba o envio de mensagens de todas as contas. Não toca em instruções da IA | B, 0a, 0b |
| 2 | **B** — confirmação grava proposta antiga | Grava marcações no dia/terapeuta errado. Depois de W1 (mesmo construtor) | A |
| 3 | **D** — saudação pela hora local | Pequeno; depois de W2 | A, B (merges um de cada vez) |
| 4 | **C / M14** — agendamento lê o Fluxo de Venda | Depende de W1, W2 e B (mesmo construtor e mesma lista) | A2 |
| 5 | **A2** — margem entre sessões | Funcionalidade nova; depois de A; precisa de decisões de produto | M14 |

A **c14** (configuração, abaixo) pode ser aplicada já — não depende de código, exceto o ponto 6.

Todas as que tocam instruções da IA (B, C/M14, D) só se juntam a `main` com o "sim" do utilizador.
A toca `backend-executors/app/runners/` e A2 toca a estrutura da base de dados — ambas sobem também ao
utilizador (`python scripts/fila/categorias_que_sobem.py`). Merges sempre um de cada vez.

---

## Configuração c14 (não é implementação — aplicar na conversa principal)

Alterações propostas a `CUSTOM_INSTRUCTIONS` / `INBOUND_OPENER` em
`.claude/agentes/sensi-vitae/gerar_config.py`, como `c14-tipo-perguntas` = c13 + texto:

1. **Saudação (paliativo para D até o código chegar):**
   `INBOUND_OPENER` → "Cumprimente com 'Olá!' e apresente-se como Lara, do Sensi Vitae, numa frase curta."
   e a orientação `sv-p0-ola` igual (sem "bom dia / boa tarde"). Se o cliente cumprimentar com o período
   do dia, a Lara pode responder com o mesmo cumprimento.
2. **Tipo de massagem — sair do parágrafo dos horários (passo 4) para uma secção própria antes do passo 3:**
   "MASSAGENS — antes de propor dia e hora, saiba qual massagem o cliente quer. Se disser só 'relaxante'
   ou 'massagem', pergunte: 'Prefere a Relaxante Clássica ou a Relaxante Exótica (Lomi Lomi)?'. Se pedir
   'relaxante de 90 min' (ou 1h30), responda: 'A de 90 min é a Relaxante Exótica (Lomi Lomi), 110 €.
   Pode ser essa?' — a Clássica vai até 1h. Nunca diga que a relaxante só tem 60 min."
   (mantém a tabela de preços e "Exótica = Lomi Lomi" que já lá estão).
3. **Várias perguntas na mesma mensagem — exceção em COMO ESCREVER:**
   "Se o cliente fizer várias perguntas na mesma mensagem, responda a cada uma, uma frase curta por
   pergunta, e só depois faça a pergunta do próximo passo."
4. **Não anunciar marcação antes do sim (PROD07 `p-ruben`: "Perfeito, fica agendada… Como se chama?"):**
   no passo 5 acrescentar: "Enquanto faltar um dos 4 dados, não diga 'fica agendada' nem 'está marcado':
   peça o dado que falta."
5. **Pedido de marcar com dados em falta (PROD07 `p-fora-horario`):** no passo 5: "Se o cliente disser
   'pode marcar' mas ainda não disse o tipo de massagem, a duração ou o nome, pergunte o que falta antes
   de confirmar." (Limite conhecido: o bloco "MARCAÇÃO JÁ GRAVADA" do código vence esta regra quando a
   Mãe marca a reunião — a correção definitiva é a Fase 2 de B.)
6. **Depois de W1 estar em produção:** passar os horários dos terapeutas para o campo
   `professional_availability` e apagar do passo 4 a frase "ATENÇÃO: o bloco 'DISPONIBILIDADE DO
   PROFISSIONAL' (08:00-22:00)…" — deixa de ser preciso.

Validar a c14 na bancada: `python simular.py p-relax-sem-tipo c14`, `p-varias-perguntas`, `p-micas`,
`p-ruben`, `p-fora-horario`, `p-manha`; regressão `p-ricardo`, `p-joaquim`, `pos-marcacao`.

---

## Prompts de início (colar numa conversa nova, um por implementação)

### P1 — A: horários comparados como texto
```
Lê CLAUDE.md, docs/implementations/_guia-documentar-implementacao.md e
docs/implementations/fix-conflito-horario-comparado-como-texto.md (já tem o diagnóstico da
investigação de 26/10/2026 — usa-o como ponto de partida do Plan Mode, sem refazer o
levantamento). Ler também docs/architecture/playground-parity.md antes de mexer no orchestrator.
Não depende de outra implementação. Segue o Passo 0 (Plan Mode) e espera a minha aprovação.
Validar com a bancada .claude/agentes/sensi-vitae: python simular.py p-seguidas A1 (setup no
próprio cenário), p-val-17h e pos-marcacao; depois do deploy os mesmos com --prod.
Toca no runner do WhatsApp (envio real): só se junta a main com o meu "sim".
```

### P2 — B: confirmação grava proposta antiga
```
Lê CLAUDE.md, docs/implementations/_guia-documentar-implementacao.md e
docs/implementations/fix-confirmacao-grava-proposta-antiga.md (diagnóstico pronto de 26/10/2026).
Antes de mexer em prompts, ler docs/architecture/prompt-engineering-principles.md e
docs/prompts_llms.md. Depende de: worktree fix+disponibilidade-campo-duplo-sentido estar em main
(mesmo construtor de prompt) — se ainda não estiver, avisa-me antes de começar. Pode correr em
paralelo com fix-conflito-horario-comparado-como-texto. Segue o Passo 0 e espera a aprovação.
Validar: python simular.py p-aceita-2a B1, p-cedo-tarde B1, p-fora-horario B2 (Fase 2);
regressão p-micas e p-ricardo; depois com --prod.
Toca instruções da IA: só se junta a main com o meu "sim".
```

### P3 — D: saudação pela hora local
```
Lê CLAUDE.md, docs/implementations/_guia-documentar-implementacao.md e
docs/implementations/fix-saudacao-hora-local.md (diagnóstico pronto de 26/10/2026).
Antes de mexer em prompts, ler docs/architecture/prompt-engineering-principles.md e
docs/prompts_llms.md. Depende de: worktree feat+temperatura-respostas-ia estar em main (mexe no
mesmo prompt da receção) — se ainda não estiver, avisa-me antes de começar. Segue o Passo 0 e
espera a aprovação. Validar: testes com relógio fixo; python simular.py p-manha D1 antes das 12h
de Lisboa e depois das 20h; p-micas D1 de manhã; depois com --prod.
Toca instruções da IA: só se junta a main com o meu "sim".
```

### P4 — C: agendamento lê o Fluxo de Venda (M14)
```
Lê CLAUDE.md, docs/implementations/_guia-documentar-implementacao.md e
docs/implementations/fix-agendamento-le-fluxo-de-venda.md (diagnóstico pronto de 26/10/2026;
origem docs/plans/fluxo-vendas-melhorias-futuras.md M14). Antes de mexer em prompts, ler
docs/architecture/prompt-engineering-principles.md, docs/prompts_llms.md e
docs/architecture/sales-flow.md. Depende de: feat+temperatura-respostas-ia,
fix+disponibilidade-campo-duplo-sentido e fix-confirmacao-grava-proposta-antiga estarem em main —
confirma isso primeiro e avisa-me se faltar alguma. No Plan Mode, ver em produção (só leitura)
que contas têm blocos em p3a/p3b. Validar com a c14 aplicada na bancada: p-relax-sem-tipo,
p-micas, p-varias-perguntas, p-ruben; regressão p-ricardo, p-cedo-tarde, pos-marcacao.
Toca instruções da IA: só se junta a main com o meu "sim".
```

### P5 — A2: margem entre sessões
```
Lê CLAUDE.md, docs/implementations/_guia-documentar-implementacao.md e
docs/implementations/feat-margem-entre-sessoes.md. Depende de:
fix-conflito-horario-comparado-como-texto estar em main (mesmas consultas de ocupados) —
confirma primeiro. No Plan Mode pergunta-me as 3 decisões de produto do ficheiro (valor por
omissão, antes/depois, por conta). Campo novo no AI profile: atualizar
docs/architecture/admin-agents-contract.md e AdminAgents.tsx. Validar: python simular.py
p-seguidas M1 com margem 15 na conta local; regressão pos-marcacao.
Mexe na estrutura da base de dados: só se junta a main com o meu "sim".
```
