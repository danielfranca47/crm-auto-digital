# Margem entre sessões configurável (tempo para preparar a sala)

**Branch:** `worktree-feat+margem-entre-sessoes`
**Status:** Todos os cenários validados (26/10/2026) — pendente: graduação
**Autonomia:** manual
**Origem:** investigação do bug A da bateria PROD07 do agente Sensi Vitae (26/10/2026) — pedido do
utilizador para avaliar uma margem entre sessões (ex.: 15 min para a terapeuta preparar a sala).
**Depende de:** `fix-conflito-horario-comparado-como-texto` (mesmas funções de conflito) — ✅ em `main` desde 26/10/2026
**Plano de execução:** [`docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md`](../plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md) — P5
**Merge:** mexe na estrutura da base de dados (coluna nova no AI profile) — só se junta a `main` com o "sim" do utilizador.

---

## Motivação

Hoje duas sessões podem ficar coladas (uma acaba às 16h, a seguinte começa às 16h). Num espaço de
massagem a terapeuta precisa de tempo para mudar a marquesa, toalhas e arejar a sala. O dono do
negócio deve poder dizer "deixe N minutos livres entre sessões", e o agente só propõe/aceita
horários que respeitem essa margem.

## Decisões de produto (Plan Mode, 26/10/2026)

1. **Valor por omissão 0** — nada muda para quem não configurar.
2. **Intervalo de N min entre quaisquer duas marcações** (não "N antes + N depois", que daria 2×N).
   Ocupado 15h–16h com margem 15 → a seguinte pode começar às 16h15; uma que acabe às 14h45 cabe antes.
3. **Uma margem por conta** — margem por profissional fica para quando a agenda distinguir
   profissionais (`docs/plans/agentes-agenda-melhorias-futuras.md` M1).
4. **Vale para todos os ocupados**, incluindo eventos pessoais do Google Calendar.

---

## Problemas Identificados (estado anterior)

1. **Sem campo de margem:** o AI profile (`backend-core/app/models/ai_profile.py`) só tinha
   `default_session_duration_minutes`.
2. **Conflito só por sobreposição exata:** todas as verificações do agente (`meeting_scheduler._has_conflict`,
   `requested_slot.find_requested_slot`, `professional_hours.nearest_free_start`, remarcação no
   `decision_engine`) aceitam uma sessão que começa no minuto em que outra acaba.
3. **Cuidado na remarcação:** `meeting_scheduler._original_duration_minutes` lê a duração do ocupado
   do próprio lead — se esse ocupado viesse alargado, a sessão remarcada ficaria mais longa.

---

## Abordagem

Um só ponto de aplicação, no CRM, antes de o contexto seguir para o executor:

```
enrich_context_bundle (B5, orchestrator.py)
  _load_calendar_busy_slots(user_id)            ← ocupados reais (sem mudança)
  → _apply_session_buffer(slots, N, lead.id)
      ├─ slot de outro lead / evento Google → [início − N, fim + N]
      └─ slot do próprio lead               → horário real (já é excluído dos conflitos;
                                               usado para a duração na remarcação e para o
                                               bloco "REUNIÃO/SESSÃO JÁ CONFIRMADA")
  → calendar_busy_slots (mesmo para Playground e WhatsApp real)
        ↓
executor: marcação nova, horário pedido + alternativa, remarcação, "HORÁRIOS JÁ OCUPADOS"
          → respeitam a margem sem código novo
```

**Cuidado da remarcação resolvido** por não alargar os ocupados do próprio lead — sem campos extra
no slot. **Fora de propósito:** `_check_conflict` do CRM (gravação manual pode ficar colada) e
`professional_hours` (abertura/fecho do dia).

---

## Plano de Implementação

### Fase 1 — Campo + aplicação da margem + ecrãs + docs

**Objetivo:** o dono configura N min e o agente deixa sempre N min livres entre marcações.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | coluna `session_buffer_minutes` (Integer, `server_default="0"`) |
| `backend-core/app/db.py` | entrada `session_buffer_minutes` (default 0) no mapa de colunas idempotentes |
| `backend-core/app/api/ai_profiles.py` | campo em `AIProfileBase` e `AIProfileUpdate` |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_resolve_session_buffer_minutes` (inválido = 0, máx. 240) + `_apply_session_buffer`; B5 de `enrich_context_bundle` aplica a margem |
| `backend-crm/routes/admin_agents.py` | `session_buffer_minutes` no detalhe do perfil + `_SYSTEM_DEFAULTS` (diff / `has_custom_config`) |
| `backend-crm/tests/test_calendar_busy_slots.py` | `SessionBufferTest`: margem 0/inválida = igual a hoje; outro lead e Google alargados ±15; próprio lead intacto; limite 240 |
| `backend-executors/tests/test_session_buffer.py` | com ocupado alargado: 16h recusado, 16h15 aceite, 14h recusado, 13h45 (60 min) aceite; ocupado do próprio lead não bloqueia |
| `frontend-crm/src/types/agente.ts` + `src/services/api.ts` | campo `session_buffer_minutes` (default 0), lido e gravado |
| `frontend-crm/src/components/agente/CamadaApresentacao.tsx` | card "Intervalo entre sessões" ao lado de "Duração da sessão" + `ModalSessionBuffer` (slider 0–60, passo 5) |
| `frontend-admin/src/pages/AdminAgents.tsx` | badge "intervalo entre sessões: N min" quando > 0 |
| `docs/architecture/agenda.md`, `agents.md`, `admin-agents-contract.md`, `docs/ai-profile-fields.md` | secção / linhas do campo novo |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `71df8ee` | Campo `session_buffer_minutes`, aplicação em `enrich_context_bundle`, ecrãs CRM e admin, testes e docs |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o agente aceitava e propunha sessões coladas (uma acaba às 16h, a seguinte começa às 16h).
**Agora:** no ecrã do agente há o card "Intervalo entre sessões". Com 15 min, o agente só propõe e
aceita horários com pelo menos 15 min livres antes e depois de qualquer coisa na agenda (incluindo
eventos do Google). Quem não mexer fica com 0 e nada muda. A remarcação de um lead mantém a duração
da sessão dele. Marcações feitas à mão na Agenda continuam a poder ficar coladas.
**Para validar:** Cenários U1, P1, P2 e P3 (local), depois C1 (produção, após merge).

---

## Checks de Validação

### Cenário U1 — Testes unitários
- [x] `backend-crm`: `pytest tests/test_calendar_busy_slots.py` — 24 passaram
- [x] `backend-executors`: suite completa — 483 passaram (inclui `test_session_buffer.py`)
- **Validado em:** 26/10/2026 — `backend-core` `-k ai_profile`: 8 falhas que não vêm deste campo
  (testes chamam `create_or_replace_ai_profile` sem `background_tasks` e ficheiros temporários
  presos no Windows); o schema expõe `session_buffer_minutes` em `AIProfileOut` e `AIProfileUpdate`.
  Frontends sem `node_modules` nesta máquina — `tsc` não corrido.

> Setup usado (26/10/2026): código da worktree copiado para `ambiente/codigo` (backup das versões
> antigas em `ambiente/codigo_backup_20261026-212213`); coluna criada no arranque do core local;
> `session_buffer_minutes=15` no perfil local 5. Como o `simular.py` limpa a agenda no arranque, o
> ocupado do P1 foi inserido por um wrapper depois dessa limpeza (evento `lead_id` NULL, user 15).

### Cenário P1 — Bancada local: sessões seguidas com margem
- [x] Na conta local da bancada (`.claude/agentes/sensi-vitae/`), aplicar `session_buffer_minutes=15`
- [x] `python simular.py p-seguidas M1` (ocupado ter 27/10 15:00–16:00)
- [x] Confirmar: a IA propõe 16h15 (ou o horário seguinte válido) em vez de 16h
- **Validado em:** 26/10/2026 — "O horário que pediram para amanhã às 16h já está ocupado. Podemos agendar
  com o Daniel às 16h15"; cliente aceitou; gravado 27/10 16:15–17:15 (60 min, sem alargar).
  Tentativa: `tentativas/20261026-2125-M1-p-seguidas.md`

### Cenário P2 — Regressão: remarcação mantém a duração
- [x] `python simular.py pos-marcacao M1` com a margem 15
- [x] Confirmar: a sessão remarcada tem a mesma duração da original
- **Validado em:** 26/10/2026 — 1.ª corrida (M1): a IA não sinalizou a remarcação
  (`meeting_reschedule_requested=false`) e nada foi remarcado — variação do modelo, a agenda nem foi
  consultada. Repetido 2x com margem 0 e 2x com margem 15: as 4 remarcaram para qui 29/10 15:00–16:00
  (60 min, igual à original). Em M1b a mensagem saiu como marcação nova ("Como se chama?") apesar de
  remarcar — texto da IA, igual com ou sem margem.

### Cenário P3 — Regressão: pedido das 17h com a Val
- [x] `python simular.py p-val-17h M1` com a margem 15
- [x] Confirmar: comportamento igual ao de antes (sem regressão)
- **Validado em:** 26/10/2026 — 17h recusada ("fora do horário de atendimento da Val"), propôs 16h,
  gravado qui 29/10 16:00–17:00. Tentativa: `tentativas/20261026-2128-M1-p-val-17h.md`

### Cenário P4 — Gravação do campo e painel admin (via API, não browser)
- [x] `PUT/GET /ai-profiles/me` (o que o ecrã do agente usa): grava 20 e relê 20; gravar só outro campo
  mantém 20; grava 0 ("Sem intervalo") e relê 0
- [x] `admin_agents_user_detail` (endpoint real do CRM, perfil lido do core por service token, sem a
  camada do JWT admin): `profile.session_buffer_minutes=15`, `diff={"default": 0, "user": 15}`,
  `has_custom_config=true`
- [x] Tipos: `tsc` do `frontend-admin` limpo; `frontend-crm` com erros antigos só noutros ficheiros
  (nenhum em `CamadaApresentacao.tsx`, `agente.ts` ou `api.ts`)
- **Validado em:** 26/10/2026 — bancada local (portas 8100/8101), margem reposta em 15 no fim.
  O desenho do card e do badge não foi visto no browser.

### Cenário C1 — Produção (`--prod`), depois do merge e deploy
- [x] Com o "sim" do utilizador: merge (`c01d0e9`) + deploy; margem na conta de produção (user 4) —
  o utilizador pediu **30 min** e que fique ligada (`configs/c13d-margem-30.json`, backup
  `ambiente/prod_backup_20261026-215502.json`, antes: 0)
- [x] `python simular.py p-seguidas PROD-M1 --prod`, `pos-marcacao PROD-M1 --prod`, `p-val-17h PROD-M1 --prod`
- [x] Confirmar os mesmos resultados de P1–P3 (ajustados à margem de 30)
- **Validado em:** 26/10/2026 — Google da Ayde com ocupados ter 27/10 15–16h e qui 29/10 15–16h.
  `p-seguidas`: 16h recusada, propôs e gravou ter 16h30–17h30. `pos-marcacao`: ter 14h recusada (acabaria
  colada às 15h), propôs e gravou 13h30–14h30; remarcação para qui 15h recusada (ocupado) e a sessão
  mantém-se — a IA escreveu "a sua sessão de terça-feira às 14h" em vez de 13h30 (texto, já conhecido em
  `docs/plans/cancelamento-reagendamento` M5). `p-val-17h`: 17h recusada (limite da Val), 16h já não serve
  (margem), propôs e gravou qui 13h30–14h30. 1.ª tentativa do `p-val-17h` caiu por falha do `railway ssh`
  (sem marcação deixada). Marcações `[Playground]` apagadas no fim de cada cenário.

---

## Ajustes Possíveis Pós-Implementação

- Margem por profissional (Val vs. Daniel) quando a agenda distinguir profissionais (plano M1).
- O bloco "HORÁRIOS JÁ OCUPADOS" mostra à IA os ocupados de outros já alargados ("15:00 até 16:15") —
  aceite por ser o tempo de facto indisponível; se a IA começar a citar esses horários ao lead de forma
  estranha, passar a mandar o horário real + margem em campos separados.
- `_check_conflict` do CRM não aplica a margem — se o dono quiser que marcações manuais também
  respeitem o intervalo, seria uma opção à parte.
