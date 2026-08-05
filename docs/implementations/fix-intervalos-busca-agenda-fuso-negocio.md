# Fix: intervalos de busca da Agenda não respeitam o fuso do negócio

**Branch:** `fix/intervalos-busca-agenda-fuso-negocio`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de `fix-confirm-exact-agenda-vazia.md`
(Fase 3) e de `feat-dual-fuso-agenda.md`.

A Fase 3 de `fix-confirm-exact-agenda-vazia.md` corrigiu a **exibição/edição** do horário
dos compromissos para usar o fuso configurado no AI Profile do negócio
(`ai_profile.timezone`) em vez do fuso do navegador — ver `docs/architecture/agenda.md`,
secção "Fuso Horário na Agenda". Essa correção não estendeu aos **intervalos de busca**:
`Dashboard.tsx` ("Reuniões de Hoje"), `WeekView.tsx`, `DayView.tsx` e `ScheduleView.tsx`
continuam calculando os limites de dia/semana/mês (`start`/`end` enviados ao backend) no
fuso do navegador de quem está a ver a tela, não no fuso do negócio.

**Impacto prático:** só afecta compromissos muito próximos da meia-noite quando o fuso do
negócio e o fuso de quem está a ver a Agenda têm uma diferença grande — um compromisso pode
aparecer no dia errado, ou faltar na lista de "hoje", dependendo de qual fuso está a ser
usado para calcular a fronteira do dia.

---

## Problemas Identificados (estado anterior)

1. **Cálculo de intervalo de busca no fuso errado:** `Dashboard.tsx`, `WeekView.tsx`,
   `DayView.tsx`, `ScheduleView.tsx` — todos calculam `start`/`end` da query a partir de
   `Date` nativo (fuso do navegador), não a partir do fuso do negócio
   (`useBusinessTimezone()`). Arquivos e linhas exactas a levantar em Plan Mode.

---

## Fora de escopo (confirmado por leitura)

- `hasEventsOnDate` em `ScheduleView.tsx:83-85` — compara `event.date` (já normalizado
  para o fuso do negócio) contra o `Date` bruto do `<Calendar>` picker. É destaque visual
  no calendário, não intervalo de busca — não mexer.
- Colunas de grade do `WeekView` (`days = eachDayOfInterval({ start: weekStart, end:
  weekEnd })`) e navegação dia-a-dia do `DayView`/`WeekView` — continuam no fuso do
  navegador (comportamento intencional de `useAgendaTimezoneMode`); só a fronteira UTC
  enviada ao backend muda.

## Abordagem

Novo par de helpers em `frontend-crm/src/lib/timezone.ts` (reaproveitando
`fromBusinessTimezoneDate`):

```ts
export function getBusinessDayBounds(date: Date, timeZone: string): { start: Date; end: Date } {
  const y = date.getFullYear();
  const m = date.getMonth();
  const d = date.getDate();
  return {
    start: fromBusinessTimezoneDate(new Date(y, m, d, 0, 0, 0, 0), timeZone),
    end: fromBusinessTimezoneDate(new Date(y, m, d, 23, 59, 59, 999), timeZone),
  };
}

export function getBusinessRangeBounds(
  startDate: Date,
  endDate: Date,
  timeZone: string
): { start: Date; end: Date } {
  return {
    start: getBusinessDayBounds(startDate, timeZone).start,
    end: getBusinessDayBounds(endDate, timeZone).end,
  };
}
```

---

## Plano de Implementação

Fase única (mudança mecânica e homogênea, mesmo padrão replicado):

| Arquivo | Mudança |
|---|---|
| `frontend-crm/src/lib/timezone.ts` | Adicionar `getBusinessDayBounds()` e `getBusinessRangeBounds()` |
| `frontend-crm/src/components/DayView.tsx` | Reordenar `useAgendaTimezoneMode()` antes do `useAppointments`; trocar `dayStart`/`dayEnd` (cálculo nativo) por `getBusinessDayBounds(selectedDay, businessTimezone)`, memoizado |
| `frontend-crm/src/components/WeekView.tsx` | Reordenar `useAgendaTimezoneMode()` antes do `useAppointments`; manter `weekStart`/`weekEnd` intactos para a grade; calcular `queryBounds = getBusinessRangeBounds(weekStart, weekEnd, businessTimezone)` para o `useAppointments` |
| `frontend-crm/src/components/ScheduleView.tsx` | `monthRange(date)` ganha parâmetro `timeZone`; usa `getBusinessRangeBounds` internamente; `useBusinessTimezone()` sobe para antes da chamada, memoizada |
| `frontend-crm/src/pages/Dashboard.tsx` | `todayRange` via `getBusinessDayBounds(new Date(), businessTimezone)`; `todayAppointments` compara via `toBusinessTimezoneDate` em vez de `Date` nativo |

---

## Checks de Validação

- [ ] `npx tsc --noEmit -p .` em `frontend-crm` sem erros
- [ ] Compromisso perto da meia-noite (fuso do negócio ≠ fuso do navegador) aparece no dia
      correto em: Dashboard ("Reuniões de Hoje"), DayView, WeekView, ScheduleView
- [ ] Regressão: fuso do navegador == fuso do negócio — nada muda visualmente
