# Agenda — Vistas Mensal, Semanal e Diária

Módulo de agenda do frontend-crm: estrutura de vistas, posicionamento de eventos, interacções e API de compromissos.

---

## Estrutura de Páginas e Vistas

A agenda está acessível em `/agenda` com 3 vistas alternáveis:

| Vista | Componente | Descrição |
|---|---|---|
| Mensal | `ScheduleView.tsx` | Calendário mensal com lista de eventos do dia selecionado |
| Semanal | `WeekView.tsx` | Grade CSS com 7 colunas (seg→dom) e faixas de 30min |
| Diária | `DayView.tsx` | Grade CSS com 1 coluna e timeline hora a hora |

**Orquestração:** `src/pages/Agenda.tsx` — mantém o estado da vista activa e da data seleccionada. Cada vista gere internamente a sua navegação (← / → / "Hoje").

**Rota:** `/agenda` no bloco `Protected + AppShell` de `App.tsx`  
**Sidebar:** item "Agenda" com ícone `CalendarDays` em `AppSidebar.tsx`

---

## Constantes da Grade (WeekView e DayView)

```ts
const START_HOUR = 7;      // primeira hora visível
const END_HOUR = 21;       // última hora visível
const SLOT_HEIGHT = 44;    // px por slot de 30min
const HALF_HOURS = (END_HOUR - START_HOUR) * 2;   // = 28 slots
const TOTAL_HEIGHT = HALF_HOURS * SLOT_HEIGHT;     // = 1232px
```

---

## Posicionamento de Eventos

Eventos posicionados com `position: absolute` dentro da coluna do dia:

```ts
function slotTopPx(date: Date): number {
  const mins = (getHours(date) - START_HOUR) * 60 + getMinutes(date);
  return (mins / 30) * SLOT_HEIGHT;
}

function durationPx(startTime: string, endTime: string | null): number {
  const start = new Date(startTime);
  const end = endTime ? new Date(endTime) : addMinutes(start, 60);
  const durationMins = Math.max(30, (end.getTime() - start.getTime()) / 60000);
  return (durationMins / 30) * SLOT_HEIGHT;
}
```

Duração mínima: 30min (eventos com `end_at` nulo ou igual a `start_at`).  
Eventos fora de `[START_HOUR, END_HOUR]` são descartados pelo render (`top < 0` ou `top >= TOTAL_HEIGHT`).

---

## Interacção com Slots e Eventos

**Clique num slot vazio** → `openCreate(day, slotIndex)` constrói uma `Date` com a hora do slot:

```ts
function openCreate(day: Date, slotIndex: number) {
  const d = new Date(day);
  d.setHours(START_HOUR + Math.floor((slotIndex * 30) / 60), (slotIndex * 30) % 60, 0, 0);
  setDialogInitialDate(d);
  setDialogOpen(true);
}
```

`ScheduleAppointmentDialog` extrai horas/minutos de `initialDate` para pré-preencher o campo "Hora" (quando não há `appointmentToEdit`).

**Clique num evento existente** → `openEdit(appointment)` — abre o dialog com `appointmentToEdit` preenchido; o form entra em modo edição com título, tipo, data e hora do evento.

---

## Cores dos Eventos

| Tipo | Classe Tailwind |
|---|---|
| `meeting` | `bg-primary/85 text-primary-foreground` |
| `call` | `bg-green-600/85 text-white` |
| `follow-up` | `bg-amber-500/85 text-white` |
| `presentation` | `bg-blue-500/85 text-white` |

---

## ScheduleAppointmentDialog

`src/components/ScheduleAppointmentDialog.tsx` — partilhado pelas 3 vistas e pelo `LeadCardDialog`.

**Props principais:**

| Prop | Tipo | Descrição |
|---|---|---|
| `initialDate` | `Date` | Data+hora pré-preenchidos (slot click) |
| `appointmentToEdit` | `Appointment \| null` | Preenche o form em modo edição |
| `fixedLeadId` | `string` | Trava o dialog num lead específico (modo card do lead) |
| `onSuccess` | `(appointment) => void` | Callback após criar ou editar |

**Payload enviado (criar e editar):**
```ts
{
  leadId: effectiveLeadId,
  title: title || appointmentTypeLabels[type],  // fallback para o label do tipo
  description: description || undefined,
  type,
  startTime: startAt.toISOString(),
}
```

**Fallback de lead:** quando não há `fixedLeadId` e nenhum lead está seleccionado, selecciona automaticamente o primeiro da lista ordenada alfabeticamente.

---

## API de Compromissos

### Endpoints usados pelo frontend

| Endpoint | Método | Usado por |
|---|---|---|
| `GET /api/appointments?start=&end=` | GET | WeekView, DayView — filtra pelo intervalo da vista; requer JWT (filtra por `user_id`) |
| `GET /api/appointments/lead/{id}` | GET | ScheduleView — lista por lead |
| `POST /api/appointments/google-sync?start=&end=` | POST | Agenda.tsx — importa eventos Google para o período (upsert + cleanup) |
| `POST /api/leads/{leadId}/appointments` | POST | Criar compromisso |
| `PATCH /api/leads/{leadId}/appointments/{id}` | PATCH | Editar compromisso |
| `DELETE /api/leads/{leadId}/appointments/{id}` | DELETE | Remover compromisso |

### Formato de resposta — AppointmentOut

```python
class AppointmentOut(BaseModel):
    id: int
    lead_id: Optional[int]           # None para eventos importados do Google sem lead associado
    user_id: Optional[int]           # preenchido em eventos Google (lead_id IS NULL)
    title: str
    description: Optional[str]
    type: Optional[str]              # "meeting" | "call" | "follow-up" | "presentation"
    start_at: datetime
    end_at: Optional[datetime]
    status: AppointmentStatus        # "pending" | "completed" | "canceled"
    outcome: Optional[AppointmentOutcome]
    outcome_note: Optional[str]
    outcome_at: Optional[datetime]
    location: Optional[str]
    google_event_id: Optional[str]   # ID do evento no Google Calendar
    source: str                      # "crm" (default) | "google"
    created_at: datetime
    updated_at: datetime
    lead_company: Optional[str]      # via LEFT JOIN com leads (companyName)
    lead_contact: Optional[str]      # via LEFT JOIN com leads (contactName)
```

`lead_company` e `lead_contact` são populados via LEFT JOIN nas queries `list_appointments` e `list_by_lead`:

```sql
SELECT a.*, l.companyName AS lead_company, l.contactName AS lead_contact
FROM appointments a LEFT JOIN leads l ON a.lead_id = l.id
```

O frontend normaliza em `normalizeAppointment()` (`useAppointments.ts`):
```ts
leadName: raw?.lead_contact ?? raw?.leadName ?? null,
leadCompany: raw?.lead_company ?? raw?.leadCompany ?? null,
```

### Hooks React Query

| Hook | Para quê |
|---|---|
| `useAppointments(filters)` | Lista por intervalo (agenda) |
| `useLeadAppointments(leadId)` | Lista por lead (card do lead) |
| `useCreateAppointment()` | Criar |
| `useUpdateAppointment()` | Editar (inclui title e type) |
| `useCancelAppointment()` | Cancelar |

Todos definidos em `src/hooks/useAppointments.ts`. Mutations invalidam `appointmentsKeys.all` no sucesso.

---

## Tabela `appointments` (crm.db)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER PK | — |
| `lead_id` | INTEGER FK nullable | Referência a `leads.id`; NULL para eventos importados do Google sem lead |
| `user_id` | INTEGER | Dono do evento; derivado de `leads.user_id` para CRM, direto para eventos Google |
| `title` | TEXT | Título do compromisso |
| `description` | TEXT | Notas/detalhes |
| `type` | TEXT | `meeting` \| `call` \| `follow-up` \| `presentation` |
| `start_at` | TEXT (ISO) | Início |
| `end_at` | TEXT (ISO) | Fim |
| `status` | TEXT | `pending` \| `completed` \| `canceled` |
| `outcome` | TEXT | `completed` \| `no_show` \| `rescheduled` |
| `outcome_note` | TEXT | Nota de outcome |
| `outcome_at` | TEXT (ISO) | Timestamp do outcome |
| `location` | TEXT | Local (opcional) |
| `google_event_id` | TEXT | ID do evento no Google Calendar (null se não sincronizado) |
| `source` | TEXT | `crm` (default) \| `google` |
| `created_at` | TEXT (ISO) | — |
| `updated_at` | TEXT (ISO) | — |

**Índices:** `idx_appointments_lead (lead_id)`, `idx_appointments_time (start_at)`, `idx_appointments_user (user_id, start_at)`.

**Filtro de listagem:** `GET /api/appointments` filtra por `user_id` usando: `(lead_id IS NOT NULL AND l.user_id = ?) OR (lead_id IS NULL AND a.user_id = ?)`.

---

## Eventos do Google Calendar na Agenda

Eventos importados via `POST /api/appointments/google-sync` têm `source='google'` e comportamento especial no frontend:

- **Badge "Google"** (azul): visível nas 3 vistas (`ScheduleView`, `WeekView`, `DayView`) via `{isGoogle && <Badge>Google</Badge>}`
- **Somente-leitura:** `onClick` verifica `if (!isGoogle) openEdit(event)` — eventos Google não abrem o dialog de edição
- **Cursor:** `isGoogle ? "cursor-default opacity-80" : "cursor-pointer"`
- **Lead:** `leadName` é `null` para eventos Google — a linha "Lead:" é suprimida na UI

**Botão "Sincronizar Google"** em `Agenda.tsx`: visível apenas quando `googleCalendar.getStatus()` retorna `connected: true`. Ao clicar, chama o endpoint google-sync para o mês corrente e invalida `appointmentsKeys.all` (refetch de todas as vistas).

**Upsert e cleanup (google-sync):**
- Upsert por `(google_event_id, user_id)` — sincronizar duas vezes não duplica
- Cleanup automático: apaga `source='google'` do período que já não existem no Google → F3-2 (evento removido do Google desaparece na próxima sync)

---

## Side-effects de criar/editar um compromisso (backend)

Ao criar (`POST /api/leads/{id}/appointments` ou via `routes/appointments.py`), o backend:

1. Valida que não há conflito de horário **para o profissional inteiro** (`_check_conflict`) — não apenas para o mesmo lead. Existem duas implementações paralelas e independentes (uma em cada arquivo, mesma regra): `routes/leads.py::_check_conflict` (usa `current_user.id` diretamente — endpoint já autenticado) e `routes/appointments.py::_check_conflict` (resolve o `user_id` via `_resolve_owner_user_id()`, a partir do `lead_id` ou do `user_id` próprio em appointments importados do Google sem lead). Ambas bloqueiam com `409` se outro appointment do mesmo `user_id` (qualquer lead, ou evento Google) sobrepuser o intervalo — esta é a defesa real contra conflito, pois roda dentro da transacção SQLite no momento exacto do INSERT/UPDATE.
2. Agenda jobs de lembrete (`whatsapp.appointment_reminder`) com offsets configuráveis por template_key
3. Agenda job de briefing (`briefing_job`) se `briefing_enabled` não for `False`
4. Faz push para Google Calendar se o utilizador tiver tokens OAuth2 válidos (`google_calendar_service.push_event`)

`google_event_id` é persistido na linha do appointment quando o push é bem-sucedido. Editar ou cancelar o compromisso actualiza/remove o evento no Google Calendar de forma fail-silent.

---

## `calendar_busy_slots` — a IA consulta disponibilidade real antes de propor/confirmar horário

Antes desta funcionalidade, a Filha de agendamento (`decision_engine.py::_build_child_prompt_agendamento`)
só recebia o campo de texto livre `ai_profile.availability_schedule` como dica
geral — não tinha nenhum dado real do que já estava ocupado, e podia inventar
disponibilidade. A criação do appointment também não checava conflito com
outros leads do mesmo profissional.

```
backend-crm (orchestrator.py)
  enrich_context_bundle() carrega calendar_busy_slots — compromissos reais do
  profissional (próximos 30 dias, status='pending', inclui CRM + importados
  do Google) — quando ai_profile.agent_mode == "agenda"
        ↓ (mesmo ContextBundle — paridade automática Playground + WhatsApp real)
backend-executors (decision_engine.py)
  _build_child_prompt_agendamento injeta bloco "HORÁRIOS JÁ OCUPADOS"
  (convertido para a timezone do perfil) antes do availability_schedule
        ↓ (só no caminho real, via runners/whatsapp.py — Playground nunca
           chama handle_meeting_scheduled, por desenho: sandbox não cria
           appointments reais)
backend-executors (meeting_scheduler.py + whatsapp.py)
  handle_meeting_scheduled() checa o horário confirmado pela IA contra
  calendar_busy_slots: se colidir com outro lead, NÃO cria o appointment, NÃO
  desabilita o bot, e devolve uma mensagem de correcção que o runner envia ao
  lead via core_client.send_whatsapp_message(). Fora da janela de 30 dias, a
  checagem é pulada (loga o evento) e segue o comportamento normal.
        ↓
backend-crm (routes/appointments.py + routes/leads.py)
  _check_conflict (ver secção acima) é a barreira final — roda na transacção
  do INSERT, cobre também a criação manual via UI e fecha a race condition
  entre o fetch do ContextBundle e a criação do appointment.
```

**Função:** `_load_calendar_busy_slots(user_id, window_days=30)` em `backend-crm/services/ai_orchestrator/orchestrator.py` — mesma cláusula de scoping de `routes/appointments.py::list_appointments`.

**Limitação conhecida (MVP):** a mensagem de correcção é texto fixo, não gerada pela LLM. Suporte a múltiplos profissionais por conta (planos Scale/Enterprise, ainda não implementado) exigirá revisar `_check_conflict`/`calendar_busy_slots` para incluir um `professional_id` — hoje o modelo assume um único profissional por conta.
