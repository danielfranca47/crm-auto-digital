# Fix: "Cancelar compromisso" falha (422) no menu rápido do Kanban

**Branch:** `main`
**Status:** Todos os cenários validados (04/08/2026) — pendente: graduação

---

## Motivação

Durante a validação do fix de `setLeadNextAction`, testar "Cancelar compromisso" no
menu rápido (⋮) do card do Kanban revelou um terceiro bug, diferente dos dois já
corrigidos: a operação **falha de verdade no backend** (não é só uma mensagem de erro
enganosa). A UI mostrava `Erro ao cancelar compromisso: [object Object],[object
Object]` e o compromisso continuava ativo.

---

## Problemas Identificados (estado anterior)

1. **`KanbanBoard.tsx:356` chamava `cancelAppointment.mutateAsync` com o formato
   errado:** `frontend-crm/src/components/KanbanBoard.tsx:348-367`
   (`handleCancelMeeting`) passava só a string do id
   (`cancelAppointment.mutateAsync(appointmentId)`), mas `useCancelAppointment()`
   (`frontend-crm/src/hooks/useAppointments.ts:205-217`) espera `{ id, leadId }`. Ao
   desestruturar `{ id, leadId }` de uma string, ambos viravam `undefined`, gerando
   `PATCH /api/leads/undefined/appointments/undefined` → `422` (confirmado via rede
   durante a validação anterior). O toast "[object Object],[object Object]" era só o
   `detail` (array de objetos do FastAPI) virando string via `Array.toString()`.

   Já sinalizado por `npx tsc --noEmit -p tsconfig.app.json`:
   `KanbanBoard.tsx(356,43): error TS2345: Argument of type 'string' is not assignable
   to parameter of type '{ id: string | number; leadId: string | number; }'.`

   Os outros 2 call sites de `cancelAppointment.mutateAsync` já passavam o formato
   correto (`LeadCardDialog.tsx:406`, `ProspectionCardDialog.tsx:307`) — bug isolado a
   este ponto de entrada.

---

## Abordagem

Alinhar `KanbanBoard.tsx` com o padrão já usado nos outros 2 pontos — `lead.id` já
estava disponível no escopo de `handleCancelMeeting`.

---

## Plano de Implementação

### Fase 1 — Corrigir o formato do argumento

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/KanbanBoard.tsx` | linha 356: `cancelAppointment.mutateAsync(appointmentId)` → `cancelAppointment.mutateAsync({ id: appointmentId, leadId: lead.id })` |

```ts
// ANTES
await cancelAppointment.mutateAsync(appointmentId);

// DEPOIS
await cancelAppointment.mutateAsync({ id: appointmentId, leadId: lead.id });
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b01c2ae` | fix: corrige formato do argumento ao cancelar compromisso no Kanban |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** cancelar uma reunião pelo menu rápido "⋮ → Cancelar compromisso" no card do
Kanban falhava de verdade (o compromisso continuava ativo) e mostrava um erro confuso
("[object Object],[object Object]").
**Agora:** o cancelamento funciona — toast "Compromisso cancelado" e o badge "Próximo
compromisso" some do card.
**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário P1 — Cancelar via menu rápido do Kanban funciona
- [x] No Kanban, agendar uma reunião num lead (para ter algo a cancelar), depois abrir o
  menu (⋮) → "Cancelar compromisso" — 04/08/2026
- [x] Confirmar: toast "Compromisso cancelado" (não o erro), badge "Próximo
  compromisso" some do card — 04/08/2026
- [x] Checar rede: `PATCH /api/leads/{id}/appointments/{id}` com ids reais (não
  `undefined`) → `200` — 04/08/2026 (`PATCH /api/leads/366/appointments/64` → `200`)

**Validado em:** 04/08/2026 — testado ao vivo via browser (MCP). Criado um compromisso
de teste no lead "DF FLOW BARBERSHOP" via menu rápido, cancelado na mesma sessão pelo
mesmo menu — toast correto, badge removido, request de rede com ids reais (não mais
`undefined`).

**Nota do processo de teste:** a primeira tentativa usou um compromisso pré-existente
que só tinha sido carregado via `GET /api/leads` (reload de página) — o backend não
inclui o campo `id` dentro de `nextScheduledAction` nessa rota (só `date`/`description`),
então o guard `if (!appointmentId) return` de `handleCancelMeeting` bloqueava
silenciosamente (nenhum toast visível a tempo, sem chamada de rede). Isso não é um bug —
é o guard funcionando como esperado diante de um dado que já vem incompleto do backend;
o teste foi refeito criando e cancelando um compromisso na mesma sessão (onde o `id`
vem do `setLeadNextAction` local) para validar o fix corretamente.

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado — fix isolado de uma linha, sem trade-offs.
