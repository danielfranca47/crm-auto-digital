# Google Calendar — Integração OAuth + Sync Bidirecional

Integração OAuth2 por utilizador com sincronização bidirecional entre os compromissos do CRM e o Google Calendar pessoal/profissional de cada operador.

---

## Visão geral

```
Utilizador conecta Google Calendar em MinhaConta
  → OAuth2 consent screen Google
  → backend-core guarda access_token + refresh_token em users

CRM → Google (push automático)
  Criar/editar/cancelar appointment no CRM
  → google_calendar_service.push_event / update_event / delete_event
  → google_event_id guardado no appointment (para update/delete futuros)

Google → CRM (pull manual)
  Utilizador clica "Sincronizar Google" na agenda
  → POST /api/appointments/google-sync
  → google_calendar_service.list_events
  → upsert por google_event_id; cleanup de eventos removidos
  → appointments com source='google' aparecem na agenda como somente-leitura
```

---

## Serviço de Integração — backend-crm

**Arquivo:** `backend-crm/services/google_calendar_service.py`

Todas as funções são **fail-silent**: qualquer erro (rede, token inválido, quota) é capturado, logado e a função retorna `None` ou `[]`. Nunca levanta excepção para o caller.

### Funções

| Função | Descrição |
|---|---|
| `push_event(user_id, title, start, end, description)` | Cria evento no Google; retorna `google_event_id` ou `None` |
| `update_event(user_id, google_event_id, title, start, end, description)` | Actualiza evento existente; retorna `True` ou `None` |
| `delete_event(user_id, google_event_id)` | Remove evento do Google; retorna `True` ou `None` |
| `list_events(user_id, time_min, time_max)` | Lista eventos do período; retorna `list[dict]` ou `[]` |

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

**Algoritmo:**

```python
google_events = list_events(user_id, start, end)

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

- **Não conectado:** botão "Conectar Google Calendar" → redirect para `GET /auth/google/calendar` (com Bearer token no header via janela nova / redirect)
- **Conectado:** texto "Conectado como [google_email]" + botão "Desconectar" → `DELETE /auth/google/calendar`
- Estado lido via `GET /users/me` (campo `google_calendar_connected: bool` + `google_email: str | null`)
