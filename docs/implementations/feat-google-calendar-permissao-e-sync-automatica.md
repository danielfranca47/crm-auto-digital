# Google Calendar — exigir a permissão do calendário e agenda do Google visível ao agente sem clique

**Branch:** `worktree-feat+google-calendar-permissao-e-sync-automatica`
**Status:** Em andamento
**Autonomia:** manual

Origem: `docs/plans/google-calendar-melhorias-pos-etapa-10-2.md`, itens M4 e M1 (promovidos em 26/10/2026).

---

## Motivação

Conta Sensi Vitae (prod `user_id` 4). Na 1ª ligação ao Google o CRM mostrou "Conectado", mas a
Google só tinha concedido o login (`email`/`openid`), sem `calendar.events`. O agente não via a
agenda, as marcações não iam para o Google e nada avisava: `list_events` dava 403 e
`POST /api/appointments/google-sync` devolvia 200.

Além disso, os eventos do Google só entram na tabela `appointments` quando alguém clica
"Sincronizar Google" — e o agente agendador só vê como ocupado o que está nessa tabela, por isso
pode oferecer um horário que só está ocupado no Google.

### O que aconteceu na ligação (logs do backend-core em produção)

| Hora (UTC) | Ligação | `scope` devolvido pela Google |
|---|---|---|
| 25/10 20:28 | 1ª | `email userinfo.email openid` — sem calendário (20 s na Google) |
| 25/10 21:09 | 2ª (depois de Desconectar) | inclui `calendar.events` |
| 26/10 08:10 e 08:12 | 3ª e 4ª (a 4ª está no vídeo) | inclui `calendar.events` |

A Google só pede o que ainda não foi concedido: na religação do vídeo o calendário já estava
autorizado, por isso só apareceu "já tem algum acesso (3 serviços)". Como pedimos um único scope
além do login, não há caixas de seleção: há uma página de login e outra só do calendário, que se
aceita ou recusa por inteiro. Na 1ª ligação essa página foi recusada/fechada e a Google devolveu
mesmo assim um token só de login — que o nosso callback aceitou.

Os 2 "botões": a ligação real é só em Minha Conta. No AI Profile, "Calendário → Google Calendar"
só grava `calendar_integration` no perfil (nenhum backend lê esse campo) — não liga nada.

---

## Problemas Identificados (estado anterior)

1. **Ligação aceite sem calendário:** `backend-core/app/api/auth_google.py::oauth_callback` guarda os
   tokens sem ler o `scope` devolvido; `/calendar/status` diz `connected` só por existir token.
2. **Falhas escondidas:** `backend-crm/services/google_calendar_service.py` é fail-silent —
   `list_events` devolve `[]` em erro; push/update/delete só fazem log.
3. **Sync com erro apaga a agenda importada:** `routes/appointments.py::google_sync` trata o `[]` de
   erro como "o Google está vazio" e apaga todos os `source='google'` do período, respondendo 200.
4. **Agente cego ao Google:** `orchestrator.py::_load_calendar_busy_slots` só lê `appointments`;
   eventos do Google só lá chegam com o clique manual.
5. **AI Profile engana:** escolher "Google Calendar" no AI Profile não mostra se a conta está ligada.

---

## Abordagem

```
Ligação (backend-core callback)
  scope sem calendar.events → não guarda tokens → /minha-conta?google_error=missing_calendar_scope
  scope ok                  → guarda tokens, limpa google_last_error

Leitura do Google (backend-crm)
  list_events falha → GoogleCalendarError(code) → reporta ao core (google_last_error)
  sync_user_google_events: erro → não apaga nada, propaga
  POST /google-sync: erro → 409 {code, message}

Agente (M1)
  enrich_context_bundle (agenda) → _load_calendar_busy_slots
    → sync_user_google_events(now, now+30d) no máx. 1x / 3 min por utilizador
    → falha: segue só com a tabela (nunca bloqueia a resposta)
    → lê appointments (já com os eventos do Google)
```

---

## Plano de Implementação

### Fase 1 — Backend: não aceitar ligação sem calendário e não esconder falhas

**Objetivo:** o backend recusa ligações sem `calendar.events`, guarda e expõe o último erro do
Google, e a sync deixa de apagar eventos quando a Google falha.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/auth_google.py` | Callback confere `scope`; códigos de erro no redirect; log do scope; `status` devolve `last_error`; novo `PUT /auth/google/tokens/{user_id}/error` |
| `backend-core/app/db.py` | `ensure_google_calendar_columns`: `google_last_error`, `google_last_error_at` |
| `backend-crm/services/google_calendar_service.py` | `GoogleCalendarError`; `list_events` lança em falha; `report_error`/limpeza no core |
| `backend-crm/services/google_calendar_sync.py` (novo) | `sync_user_google_events` (upsert + limpeza, só com leitura bem-sucedida) |
| `backend-crm/routes/appointments.py` | `google-sync` fino: chama o serviço; 409 em erro |
| `backend-crm/tests/test_google_calendar_sync.py` (novo) | falha → não apaga; sucesso → upsert + limpeza; erro → 409 |
| `backend-core/tests/test_google_oauth_scope.py` (novo) | callback sem/com `calendar.events`, recusa do utilizador |
| `docs/architecture/google-calendar.md` | Ligação OAuth, códigos de erro, pull |

Decisão: só `missing_calendar_scope` e `token_revoked` ficam gravados em `google_last_error` —
falhas temporárias da Google (`google_unavailable`) não, para não mostrar um aviso que se resolve sozinho.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `de6cd34` | Callback recusa ligação sem calendário; último erro do Google no core; `list_events` com exceção; sync extraída e sem apagar em falha; 409 na rota |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a Google só desse acesso ao login, o CRM dizia "Conectado" na mesma; quando a Google
falhava, o "Sincronizar Google" dizia que correu bem e ainda apagava da agenda os eventos já importados.
**Agora:** uma ligação sem acesso ao calendário é recusada (o CRM não guarda nada e volta com o motivo);
quando a Google falha, a agenda importada fica intacta e o CRM responde com o erro e uma mensagem em
português. O erro fica guardado na conta para o ecrã o mostrar (o ecrã vem na Fase 2).
**Para validar:** Cenários P1 e P2 (testes automáticos — validados).

### Fase 2 — Frontend: mostrar o erro ao utilizador

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/App.tsx` | `GoogleAuthHandler` passa o código de erro |
| `frontend-crm/src/pages/MinhaConta.tsx` | Aviso fixo para `missing_calendar_scope`; aviso de `last_error` com "Voltar a ligar" |
| `frontend-crm/src/pages/Agenda.tsx` | Mostra a mensagem do backend no erro do sync |
| `frontend-crm/src/components/agente/CamadaApresentacao.tsx` | Estado da ligação ao escolher Google Calendar + link para Minha Conta |
| `frontend-crm/src/services/api.ts` | Tipo do `getStatus` com `last_error` |

### Fase 3 — Agenda do Google visível ao agente sem clique (M1)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_load_calendar_busy_slots` sincroniza antes (cache 3 min, nunca bloqueia) |
| `frontend-crm/src/pages/Agenda.tsx` | Sync automático do mês ao abrir |
| `docs/architecture/google-calendar.md`, `docs/architecture/playground-parity.md` | Estado atual |
| `docs/plans/google-calendar-melhorias-pos-etapa-10-2.md` | Retirar M1 e M4 |

---

## Checks de Validação

### Cenário P1 — Ligação sem calendário é recusada (testes automáticos)
- [x] Callback com `scope` sem `calendar.events` → redirect `google_error=missing_calendar_scope`, tokens não gravados
- [x] Callback com `calendar.events` → tokens gravados e `google_last_error` limpo
- **Validado em:** 26/10/2026 — `backend-core/tests/test_google_oauth_scope.py` (3 testes) verde

### Cenário P2 — Sync com erro não apaga a agenda (testes automáticos)
- [x] `list_events` com 403 de scope → `google-sync` responde 409 `missing_calendar_scope`, eventos `source='google'` intactos
- [x] `list_events` bem-sucedido → upsert + limpeza como antes
- **Validado em:** 26/10/2026 — `backend-crm/tests/test_google_calendar_sync.py` (10 testes) + suites existentes de Google/appointments/busy slots (68 verdes)

### Cenário P3 — Minha Conta e Agenda mostram o erro (browser, local)
- [ ] `/minha-conta?google_error=missing_calendar_scope` → aviso fixo com "Ligar de novo"
- [ ] Conta ligada com `google_last_error` preenchido → aviso amarelo em Minha Conta
- [ ] "Sincronizar Google" com erro → toast com a mensagem do backend
- [ ] AI Profile → Calendário → Google Calendar mostra se a conta está ligada

### Cenário C1 — Agente vê o Google sem clique (produção, bancada `.claude/agentes/sensi-vitae/`)
- [ ] `prod_turno.py` ação `sync` → 200
- [ ] Evento criado só no Google (hora livre) → turno `chat` de agendamento sem clicar em sincronizar → o agente não oferece essa hora

---

## Ajustes Possíveis Pós-Implementação

- Imagem da página de consentimento do calendário no aviso de Minha Conta (captar ligando uma conta Google de teste que nunca autorizou a app).
