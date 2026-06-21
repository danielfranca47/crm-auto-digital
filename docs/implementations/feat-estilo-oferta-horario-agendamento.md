# Estilo de oferta de horário no agendamento — confirmação direta vs. escassez comercial

**Branch:** `main`
**Status:** Todos os cenários validados

---

## Motivação

Durante a validação ao vivo da Fase 7 de `fix-robustez-decisao-mae-multinicho.md`, notou-se
um padrão suspeito: em todos os testes (leads #276, #278, #279), a filha de agendamento
recusava o primeiro horário pedido pelo lead — "infelizmente não está disponível" — e
oferecia 2-3 alternativas, mesmo quando, conferindo directamente no banco
(`appointments`), não havia nenhum compromisso real naquele horário.

O utilizador pediu para investigar a causa raiz e, sendo uma tática comercial deliberada,
torná-la configurável no AI Profile — o utilizador escolhe se o agente confirma o horário
exacto pedido quando está livre, ou se sempre oferece alternativas como gatilho de
escassez — e mapear o melhor lugar no frontend para expor essa opção.

---

## Problemas Identificados (estado anterior)

1. **Instrução incondicional de "sempre propor 2-3 horários" (`backend-executors/app/services/decision_engine.py`, função `_build_child_prompt_agendamento`):**
   sempre que `availability_schedule` estava configurado (o caso normal), a filha de
   agendamento era instruída a propor sempre 2-3 horários — nunca a confirmar
   directamente o horário único que o lead pediu, independentemente de haver ou não
   conflito real em `calendar_busy_slots`.
2. **Nenhuma opção de configuração:** não existia, em lugar nenhum do AI Profile, forma
   de o utilizador escolher um comportamento diferente — a tática de "sempre oferecer
   alternativas" era fixa e não documentada como decisão deliberada.

---

## Abordagem

```
ai_profile.scheduling_offer_style
  ├─ 'offer_alternatives' (default — preserva o comportamento actual)
  │     → instrução: sempre propor 2-3 horários concretos
  └─ 'confirm_exact' (novo)
        → se o horário pedido estiver livre (não em HORÁRIOS JÁ OCUPADOS, dentro da
          disponibilidade): confirma directamente, sem oferecer alternativas
        → só propõe alternativas quando o horário pedido estiver realmente
          ocupado/fora da disponibilidade, ou quando o lead não especificou horário
```

Novo campo no AI Profile, seguindo o padrão já usado por `appointment_mode` (3 camadas:
modelo + migração + schema no backend-core; leitura condicional no prompt do
backend-executors; campo + UI no frontend-crm).

---

## Plano de Implementação

### Fase 1 — Backend: campo, migração e leitura condicional no prompt

**Objetivo:** introduzir o campo `scheduling_offer_style` e usá-lo para escolher a
instrução certa na filha de agendamento.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | Novo `Column(String, nullable=True, server_default="offer_alternatives")` |
| `backend-core/app/db.py` | Nova entrada na migração `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | Novo `scheduling_offer_style: Optional[str] = None` em `AIProfileBase` e `AIProfileUpdate` |
| `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_agendamento`) | Lê `scheduling_offer_style`; quando `confirm_exact`, substitui a instrução "proponha 2-3 horários" por uma regra de confirmação directa com exemplo concreto |
| `backend-executors/tests/test_scheduling_offer_style.py` | Novo arquivo, 3 cenários: default, `offer_alternatives` explícito, `confirm_exact` |

```python
# ANTES — sempre propor alternativas, incondicional
"Com base na disponibilidade acima, proponha 2-3 horários concretos que se encaixem "
"no que o lead solicitou. Use linguagem natural e fluida.\n\n"

# DEPOIS — condicional a scheduling_offer_style
if scheduling_offer_style == "confirm_exact":
    _offer_instruction = (
        "REGRA CRÍTICA — CONFIRMAÇÃO DIRETA (obrigatória, máxima prioridade nesta fase):\n"
        "...NÃO INVENTE conflito que não está listado..."
        "Exemplo: lead pede 'amanhã às 14h' → responda 'Perfeito, fica confirmado amanhã às 14h.'\n"
    )
else:
    _offer_instruction = (...)  # comportamento actual, inalterado
```

**Nota sobre a primeira versão da instrução:** a primeira tentativa (regra abstracta, sem
exemplo) não foi seguida pela LLM em teste real — pedido "amanhã às 14h" sem nenhum
conflito real nos dados, e a IA mesmo assim respondeu "não temos disponibilidade", duas
vezes na mesma conversa. Reforçada com exemplo concreto, frase "NÃO INVENTE conflito que
não está listado" e marcada como regra de "máxima prioridade" — só essa versão foi seguida
correctamente em teste ao vivo (ver Cenário C1).

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(pendente)_ | Campo `scheduling_offer_style` (backend-core + backend-executors) + testes |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o agente de agendamento sempre oferecia 2-3 horários alternativos quando o lead pedia um horário específico, mesmo que esse horário estivesse livre — sem nenhuma forma de desligar esse comportamento.
**Agora:** existe um campo de configuração que permite escolher entre o comportamento actual (sempre oferecer alternativas — pode servir como tática comercial de escassez) ou confirmar directamente quando o horário pedido está livre.
**Para validar:** Cenário C1 (backend) e P1 (frontend), abaixo.

---

### Fase 2 — Frontend: expor a opção na Camada de Apresentação

**Objetivo:** dar ao utilizador uma forma de escolher o estilo, no lugar mais coeso
possível da UI já existente.

**Local escolhido:** dentro de `CamadaApresentacao.tsx`, na secção já existente
"Disponibilidade de horários" — é literalmente a secção que já explica que "o bot usará
estas informações para propor horários ao lead na fase de Agendamento", o lugar mais
relacionado de toda a UI (mais do que "Modo de operação", que trata de venda vs.
exploração, não de como o horário é oferecido).

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | Novo campo `scheduling_offer_style` em `AgentConfig`; default em `DEFAULT_AGENT_CONFIG`; novo `SCHEDULING_OFFER_STYLE_LABELS` |
| `frontend-crm/src/components/agente/CamadaApresentacao.tsx` | Novo `ModalSchedulingOfferStyle` (mesmo padrão de `ModalAppointmentMode`, 2 `OptCard`); novo `EditCard` na secção "Disponibilidade de horários"; novo `ModalKey` (`'ofertaHorario'`) |
| `frontend-crm/src/services/api.ts` | Mapeamento explícito de `scheduling_offer_style` no load (`profile → AgentConfig`) e no save (`AgentConfig → payload`) — este arquivo faz mapeamento campo-a-campo manual, não spread automático |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(pendente)_ | UI do estilo de oferta de horário (frontend-crm) |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** não existia nenhuma forma de configurar isto pela interface — só seria possível alterando o banco de dados directamente.
**Agora:** na página de configuração do agente, secção "Disponibilidade de horários", há um novo card "Estilo de oferta de horário" com duas opções claras, cada uma com uma explicação do que significa.
**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário C1 — `confirm_exact` confirma directamente quando o horário está livre (Playground)
- [x] Testes unitários directos (`test_scheduling_offer_style.py`, 3 cenários): default e `offer_alternatives` mantêm a instrução actual; `confirm_exact` produz a regra de confirmação directa com exemplo
- [x] Regressão: `pytest tests/ scripts/test_meeting_scheduler_hook.py scripts/test_meeting_candidate_e2e.py scripts/test_structured_meeting_signal_dual_read.py scripts/test_mother_prompt_agent_mode.py -q` — 25 falhas pré-existentes idênticas / 83 passes
- [x] Validação ao vivo (Playground, perfil id=5): com `scheduling_offer_style=confirm_exact`, lead novo pediu "amanhã às 16h" (horário livre, confirmado via `calendar_busy_slots`/banco antes do teste); após negociação (1ª resposta da Mãe roteou para pré-agendamento, 2ª mensagem do lead confirmou), a IA respondeu "A sessão está confirmada para amanhã às 16h" — sem oferecer alternativas
- **Validado em:** 21/06/2026 — via UI real (Playground, MCP chrome-devtools), lead #281. Log: `event=meeting_datetime_source source=structured_candidate`. `signals_structured.meeting_datetime_candidate="2026-06-22T16:00:00"`. `GET` directo ao banco: `appointments` com `lead_id=281, start_at="2026-06-22T16:00:00+00:00"`.
- **Nota:** a primeira tentativa de instrução (sem exemplo concreto) falhou em 2 tentativas consecutivas (lead #280, mesmo horário livre, IA insistiu "não temos disponibilidade" mesmo quando directamente contestada) — corrigido reforçando o prompt antes deste commit (ver nota na Fase 1). Mesmo a versão reforçada depende da LLM cumprir a instrução — não é uma garantia matemática (ver "Ajustes Possíveis").

### Cenário C2 — `offer_alternatives` (default) mantém o comportamento actual
- [x] Confirmado nas Fases 6/7 de `fix-robustez-decisao-mae-multinicho.md` (leads #276, #278, #279, todos sem o campo configurado/com o default) — IA sempre ofereceu 2-3 alternativas
- **Validado em:** 21/06/2026 — comportamento pré-existente confirmado como o default deste novo campo, sem alteração

### Cenário P1 — UI do novo card na Camada de Apresentação
- [x] Abrir Camada 5 (Apresentação) no AI Profile — card "Estilo de oferta de horário" aparece na secção "Disponibilidade de horários", com o valor actual
- [x] Abrir o modal — duas opções claras com descrição
- [x] Selecionar "Confirmar horário exacto quando disponível" → Salvar (modal) → Salvar (banner de rascunho) → `PUT /ai-profiles/me` 200
- [x] Confirmar via banco: `scheduling_offer_style="confirm_exact"` persistido
- [x] Repetir o fluxo de volta para "Sempre oferecer alternativas" → persistido como `offer_alternatives`
- **Validado em:** 21/06/2026 — via UI real (browser, MCP chrome-devtools), perfil id=5, round-trip nos dois sentidos confirmado via leitura directa do banco

---

## Ajustes Possíveis Pós-Implementação

- **Cumprimento da instrução não é garantido a 100%:** mesmo com a regra reforçada (exemplo
  concreto, "NÃO INVENTE conflito", máxima prioridade), o comportamento depende da LLM
  seguir a instrução — mesma classe de risco residual já documentada para outras
  instruções do sistema (ex.: "Não-determinismo da Mãe" em
  `fix-robustez-decisao-mae-multinicho.md`). Se o padrão de não-cumprimento se repetir
  com frequência em uso real, pode ser necessário reforçar ainda mais ou mudar de
  abordagem (ex.: gate de código que sobrescreve a resposta da IA quando o horário pedido
  bate exactamente com a disponibilidade e está livre).
- **Campo não se aplica à filha de apresentação:** confirmado por leitura directa que
  `_build_child_prompt_apresentation` não tem a instrução equivalente de "sempre propor
  2-3 horários" — o problema só existia na filha de agendamento. Se esse padrão for
  observado também na apresentação no futuro, será necessário estender o campo lá.
- **"Primeira oferta sempre recusada" pode ter outras causas concorrentes:** notei,
  durante os testes desta feature, que mesmo com `confirm_exact`, a primeira resposta da
  Mãe a uma saudação composta com horário específico às vezes roteia para
  `pré-agendamento` em vez de `agendamento` direto (não-determinismo já documentado na
  Fase 3D de `fix-robustez-decisao-mae-multinicho.md`) — nesses casos, a filha de
  agendamento (e a nova regra) só entra em jogo no turno seguinte. Não é um bug desta
  feature, é uma interacção com um comportamento já conhecido e aceite noutro lugar.
