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

Decisão: no AI Profile não há segundo botão de ligar — a ligação é da conta e vive só em Minha
Conta; o modal mostra o estado real e aponta para lá (evita dois fluxos OAuth).

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4aef104` | Avisos de ligação recusada / último erro em Minha Conta, mensagem real no erro da Agenda, estado da ligação no AI Profile |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** uma ligação falhada dava só um aviso rápido genérico ("Erro ao conectar") que desaparecia;
uma conta ligada sem acesso ao calendário aparecia como "Conectado" sem mais nada; no AI Profile,
escolher "Google Calendar" dava a ideia de que o calendário ficava ligado.
**Agora:** Minha Conta mostra um aviso que fica no ecrã a explicar o motivo (ex.: "A Google não deu
acesso ao seu calendário") com o botão "Ligar de novo"; se a conta está ligada mas a Google recusa,
aparece um aviso amarelo com "Voltar a ligar"; o erro do "Sincronizar Google" diz o motivo real; e
no AI Profile, ao escolher Google Calendar, aparece se a conta está mesmo ligada e um link para
Minha Conta.
**Para validar:** Cenário P3 (browser, local).

### Fase 3 — Agenda do Google visível ao agente sem clique (M1)

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_load_calendar_busy_slots` sincroniza antes (cache 3 min, timeout 5 s, nunca bloqueia); ignora eventos Google "Disponível" |
| `backend-crm/services/google_calendar_sync.py` | Guarda `transparency` do evento em `google_transparency` |
| `backend-crm/database.py` | `ensure_column` `appointments.google_transparency` (depois da reconstrução de `_migrate_appointments_lead_nullable`) |
| `backend-crm/routes/appointments.py`, `backend-crm/routes/leads.py` | `_check_conflict` ignora eventos Google "Disponível" |
| `frontend-crm/src/pages/Agenda.tsx` | Sync automático do mês ao abrir |
| `backend-crm/tests/*` | TTL/falha da sync antes dos ocupados; transparency na sync e no conflito; coluna nova nos esquemas de teste |
| `docs/architecture/agenda.md`, `google-calendar.md`, `playground-parity.md`, `_overview.md` | Estado atual |
| `docs/plans/google-calendar-melhorias-pos-etapa-10-2.md` | Retirar M1 e M4; nota de consentimento para M2 |

Decisões:
- **Sob demanda, não job periódico:** a sync corre quando o agente precisa (dentro de
  `enrich_context_bundle`, só `agent_mode == "agenda"`) e ao abrir a Agenda. Sem agendador novo
  (o backend-crm não tem um) e sem chamadas à Google para contas paradas.
- **Só "Ocupado" bloqueia** (decisão do utilizador em 26/10/2026): com a sync automática, um
  aniversário de dia inteiro (no Google é "Disponível" por defeito) bloquearia o dia todo. Eventos
  "Disponível" continuam na Agenda mas não contam no agente nem no `_check_conflict`.

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `6d7ffaf` | Sync do Google antes dos ocupados do agente, "Disponível" não bloqueia, sync ao abrir a Agenda, docs |

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o agente só sabia das sessões marcadas pelo CRM ou importadas por alguém que tivesse
clicado "Sincronizar Google" — uma sessão marcada só no Google podia ser oferecida a outro cliente.
**Agora:** sempre que o agente vai propor ou confirmar horários, o CRM vai primeiro buscar ao Google
os próximos 30 dias (no máximo de 3 em 3 minutos por conta). Se a Google falhar, o agente responde
na mesma com o que já sabe. Eventos marcados no Google como "Disponível" (ex.: aniversários)
aparecem na Agenda mas não ocupam horário. A Agenda também vai buscar o mês ao Google sozinha
quando é aberta.
**Para validar:** Cenário P4 (testes automáticos — validados) e C1 (produção, depois do deploy).

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

### Cenário P4 — Sync antes dos ocupados e "Disponível" (testes automáticos)
- [x] Sync da janela antes de ler os ocupados, com timeout de 5 s; 2ª chamada dentro de 3 min não sincroniza; depois de 3 min sincroniza
- [x] Falha da Google (ou erro inesperado) não bloqueia e devolve o que está na tabela
- [x] Evento Google "Disponível" fica guardado, não conta como ocupado nem como conflito
- [x] Migração: `init_db` 2x numa base nova cria `google_transparency` sem perder `user_id`/`source`
- **Validado em:** 26/10/2026 — suite backend-crm 259 verdes; migração verificada com base temporária

### Cenário C1 — Agente vê o Google sem clique (produção, bancada `.claude/agentes/sensi-vitae/`)

Só testável depois do deploy (merge em `main` → Railway).

- [ ] `prod_turno.py` ação `sync` → 200
- [ ] Evento criado só no Google (hora livre, marcado como Ocupado) → turno `chat` de agendamento sem clicar em sincronizar → o agente não oferece essa hora
- [ ] Evento de dia inteiro "Disponível" nesse dia → o agente continua a oferecer horários desse dia

---

## Ajustes Possíveis Pós-Implementação

- Imagem da página de consentimento do calendário no aviso de Minha Conta (captar ligando uma conta Google de teste que nunca autorizou a app).
- Contas já ligadas sem `calendar.events` antes deste deploy só ficam sinalizadas depois do primeiro erro (sync, Agenda aberta ou mensagem do agente) — não há verificação retroativa.
- Formato das datas do Google: `start_at` fica com o offset do calendário (`+00:00`/`+01:00`) ou só a data (dia inteiro), e a limpeza compara texto com ISO UTC. Nas bordas da janela, um evento pode ser apagado e reimportado na sync seguinte; normalizar para UTC se causar problema visível.
- Cache da sync é por processo: com vários workers, uma conta pode ter algumas sincronizações a mais em 3 min.
