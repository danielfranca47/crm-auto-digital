# Agenda Local — Vistas Mensal, Semanal e Diária

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

---

## Motivação

O sistema já tem CRUD completo de compromissos (`/api/appointments`) e um componente de agenda (`ScheduleView.tsx`) com vista mensal e lista. No entanto, esse componente nunca foi exposto como página — não há rota `/agenda` nem item na sidebar. Além disso, faltam as vistas semanal (7 colunas com faixas de horário) e diária (timeline hora a hora), que são fundamentais para um uso operacional da agenda. O utilizador quer a agenda como uma área dedicada do CRM com as três vistas.

---

## Problemas Identificados (estado anterior)

1. **Sem rota de agenda:** `ScheduleView.tsx` existe em `frontend-crm/src/components/` mas não está importado em `App.tsx` — inacessível ao utilizador.
2. **Sem item na sidebar:** `AppSidebar.tsx` não tem entrada "Agenda".
3. **Sem vista semanal:** não existe componente de calendário com colunas por dia da semana e faixas de horário.
4. **Sem vista diária:** não existe timeline hora a hora para o dia seleccionado.

---

## Abordagem

```
/agenda (nova página Agenda.tsx)
  ├─ Tabs / botões de vista: [Mensal] [Semanal] [Diária]
  │
  ├─ Mensal → ScheduleView.tsx (reaproveitado sem alterações)
  ├─ Semanal → WeekView.tsx (novo)
  │     7 colunas (seg–dom), faixas de 30min (00h–23:30h)
  │     Eventos posicionados pelo start_at/end_at
  │     Clique em slot vazio → abre ScheduleAppointmentDialog com data/hora pré-preenchidos
  └─ Diária → DayView.tsx (novo)
        1 coluna, faixas de 30min, mesma lógica
        Clique em slot → abre dialog

Navegação:
  ← / → para avançar/recuar semana ou dia
  "Hoje" para voltar ao presente
```

Sem alterações de backend — a API existente (`GET /api/appointments?start=&end=`) serve todos os filtros necessários.

---

## Plano de Implementação

### Fase 1 — Agenda local com vistas semanal e diária

**Objetivo:** expor a agenda como página dedicada com 3 vistas funcionais (mensal, semanal, diária).

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/Agenda.tsx` | Nova página — tabs de vista, estado de data seleccionada, orquestra os 3 componentes de vista |
| `frontend-crm/src/components/WeekView.tsx` | Novo componente — grade CSS 7 colunas × 48 slots de 30min, eventos posicionados por horário |
| `frontend-crm/src/components/DayView.tsx` | Novo componente — grade CSS 1 coluna × 48 slots, timeline do dia |
| `frontend-crm/src/App.tsx` | Adicionar `import Agenda` + `<Route path="/agenda" element={<Agenda />} />` dentro do bloco `Protected + AppShell` |
| `frontend-crm/src/components/AppSidebar.tsx` | Adicionar item "Agenda" com ícone `CalendarDays` e link para `/agenda` |

**Detalhes de WeekView e DayView:**

- Construídos com CSS Grid + Tailwind (sem biblioteca de calendário externa)
- `date-fns` para geração dos slots, formatação, `startOfWeek`, `endOfWeek`, `eachDayOfInterval`
- Os eventos são posicionados com `top` e `height` calculados em função do `start_at` / `end_at` relativamente à grade (estilo `position: absolute` dentro de cada coluna)
- Clique num slot vazio abre `ScheduleAppointmentDialog` com `initialDate` pré-preenchido com a data+hora do slot
- Clique num evento existente abre o dialog em modo edição (`appointmentToEdit`)
- Cores dos eventos mantêm a convenção já existente em `ScheduleView.tsx`: `meeting`, `call`, `follow-up`, `presentation`

---

## Checks de Validação

### Cenário 1 — Navegação à agenda

- [ ] Aceder a `/agenda` carrega a página sem erro
- [ ] Item "Agenda" aparece na sidebar e está activo (highlighted) quando na rota `/agenda`
- [ ] Por defeito abre na vista mensal (ou a última usada se persistida)

### Cenário 2 — Vista mensal (reaproveitada)

- [ ] Dias com compromissos têm marcação visual
- [ ] Ao clicar num dia, os eventos desse dia aparecem na lista abaixo do calendário
- [ ] Botão "Novo" abre `ScheduleAppointmentDialog` e após guardar o evento aparece no calendário

### Cenário 3 — Vista semanal

- [ ] 7 colunas com o nome do dia e data (ex.: "Seg 09")
- [ ] Eventos existentes aparecem na coluna e horário correcto
- [ ] Navegar para semana anterior e seguinte com botões ← / →
- [ ] Botão "Hoje" volta à semana actual
- [ ] Clicar num slot vazio abre o dialog com data e hora pré-preenchidos

### Cenário 4 — Vista diária

- [ ] Timeline hora a hora do dia seleccionado
- [ ] Eventos aparecem na faixa de horário correcta
- [ ] Navegar para dia anterior e seguinte com botões ← / →
- [ ] Clicar num slot abre o dialog com data e hora pré-preenchidos

### Cenário 5 — Criação e edição de compromisso

- [ ] Criar compromisso pela vista semanal → aparece correctamente em todas as 3 vistas
- [ ] Clicar num evento existente em WeekView ou DayView → abre em modo edição
- [ ] Editar título ou hora → evento actualiza nas 3 vistas

---

## Ajustes Possíveis Pós-Implementação

- Arrastar eventos para reagendar (drag-and-drop com `@dnd-kit` — já disponível no projecto)
- Persistir a última vista usada em `localStorage`
- Filtro por tipo de compromisso (meeting / call / follow-up / presentation)
- Indicador visual de eventos do Google Calendar (relevante para a Fase de integração Google — `etapa-10-2-google-calendar.md`)
