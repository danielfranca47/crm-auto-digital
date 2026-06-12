# Melhorias Pós-Implementação: Google Calendar (etapa-10-2)

> **Contexto:** documento escrito após a graduação da etapa-10-2 (Google Calendar — OAuth por
> Utilizador + Sync Bidirecional). Serve de referência para priorizar melhorias futuras
> relacionadas com a integração Google Calendar.

---

## O que foi implementado (base de referência)

A etapa-10-2 entregou a integração Google Calendar completa em duas fases:

- **OAuth por utilizador** (`backend-core/app/api/auth_google.py`): cada operador conecta a
  sua própria conta Google via OAuth2. Tokens guardados na tabela `users` (5 colunas).

- **Push CRM → Google** (`backend-crm/services/google_calendar_service.py`): ao criar,
  actualizar ou cancelar um compromisso no CRM, o evento é replicado automaticamente no
  Google Calendar do utilizador.

- **Pull Google → CRM** (`POST /api/appointments/google-sync`): botão "Sincronizar Google"
  na agenda importa eventos do Google Calendar para o período visível. Eventos importados
  têm `source='google'`, badge visual azul "Google" e são somente-leitura no CRM.
  Cleanup automático: eventos removidos no Google desaparecem na próxima sync.

**Resultado prático:** operador conecta o Google uma vez em MinhaConta; a partir daí,
todos os compromissos do CRM aparecem no Google Calendar e vice-versa (via sync manual).

---

## Pontos de melhoria identificados

### M1 — Sync automática periódica

**Prioridade: MÉDIA — melhoria de conforto, sem impacto em receita**

Actualmente o utilizador precisa de clicar "Sincronizar Google" manualmente para importar
eventos do Google Calendar. Um job periódico (a cada 5–15 min) executaria o mesmo
`/api/appointments/google-sync` automaticamente para todos os utilizadores com Google
conectado.

**Comportamento actual:** sync só acontece quando o utilizador clica o botão na agenda.

**Comportamento desejado:** eventos criados no Google Calendar aparecem no CRM
automaticamente sem interação do utilizador.

**Área do sistema:** `backend-core` ou `backend-crm` (APScheduler já disponível no
`backend-core`). O job precisa de iterar por todos os `user_id` com `google_access_token`
não-nulo e chamar o serviço de sync para o período relevante (ex.: ±30 dias).

**Notas técnicas:**
- APScheduler já está instalado no `backend-core`.
- O endpoint de sync já tem toda a lógica de upsert + cleanup — o job só precisa de o chamar.
- Cuidado com rate limiting da Google Calendar API (quota: 1M requests/day por projecto).

---

### M2 — Seleção de qual calendário Google usar

**Prioridade: MÉDIA — diferenciador de valor para planos premium**
**Restrição de produto: disponível apenas nos planos Scale e Enterprise**

Actualmente o sistema sincroniza sempre com o calendário `primary` da conta Google.
Utilizadores com múltiplos calendários (ex.: "Trabalho", "Pessoal", "Equipa") não
conseguem escolher qual calendário vincular ao CRM.

**Comportamento actual:** sync sempre com o calendário padrão (`primary`).

**Comportamento desejado:** em MinhaConta, após conectar o Google, aparece um dropdown
com os calendários disponíveis na conta. O utilizador escolhe qual calendário vincular.
Para planos Start e Growth: funcionalidade bloqueada com CTA de upgrade visível.

**Área do sistema:**
- `backend-core` — endpoint `GET /auth/google/calendar/list` (chama Google Calendar API
  `/users/me/calendarList`) + guardar `google_calendar_id` escolhido.
- `frontend-crm` — MinhaConta: dropdown de calendários + guard por plano.
- `backend-crm` — google_calendar_service: substituir `primary` pelo `google_calendar_id`
  guardado no perfil do utilizador.

**Notas de produto:**
- O guard de plano deve ser feito via `entitlements` (o padrão existente no sistema).
- Avaliar se criar uma nova entitlement `google_calendar_multi_calendar: bool` ou reaproveitar
  outra lógica de gate já existente.

---

### M3 — Publicação do Google OAuth para produção

**Prioridade: ALTA quando o produto entrar em produção real — processo burocrático**
**Natureza: não é código — é processo no Google Cloud Console**

Existem 3 estados possíveis do projecto Google Cloud, com comportamentos diferentes:

| Estado | Utilizadores não cadastrados | Refresh token | Adequado para |
|---|---|---|---|
| **Testing** (actual) | Bloqueados — não conseguem sequer passar do aviso | Expira em 7 dias | Desenvolvimento/testes internos apenas |
| **In Production** (sem verificação) | Vêem aviso "app não verificada" mas podem prosseguir | Não expira | Primeiros ~100 clientes |
| **Verificado pelo Google** | Sem avisos, sem limite | Não expira | Produção a escala |

**⚠️ Problema crítico do modo Testing:** os refresh tokens expiram ao fim de 7 dias.
Após esse prazo o utilizador tem de re-autorizar manualmente — completamente inadequado
para qualquer fluxo de produção.

---

**Passo 1 — In Production sem verificação** — ✅ Concluído em 12/06/2026

Suficiente para os primeiros ~100 clientes pagantes. Clientes vêem aviso "app não
verificada" mas conseguem prosseguir e a integração funciona normalmente (tokens
não expiram). Feito no Google Cloud Console — OAuth consent screen — Status — "In Production".

---

**Passo 2 — Verificação completa pelo Google (quando escalar)**

Necessário para eliminar o aviso e ultrapassar o limite de ~100 utilizadores.

1. Privacy policy pública publicada numa URL acessível
2. Vídeo de demonstração mostrando o uso dos scopes OAuth solicitados
3. Submissão do formulário de verificação no Google Cloud Console
4. Aguardar review (tipicamente 1–2 semanas para apps não sensíveis)

**Timing recomendado:** iniciar quando o produto tiver > 1–2 clientes pagantes activos
(para ter material de demonstração realista para o Passo 2).

**Notas:**
- Os scopes OAuth solicitados actualmente: `calendar.events` (read/write de eventos).
- Se M2 for implementado antes da verificação, adicionar `calendar.readonly`
  (para listar calendários) ao escopo e incluir no review.

---

## Dependências entre os itens

- **M2 depende de M1 estar pelo menos planeado:** se M2 adicionar um `calendar_id` customizado,
  o job de M1 precisa de respeitar esse campo — convém desenhar M1 com esse campo em mente.
- **M3 é independente de M1 e M2**, mas se M2 for implementado, incluir os novos scopes
  na submissão do App Review (fazer tudo num só review).
- **M3 é o mais urgente em termos de timing** — tem prazo implícito (quando clientes
  pagantes começarem a usar a funcionalidade), mas o processo é externo (não depende de código).
