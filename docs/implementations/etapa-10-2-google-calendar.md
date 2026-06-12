# Google Calendar — OAuth por Utilizador + Sync Bidirecional

**Branch:** `etapa-9-planos-limites`
**Status:** Em andamento

---

## Motivação

O utilizador quer que os compromissos criados no CRM sejam automaticamente sincronizados com o Google Calendar pessoal/profissional de cada operador, e que eventos criados no Google Calendar apareçam também na agenda do CRM. Cada utilizador conecta a sua própria conta Google via OAuth2. O campo `calendar_integration` estava previsto em `pipeline-configurable-fields.md` (Etapa I) e foi abortado por falta de prioridade — é o que retomamos agora.

---

## Problemas Identificados (estado anterior)

1. **Sem OAuth Google por utilizador:** não há rota de autenticação Google, nem armazenamento de tokens por utilizador no `backend-core`.
2. **Sem push CRM → Google:** ao criar/editar/cancelar um compromisso no CRM, nenhuma chamada é feita à Google Calendar API.
3. **Sem pull Google → CRM:** eventos criados no Google não aparecem na agenda do CRM.
4. **Sem `google_event_id` nos appointments:** sem este campo, o sistema não consegue actualizar ou cancelar eventos já criados no Google.
5. **Sem bibliotecas Google no backend:** `google-auth-oauthlib` e `google-api-python-client` não estão nos `requirements.txt`.

---

## Pré-requisito externo (a cargo do utilizador)

Antes de iniciar a Fase 2, é necessário:

1. Criar um projecto no [Google Cloud Console](https://console.cloud.google.com)
2. Activar a **Google Calendar API**
3. Criar credenciais OAuth2 (tipo "Web application")
   - Authorized redirect URI: `http://localhost:8001/auth/google/calendar/callback` (dev) + URL produção
4. Obter `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`
5. Adicionar às `.env` do `backend-core`

Para produção com múltiplos utilizadores reais (além dos "Test Users" da conta do developer), o App precisa passar pelo **Google App Review** (privacy policy pública + vídeo de demo). O desenvolvimento pode correr com utilizadores de teste enquanto o review não está aprovado.

---

## Abordagem

```
Fase 2 — OAuth + CRM → Google
  Utilizador clica "Conectar Google Calendar" em MinhaConta
    → redirect para Google OAuth2 consent screen
    → callback: troca code por access_token + refresh_token
    → tokens guardados no backend-core (colunas na tabela users)
  
  Ao criar/actualizar/cancelar appointment no CRM:
    → appointments.py chama google_calendar_service.push_event() (se user tem tokens)
    → event_id do Google guardado em appointments.google_event_id
    → ao actualizar: update_event(google_event_id)
    → ao cancelar: delete_event(google_event_id)

Fase 3 — Google → CRM (pull)
  Novo endpoint GET /api/appointments/google-sync?start=&end=
    → chama google_calendar_service.list_events()
    → para cada evento Google não existente no CRM (por google_event_id):
        INSERT INTO appointments com source='google'
    → retorna lista unificada CRM + Google
  
  Na agenda (WeekView/DayView):
    → eventos com source='google' têm badge visual distinto
    → não é possível editar eventos source='google' no CRM (somente-leitura)
```

---

## Plano de Implementação

### Fase 2 — OAuth por utilizador + push CRM → Google

**Objetivo:** utilizador conecta a sua conta Google; todos os appointments criados no CRM são automaticamente criados/actualizados/cancelados no Google Calendar.

| Arquivo | O que muda |
|---|---|
| `backend-core/requirements.txt` | Adicionar `google-auth-oauthlib`, `google-api-python-client` |
| `backend-core/.env` | Adicionar `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` |
| `backend-core/app/db.py` | 4 `ensure_column()` na tabela `users`: `google_access_token`, `google_refresh_token`, `google_token_expiry`, `google_calendar_id` |
| `backend-core/app/api/auth_google.py` | Novo router: `GET /auth/google/calendar` (start OAuth), `GET /auth/google/calendar/callback` (exchange + save), `DELETE /auth/google/calendar` (desconectar) |
| `backend-core/app/main.py` | Incluir router `auth_google` |
| `backend-core/app/api/users.py` | Incluir `google_calendar_connected: bool` no `/users/me` |
| `backend-crm/services/google_calendar_service.py` | Novo serviço: `push_event`, `update_event`, `delete_event` — autentica via tokens do core (chamada server-to-server `CORE_SERVICE_TOKEN`) |
| `backend-crm/database/` (schema em `db.py`) | `ensure_column("appointments", "google_event_id", "TEXT")` + `ensure_column("appointments", "source", "TEXT DEFAULT 'crm'")` |
| `backend-crm/routes/appointments.py` | Chamar `google_calendar_service` no `create_appointment`, `update_appointment`, `delete_appointment` — fail silently (não bloquear se Google falhar) |
| `frontend-crm/src/pages/MinhaConta.tsx` | Secção "Google Calendar" — botão "Conectar" / estado "Conectado como X@gmail.com" / botão "Desconectar" |
| `frontend-crm/src/services/api.ts` | Endpoints: `getGoogleCalendarStatus()`, `disconnectGoogleCalendar()` + redirect URL para connect |

---

### Fase 3 — Pull Google → CRM (sync bidirecional)

**Objetivo:** eventos criados no Google Calendar do utilizador aparecem na agenda do CRM como compromissos somente-leitura, marcados como "Google".

**Dependência:** Fase 2 implementada e validada.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/google_calendar_service.py` | Adicionar `list_events(user_id, time_min, time_max)` |
| `backend-crm/routes/appointments.py` | Novo endpoint `POST /api/appointments/google-sync` — importa eventos Google para o período solicitado (upsert por `google_event_id`) |
| `frontend-crm/src/pages/Agenda.tsx` | Botão "Sincronizar Google" que chama o endpoint de sync e actualiza a lista |
| `frontend-crm/src/components/WeekView.tsx` | Badge visual "Google" em eventos com `source === 'google'`; bloquear clique de edição nesses eventos |
| `frontend-crm/src/components/DayView.tsx` | Mesmo tratamento que WeekView |
| `frontend-crm/src/types/crm.ts` | Adicionar `source: 'crm' \| 'google'` e `google_event_id?: string` ao tipo `Appointment` |

---

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f50a158` | `backend-core/app/config.py` — vars Google OAuth2 |
| 2 | `ebe99e7` | OAuth backend-core (auth_google.py, db.py, main.py, __init__.py) + serviço push backend-crm (google_calendar_service.py, appointments.py, database.py) + frontend (MinhaConta, api.ts, types/crm.ts, api-client.ts) |
| 3 | `39cf566` | Correcção de 3 bugs: push/update/delete Google adicionados a routes/leads.py (rota primária do frontend); guard end_at opcional em routes/appointments.py; google_event_id + source adicionados a AppointmentOut |

**Bugs corrigidos no commit 3:**
- **CRÍTICO** — gcal_push/update/delete estavam apenas em `routes/appointments.py`; o frontend usa `routes/leads.py` → push nunca disparava
- `payload.end_at.isoformat()` crashava com AttributeError quando `end_at=None` (linhas 160 e 198 de `routes/appointments.py`)
- `AppointmentOut` em `models.py` não expunha `google_event_id` e `source` (necessários para Fase 3)

**Notas de implementação (divergências do plano):**
- `requirements.txt` — **sem alteração**: usamos `httpx` (já instalado) para todas as chamadas Google em vez das libs `google-auth-oauthlib`/`google-api-python-client`. Zero novas dependências.
- Tabela `users` recebe **5 colunas** (planeadas 4): adicionado `google_email` para mostrar a conta conectada na UI.
- OAuth usa **HMAC-SHA256 signed state** (sem sessão server-side): o `user_id` é codificado no parâmetro `state` com TTL de 10 min.
- Adicionados **2 endpoints service-to-service** (`GET/PUT /auth/google/tokens/{user_id}`) para o `backend-crm` ler/actualizar tokens do `backend-core`.
- `source` e `google_event_id` em `frontend-crm/src/types/crm.ts` adiantados da Fase 3.

---

## Checks de Validação

### Fase 2

#### Cenário F2-1 — Conectar conta Google

- [x] Clicar "Conectar Google Calendar" em MinhaConta redireciona para a consent screen do Google
- [x] Após autorizar, regressa ao CRM com a conta conectada ("Conectado como X@gmail.com")
- [x] Botão "Desconectar" limpa os tokens; status volta a "Não conectado"

#### Cenário F2-2 — Push CRM → Google

- [ ] Criar um compromisso no CRM → evento aparece no Google Calendar do utilizador com título, data, hora e localização correctos
- [ ] Actualizar o horário do compromisso no CRM → evento no Google é actualizado
- [ ] Cancelar o compromisso no CRM → evento no Google é removido ou marcado como cancelado
- [ ] Se o utilizador não tem conta Google conectada: criar compromisso funciona normalmente sem erro

#### Cenário F2-3 — Resiliência

- [ ] Criar compromisso quando o Google está inacessível: o appointment é criado no CRM normalmente; erro Google é logado mas não bloqueia o utilizador

---

### Fase 3

#### Cenário F3-1 — Sync Google → CRM

- [ ] Clicar "Sincronizar Google" na agenda → eventos do Google Calendar do período visível aparecem na agenda
- [ ] Eventos do Google têm badge visual distinto ("Google")
- [ ] Clicar num evento do Google não abre o dialog de edição (somente-leitura)
- [ ] Sincronizar duas vezes não duplica os eventos (upsert por `google_event_id`)

#### Cenário F3-2 — Evento removido do Google

- [ ] Remover um evento do Google Calendar → na próxima sync, o evento desaparece da agenda do CRM

---

## Ajustes Possíveis Pós-Implementação

- Sync automática periódica (job a cada 5–15 min com `APScheduler`, já disponível no `backend-core`)
- Selecção de qual calendário Google usar (o utilizador pode ter múltiplos calendários)
- Embedded OAuth sem redirect manual (flow mais polido dentro do SPA)
- App Review do Google para produção com utilizadores reais ilimitados (process paralelo ao desenvolvimento)
