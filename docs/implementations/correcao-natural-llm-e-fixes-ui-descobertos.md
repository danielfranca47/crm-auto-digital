# Mensagem de correção gerada pela LLM + 2 bugs de UI descobertos em testes

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Durante a sessão de testes manuais locais de três implementações (`disponibilizar-fluxo-venda-todos-agentes.md`, `retry-llm-service-playground.md`, `disponibilidade-real-agendamento-ia.md`, 19/06/2026), surgiram três oportunidades de melhoria que não faziam parte do escopo original de nenhuma das três:

1. Uma melhoria de UX já prevista como "ajuste futuro" na implementação de disponibilidade real de agenda — a mensagem de correção de conflito é texto fixo, igual para todos os agentes.
2. Dois bugs de UI descobertos por acidente ao testar funcionalidades não-relacionadas a eles.

Nenhum dos três bloqueava a validação das implementações que estavam a ser testadas — foram documentados nos respetivos arquivos (`Ajustes Possíveis Pós-Implementação`) e agora são tratados aqui como itens próprios, antes de esses arquivos serem graduados para `docs/architecture/`.

---

## Problemas Identificados (estado anterior)

1. **Mensagem de correção de conflito é texto fixo:** `backend-executors/app/services/meeting_scheduler.py:22-25` —
   constante `MEETING_CONFLICT_MESSAGE = "Peço desculpa, esse horário acabou de ficar indisponível. Pode escolher outro horário, por favor?"`,
   retornada sempre igual (linha ~454) independentemente do `tone_of_voice`, `brand_name` ou personalidade configurada no AI Profile do agente. Foi uma decisão deliberada de MVP na implementação original (`disponibilidade-real-agendamento-ia.md`), não um bug.

2. **Conteúdo perdido ao criar uma NOVA ação no Fluxo de Venda (Camada 7):** `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx`, componente `RuleBuilderModal` (~linha 632), estados `pendingTypeId`/`pendingBlock` (~linhas 642-643) e função `confirmPendingBlock()` (~linhas 665-672).
   **Reprodução confirmada:** "Montar regra" → "+ Adicionar ação" → escolher um tipo (ex.: "Orientação ao Agente") → digitar texto na textarea → "Confirmar ação" → "Salvar regra" → o bloco é persistido no backend com `content` ausente (`{"id": "...", "typeId": "orientacao"}`, sem o campo `content`).
   **O que funciona normalmente:** editar o MESMO bloco depois de já criado, pelo botão "EDITAR" na lista de blocos da fase — esse fluxo usa um componente standalone diferente (o modal com `isEdit`/`initial`, ~linha 500, com botão "Salvar bloco"), e persiste o `content` corretamente.
   **Causa raiz ainda não isolada.** O código de `RuleBuilderModal` lido linha a linha não mostra nenhum reset óbvio de `pendingBlock` entre o preenchimento e a confirmação — `BlockForm` está correctamente ligado a `pendingBlock`/`setPendingBlock`. Hipótese a validar em Plan Mode: perda do estado local por re-render do componente pai (`AiProfile.tsx`/`CamadaFluxoVenda.tsx`) entre o preenchimento do texto e o clique em "Confirmar ação" — possivelmente disparado por um refetch concorrente do React Query nesta página. **Importante:** a reprodução foi feita por automação de browser (Chrome DevTools MCP) — antes de assumir como bug confirmado em produção, validar manualmente com interação humana real (pode ser uma particularidade da automação, embora o mesmo tipo de interação tenha funcionado sem problema no fluxo "EDITAR").

3. **Crash na vista Mensal da Agenda com appointment malformado:** `frontend-crm/src/components/ScheduleView.tsx:55` lança `Uncaught RangeError: Invalid time value` ao montar `normalized` (`format(date, "HH:mm")` do `date-fns` sobre uma `Date` inválida), sem Error Boundary — a página fica em branco até reload.
   **Causa raiz identificada:** `frontend-crm/src/hooks/useAppointments.ts:23-24,45-46` — `normalizeAppointment()` usa `""` (string vazia) como fallback final quando nenhum dos campos reconhecidos (`start_at`/`start_time`/`startAt`/`start`) está presente no appointment retornado pela API. Como `""` é do tipo `string`, a normalização (`typeof start === "string" ? start : new Date(start).toISOString()`) propaga a string vazia directamente como `startTime`, em vez de cair no `new Date(start).toISOString()`. Em `ScheduleView.tsx`, `new Date("")` é uma `Date` inválida, e `format()` lança a excepção ao recebê-la.
   **Falta confirmar** qual appointment específico chega sem nenhum desses campos — suspeita: um evento importado do Google Calendar com forma de resposta diferente, ou uma resposta optimista parcial de uma mutation do React Query ainda em voo no momento do crash.

---

## Abordagem

Três correções independentes, sem dependência entre si — cada uma pode ser implementada, testada e comitada isoladamente, em qualquer ordem.

```
Fase 1 — meeting_scheduler.py: mensagem de correção via LLM (fallback no texto fixo se a chamada falhar)
Fase 2 — CamadaFluxoVenda.tsx: investigar e corrigir perda de content no RuleBuilderModal
Fase 3 — useAppointments.ts + ScheduleView.tsx: fallback seguro para datas ausentes/malformadas
```

---

## Impacto esperado em linguagem simples (pré-implementação)

> **Nenhuma das 3 fases abaixo foi implementada ainda** — isto é uma
> pré-visualização do impacto esperado quando cada uma for feita, não um
> registo de mudança já realizada.

**Fase 1 — Mensagem de correção mais natural**
**Hoje:** quando um horário fica indisponível por um conflito de última hora, a mensagem de desculpas ao cliente é sempre o mesmo texto genérico, igual para todos os agentes, independentemente do tom configurado (formal, informal, etc.).
**Quando implementado:** essa mensagem passa a ser escrita no tom de cada agente — sem nunca deixar o cliente sem nenhuma resposta, mesmo que a geração falhe (nesse caso, cai no texto genérico actual como reserva).

**Fase 2 — Corrigir perda de texto ao criar uma ação nova no Fluxo de Venda**
**Hoje:** ao criar uma ação nova (não editar uma já existente) na configuração avançada do agente, o texto digitado pode não ser salvo — o bloco fica vazio sem aviso.
**Quando corrigido:** o texto digitado numa ação nova fica salvo, igual ao que já acontece ao editar uma ação existente.

**Fase 3 — Agenda não trava com um compromisso malformado**
**Hoje:** se um compromisso chegar sem uma data reconhecível pelo sistema (caso raro, causa ainda não confirmada), a vista Mensal da Agenda trava por completo, obrigando a recarregar a página.
**Quando corrigido:** esse compromisso específico é ignorado ou mostrado de forma segura, sem travar a vista para os demais compromissos do mês.

---

## Plano de Implementação

### Fase 1 — Mensagem de correção gerada pela LLM

**Objetivo:** a mensagem enviada ao lead quando um conflito é detetado passa a ser gerada no tom configurado do agente, com fallback no texto fixo actual se a chamada à LLM falhar ou demorar.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_scheduler.py` | Novo helper (ex.: `_generate_conflict_message(ai_profile)`) que monta um prompt curto usando `tone_of_voice`/`brand_name`/`identity_mode` e chama `llm_service`; `handle_meeting_scheduled()` passa a chamar este helper em vez de devolver `MEETING_CONFLICT_MESSAGE` directamente |
| `backend-executors/app/services/llm_service.py` | Reaproveitar `_post_with_retry()` (já existe, ver `retry-llm-service-playground.md`) para esta nova chamada — não duplicar lógica de retry |

**Risco a mitigar:** a chamada extra à LLM não pode bloquear ou atrasar significativamente o fluxo de bloqueio do conflito — se falhar (mesmo após retry), usar `MEETING_CONFLICT_MESSAGE` como já acontece hoje. Nunca deixar o lead sem nenhuma mensagem.

### Fase 2 — Fix: conteúdo perdido ao criar bloco novo no Fluxo de Venda

**Objetivo:** o texto digitado ao criar uma nova ação (`orientacao`, `mensagem`, etc.) pelo fluxo "Montar regra" deve persistir igual ao fluxo de edição de bloco existente.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | A investigar em Plan Mode antes de codar — causa raiz ainda não confirmada (ver Problema 2). Primeiro passo: reproduzir manualmente (sem automação) para confirmar que não é uma particularidade da sessão de testes anterior. |

### Fase 3 — Fix: crash na vista Mensal da Agenda

**Objetivo:** um appointment sem campo de data reconhecível não deve crashar a vista Mensal.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/hooks/useAppointments.ts` | `normalizeAppointment()`: fallback de `start` deve ser `null`/`undefined` (não `""`) quando nenhum campo reconhecido está presente, para que a normalização caia no `new Date(...)` em vez de propagar string vazia |
| `frontend-crm/src/components/ScheduleView.tsx` | `normalized` (useMemo, ~linha 59): ignorar/filtrar appointments cuja `Date` resultante seja inválida (`isNaN(date.getTime())`), em vez de deixar `format()` lançar excepção sem proteção |

---

## Checks de Validação

### Cenário P1 — Mensagem de correção varia por agente
- [ ] Configurar 2 agentes com `tone_of_voice` claramente distintos (ex.: um formal, um informal)
- [ ] Forçar um conflito de horário para cada um (via script `test_meeting_scheduler_hook.py` ou Playground+criação manual)
- [ ] Confirmar: a mensagem de correção reflete o tom de cada agente, não é idêntica
- [ ] Forçar falha da LLM durante o conflito (ex.: `LLM_API_BASE` inválido) e confirmar que o fallback `MEETING_CONFLICT_MESSAGE` ainda é enviado (nunca fica sem mensagem)

### Cenário C1 — Fluxo de Venda: bloco novo persiste o conteúdo
- [ ] Reproduzir manualmente (interação humana real, não automação): criar uma nova ação "Orientação ao Agente" via "Montar regra → + Adicionar ação", confirmar e salvar
- [ ] Confirmar no resumo do bloco (lista da fase) que o texto aparece, não "—"
- [ ] Confirmar via API (`GET /ai-profiles/me`) que o `content` foi persistido no `sales_flow.phases[].blocks[]`

### Cenário C2 — Agenda não crasha com appointment malformado
- [ ] Simular (ou aguardar ocorrência real) um appointment sem `start_at` reconhecível
- [ ] Navegar a vista Mensal para o mês/dia correspondente
- [ ] Confirmar: a página não crasha; o appointment malformado é ignorado ou exibido com um placeholder, mas os demais continuam visíveis

---

## Ajustes Possíveis Pós-Implementação

- Se a Fase 2 confirmar que a causa raiz está em refetches concorrentes do React Query, avaliar se outros modais de criação na mesma página (`AiProfile.tsx`) têm o mesmo risco estrutural.
- A Fase 3 resolve o crash, mas não explica *por que* um appointment chega sem `start_at` — se a causa for um formato de evento Google Calendar não tratado, pode justificar uma fase adicional em `google-calendar.md`.
