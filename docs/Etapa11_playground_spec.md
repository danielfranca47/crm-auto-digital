# Etapa 11 — Playground de Testes: Spec + Plano de Implementação

## Sumário Executivo

O Playground é um endpoint REST que permite simular conversas completas com qualquer agente de IA configurado, sem dependência de WhatsApp, UazAPI, webhooks ou qualquer infraestrutura de mensageria. Ele reutiliza o `decision_engine.decide()` existente e mantém estado de lead entre chamadas para suportar conversas multi-turno.

---

## 1. Onde Vive o Endpoint

**Serviço:** `backend-crm` (porta 8000)
**Justificativa:** É o serviço que contém o pipeline de IA (`orchestrator`, `qualification_state`, `field_extractor`), o banco de dados de leads (`crm.db`), e as rotas de leads. O `backend-executors` seria alternativa, mas introduziria dependência cruzada desnecessária.

**Nova rota:**
```
backend-crm/routes/playground.py
```

---

## 2. Spec do Endpoint

### `POST /api/playground/chat`

#### Request Schema

```json
{
  "ai_profile_id": 7,
  "message": "Olá, quero saber mais sobre os vossos serviços",
  "lead_id": null,
  "reset": false
}
```

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `ai_profile_id` | `int` | Sim | ID do `AiProfile` no `backend-core`. Define o agente a simular. |
| `message` | `str` | Sim | Texto da mensagem do lead (simulada). Mínimo 1 caractere. |
| `lead_id` | `int \| null` | Não | ID de um lead sandbox existente. Se `null`, cria um novo lead sandbox. |
| `reset` | `bool` | Não (default: `false`) | Se `true`, limpa o histórico e estado de qualificação do lead antes de processar. |

#### Response Schema

```json
{
  "lead_id": 42,
  "message_to_send": "Olá! Meu nome é Lucas, especialista da XYZ...",
  "next_action": "reply",

  "mother_decision": {
    "route_to": "qualification",
    "confidence": 0.91,
    "reason": "Lead em fase inicial, sem dados de qualificação.",
    "signals": { "is_short_reply": false, "buying_signal": false }
  },

  "child_result": {
    "message_text": "Olá! Meu nome é Lucas...",
    "question_text": "Qual é o principal desafio que a sua empresa enfrenta hoje?",
    "field": "main_challenge",
    "should_ask": true,
    "did_complete_phase": false,
    "recommended_next_category": null,
    "outcome": null,
    "kanban_highlight": null,
    "confidence": 0.87,
    "signals_structured": {}
  },

  "lead_state": {
    "category": "qualification",
    "qualification_state": {
      "exists": true,
      "data_json": { "main_challenge": null, "decision_role": null },
      "missing_fields": ["main_challenge", "decision_role", "budget_or_price_acceptance"],
      "filled_fields": [],
      "power_score": 0,
      "priority_score": 0,
      "price_score": 0,
      "timing_score": 0,
      "qualification_total_score": 0
    }
  },

  "decision_trace": {
    "agent_mode": "consultivo",
    "presentation_variant": "sales",
    "mother_route": "qualification",
    "guardrails_applied": [],
    "category_suggestion_cleared": false,
    "ai_profile_id": 7,
    "lead_is_sandbox": true,
    "timestamp": "2026-03-29T14:32:10Z"
  }
}
```

| Campo | Descrição |
|---|---|
| `lead_id` | ID do lead sandbox usado/criado. Persistir para chamadas subsequentes. |
| `message_to_send` | Mensagem que seria enviada pelo WhatsApp ao lead real. |
| `next_action` | `reply` / `ask_qualification` / `handoff` / `ignore` |
| `mother_decision` | Saída completa da LLM Mãe (roteamento). |
| `child_result` | Saída completa da LLM Filha (geração da mensagem). |
| `lead_state` | Estado atual do lead após a chamada (categoria, qualificação). |
| `decision_trace` | Metadados de debug do pipeline. |

---

## 3. Fluxo Interno do Endpoint

```
POST /api/playground/chat
  │
  ├─ 1. Autenticação: require_crm_access (token normal do operador)
  │       → user_id extraído do token
  │       → ai_profile_id validado: deve pertencer ao mesmo user_id no backend-core
  │
  ├─ 2. Gestão do Lead Sandbox
  │       se lead_id fornecido:
  │           → SELECT * FROM leads WHERE id=? AND user_id=? AND is_playground=1
  │           → 404 se não encontrado ou não é sandbox
  │       se lead_id=null:
  │           → INSERT INTO leads (..., is_playground=1, category='qualification', origin='playground')
  │               phone = f"playground_{uuid4().hex[:8]}"  ← número fictício único
  │               companyName = "Playground Test"
  │               contactName = "Lead de Teste"
  │       se reset=true:
  │           → DELETE FROM messages WHERE lead_id=? AND user_id=?
  │           → DELETE FROM lead_qualification_state WHERE lead_id=?
  │           → UPDATE leads SET category='qualification' WHERE id=?
  │
  ├─ 3. Guardar Mensagem Inbound (histórico)
  │       → INSERT INTO messages (lead_id, channel='playground', body=message, model='inbound')
  │
  ├─ 4. Fetch AI Profile do Core
  │       → GET {CORE_API_BASE}/ai-profiles/{ai_profile_id}?user_id={user_id}  (service token)
  │       → Valida que pertence ao user_id correto
  │
  ├─ 5. Build Context Bundle (sem WhatsApp)
  │       → Reutiliza lógica de build_context_bundle_from_inbound mas sem InboundEvent real:
  │           - lead: SELECT * FROM leads WHERE id=?
  │           - history: get_recent_history(lead_id)
  │           - ai_profile: do passo 4
  │           - playbook: get_playbook(template_key)
  │           - entitlements: GET /me/entitlements (service token)
  │           - qualification_state: get_qualification_state(lead_id)
  │           - knowledge_items: SELECT ... FROM knowledge_items WHERE user_id=?
  │           - metadata: channel='playground', received_at=now()
  │
  ├─ 6. Chamar Decision Engine
  │       → decision_engine.decide(context_bundle)  ← sem modificação
  │       → Retorna DecisionOutput com mother_decision, child_result, next_action
  │
  ├─ 7. Persistir Estado Pós-Decisão
  │       → se child_result.field: upsert_qualification_state(lead_id, ...)
  │       → se DecisionOutput.suggested_category: UPDATE leads SET category=?
  │       → INSERT INTO messages (model='outbound', body=message_to_send)  ← histórico da resposta
  │
  └─ 8. Construir e Retornar Response
          → Monta PlaygroundChatResponse com todos os campos acima
```

---

## 4. Dependências do Pipeline Real e Como Contorná-las

| Dependência | No pipeline real | No playground |
|---|---|---|
| `fetch_core_whatsapp_connection_resolve(instance_id)` | Valida conexão WhatsApp ativa | **Bypass total** — não há instância WhatsApp |
| `normalize_phone(sender)` | Valida número E.164 | **Bypass** — usa phone fictício gerado na criação do lead |
| `insert_inbound_event()` | Deduplicação por (provider, instance_id, event_id) | **Bypass** — cada chamada POST é única por design |
| `try_register_conversation()` | Conta quota mensal de conversas Orion | **Bypass** — leads sandbox não consomem quota |
| `stop_followup_on_inbound_reply()` | Para follow-ups agendados | **Bypass** — leads sandbox não têm follow-up agendado |
| `create_job()` + fila assíncrona | Enfileira job para executor | **Bypass** — chama `decision_engine.decide()` diretamente e síncrono |
| `build_context_bundle_from_inbound(event)` | Requer `InboundEvent` com instance_id, provider | **Nova função** `build_context_bundle_for_playground()` com os mesmos campos mas sem provider/instance |
| `fetch_core_ai_profile_resolve(user_id)` | Resolve perfil pelo user_id do operador (service-to-service) | **Substituído** por fetch direto do ai_profile_id (mais preciso) |
| Executor worker (backend-executors) | Executa o job de forma assíncrona | **Bypass** — chamada síncrona no endpoint do playground |

### O que NÃO precisa ser contornado (reutilizado intacto)

- `decision_engine.decide()` — core da IA, sem dependência de WhatsApp
- `get_qualification_state()` / `upsert_qualification_state()` — gestão de estado
- `get_recent_history()` — histórico de mensagens
- `get_playbook()` — carregamento de playbook
- `compute_4p_scores()` — pontuação 4P
- `_build_prompt()`, `_build_tone_block()`, `_build_offer_pack_summary()` — construção de prompt
- Tabelas: `leads`, `messages`, `lead_qualification_state`, `knowledge_items`

---

## 5. Isolamento de Leads Sandbox

### Decisão: Flag `is_playground` na tabela `leads`

**Opção escolhida:** adicionar coluna `is_playground INTEGER NOT NULL DEFAULT 0` à tabela `leads`.

**Motivo:** reutiliza toda a infraestrutura existente (qualification_state, messages, prospection_logs) sem duplicação de schema. A coluna flag é o menor esforço com o maior isolamento.

**Alternativas rejeitadas:**
- Tabela separada `playground_leads`: duplicaria todo o schema, forçaria fork de todos os serviços de query.
- Leads temporários com cleanup automático: introduz complexidade de TTL/cronjob e pode limpar dados úteis de debug.

### Regras de Isolamento

1. Leads sandbox têm `is_playground = 1`.
2. Phone gerado: `playground_{uuid4().hex[:8]}` — garante unicidade sem conflito com números reais.
3. Origin: `playground`.
4. Nenhuma query de negócio real (Kanban, follow-up, prospecção) filtra `is_playground=1` — ficam invisíveis nas vistas normais graças ao WHERE do user_id e a ausência de filtro explícito (leads reais nunca têm esse flag).
5. Leads sandbox **não consomem quota** de conversas Orion.
6. Leads sandbox **não disparam follow-up automático**.
7. Cleanup opcional: `DELETE FROM leads WHERE is_playground=1 AND created_at < datetime('now', '-30 days')` — pode ser um endpoint admin separado.

---

## 6. Migração de Banco de Dados

### `backend-crm/migrations/`

```sql
-- Ficheiro: add_is_playground_to_leads.sql
ALTER TABLE leads ADD COLUMN is_playground INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_leads_is_playground ON leads (user_id, is_playground);
```

Via `ensure_column()` em `db.py` (padrão idempotente do projecto):

```python
ensure_column(conn, "leads", "is_playground", "INTEGER NOT NULL DEFAULT 0")
```

Nenhuma outra tabela precisa de migração — `lead_qualification_state`, `messages`, e `prospection_logs` ligam por `lead_id` e funcionam igual para leads sandbox.

---

## 7. Nova Função: `build_context_bundle_for_playground()`

Localização: `backend-crm/services/ai_orchestrator/orchestrator.py`

```python
async def build_context_bundle_for_playground(
    user_id: int,
    ai_profile: Dict[str, Any],    # já carregado pelo endpoint
    lead_id: int,
    message_text: str,
) -> ContextBundle:
    """
    Constrói um ContextBundle para o playground, sem InboundEvent nem WhatsApp.
    Reutiliza toda a lógica de normalização de agent_mode, playbook, e histórico.
    """
    lead = _load_lead(user_id, lead_id)
    history = get_recent_history(lead_id)
    template_key = ai_profile.get("template_key", "")
    agent_mode = _normalize_agent_mode_for_bundle(ai_profile, template_key)
    playbook = get_playbook(template_key)
    playbook = apply_mode_overrides(playbook, agent_mode)
    presentation = _resolve_presentation_contract(ai_profile, agent_mode)
    qualification_state = get_qualification_state(lead_id)
    knowledge_items = _load_knowledge_items(user_id)

    return ContextBundle(
        user_id=user_id,
        entitlements={},           # playground não tem guardrails de entitlement
        ai_profile=ai_profile,
        playbook=playbook,
        lead=lead,
        history=history,
        next_action="reply",
        metadata={
            "channel": "playground",
            "received_at": datetime.utcnow().isoformat(),
            "presentation_variant": presentation["variant"],
            "hybrid_flow_style": presentation.get("hybrid_flow_style"),
            "lead_origin": "playground",
            "inbound_message_text": message_text,
        },
        conversation_goal="qualify" if len(history) <= 1 else "advance",
        qualification_state=qualification_state,
        knowledge_items=knowledge_items,
    )
```

---

## 8. Fetch do AI Profile pelo ID (novo helper)

O pipeline real usa `fetch_core_ai_profile_resolve(user_id)` que devolve o único perfil activo do utilizador. O playground precisa de buscar um perfil específico por `ai_profile_id`.

Nova função em `backend-crm/services/core_client.py` (ou equivalente):

```python
async def fetch_core_ai_profile_by_id(ai_profile_id: int, user_id: int) -> Dict[str, Any]:
    """
    Busca um AiProfile específico pelo ID via service token.
    Valida que pertence ao user_id.
    """
    url = f"{CORE_API_BASE}/api/ai-profiles/{ai_profile_id}"
    headers = {"X-Service-Token": CORE_SERVICE_TOKEN}
    resp = await http_client.get(url, headers=headers)
    resp.raise_for_status()
    profile = resp.json()
    if profile["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="ai_profile_id não pertence ao utilizador")
    return profile
```

> **Nota:** verificar a rota exacta no `backend-core/routes/ai_profiles.py` antes de implementar.

---

## 9. Autenticação

O endpoint usa `require_crm_access` — o mesmo mecanismo das outras rotas do backend-crm. O operador autentica com o seu token JWT normal. Não há endpoint público sem autenticação.

O `user_id` extraído do token é usado para:
1. Validar que `ai_profile_id` pertence ao utilizador.
2. Criar/buscar leads sandbox com o `user_id` correcto.
3. Garantir que o operador só vê os seus próprios leads sandbox.

---

## 10. Plano de Implementação

### Fase 1 — Infraestrutura de Dados (1-2h)

| Tarefa | Ficheiro | Descrição |
|---|---|---|
| 1.1 | `backend-crm/db.py` | Adicionar `ensure_column(conn, "leads", "is_playground", "INTEGER NOT NULL DEFAULT 0")` no startup |
| 1.2 | `backend-crm/migrations/` | Criar `add_is_playground_to_leads.sql` para referência |

### Fase 2 — Core API Helper (1h)

| Tarefa | Ficheiro | Descrição |
|---|---|---|
| 2.1 | `backend-crm/services/core_client.py` (ou equivalente) | Criar `fetch_core_ai_profile_by_id(ai_profile_id, user_id)` |
| 2.2 | `backend-core/routes/ai_profiles.py` | Verificar/adicionar rota `GET /api/ai-profiles/{id}` acessível via service token |

### Fase 3 — Context Bundle para Playground (1-2h)

| Tarefa | Ficheiro | Descrição |
|---|---|---|
| 3.1 | `backend-crm/services/ai_orchestrator/orchestrator.py` | Criar `build_context_bundle_for_playground()` |
| 3.2 | `backend-crm/services/ai_orchestrator/orchestrator.py` | Extrair `_load_knowledge_items(user_id)` como helper reutilizável |

### Fase 4 — Rota do Playground (2-3h)

| Tarefa | Ficheiro | Descrição |
|---|---|---|
| 4.1 | `backend-crm/routes/playground.py` | Criar ficheiro novo com router FastAPI |
| 4.2 | `backend-crm/routes/playground.py` | Implementar `POST /api/playground/chat` com toda a lógica de fluxo descrita na secção 3 |
| 4.3 | `backend-crm/app.py` (ou `main.py`) | Registar `playground_router` na app FastAPI |

### Fase 5 — Modelos Pydantic (0.5h)

| Tarefa | Ficheiro | Descrição |
|---|---|---|
| 5.1 | `backend-crm/routes/playground.py` | Definir `PlaygroundChatRequest` e `PlaygroundChatResponse` (ver secção 2) |

### Fase 6 — Testes Manuais (1h)

| Tarefa | Descrição |
|---|---|
| 6.1 | Criar lead sandbox via `lead_id=null`, verificar `is_playground=1` no DB |
| 6.2 | Enviar 3 mensagens sequenciais ao mesmo `lead_id`, verificar que o histórico é mantido e o estado de qualificação evolui |
| 6.3 | Testar `reset=true`, verificar limpeza de histórico e estado |
| 6.4 | Verificar que o lead sandbox não aparece no Kanban do frontend |

### Fase 7 — Cleanup Endpoint (opcional, 0.5h)

| Tarefa | Ficheiro | Descrição |
|---|---|---|
| 7.1 | `backend-crm/routes/playground.py` | `DELETE /api/playground/leads/{lead_id}` — elimina lead sandbox e dados associados |
| 7.2 | `backend-crm/routes/playground.py` | `GET /api/playground/leads` — lista leads sandbox do utilizador |

---

## 11. Riscos e Decisões

### Risco 1: Rota do AI Profile no backend-core pode não existir via service token

**Problema:** `fetch_core_ai_profile_by_id()` precisa de uma rota no `backend-core` que aceite `X-Service-Token`. Pode não existir ou estar restrita a token de utilizador.

**Mitigação:** Antes de implementar a fase 2, verificar `backend-core/routes/ai_profiles.py`. Se não existir, criar rota `GET /api/ai-profiles/{id}` com `Depends(require_service_token)`.

---

### Risco 2: `decision_engine.decide()` pode estar no backend-executors, não no backend-crm

**Problema:** O `decision_engine.py` está em `backend-executors`. Para o playground no `backend-crm` o chamar directamente, seria necessária uma chamada HTTP interna (entre serviços) ou mover o módulo.

**Decisão recomendada:** Chamar `backend-executors` via HTTP interno (`GET /api/whatsapp/execution-context` + `POST /api/internal/jobs/{job_id}/complete`). Mas isto recria o sistema de jobs.

**Alternativa preferida:** Expor um endpoint de execução síncrona no `backend-executors`:

```
POST /api/internal/playground/decide
Body: { context_bundle: ContextBundle }
Response: DecisionOutput
```

O playground no `backend-crm` monta o `ContextBundle` e faz uma chamada HTTP síncrona ao `backend-executors`. Evita duplicar o `decision_engine` e mantém a separação de responsabilidades.

> **Esta é a decisão mais importante a tomar antes de implementar.**

---

### Risco 3: Leads sandbox aparecerem no Kanban do frontend

**Problema:** Se o frontend busca todos os leads do utilizador sem filtro `is_playground`, os leads sandbox aparecem no Kanban.

**Mitigação:** Verificar o query em `backend-crm/routes/leads.py`. Adicionar `AND is_playground = 0` (ou `AND (is_playground IS NULL OR is_playground = 0)`) nas queries de listagem de leads. Não afecta leads existentes (valor DEFAULT 0).

---

### Risco 4: Quota de conversas Orion consumida por leads sandbox

**Problema:** `try_register_conversation()` pode ser chamado inadvertidamente para leads sandbox.

**Mitigação:** O playground **não chama** `try_register_conversation()` — bypass total, como descrito na secção 4.

---

### Risco 5: `build_context_bundle_for_playground()` divergir do pipeline real ao longo do tempo

**Problema:** Se o `build_context_bundle_from_inbound()` for actualizado com nova lógica (novos campos do ai_profile, nova lógica de playbook), o playground pode ficar desactualizado.

**Mitigação a longo prazo:** Refactorizar `build_context_bundle_from_inbound()` e `build_context_bundle_for_playground()` para partilharem um `_build_context_bundle_core()` com os parâmetros comuns. O playground e o inbound apenas diferem na fonte do ai_profile e na ausência de InboundEvent.

---

## 12. Exemplos de Uso

### Primeira mensagem (cria lead sandbox)

```bash
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": 7,
    "message": "Olá, vi o vosso anúncio e tenho interesse",
    "lead_id": null
  }'
```

### Segunda mensagem (continua conversa)

```bash
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": 7,
    "message": "Sou o dono do negócio e decido sozinho",
    "lead_id": 42
  }'
```

### Reset da conversa

```bash
curl -X POST http://localhost:8000/api/playground/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_profile_id": 7,
    "message": "Olá, começo de novo",
    "lead_id": 42,
    "reset": true
  }'
```

---

## 13. Estrutura de Ficheiros a Criar/Alterar

```
backend-crm/
├── routes/
│   └── playground.py                          ← NOVO
├── services/
│   └── ai_orchestrator/
│       └── orchestrator.py                    ← ALTERAR (nova função)
├── db.py                                      ← ALTERAR (ensure_column)
└── migrations/
    └── add_is_playground_to_leads.sql         ← NOVO (referência)

backend-executors/
└── app/
    └── routes/
        └── playground_internal.py             ← NOVO (se opção HTTP interna)
```

---

## 14. Critérios de Aceite

- [ ] `POST /api/playground/chat` retorna `DecisionOutput` completo (mother + child + trace)
- [ ] Lead sandbox criado com `is_playground=1` não aparece no Kanban normal
- [ ] Chamadas sequenciais ao mesmo `lead_id` mantêm histórico e estado de qualificação entre chamadas
- [ ] `reset=true` limpa histórico e qualification_state antes de processar
- [ ] Zero dependência de WhatsApp, UazAPI, ou webhooks
- [ ] Zero consumo de quota de conversas Orion
- [ ] Autenticado com token JWT normal do operador
- [ ] `ai_profile_id` de outro utilizador retorna 403

---

*Documento gerado em 2026-03-29. Revisar Risco 2 (localização do decision_engine) antes de iniciar implementação.*
