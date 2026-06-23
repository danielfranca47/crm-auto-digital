# Fix: Persistência de campos de follow-up/agenda no AI Profile

**Branch:** `main`
**Status:** Em andamento
**Origem:** `docs/plans/followup-proativo-e-cancelamento-agenda.md` (M1, prioridade ALTA)

---

## Motivação

Vários campos de follow-up/agenda do AI Profile não têm efeito real quando configurados
pela tela `/ai-profile` — o operador preenche, salva, a tela não mostra erro nenhum, mas
o valor nunca chega ao motor real (`decision_engine.py`, `followup_state.py`,
`jobs_service.py`, `briefing_service.py`, `routes/appointments.py`). É um bug silencioso:
parece que funcionou, nunca funcionou.

Causa raiz: `frontend-crm/src/services/api.ts` (`getConfig()`/`saveConfig()` dentro de
`api.aiProfile`) lê e escreve estes campos de dentro do JSON auxiliar `offer_pack`, em
vez das colunas de topo do AI Profile que `PUT /ai-profiles/me` já aceita. O backend já
está pronto — `backend-core/app/api/ai_profiles.py` já tem todos estes campos como
colunas de primeira classe em `AIProfileBase`/`AIProfileUpdate`; nenhuma mudança de
backend é necessária.

Esse bug bloqueia dois itens futuros do mesmo plano: o gatilho automático de follow-up
por inatividade (M2) e a camada dedicada de Follow-up no AI Profile (M3) — qualquer campo
novo construído sobre o mesmo padrão herdaria o problema.

---

## Problemas Identificados (estado anterior)

1. **9 campos de mapeamento directo trocados:** `frontend-crm/src/services/api.ts` —
   `followup_cadence` (linha 1330/1424), `followup_max_attempts` (1328/1422),
   `followup_first_offset` (1329/1423), `followup_allowed_hours` (1331/1425),
   `nurture_vs_discard_rule` (1322/1398), `briefing_enabled` (1348/1431),
   `briefing_channel` (1349/1432), `briefing_lead_time` (1350/1433),
   `operator_whatsapp` (1351/1434) — todos lidos de `pack.<campo>` em `getConfig()` e
   escritos dentro do objecto `offer_pack` em `saveConfig()`, em vez de
   `(profile as any)?.<campo>` e chave de topo no payload do PUT.

2. **`appointment_reminder_offsets` com nomes e formato diferentes:** linhas
   1346-1347/1429-1430 — a UI usa dois campos cosméticos (`appointment_reminder_h1`/`h2`,
   horas positivas) gravados em `offer_pack`, enquanto o backend espera uma lista de
   minutos negativos na coluna `appointment_reminder_offsets`. Não é um rename simples —
   precisa de conversão nos dois sentidos.

3. **`followup_first_offset` e `followup_allowed_hours` descobertos durante o
   diagnóstico** — não estavam no plano original (`docs/plans/followup-proativo-e-cancelamento-agenda.md`
   listava só 6 campos), têm o mesmo bug exacto no mesmo domínio (cadência de follow-up),
   por isso entraram no mesmo escopo desta implementação.

---

## Abordagem

```
UI preenche campo → saveConfig() → PUT /ai-profiles/me
  ANTES: campo entra dentro de offer_pack {...}        → coluna de topo nunca é escrita
  DEPOIS: campo vai como chave de topo do payload       → coluna de topo é escrita

GET /ai-profiles/me → getConfig() → AgentConfig (UI)
  ANTES: campo lido de pack.<campo> (dentro de offer_pack) → sempre vazio/default
  DEPOIS: campo lido de (profile as any)?.<campo>          → reflecte o valor real salvo
```

Padrão correcto já existente no mesmo arquivo, usado como referência: `meeting_management_enabled`
(linha 1356 no `getConfig`, 1482 no `saveConfig`) e `payment_gateway`/`availability_mode`/
`scheduling_offer_style` — leem de `profile`, escrevem como chave de topo.

**Fora de escopo:** `qualification_score_threshold` e `buying_signal_keywords` têm o
mesmo bug mas não são do domínio follow-up/agenda — decisão já registada no plano de
origem.

---

## Plano de Implementação

### Fase 1 — Corrigir os 9 campos de mapeamento directo

**Objetivo:** fazer `followup_cadence`, `followup_max_attempts`, `followup_first_offset`,
`followup_allowed_hours`, `nurture_vs_discard_rule`, `briefing_enabled`,
`briefing_channel`, `briefing_lead_time` e `operator_whatsapp` lerem/escreverem nas
colunas de topo do AI Profile, em vez de dentro de `offer_pack`.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `getConfig()`: trocar `pack.<campo>` por `(profile as any)?.<campo>` para os 9 campos. `saveConfig()`: remover os 9 campos do objecto literal `offer_pack`; adicionar como chaves de topo no payload de `coreClient.put('/ai-profiles/me', {...})` |

```ts
// ANTES (getConfig)
followup_cadence: pack.followup_cadence ?? DEFAULT_AGENT_CONFIG.followup_cadence,

// DEPOIS
followup_cadence: (profile as any)?.followup_cadence ?? DEFAULT_AGENT_CONFIG.followup_cadence,
```

```ts
// ANTES (saveConfig) — dentro do objecto offer_pack
const offer_pack = {
  ...
  followup_cadence: config.followup_cadence,
  ...
};
await coreClient.put('/ai-profiles/me', { ..., offer_pack });

// DEPOIS — chave de topo no payload do PUT
await coreClient.put('/ai-profiles/me', {
  ...,
  followup_cadence: config.followup_cadence,
  ...,
  offer_pack,
});
```

### Fase 2 — Corrigir `appointment_reminder_offsets` (conversão horas ↔ minutos)

**Objetivo:** fazer os campos de UI `appointment_reminder_h1`/`h2` (horas positivas)
convergirem com a coluna real `appointment_reminder_offsets` (lista de minutos
negativos).

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `getConfig()`: converte `(profile as any)?.appointment_reminder_offsets` em `appointment_reminder_h1`/`h2`. `saveConfig()`: converte `appointment_reminder_h1`/`h2` em `appointment_reminder_offsets`, enviado como chave de topo |

```ts
// ANTES (getConfig)
appointment_reminder_h1: pack.appointment_reminder_h1 ?? DEFAULT_AGENT_CONFIG.appointment_reminder_h1,
appointment_reminder_h2: pack.appointment_reminder_h2 ?? DEFAULT_AGENT_CONFIG.appointment_reminder_h2,

// DEPOIS
const _offsets = (profile as any)?.appointment_reminder_offsets as number[] | null | undefined;
appointment_reminder_h1: _offsets?.[0] != null ? Math.round(Math.abs(_offsets[0]) / 60) : DEFAULT_AGENT_CONFIG.appointment_reminder_h1,
appointment_reminder_h2: _offsets?.[1] != null ? Math.round(Math.abs(_offsets[1]) / 60) : DEFAULT_AGENT_CONFIG.appointment_reminder_h2,
```

```ts
// ANTES (saveConfig) — dentro do offer_pack
appointment_reminder_h1: config.appointment_reminder_h1,
appointment_reminder_h2: config.appointment_reminder_h2,

// DEPOIS — chave de topo, convertida para minutos negativos
appointment_reminder_offsets: [
  -(config.appointment_reminder_h1 * 60),
  -(config.appointment_reminder_h2 * 60),
],
```

---

## Checks de Validação

### Cenário P1 — Campos de mapeamento directo persistem
- [ ] Abrir `/ai-profile`, preencher `briefing_lead_time` e `operator_whatsapp` com
  valores diferentes do default
- [ ] Salvar, recarregar a página
- [ ] Confirmar: os valores preenchidos continuam aparecendo (não voltaram ao default)
- [ ] Inspecionar `GET /ai-profiles/me` (Network tab) e confirmar que os valores estão
  nas colunas de topo da resposta, não dentro de `offer_pack`

### Cenário P2 — `appointment_reminder_offsets` convertido correctamente
- [ ] Configurar lembretes para 48h e 6h (diferente do default 24h/2h) e salvar
- [ ] Recarregar a página — confirmar que a tela mostra 48/6, não voltou a 24/2
- [ ] Inspecionar `GET /ai-profiles/me` e confirmar `appointment_reminder_offsets: [-2880, -360]`

### Cenário C1 — Lembrete real reflecte o valor configurado
- [ ] Com 48h/6h configurado, criar um compromisso de teste
- [ ] Confirmar na tabela `jobs` que os jobs `whatsapp.appointment.reminder` criados têm
  `scheduled_at` em 48h e 6h antes do compromisso, não 24h/2h (default do template)

---

## Ajustes Possíveis Pós-Implementação

- Contas que já tinham preenchido estes campos pela UI (gravados em `offer_pack`, sem
  efeito real) vão ver o valor "resetar" para o default na primeira vez que abrirem a
  tela depois do fix — não há migração de dado de `offer_pack` para a coluna de topo,
  porque o valor nunca teve efeito real (não há comportamento em produção a preservar).
- `qualification_score_threshold` e `buying_signal_keywords` têm o mesmo bug, fora deste
  domínio — registar como item próprio se decidido corrigir.
