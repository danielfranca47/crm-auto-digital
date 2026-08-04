# Fix: "setLeadNextAction is not a function" ao agendar reunião pelo menu rápido do Kanban

**Branch:** `main`
**Status:** Em andamento

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
| 1 | *(pendente)* | fix: implementa setLeadNextAction ausente em LeadsContext |

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
- [ ] No Kanban, abrir o menu (⋮) de um card → "Agendar Reunião" → preencher e salvar
- [ ] Confirmar: toast "Compromisso criado" (não "Erro ao salvar"), badge "Próximo
  compromisso" do card atualiza

### Regressão — Reagendar e cancelar pelo mesmo menu
- [ ] "Reagendar compromisso" pelo menu rápido — sem erro, badge atualiza
- [ ] "Cancelar compromisso" pelo menu rápido — sem erro, badge some

### Regressão — "Abrir card" continua funcionando
- [ ] Agendar/editar reunião via "Abrir card" (`LeadCardDialog`) — sem regressão

---

## Ajustes Possíveis Pós-Implementação

- Os guards defensivos `?? (() => {})` em `LeadCardDialog.tsx`,
  `ScheduleAppointmentDialog.tsx` e `ProspectionCardDialog.tsx` ficam redundantes agora
  que `setLeadNextAction` sempre existe no contexto — inofensivos, não removidos nesta
  fase por não serem necessários para a correção.
