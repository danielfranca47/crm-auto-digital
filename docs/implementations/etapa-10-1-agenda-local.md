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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8233848` | Página Agenda.tsx (rota /agenda, tabs de vista), WeekView.tsx (semanal), DayView.tsx (diária), rota em App.tsx, item na sidebar |

---

## Checks de Validação

### Cenário 1 — Navegação à agenda

- [x] Aceder a `/agenda` carrega a página sem erro — 2026-06-11 (MCP browser)
- [x] Item "Agenda" aparece na sidebar e está activo (highlighted) quando na rota `/agenda` — 2026-06-11 (MCP browser)
- [x] Por defeito abre na vista mensal (ou a última usada se persistida) — 2026-06-11 (MCP browser)

### Cenário 2 — Vista mensal (reaproveitada)

- [x] Dias com compromissos têm marcação visual — 2026-06-11 (MCP browser; dia 11 listado com evento após criação)
- [x] Ao clicar num dia, os eventos desse dia aparecem na lista abaixo do calendário — 2026-06-11 (MCP browser; "Nenhum evento agendado para esta data" visível)
- [x] Botão "Novo" abre `ScheduleAppointmentDialog` e após guardar o evento aparece no calendário — 2026-06-11 (MCP browser; POST /api/leads/247/appointments 200)

### Cenário 3 — Vista semanal

- [x] 7 colunas com o nome do dia e data (ex.: "Seg 09") — 2026-06-11 (MCP browser; "08 jun – 14 jun 2026" com SEGUNDA→DOMINGO)
- [x] Eventos existentes aparecem na coluna e horário correcto — 2026-06-11 (MCP browser; "09:00 Compromisso" na coluna QUINTA 11)
- [x] Navegar para semana anterior e seguinte com botões ← / → — 2026-06-11 (MCP browser; ← → testados)
- [x] Botão "Hoje" volta à semana actual — 2026-06-11 (MCP browser)
- [x] Clicar num slot vazio abre o dialog com data e hora pré-preenchidos — 2026-06-11 (browser manual; data correta; hora sempre 09:00 → bug corrigido em `ScheduleAppointmentDialog.tsx`)

### Cenário 4 — Vista diária

- [x] Timeline hora a hora do dia seleccionado — 2026-06-11 (MCP browser; "Quinta-Feira, 11 De Junho 2026" com slots 07:00–12:00+)
- [x] Eventos aparecem na faixa de horário correcta — 2026-06-11 (MCP browser; evento visível às 09:00 no DayView)
- [x] Navegar para dia anterior e seguinte com botões ← / → — 2026-06-11 (MCP browser; mesmos botões do WeekView funcionam)
- [x] Clicar num slot abre o dialog com data e hora pré-preenchidos — 2026-06-11 (browser manual; mesmo comportamento do WeekView; bug de hora corrigido)

### Cenário 5 — Criação e edição de compromisso

- [x] Criar compromisso pela vista diária → aparece correctamente em todas as 3 vistas — 2026-06-11 (MCP browser; aparece em Diária, Semanal e Mensal)
- [x] Clicar num evento existente em WeekView ou DayView → abre em modo edição — 2026-06-11 (browser manual; dialog "Editar compromisso" com dados correctos)
- [x] Editar título ou hora → evento actualiza nas 3 vistas — 2026-06-11 (browser manual; título não persistia → bug corrigido em `useAppointments.ts`)

### Bugs detectados e corrigidos durante testes

- **Hora sempre 09:00 ao clicar slot** (CORRIGIDO): `ScheduleAppointmentDialog.tsx` ignorava a hora de `initialDate` ao criar novo compromisso — `setTime("09:00")` hardcoded. Corrigido para extrair `getHours()/getMinutes()` de `initialDate`.
- **Título e tipo não persistiam na edição** (CORRIGIDO): `useUpdateAppointment` e `useCreateAppointment` em `useAppointments.ts` não passavam `title` nem `type` para `api.updateAppointment`/`api.createAppointment`. Os campos estão correctamente suportados pelo `api.ts` e pelo backend — só faltavam ser propagados no hook.
- **"Lead sem nome" nos eventos** (CORRIGIDO em commit b06ead5): `GET /api/appointments` não fazia JOIN com `leads` → `lead_company`/`lead_contact` sempre nulos.

---

## Ajustes Possíveis Pós-Implementação

- Arrastar eventos para reagendar (drag-and-drop com `@dnd-kit` — já disponível no projecto)
- Persistir a última vista usada em `localStorage`
- Filtro por tipo de compromisso (meeting / call / follow-up / presentation)
- Indicador visual de eventos do Google Calendar (relevante para a Fase de integração Google — `etapa-10-2-google-calendar.md`)
