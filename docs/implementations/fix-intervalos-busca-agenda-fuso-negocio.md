# Fix: intervalos de busca da Agenda não respeitam o fuso do negócio

**Branch:** *(a definir ao iniciar)*
**Status:** Aguardando Plan Mode

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

## Abordagem (rascunho — a confirmar em Plan Mode)

A confirmar: provavelmente usar `toBusinessTimezoneDate`/`fromBusinessTimezoneDate`
(`src/lib/timezone.ts`, já existentes — ver `docs/architecture/agenda.md`) para calcular os
limites de dia/semana/mês a partir do fuso do negócio antes de montar a query, em vez do
`Date` nativo do navegador.

---

## Plano de Implementação

*(a preencher em Plan Mode)*

---

## Checks de Validação

*(a preencher em Plan Mode)*
