# Fix: presentation_variant travado em "scheduler" para agentes diretos (closer)

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Ao testar o agente "Ana" (`agent_mode=direto`, template `closer_agressivo` — vendedor
autônomo/closer), o bot pediu para agendar uma conversa em vez de fechar a venda
diretamente. O comportamento esperado para `agent_mode=direto` é apresentar a oferta e
conduzir para fechamento/checkout no mesmo turno, não propor uma reunião.

Causa raiz: o campo `presentation_variant` — que controla se a Filha de Apresentação usa
tom de fechamento direto (`sales`) ou de agendamento (`scheduler`) — estava persistido
como `"scheduler"` no perfil da Ana, quando o correto para `direto` é `"sales"`.

---

## Problemas Identificados (estado anterior)

1. **Derivação incondicional no save (`frontend-crm/src/services/api.ts:1538`):**
   `saveConfig()` grava `presentation_variant` a partir **apenas** de
   `appointment_mode` (`commercial→sales`, `exploratory→scheduler`), ignorando
   `agent_mode`/`template_key`.

2. **`appointment_mode` é inacessível para agentes `direto`/`closer`
   (`frontend-crm/src/pages/AiProfile.tsx:461-462,479,683`):** a aba "Camada 5 ·
   Apresentação", onde `appointment_mode` é editável, fica oculta para esse grupo
   (`isDirectMode` gate). Resultado: esses perfis nunca saem do default
   `appointment_mode="exploratory"` → todo save grava `presentation_variant="scheduler"`.

3. **Sem fallback no backend uma vez persistido
   (`backend-executors/app/services/decision_engine.py:1273-1286`,
   `_resolve_presentation_variant`):** o valor salvo em `ai_profile.presentation_variant`
   tem prioridade sobre o default por `agent_mode` (`direto→sales`, L1281-1283). Esse
   default só é alcançado quando o valor salvo é `None` — e o frontend nunca envia
   `None`, sempre uma string concreta.

4. **Sem validação server-side (`backend-core/app/api/ai_profiles.py`,
   `_upsert_ai_profile`):** o `PUT /ai-profiles/me` persiste `presentation_variant`
   verbatim, sem checar consistência com `agent_mode`. Qualquer outro caller (admin
   patch-by-user, integrações futuras) pode reintroduzir o mesmo problema.

5. **Perfis já quebrados em produção:** todo perfil `direto`/`closer` salvo pela UI
   desde a regressão (commit `dbf5d46`, 01/04/2026) ficou com `presentation_variant`
   incorreto persistido — inclusive o da Ana. Corrigir só o código novo não repara o
   que já está salvo.

Regressão introduzida no commit `dbf5d46` ("Fix #9", 01/04/2026) e nunca corrigida
porque a validação subsequente (`1100fb5`, 27/06/2026 — fix de persistência de
`appointment_mode`) testou só o caminho "Compromisso Comercial" (agentes de
agendamento), nunca o pipeline `direto`.

Confirmado por investigação: `api.ts:1538` é o único ponto de escrita de
`presentation_variant` em todo o frontend (crm + admin) — não há lógica paralela a
manter sincronizada.

---

## Abordagem

```
saveConfig() [frontend]
  ├─ agent_mode ∈ {direto, closer} → presentation_variant = "sales" (sempre)
  └─ demais modos → presentation_variant = appointment_mode==commercial ? sales : scheduler (como já era)

PUT /ai-profiles/me [backend-core]
  → _upsert_ai_profile(): se agent_mode efetivo ∈ {direto, closer}, força
    presentation_variant="sales" independente do payload recebido (defesa em profundidade)

Startup backend-core [ensure_* migration]
  → backfill: UPDATE ai_profiles SET presentation_variant=NULL
    WHERE agent_mode IN ('direto','closer') AND presentation_variant='scheduler'
  → decision_engine._resolve_presentation_variant() volta a aplicar o fallback
    agent_mode_default (direto→sales) para os perfis já quebrados
```

---

## Plano de Implementação

### Fase 1 — Fix no frontend (causa raiz)

**Objetivo:** parar de sobrescrever `presentation_variant` incondicionalmente ao salvar

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `saveConfig()`: `presentation_variant` condicional a `config.agent_mode` |
| `docs/architecture/agents.md` | Atualizar L189-191 (regra deixa de ser incondicional) |

```ts
// ANTES
presentation_variant: config.appointment_mode === 'commercial' ? 'sales' : 'scheduler',

// DEPOIS
const isDirectAgent = config.agent_mode === 'direto' || config.agent_mode === 'closer';
...
presentation_variant: isDirectAgent
  ? 'sales'
  : (config.appointment_mode === 'commercial' ? 'sales' : 'scheduler'),
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7ca074a` | frontend: presentation_variant condicional a agent_mode + docs/agents.md |

**Detalhes do commit `7ca074a`:**
- `frontend-crm/src/services/api.ts` — `saveConfig()`: nova const `isDirectAgent`; `presentation_variant` passa a ser `"sales"` fixo para `direto`/`closer`, mantendo a derivação por `appointment_mode` só para os demais modos
- `docs/architecture/agents.md` — L189-191 reescrito para descrever a regra condicional e o default por `agent_mode` em `_resolve_presentation_variant()`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** todo save do AI Profile — de qualquer tipo de agente — gravava
`presentation_variant` só olhando o campo "Modo de Operação" (`appointment_mode`),
mesmo quando esse campo é invisível/irrelevante para agentes do tipo `direto`/closer.

**Agora:** ao salvar um agente `direto`/`closer`, `presentation_variant` é sempre
`"sales"`, independente de `appointment_mode`. Os demais tipos de agente
(`agenda`, `sdr_scheduler`, `consultivo`) continuam exatamente como antes.

**Para validar:** Cenário P1, abaixo.

### Fase 2 — Guarda de defesa em profundidade no backend

**Objetivo:** impedir que qualquer outro caller reintroduza o bug

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/ai_profiles.py` | `_upsert_ai_profile()`: força `presentation_variant="sales"` quando `agent_mode` efetivo é `direto`/`closer` |
| `backend-core/tests/test_ai_profile_agent_mode.py` | Novo caso: PUT com `agent_mode=direto` + `presentation_variant=scheduler` persiste `sales` |

```python
# Logo após o bloco de inferência de agent_mode (L427-434), antes de `if profile:`
effective_agent_mode = str(data.get("agent_mode") or (profile.agent_mode if profile else "") or "")
if effective_agent_mode in ("direto", "closer") and "presentation_variant" in data:
    data["presentation_variant"] = "sales"
```

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `0bd58fa` | backend: guarda force presentation_variant=sales para direto/closer |

**Detalhes do commit `0bd58fa`:**
- `backend-core/app/api/ai_profiles.py` — `_upsert_ai_profile()`: novo bloco que
  força `presentation_variant="sales"` quando o `agent_mode` efetivo (enviado no
  payload ou já salvo no perfil) é `direto`/`closer`, antes do loop de `setattr`
- `backend-core/tests/test_ai_profile_agent_mode.py` — novo caso
  `test_direto_agent_presentation_variant_forced_to_sales` (create + update)

**Nota de validação:** o módulo de teste já estava com as 6 suítes falhando
antes desta mudança — `create_or_replace_ai_profile()` mudou de assinatura
(passou a exigir `background_tasks`) e os testes não foram atualizados; é uma
regressão pré-existente, não relacionada a este fix. A lógica da guarda foi
validada chamando `_upsert_ai_profile()` isoladamente (fora do wrapper de
rota quebrado): `direto`+`scheduler`→`sales` no create e no update, `agenda`+
`scheduler` permanece `scheduler` (controle).

### Relatório da Fase 2 — o que mudou na prática

**Antes:** só o frontend garantia `presentation_variant` correto para agentes
diretos; qualquer outra via de escrita (painel admin, integração futura) podia
voltar a gravar `"scheduler"` sem ninguém perceber.

**Agora:** o próprio backend recusa persistir `presentation_variant` diferente
de `"sales"` para um perfil `direto`/`closer`, não importa quem enviou o PUT.

**Para validar:** Cenário C2, abaixo.

### Fase 3 — Backfill dos perfis já quebrados em produção

**Objetivo:** corrigir perfis existentes (inclusive o da Ana) sem exigir re-save manual

| Arquivo | O que muda |
|---|---|
| `backend-core/app/db.py` | Nova função `ensure_*` (mesmo padrão de `ensure_ai_profile_columns`): reset de `presentation_variant` para `NULL` em perfis `direto`/`closer` presos em `scheduler` |
| `backend-core/app/main.py` | Registrar a nova função no startup, após `ensure_ai_profile_columns()` |

```sql
UPDATE ai_profiles
SET presentation_variant = NULL
WHERE agent_mode IN ('direto', 'closer') AND presentation_variant = 'scheduler'
```

Idempotente: após Fase 1+2 em produção, nenhum novo registro cai nessa condição — a
função vira no-op nos boots seguintes.

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4084446` | backend: backfill de presentation_variant para perfis direto/closer |

**Detalhes do commit `4084446`:**
- `backend-core/app/db.py` — nova `ensure_presentation_variant_direto_backfill()`,
  mesmo padrão de `ensure_ai_profile_columns` (guarda de tabela inexistente,
  branch sqlite/postgres, `engine.begin()` + `text()`)
- `backend-core/app/main.py` — registrada no `on_startup()`, logo após
  `ensure_ai_profile_columns()`

**Nota de validação:** lógica confirmada isoladamente contra uma tabela sqlite
sintética com 5 perfis (`direto`+`scheduler`, `closer`+`scheduler`,
`agenda`+`scheduler`, `direto`+`sales`, `direto`+`NULL`) — só os dois primeiros
foram resetados para `NULL`, os demais permaneceram intocados.

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o perfil da Ana (e qualquer outro agente `direto`/`closer` salvo
antes deste fix) continuaria com `presentation_variant="scheduler"` gravado no
banco para sempre — corrigir só o código novo não repara o que já foi salvo.

**Agora:** na próxima vez que o backend-core subir (dev ou produção), esse
backfill roda automaticamente uma única vez de forma efetiva e corrige todos
os perfis nessa condição, sem precisar reabrir e salvar cada AI Profile
manualmente.

**Para validar:** Cenário P2 e C1, abaixo.

---

## Checks de Validação

### Cenário P1 — Save do frontend envia presentation_variant correto
- [ ] Abrir o AI Profile de um agente `agent_mode=direto` no frontend-crm
- [ ] Salvar (mesmo sem alterar nada) e inspecionar o payload de rede do `PUT /ai-profiles/me`
- [ ] Confirmar: `presentation_variant: "sales"` é enviado

### Cenário P2 — Backfill corrige o perfil da Ana
- [ ] Subir backend-core localmente
- [ ] Consultar `ai_profiles` da Ana (`app/core.db`) e confirmar `presentation_variant` mudou de `"scheduler"` para `NULL`

### Cenário C1 — Playground reproduz o cenário original corrigido
- [ ] Repetir a mensagem do teste original ("Olá boa tarde gostaria de saber as
      condições") no Playground com o perfil da Ana
- [ ] Confirmar: resposta conduz a fechamento direto (oferta + CTA de compra/checkout),
      não a "Que dia ou horário seria bom para agendarmos uma conversa?"

### Cenário C2 — Guarda do backend resiste a payload malicioso/desatualizado
- [ ] Enviar `PUT /ai-profiles/me` com `agent_mode=direto` e
      `presentation_variant=scheduler` explícito no payload
- [ ] Confirmar: perfil persiste com `presentation_variant="sales"` (guarda do backend
      sobrescreve)

---

## Ajustes Possíveis Pós-Implementação

- `getConfig()` não lê `presentation_variant` de volta do backend (é write-only do
  ponto de vista do frontend) — não afeta este fix, mas significa que a UI nunca
  exibe o valor real salvo. Fora de escopo aqui.
- Se no futuro `agent_mode=consultivo` também ganhar uma variante de fechamento direto
  equivalente a `direto`/`closer`, a lista `("direto", "closer")` nos dois pontos
  (frontend e backend) precisa crescer junto.
