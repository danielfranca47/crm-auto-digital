# Google Calendar — Integração OAuth + Sync Bidirecional

Integração OAuth2 por utilizador com sincronização bidirecional entre os compromissos do CRM e o Google Calendar pessoal/profissional de cada operador.

---

## Visão geral

```
Utilizador conecta Google Calendar em MinhaConta
  → OAuth2 consent screen Google
  → backend-core confere o scope concedido (sem calendar.events → ligação recusada)
  → backend-core guarda access_token + refresh_token em users

CRM → Google (push automático)
  Criar/editar/cancelar appointment no CRM
  → google_calendar_service.push_event / update_event / delete_event
  → google_event_id guardado no appointment (para update/delete futuros)

Google → CRM (pull)
  Utilizador clica "Sincronizar Google" na agenda
  → POST /api/appointments/google-sync
  → services/google_calendar_sync.sync_user_google_events
  → google_calendar_service.list_events
  → upsert por google_event_id; cleanup de eventos removidos (só com leitura bem-sucedida)
  → appointments com source='google' aparecem na agenda como somente-leitura
```

---

## Ligação OAuth — backend-core

**Arquivo:** `backend-core/app/api/auth_google.py`

Scopes pedidos: `calendar.events` + `userinfo.email`. Como só há **um** scope além do login, a
Google não mostra caixas de seleção: mostra a página de login e depois uma página só do
calendário, aceite ou recusada por inteiro — e só pede o que ainda não foi concedido (numa
religação com o calendário já autorizado, aparece apenas "já tem algum acesso").

Se a página do calendário for recusada/fechada, a Google devolve mesmo assim um token só de
login. Por isso o callback lê o `scope` da resposta do token:

| Situação no callback | Redirect para o frontend | Tokens |
|---|---|---|
| `scope` inclui `calendar.events` | `/?google_connected=1` | guardados; `google_last_error` limpo |
| `scope` sem `calendar.events` | `/?google_error=missing_calendar_scope` | **não** guardados |
| Utilizador recusou (`error=access_denied`) | `/?google_error=denied` | — |
| Troca do code falhou | `/?google_error=exchange_failed` | — |
| State inválido / outro erro | `/?google_error=1` | — |

O log `google_calendar_connected` / `google_calendar_scope_missing` inclui o `scope` concedido.

**Último erro do Google por utilizador:** colunas `users.google_last_error` (código) e
`google_last_error_at`. Escritas pelo backend-crm via `PUT /auth/google/tokens/{user_id}/error`
(service token, `{"error": "<código>" | null}`); limpas ao ligar com sucesso e ao desligar.
`GET /auth/google/calendar/status` devolve `connected`, `email`, `last_error`, `last_error_at`.

---

## Serviço de Integração — backend-crm

**Arquivo:** `backend-crm/services/google_calendar_service.py`

`push_event` / `update_event` / `delete_event` são **fail-silent** para o CRM: nunca bloqueiam a
criação/edição de um compromisso. `list_events` **lança** `GoogleCalendarError(code)` quando a
Google falha — quem sincroniza tem de distinguir "Google vazio" de "Google inacessível".

Códigos de erro (`exc.code`; `exc.message` é o texto em português para o utilizador):

| Código | Quando | Gravado em `google_last_error` |
|---|---|---|
| `missing_calendar_scope` | 403 com `ACCESS_TOKEN_SCOPE_INSUFFICIENT` / `insufficientPermissions` | sim |
| `token_revoked` | 401 que persiste após refresh, ou refresh impossível | sim |
| `google_unavailable` | rede, timeout, 5xx, outros | não (temporário) |

Uma leitura bem-sucedida em `list_events` limpa `google_last_error`. Push/update/delete gravam o
erro quando é de um dos dois tipos acionáveis.

### Funções

| Função | Descrição |
|---|---|
| `push_event(user_id, appointment)` | Cria evento no Google; retorna `google_event_id` ou `None` |
| `update_event(user_id, google_event_id, appointment)` | Actualiza evento existente |
| `delete_event(user_id, google_event_id)` | Remove evento do Google (404/410 = sucesso) |
| `list_events(user_id, time_min, time_max, timeout=10)` | `None` sem Google ligado; `list[dict]` em sucesso; `GoogleCalendarError` em falha |

### Fluxo de autenticação

```python
_get_tokens(user_id)         # GET /auth/google/tokens/{user_id} no backend-core (x-service-token)
  → access_token, refresh_token, expiry, calendar_id

_get_valid_token(tokens)     # verifica se expiry > now + 5min
  → se expirado: POST https://oauth2.googleapis.com/token com refresh_token
  → PUT /auth/google/tokens/{user_id} no backend-core (persiste novo access_token)
  → retorna access_token válido
```

Se `_get_tokens` retornar `None` (utilizador sem Google conectado), a função retorna `None`/`[]` imediatamente.

### Retry em 401

Todas as funções fazem uma tentativa de refresh em caso de `HTTP 401`:

```python
r = httpx.post(url, headers={"Authorization": f"Bearer {token}"}, ...)
if r.status_code == 401:
    token = _refresh_token(user_id)
    r = httpx.post(url, headers={"Authorization": f"Bearer {token}"}, ...)
```

---

## Push CRM → Google

Pontos de integração no backend-crm:

| Arquivo | Momento | Acção |
|---|---|---|
| `routes/leads.py` | `POST /api/leads/{id}/appointments` | `push_event` → guarda `google_event_id` |
| `routes/leads.py` | `PATCH /api/leads/{id}/appointments/{appt_id}` | `update_event(google_event_id)` |
| `routes/leads.py` | `DELETE /api/leads/{id}/appointments/{appt_id}` | `delete_event(google_event_id)` |
| `routes/appointments.py` | Mesmas operações via rota alternativa | Mesmo padrão |

**Descrição do evento Google gerada:**
```
[Tipo] · Lead: [nome do lead]
[Descrição do appointment, se existir]
```

**Hora de fim:** se `end_at` for `None`, o evento Google usa `start_at + 1h` como padrão.

---

## Pull Google → CRM

**Endpoint:** `POST /api/appointments/google-sync?start=&end=`

Requer Bearer token (JWT do utilizador). Parâmetros `start` e `end` são ISO datetimes.

A rota é fina: chama `services/google_calendar_sync.py::sync_user_google_events(user_id, start, end)`.
Se a Google falhar, responde **409** com `{"detail": {"code", "message"}}` e **não altera nada**
na tabela (uma falha nunca esvazia a agenda importada).

**Algoritmo (`sync_user_google_events`):**

```python
google_events = list_events(user_id, start, end)   # None → sem Google, nada a fazer
                                                    # GoogleCalendarError → propaga, nada apagado

for event in google_events:
    existing = SELECT WHERE google_event_id=? AND user_id=?
    if existing:
        UPDATE title, start_at, end_at, description WHERE id=existing.id
    else:
        INSERT (user_id=?, lead_id=NULL, source='google', google_event_id=?, ...)

# Cleanup: apaga eventos Google do período que já não existem no Google
synced_ids = [e["id"] for e in google_events]
DELETE WHERE source='google' AND user_id=? AND start_at>=? AND start_at<=?
            AND google_event_id NOT IN (synced_ids)
```

Retorna todos os appointments do período para o utilizador (CRM + Google).

**Mapeamento Google Event → Appointment:**

| Campo Google | Campo appointments |
|---|---|
| `summary` (title) | `title` |
| `start.dateTime` | `start_at` |
| `end.dateTime` | `end_at` |
| `description` | `description` |
| `id` | `google_event_id` |
| — | `source = 'google'` |
| — | `type = 'meeting'` (default) |
| — | `status = 'pending'` |

---

## Variáveis de ambiente — backend-crm

| Variável | Descrição |
|---|---|
| `CORE_API_BASE` | URL do backend-core (ex.: `http://localhost:8001`) — usado para ler/guardar tokens Google |
| `CORE_SERVICE_TOKEN` | Token server-to-server para `GET/PUT /auth/google/tokens/{user_id}` |

---

## MinhaConta — frontend-crm

`frontend-crm/src/pages/MinhaConta.tsx` — secção "Google Calendar":

É o **único** sítio onde a conta liga o Google. Estado lido via `GET /auth/google/calendar/status`.

- **Não conectado:** botão "Conectar Google Calendar" → `GET /auth/google/calendar/url` (Bearer) → redirect para a Google
- **Conectado:** "Conectado" + email + botão "Desconectar" → `DELETE /auth/google/calendar`
- **Volta do callback:** `App.tsx::GoogleAuthHandler` reencaminha `/?google_connected=1` e
  `/?google_error=<código>` para `/minha-conta`. Um erro fica num aviso fixo (não toast) com texto
  por código (`missing_calendar_scope`, `denied`, genérico) e botão "Ligar de novo".
- **`last_error` preenchido** (conta ligada mas a Google recusa): aviso amarelo com o motivo e
  botão "Voltar a ligar".

**Agenda** (`pages/Agenda.tsx`): erro do "Sincronizar Google" mostra `detail.message` do 409.

**AI Profile → Calendário** (`components/agente/CamadaApresentacao.tsx`): a opção
`calendar_integration = google_calendar` só fica gravada no perfil — não liga a conta. Ao escolhê-la,
o modal mostra o estado da ligação (`/status`) e, se não estiver ligada ou tiver `last_error`, um
link "Ligar em Minha Conta".
