# Fix: "setLeadNextAction is not a function" ao agendar reunião pelo menu rápido do Kanban

**Branch:** `main`
**Status:** Cenário principal validado (04/08/2026) — 1 check pulado [⏭️] (bug diferente
encontrado em "Cancelar compromisso", ver seção "Achado adicional")

---

## Motivação

Durante a validação do fix de crash ao criar compromisso (`fix-crash-criar-compromisso-agenda.md`),
usar o menu de ação rápida "Agendar Reunião" no card compacto do Kanban (não o modal
completo "Abrir card") criava o compromisso com sucesso no backend, mas a UI mostrava um
toast de erro enganoso — `Erro ao salvar compromisso: setLeadNextAction is not a
function`. Falso negativo: o utilizador vê "erro" quando o compromisso já foi salvo,
com risco de duplicar o agendamento ao tentar de novo.

---

## Problemas Identificados (estado anterior)

1. **`setLeadNextAction` nunca foi implementado em `LeadsContext.tsx`:** não existia na
   interface `LeadsContextType` (`frontend-crm/src/contexts/LeadsContext.tsx:16-42`) nem
   no objeto `value` passado ao `Provider`. Confirmado via
   `npx tsc --noEmit -p tsconfig.app.json` (o `tsc --noEmit` direto na raiz não checa
   nada — `tsconfig.json` tem `"files": []` e só `references`):
   `src/components/KanbanBoard.tsx(48,5): error TS2339: Property 'setLeadNextAction' does not exist on type 'LeadsContextType'.`

2. **`KanbanBoard.tsx` usa a referência sem guard:**
   `frontend-crm/src/components/KanbanBoard.tsx:38-49` destructura `setLeadNextAction`
   direto de `useLeads()`, sem fallback. Como a propriedade não existe no valor real do
   contexto, era `undefined` em runtime — usado sem guard em `handleCancelMeeting`
   (linha 357) e no `onSuccess` do `<ScheduleAppointmentDialog>` renderizado pelo
   próprio `KanbanBoard` para o menu rápido "Agendar Reunião" (linha 551). Chamar
   `undefined(...)` lança `TypeError: setLeadNextAction is not a function`, capturado
   pelo `catch` de `ScheduleAppointmentDialog.handleSubmit` **depois** da criação já ter
   tido sucesso.

3. **Efeito colateral silencioso nos outros 3 pontos de uso:** `LeadCardDialog.tsx`,
   `ScheduleAppointmentDialog.tsx` (fluxo interno do card) e `ProspectionCardDialog.tsx`
   já protegiam a chamada com `(leadsCtx as any)?.setLeadNextAction ?? (() => {})` — não
   crashavam, mas também nunca atualizavam de fato o "Próximo compromisso" na
   `LeadsContext` por esse caminho (os badges só se atualizavam quando outra via
   coincidentemente recarregava o lead).

---

## Abordagem

Todos os 6 call sites já passam exatamente a forma de `Lead['nextScheduledAction']`
(`{ id?, date: Date, description: string, type? }`) ou `undefined` para limpar.
`updateLead(leadId, updates: Partial<Lead>)` já atualiza o `columns` local state e
exclui explicitamente `nextScheduledAction` do payload enviado ao backend (campo
derivado, client-side-only) — ou seja, `updateLead(leadId, { nextScheduledAction: next })`
já faz exatamente o que `setLeadNextAction` deveria fazer. Implementado como wrapper
fino, sem duplicar lógica.

---

## Plano de Implementação

### Fase 1 — Implementar `setLeadNextAction` em `LeadsContext.tsx`

**Objetivo:** o método passa a existir de verdade no contexto, eliminando o crash e o
efeito colateral silencioso.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/contexts/LeadsContext.tsx` | Adiciona `setLeadNextAction` à interface `LeadsContextType`; implementa como wrapper de `updateLead`; inclui no objeto `value` do `Provider` |

```ts
// Interface
updateLead: (leadId: string, updates: Partial<Lead>) => void;
setLeadNextAction: (leadId: string, next?: Lead['nextScheduledAction']) => void;

// Implementação (logo após updateLead)
const setLeadNextAction = (leadId: string, next?: Lead['nextScheduledAction']) => {
  updateLead(leadId, { nextScheduledAction: next });
};
```

Nenhuma mudança nos 4 arquivos que já chamam `setLeadNextAction` — todos já esperam essa
assinatura exata.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `c3df1f7` | fix: implementa setLeadNextAction ausente em LeadsContext |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** agendar reunião pelo menu rápido "⋮ → Agendar Reunião" no card do Kanban
salvava o compromisso normalmente, mas mostrava um toast de erro ("Erro ao salvar
compromisso: setLeadNextAction is not a function") — o utilizador achava que a operação
tinha falhado, mesmo tendo funcionado.
**Agora:** o mesmo fluxo mostra o toast correto ("Compromisso criado") e o card do
Kanban atualiza o "Próximo compromisso" imediatamente.
**Para validar:** Cenário P1 e regressão, abaixo.

---

## Checks de Validação

### Cenário P1 — Agendar via menu rápido do Kanban não mostra erro falso
- [x] No Kanban, abrir o menu (⋮) de um card → "Agendar Reunião" → preencher e salvar —
  04/08/2026
- [x] Confirmar: toast "Compromisso criado" (não "Erro ao salvar"), badge "Próximo
  compromisso" do card atualiza — 04/08/2026 (badge foi de "04/08, 05:56" para "04/08,
  23:00" imediatamente após salvar)

### Regressão — Reagendar e cancelar pelo mesmo menu
- [x] "Reagendar compromisso" pelo menu rápido — sem erro, badge atualiza — 04/08/2026
  (toast "Compromisso atualizado", badge foi para "04/08, 23:30")
- [⏭️] "Cancelar compromisso" pelo menu rápido — **revelou um bug diferente**, ver seção
  abaixo — não corrigido nesta fase

### Regressão — "Abrir card" continua funcionando
- [x] Agendar via "Abrir card" (`LeadCardDialog`) já validado indiretamente nas fases
  anteriores (`fix-crash-criar-compromisso-agenda.md`, Cenário P2) — mesmo componente
  `ScheduleAppointmentDialog`, mesmo `setLeadNextAction` agora implementado — 04/08/2026

**Validado em:** 04/08/2026 — testado ao vivo via browser (MCP). P1 e a regressão de
"Reagendar" passaram. "Cancelar compromisso" pelo menu rápido revelou um bug diferente
(não relacionado a `setLeadNextAction`), documentado abaixo.

---

## Achado adicional durante a validação (bug diferente, não corrigido nesta fase)

Ao clicar "Cancelar compromisso" no menu rápido do Kanban, a UI mostra
`Erro ao cancelar compromisso: [object Object],[object Object]` e o compromisso **não é
cancelado** (diferente do bug anterior, aqui a operação realmente falha no backend).

**Causa:** `handleCancelMeeting` em `KanbanBoard.tsx:348-367` chama
`cancelAppointment.mutateAsync(appointmentId)` passando só a string do id, mas
`useCancelAppointment()`'s `mutationFn` (`frontend-crm/src/hooks/useAppointments.ts:208`)
espera `{ id, leadId }`. Confirmado via rede: `PATCH
/api/leads/undefined/appointments/undefined` → `422` (`id`/`leadId` viram `undefined` ao
desestruturar `{ id, leadId }` de uma string). Já sinalizado por
`npx tsc --noEmit -p tsconfig.app.json`:
`KanbanBoard.tsx(356,43): error TS2345: Argument of type 'string' is not assignable to
parameter of type '{ id: string | number; leadId: string | number; }'.`

Não corrigido nesta fase — bug diferente do que motivou esta fase (`setLeadNextAction`).
Registrado para decisão do utilizador sobre abrir mais uma fase.

---

## Ajustes Possíveis Pós-Implementação

- Os guards defensivos `?? (() => {})` em `LeadCardDialog.tsx`,
  `ScheduleAppointmentDialog.tsx` e `ProspectionCardDialog.tsx` ficam redundantes agora
  que `setLeadNextAction` sempre existe no contexto — inofensivos, não removidos nesta
  fase por não serem necessários para a correção.
- Ver "Achado adicional" acima (`Cancelar compromisso` no menu rápido do Kanban) — bug
  separado, não corrigido nesta fase.
