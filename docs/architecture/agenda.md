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
  endTime: endAt.toISOString(),  // calculado a partir do campo "Hora fim" do form (mín. 1h se ficar <= startAt)
}
```

**Fallback de lead:** quando não há `fixedLeadId` e nenhum lead está seleccionado, selecciona automaticamente o primeiro da lista ordenada alfabeticamente.

---

## Fuso Horário na Agenda

Todo horário de compromisso é exibido e editado no fuso configurado no AI Profile do
negócio (`ai_profile.timezone`), não no fuso do navegador de quem está a ver a tela —
resolvido por `useBusinessTimezone()` (`src/hooks/useBusinessTimezone.ts`), que expõe
`businessTimezone` (do AI Profile, fallback para o fuso do navegador quando não
configurado) e `browserTimezone`. Utilitários de conversão/formatação em
`src/lib/timezone.ts` (`formatInBusinessTimezone`, `toBusinessTimezoneDate`,
`fromBusinessTimezoneDate`, `getTimezoneCityLabel`) — usados nas 3 vistas, no Dashboard
("Reuniões de Hoje"), no card do lead e na Prospecção.

**Quando o fuso do negócio difere do fuso do navegador:**
- **Listagens** (Agenda modo lista/calendário, Dashboard, card do lead, Prospecção) —
  `AppointmentTimeLabel` (`src/components/AppointmentTimeLabel.tsx`) mostra os dois
  horários lado a lado com o nome da cidade (ex.: "17:00 (São Paulo) · 21:00 (Lisboa)");
  com fusos iguais mostra só um horário, sem rótulo de cidade.
- **Grade visual (WeekView/DayView)** — posicionamento dos eventos e a agulha de "hora
  actual" seguem `useAgendaTimezoneMode()` (`src/hooks/useAgendaTimezoneMode.ts`,
  persistido em `localStorage` como `agenda_grid_timezone_mode`), com um botão de
  alternância visível só quando há mismatch. Default `"browser"` — grade no fuso de
  quem está a ver a tela; alternar para `"business"` mostra no fuso do negócio.
- **`ScheduleAppointmentDialog`** — grava sempre no fuso do negócio (decisão mantida:
  os campos não são editáveis nos dois fusos), mas exibe uma legenda abaixo dos campos
  Início/Fim com a conversão para o fuso do navegador quando há mismatch
  (`combineDateTimeInTimezone`, calculado via `useMemo`).

**Limitação conhecida:** os intervalos de busca (`start`/`end` enviados ao backend por
`Dashboard.tsx`, `WeekView.tsx`, `DayView.tsx`, `ScheduleView.tsx`) usam os limites de
dia/semana/mês no fuso do navegador, não no fuso do negócio — só afecta compromissos
muito próximos da meia-noite quando a diferença de fuso é grande (podem aparecer no dia
errado, ou faltar na lista de "hoje").

---

## API de Compromissos

### Endpoints usados pelo frontend

| Endpoint | Método | Usado por |
|---|---|---|
| `GET /api/appointments?start=&end=` | GET | WeekView, DayView — filtra pelo intervalo da vista; requer JWT (filtra por `user_id`) |
| `GET /api/appointments/lead/{id}` | GET | ScheduleView — lista por lead; requer JWT (verifica que o lead pertence ao `user_id` do token, 404 caso contrário) |
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
    source: str                      # "crm" (default) | "google" | "playground"
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

**Datas malformadas:** `normalizeAppointment()` nunca lança excepção mesmo se `start`/`end` vier num formato não conversível (`toIsoOrEmpty()` devolve `""` em vez de chamar `.toISOString()` sobre uma `Date` inválida). `useAppointments()` e `useLeadAppointments()` filtram (`hasValidStart`) qualquer appointment cujo `startTime` não produza uma `Date` válida antes de devolver a lista — um appointment sem data reconhecível é descartado silenciosamente na origem, nunca chega a `ScheduleView`/`WeekView`/`DayView` (que chamam `format()` sem protecção contra `Date` inválida).

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
| `source` | TEXT | `crm` (default) \| `google` \| `playground` |
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

## Side-effects de criar/editar/cancelar um compromisso (backend)

**Ao criar** (`POST /api/leads/{id}/appointments` ou via `routes/appointments.py`), o backend:

1. Valida que não há conflito de horário **para o profissional inteiro** (`_check_conflict`) — não apenas para o mesmo lead. Existem duas implementações paralelas e independentes (uma em cada arquivo, mesma regra): `routes/leads.py::_check_conflict` (usa `current_user.id` diretamente — endpoint já autenticado) e `routes/appointments.py::_check_conflict` (resolve o `user_id` via `_resolve_owner_user_id()`, a partir do `lead_id` ou do `user_id` próprio em appointments importados do Google sem lead). Ambas bloqueiam com `409` se outro appointment do mesmo `user_id` (qualquer lead, ou evento Google) sobrepuser o intervalo — esta é a defesa real contra conflito, pois roda dentro da transacção SQLite no momento exacto do INSERT/UPDATE.
2. Agenda jobs de lembrete (`whatsapp.appointment.reminder`, `jobs_service.schedule_appointment_reminder_jobs()`) com offsets configuráveis por `appointment_reminder_offsets` do AI Profile (default por `template_key`) — cada job recebe um `reminder_kind` (`"early"`/`"final"`, ver secção dedicada abaixo)
3. Agenda job de briefing (`whatsapp.appointment.briefing`, `briefing_service.schedule_briefing_job_for_appointment()`) se `briefing_enabled` não for `False`
4. Faz push para Google Calendar se o utilizador tiver tokens OAuth2 válidos (`google_calendar_service.push_event`)

`google_event_id` é persistido na linha do appointment quando o push é bem-sucedido. Os passos 2–4 são pulados para appointments com `source="playground"`.

**Ao cancelar** (`POST /{id}/cancel`, ou `DELETE /{id}`, ou o equivalente em `routes/leads.py`):
1. `jobs_service.cancel_pending_appointment_jobs(conn, appointment_id)` — cancela os jobs `pending` de lembrete/briefing deste appointment. Não existe status `'cancelled'` no `CHECK` constraint da tabela `jobs` (só `pending`/`in_progress`/`completed`/`failed`) — a função usa `status='completed'` com `result={"skipped": true, ...}` em vez de um valor fora do enum.
2. Remove o evento do Google Calendar (`gcal_delete`, fail-silent) se `google_event_id` estiver presente.

**Ao reagendar** (`PUT /{id}` ou `PATCH` equivalente em `routes/leads.py`, quando `start_at` muda de fato): cancela os jobs de lembrete/briefing antigos (mesmo mecanismo do cancelamento) e cria novos para o novo horário; sincroniza o evento no Google Calendar via `gcal_update` (fail-silent).

Estas três funções (`cancel_pending_appointment_jobs`, `schedule_appointment_reminder_jobs`, `schedule_briefing_job_for_appointment`) vivem em `backend-crm/services/jobs_service.py`/`services/briefing_service.py` e são compartilhadas pelos dois pontos de entrada de appointment (`routes/appointments.py` e `routes/leads.py`) — garante que criar/cancelar/reagendar tem o mesmo efeito independentemente de qual rota o caller usa.

Todas as rotas de `routes/appointments.py` (`GET /lead/{id}`, `POST`, `PUT/{id}`, `DELETE/{id}`, `POST /{id}/complete`, `POST /{id}/cancel`) exigem `Depends(require_crm_access)` e verificam que o `user_id` resolvido via `_resolve_owner_user_id()` bate com o do token — `404` (não `403`) em caso de mismatch, mesmo padrão de `_require_lead_for_user()` em `routes/leads.py`. Os dois pontos de entrada são chamados directamente pelo frontend (`frontend-crm/src/services/api.ts`), então a paridade de auth entre eles não é opcional.

### Rotas internas para o backend-executors (service token)

O `backend-executors` (Playground e fluxo real via `crm_client.py`) nunca chama as rotas
públicas `/api/appointments/*` — só tem `X-Service-Token`, nunca um JWT de usuário. Três
rotas internas dedicadas em `routes/executor.py`, todas `Depends(_require_service_token)`
(mesmo padrão de `/internal/logs/meeting-scheduled`):

| Rota interna | Equivalente público | Usada por |
|---|---|---|
| `POST /api/internal/appointments` | `POST /api/leads/{id}/appointments` | `crm_client.create_lead_appointment` |
| `PUT /api/internal/appointments/{id}` | `PUT /api/appointments/{id}` | `crm_client.reschedule_appointment` |
| `POST /api/internal/appointments/{id}/cancel` | `POST /api/appointments/{id}/cancel` | `crm_client.cancel_appointment` |

A lógica de criação/atualização é compartilhada com as rotas públicas via
`_create_appointment_row`/`_update_appointment_row` (`routes/appointments.py`) — as
rotas internas resolvem o dono a partir do `lead_id` e chamam essas funções
directamente, sem checagem de JWT; as rotas públicas continuam exigindo
`require_crm_access` normalmente para usuários reais.

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
        ↓ (via runners/whatsapp.py no fluxo real, ou via playground_internal.py
           no Playground — ambos chamam handle_meeting_scheduled; ver secção
           "Playground cria appointments reais" abaixo)
```

**Agenda vazia:** quando não há nenhum compromisso na janela consultada, o bloco não é
omitido — `_busy_block` declara explicitamente "HORÁRIOS JÁ OCUPADOS: nenhum compromisso
encontrado — a agenda está livre no período consultado." em vez de virar string vazia.
Sem essa afirmação positiva, `scheduling_offer_style: confirm_exact` (ver
[`agents.md`](agents.md)) tendia a recusar horários "redondos" por cautela, mesmo com a
agenda livre.

```
backend-executors (meeting_scheduler.py + whatsapp.py)
  handle_meeting_scheduled() checa o horário confirmado pela IA contra
  calendar_busy_slots: se colidir com outro lead, NÃO cria o appointment, NÃO
  desabilita o bot, e devolve uma mensagem de correcção no tom do agente
  (gerada via _generate_conflict_message(), ver abaixo) que o runner envia ao
  lead via core_client.send_whatsapp_message(). Fora da janela de 30 dias, a
  checagem é pulada (loga o evento) e segue o comportamento normal.
        ↓
backend-crm (routes/appointments.py + routes/leads.py)
  _check_conflict (ver secção acima) é a barreira final — roda na transacção
  do INSERT, cobre também a criação manual via UI e fecha a race condition
  entre o fetch do ContextBundle e a criação do appointment.
```

**Função:** `_load_calendar_busy_slots(user_id, window_days=30)` em `backend-crm/services/ai_orchestrator/orchestrator.py` — mesma cláusula de scoping de `routes/appointments.py::list_appointments`.

### Mensagem de correcção de conflito (gerada via LLM)

`_generate_conflict_message(ai_profile, *, logger=None)` em `meeting_scheduler.py` monta um prompt curto em PT usando `tone_of_voice`/`brand_name`/`identity_mode` do AI Profile e chama `llm_service.generate_conflict_message()` (reaproveita o `_post_with_retry()` partilhado — ver `llm-architecture.md`). `handle_meeting_scheduled()` usa `_generate_conflict_message(...) or MEETING_CONFLICT_MESSAGE` — se a geração falhar por qualquer motivo (sem `LLM_API_KEY`, erro de rede, timeout, resposta vazia), cai no texto fixo `MEETING_CONFLICT_MESSAGE` ("Peço desculpa, esse horário acabou de ficar indisponível...") definido em `meeting_scheduler.py`.

**Limitação conhecida (MVP):** suporte a múltiplos profissionais por conta (planos Scale/Enterprise, ainda não implementado) exigirá revisar `_check_conflict`/`calendar_busy_slots` para incluir um `professional_id` — hoje o modelo assume um único profissional por conta.

### Playground cria appointments reais (tag `"[Playground]"`)

Quando a IA confirma um agendamento dentro de uma sessão do Playground, `backend-executors/app/api/playground_internal.py` chama `meeting_scheduler.handle_meeting_scheduled(..., is_playground=True)` — o mesmo mecanismo do fluxo real, incluindo a checagem de conflito contra `calendar_busy_slots` — mas com:

- `title = "[Playground] Reunião agendada"`, `description = "Reunião simulada no Playground."`
- `source = "playground"` no INSERT de `appointments`
- reminders (`whatsapp.appointment.reminder`), briefing e push para o Google Calendar real do utilizador são pulados — `routes/appointments.py::create_appointment` só dispara esses side-effects quando `source != "playground"`

Conflito de horário é respeitado pela mesma barreira `_check_conflict`: se o horário já estiver ocupado, o appointment não é criado e uma mensagem de correcção é anexada aos `system_actions`/`auto_items` da resposta do Playground, em vez de ser enviada via WhatsApp.

`routes/playground.py::_reset_sandbox_lead` apaga os appointments do lead sandbox antes do reset de mensagens — evita acumular compromissos `[Playground]` na Agenda real entre sessões de teste repetidas no mesmo lead.

O fluxo real (WhatsApp) chama `handle_meeting_scheduled(...)` sem `is_playground` (default `False`) — side-effects e comportamento de conflito inalterados, mas o título passa por geração via IA (ver secção seguinte) em vez do texto fixo usado no Playground.

---

## Duração da sessão: fixa vs. por serviço

Todo appointment criado ou reagendado via IA tem uma duração resolvida por
`meeting_scheduler.py` segundo uma cadeia de prioridade — nunca mais um valor
fixo de 30 min hardcoded:

```
1. signal.duration_minutes        ← extraído de signals_structured.meeting_duration_minutes
                                     (filha de agendamento, só quando a Tabela de
                                     Serviços e Preços identifica a linha do lead)
2. default_session_duration_minutes  ← AI Profile (ver agents.md), padrão 30
3. 30                              ← fallback final, se o AI Profile vier vazio
```

**Criação** (`handle_meeting_scheduled()`): `duration_minutes = signal.duration_minutes
or _resolve_default_duration_minutes(ai_profile)`.

**Reagendamento** (`handle_meeting_cancel_or_reschedule()`): a duração original do
appointment é preservada, **não** recalculada a partir do sinal da IA — remarcar um
horário não deveria trocar silenciosamente a duração combinada. `duration_minutes =
_original_duration_minutes(original_slot) or _resolve_default_duration_minutes(ai_profile)`,
onde `original_slot` vem de `context["calendar_busy_slots"]` filtrado por `lead_id`
(mesma limitação de janela de 30 dias) e `_original_duration_minutes()` calcula
`end_at - start_at` do appointment encontrado.

### Múltiplos serviços com durações diferentes (Tabela de Serviços e Preços)

Quando o profissional oferece sessões de duração variável (ex.: 30/60/90 min por
tipo de serviço), ele cadastra cada linha em **Base de Conhecimento → "Tabela de
Serviços e Preços"** (categoria `service_pricing_table`, texto livre — uma linha por
serviço, formato `Nome — duração: preço`, ex.: `Sessão avulsa - 30min: R$120`).
Disponível em qualquer `appointment_mode` (não exclusiva do modo comercial).

`_build_child_prompt_agendamento()` (`decision_engine.py`) lê
`context["knowledge_items"]["service_pricing_table"]` (mesma chave já consumida pela
filha de qualificação no modo comercial) e injeta um bloco "SERVIÇOS E DURAÇÕES
DISPONÍVEIS" instruindo a IA a identificar a qual linha o lead se refere e preencher
`signals_structured.meeting_duration_minutes` com a duração (minutos) dessa linha.
**Regra de ambiguidade:** se houver mais de uma linha e não for possível saber qual o
lead quer, a IA deve perguntar antes de confirmar — nunca assume uma duração quando
há ambiguidade real. Sem tabela cadastrada, o bloco não é injetado e a duração cai
direto no `default_session_duration_minutes` da conta.

**Onde configurar:** "Configurar Agente → Apresentação → Disponibilidade de horários
→ Duração da sessão" (duração padrão, slider 15–180 min) e "Configurar Agente →
Base de Conhecimento → Tabela de Serviços e Preços" (durações por serviço).

---

## Título do compromisso gerado por IA (fluxo real)

No fluxo real (não-Playground), `handle_meeting_scheduled()` chama
`meeting_scheduler.generate_appointment_title(ai_profile, *, logger=None)` em vez
de gravar sempre `"Reunião agendada"`. Mesmo padrão de `_generate_conflict_message`:
prompt curto usando `niche`/`offer_description` do AI Profile, pedindo um título de
2-4 palavras adequado ao nicho. Nunca propaga excepção — qualquer falha cai no
fallback `meeting_scheduler.default_appointment_title(ai_profile)`, o agendamento
nunca falha por causa disso.

**Palavra-base obrigatória por arquétipo (`template_key`):** `_TITLE_BASE_WORD_BY_TEMPLATE`
em `meeting_scheduler.py` fixa a palavra que o título tem que conter, independente
do nicho — `sdr_padrao` (Agente 01 · SDR de Alto Ticket) → "Reunião";
`hybrid_scheduler` (Agente 03 · Híbrido Agendador) → "Sessão". O prompt instrui a IA
a usar essa palavra literalmente (podendo complementar com termo do nicho, ex.:
"Sessão de Massagem", "Reunião Comercial"); se a resposta da IA não contiver a
palavra exigida (ou a IA falhar), o título cai em `default_appointment_title()`
(`"{palavra} agendada"`, função pública — também usada em `whatsapp.py`, ver secção
seguinte) — garante o vocabulário certo por tipo de negócio mesmo quando a IA não
segue a instrução. `template_key` sem entrada no mapa (ex. `closer_agressivo`)
mantém o comportamento livre, escolhido pela IA conforme o nicho, com fallback
genérico `"Reunião agendada"`.

O Playground continua a usar o título fixo `"[Playground] Reunião agendada"`, sem
chamar IA extra (sem custo/latência em testes internos).

Este título é gravado em `appointments.title` e lido sem transformação por todos os
consumidores: Dossiê pré-reunião (`briefing_service.py`), Kanban, `ScheduleAppointmentDialog`
e o próprio lembrete de reunião (secção seguinte) — corrigir na origem beneficia
todos de uma vez.

---

## Lembrete de reunião gerado por IA

O job `whatsapp.appointment.reminder` (`app/runners/whatsapp.py::_execute_appointment_reminder_pipeline`)
gera o texto do lembrete via `meeting_scheduler.generate_appointment_reminder_message(
ai_profile, lead, *, appointment_title, time_str, reminder_kind, logger)` em vez de um
template fixo. O prompt usa `tone_of_voice`/`brand_name`/`identity_mode`/`niche`/
`offer_description` do AI Profile; troca o título genérico por um termo do nicho
quando aplicável; nunca inventa o nome do lead quando ausente (`contactName`/`name`
vazios → instrução explícita de não usar placeholder genérico tipo "Cliente").

**Tom early vs. final:** `jobs_service.schedule_appointment_reminder_jobs()` calcula
um `reminder_kind` por offset configurado — `"final"` para o offset com menor valor
absoluto (o mais próximo do compromisso, ex. `-120` = 2h antes), `"early"` para os
demais (ex. `-1440` = 24h antes) — e grava no payload do job. Não assume exactamente
2 offsets configurados. O prompt usa esse valor para diferenciar o tom: `"early"`
pede um aviso leve (convite a confirmar ou avisar com antecedência se for remarcar);
`"final"` pede confirmação de forma mais directa (não há mais tempo de remarcar).

**Retry com backoff próprio antes do fallback fixo:** se a geração via IA falhar,
o job não cai direto no template fixo — `whatsapp.appointment.reminder` tem um
override do retry/backoff global de jobs (`JOB_MAX_ATTEMPTS=3`,
`JOB_BACKOFF_SECONDS={1:60,2:180}`), definido em `jobs_service.py`:

```python
APPOINTMENT_REMINDER_MAX_ATTEMPTS = 5
APPOINTMENT_REMINDER_BACKOFF_SECONDS = {1: 60, 2: 180, 3: 900, 4: 60}  # 15min antes da penúltima tentativa
```

`_JOB_TYPE_MAX_ATTEMPTS`/`_JOB_TYPE_BACKOFF_SECONDS` mapeiam `TYPE_WHATSAPP_APPOINTMENT_REMINDER`
para estes valores; `max_attempts_for(job_type)`/`backoff_schedule_for(job_type)` são
consultados em `routes/executor.py` (`fail_job_internal`, `get_next_job_internal`) em vez
das constantes globais — outros tipos de job continuam no default global, inalterado.

Na 5ª (última) tentativa — ou quando `attempt is None` — `_execute_appointment_reminder_pipeline`
não chama mais `_fail_job`: usa o template fixo e **envia o lembrete de qualquer
forma** — a garantia de que o lead nunca deixa de receber o lembrete nunca é
quebrada, mesmo que a IA falhe em todas as tentativas. O template evita repetir a
palavra "agendada" quando `appointment_title` já termina com ela (ex. o fallback
genérico "Reunião agendada"): `appointment_phrase = title if title termina em
"agendada"/"agendado" senão f"{title} agendada"`, usado em
`f"... Lembrando da sua {appointment_phrase} para {time_str}. Qualquer dúvida,
estou por aqui. Até lá! 😊"`.

**De onde vem o `title` usado nesse template fixo:** `title = payload.get("appointment_title")
or meeting_scheduler.default_appointment_title(ai_profile)` — na prática quase sempre vem do
título real do compromisso (gravado na criação, já respeitando a palavra-base por
`template_key` da secção anterior), então o template fixo herda automaticamente o
vocabulário certo (SDR → "Reunião…", Híbrido Agendador → "Sessão…"). Só cai no
`default_appointment_title(ai_profile)` no caso raro de `appointment_title` vir
vazio do payload do job — e mesmo nesse caso o resultado já é agent-aware
("Reunião agendada" / "Sessão agendada"), nunca um literal genérico fixo
independente do tipo de agente.

---

## Cancelamento e reagendamento via IA

Quando o lead pede para cancelar ou remarcar uma reunião já confirmada (`bot_disabled_reason="meeting_scheduled"`, ver [`agents.md`](agents.md) e [`llm-architecture.md`](llm-architecture.md)), a ação real no appointment é aplicada por `meeting_scheduler.handle_meeting_cancel_or_reschedule()` (`backend-executors/app/services/meeting_scheduler.py`), chamada ao lado de `handle_meeting_scheduled()` tanto em `app/runners/whatsapp.py` (fluxo real) quanto em `app/api/playground_internal.py` (Playground).

**Localização do appointment:** filtra `context["calendar_busy_slots"]` pelo `lead_id`, ordena por `start_at` e usa o mais próximo. Mesma limitação de janela do `calendar_busy_slots` (30 dias) — reuniões mais distantes não são encontradas.

| Sinal | Ação | Efeito no bot |
|---|---|---|
| `meeting_cancel_requested` | `crm_client.cancel_appointment(appointment_id)` → `POST /api/appointments/{id}/cancel` | `set_lead_bot_disabled(lead_id, False)` — bot reactivado, volta ao fluxo normal |
| `meeting_reschedule_requested` + `meeting_datetime_candidate` válido | `crm_client.reschedule_appointment(appointment_id, start_at=..., end_at=...)` → `PUT /api/appointments/{id}` (`end_at` preserva a duração original do appointment — ver "Duração da sessão" acima) | Bot permanece desactivado, `bot_disabled_reason` inalterado — continua em modo de gestão pós-confirmação |

Ambas as chamadas passam por `routes/appointments.py` (não pelas rotas de `routes/leads.py`), aplicando automaticamente a limpeza/recriação de jobs e a sincronização com o Google Calendar descritas na secção anterior.

**Conflito de horário no reagendamento:** se o novo horário colidir com outro appointment do mesmo profissional (`409` de `_check_conflict`), o appointment original **não é alterado** — a função devolve uma mensagem de correcção (mesmo padrão de `_generate_conflict_message()`/`MEETING_CONFLICT_MESSAGE` usado em `handle_meeting_scheduled()`) para o caller enviar ao lead.

**Sem sinal de cancelamento/reagendamento:** `handle_meeting_cancel_or_reschedule()` é no-op — não faz nenhuma chamada.
