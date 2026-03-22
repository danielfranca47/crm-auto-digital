# SCHEMA_AGENTS.md — Documentação de Schema dos Endpoints de Agente

> Análise técnica do código-fonte realizada em 2026-03-22.
> Nenhum código foi alterado — documento de referência apenas.

---

## AVISO IMPORTANTE — Dois Conceitos Distintos

O sistema tem **dois endpoints completamente diferentes** que ambos se chamam "agente":

| Conceito | Endpoint | Serviço | O que representa |
|---|---|---|---|
| **Agente Local** | `GET /api/agents/` | `backend-crm` (porta 8000) | Processo de execução local (runner) que processa jobs de envio |
| **Perfil de IA** | `GET /ai-profiles/me` | `backend-core` (porta 8001) | Configuração de personalidade e comportamento do agente de IA |

**Para o frontend de configuração do agente, ambos os endpoints são necessários.** Eles não se sobrepõem — um descreve a infraestrutura, o outro descreve o comportamento.

---

## 1. Schema do `GET /api/agents/` — Agente Local (Infrastructure Layer)

### Endpoint

```
GET /api/agents/
Host: backend-crm (porta 8000)
Authorization: Bearer <jwt>
Query param opcional: seconds=90  (janela de tempo para considerar "online", 30–600)
```

**Retorna:** `Array` de objetos `AgentOut`

### Schema de um item da lista

| Campo | Tipo | Valor de exemplo | Descrição |
|---|---|---|---|
| `agent_id` | `string` | `"a1b2c3d4e5f6..."` | UUID do agente (32 chars hex). Mapeado internamente do campo `id` via alias Pydantic |
| `name` | `string \| null` | `"Agent Alpha"` | Nome amigável atribuído ao provisionar o agente |
| `capabilities` | `string[] \| null` | `["whatsapp.send.local"]` | Lista de tipos de job que este runner consegue executar (deserializado de JSON no banco) |
| `status` | `string \| null` | `"online"` | Estado atual: `"online"`, `"offline"` ou `"disabled"` |
| `last_seen_at` | `string (ISO-8601) \| null` | `"2026-03-22T15:30:45"` | Último heartbeat recebido (normalizado de espaço para `T`) |
| `revoked` | `boolean` | `false` | `true` se o agente foi revogado (campo derivado de `revoked_at != NULL`) |
| `online` | `boolean` | `true` | `true` se `last_seen_at >= agora - seconds` (calculado dinamicamente na requisição) |

### Valores possíveis de `capabilities`

```json
["whatsapp.send.local"]        // Envio de WhatsApp pelo runner local
["whatsapp.inbound.n8n"]       // Processamento de inbound via n8n
["whatsapp.followup.tick"]     // Tick de follow-up agendado
["maps.search.local"]          // Busca no Google Maps local
["maps.enrich.local"]          // Enriquecimento de lead via Maps
```

### Valores possíveis de `status`

| Valor | Significado |
|---|---|
| `"online"` | Agente ativo e reportando dentro da janela de tempo configurada |
| `"offline"` | Agente não reporta dentro da janela (mas não foi revogado) |
| `"disabled"` | Agente foi revogado (`revoked_at != NULL`) — ignorado pelo job scheduler |

### Campos do banco que NÃO aparecem na resposta da API

| Campo | Motivo da ausência |
|---|---|
| `token` | Removido por `_sanitize_agent()` por segurança (`routes/agents.py`) |
| `user_id` | Derivado do JWT; não exposto |
| `created_at` | Filtrado na serialização para `AgentOut` |
| `updated_at` | Filtrado na serialização para `AgentOut` |
| `last_seen` | Campo legado, substituído por `last_seen_at` |
| `revoked_at` | Convertido para o booleano `revoked` |

### Exemplo de resposta completa

```json
[
  {
    "agent_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "name": "Agent Alpha",
    "capabilities": ["whatsapp.send.local", "maps.search.local"],
    "status": "online",
    "last_seen_at": "2026-03-22T15:30:45.123456",
    "revoked": false,
    "online": true
  }
]
```

---

## 2. Schema do `GET /ai-profiles/me` — Perfil de IA (Business Layer)

### Endpoint

```
GET /ai-profiles/me
Host: backend-core (porta 8001)
Authorization: Bearer <jwt>
```

**Retorna:** Objeto único `AIProfileOut`

### Schema completo

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `id` | `integer` | sim | ID interno do perfil |
| `user_id` | `integer` | sim | ID do usuário dono do perfil |
| `template_key` | `string` | sim | Template base do agente (ver valores abaixo) |
| `name` | `string` | sim | **Nome do agente** — como ele se apresenta ao lead |
| `brand_name` | `string` | sim | **Nome da empresa/marca** que o agente representa |
| `tone_of_voice` | `string` | sim | **Tom de comunicação** (texto livre — ex: "formal", "descontraído") |
| `timezone` | `string \| null` | não | Fuso horário do agente (padrão: `"UTC"`) |
| `niche` | `string` | sim | Nicho de mercado em que atua |
| `target_audience` | `string` | sim | Descrição do público-alvo |
| `offer_description` | `string` | sim | Descrição completa da oferta/produto |
| `goals` | `string` | sim | Objetivos do agente (texto livre — ex: "qualificar e agendar reunião") |
| `custom_instructions` | `string \| null` | não | **Instruções customizadas** — texto adicional injetado no system prompt do LLM |
| `agent_mode` | `string (enum)` | não | **Forma de vender** (ver enum abaixo; padrão: `"sdr_scheduler"`) |
| `presentation_variant` | `string (enum) \| null` | não | Variante de apresentação (ver enum abaixo) |
| `hybrid_flow_style` | `string (enum) \| null` | não | Estilo de fluxo híbrido (ver enum abaixo) |
| `offer_pack` | `object \| null` | não | **JSON de configuração da oferta** (ver sub-campos abaixo) |
| `identity_mode` | `string (enum)` | não | **Modo de identidade do agente** (ver enum abaixo; padrão: `"human_agent"`) |
| `handoff_policy` | `string (enum)` | não | Política de handoff para humano (ver enum abaixo; padrão: `"keep_active_notify"`) |
| `handoff_custom_text` | `string \| null` | não | Mensagem customizada enviada ao lead no momento do handoff |
| `requires_handoff` | `boolean` | não | Se o fluxo sempre exige handoff ao final (padrão: `false`) |
| `human_in_loop` | `boolean` | não | Se humano deve aprovar mensagens antes do envio (padrão: `false`) |
| `created_at` | `string (ISO-8601)` | sim | Timestamp de criação |
| `updated_at` | `string (ISO-8601)` | sim | Timestamp de última atualização |

---

## 3. Sub-campos dos campos Enum e JSON

### `template_key` — Templates disponíveis

| Valor | Nome display | Quando usar |
|---|---|---|
| `"sdr_padrao"` | SDR Padrão | Agente de vendas geral, qualificação e agendamento |
| `"consultor_especialista"` | Consultor Especialista | Processos longos, diagnóstico e educação |
| `"closer_agressivo"` | Closer Agressivo Controlado | Foco em fechamento direto |
| `"hybrid_scheduler"` | Híbrido Agendador | Agendamento com autonomia operacional |

### `agent_mode` — Forma de vender

| Valor | Descrição |
|---|---|
| `"sdr_scheduler"` | SDR focado em agendamento (padrão) |
| `"closer"` | Foco em fechamento |
| `"consultivo"` | Atendimento consultivo aprofundado (6 campos de qualificação obrigatórios) |
| `"agenda"` | Foco em agendar (4 campos de qualificação obrigatórios) |
| `"direto"` | Fechamento direto (3 campos de qualificação obrigatórios) |

### `presentation_variant` — Variante de apresentação

| Valor | Descrição |
|---|---|
| `"sales"` | Apresentação com oferta direta |
| `"scheduler"` | Apresentação focada em agendamento primeiro |
| `null` | Sem variante específica (usa default do template) |

### `hybrid_flow_style` — Estilo do fluxo híbrido

| Valor | Descrição |
|---|---|
| `"offer_then_schedule"` | Apresenta oferta primeiro, depois agenda |
| `"schedule_then_offer"` | Agenda primeiro, apresenta oferta depois |
| `null` | Não aplicável (só relevante quando `presentation_variant` combina com híbrido) |

### `identity_mode` — Modo de identidade

| Valor | Como o agente se apresenta |
|---|---|
| `"human_agent"` | Como um humano membro do time (padrão) |
| `"virtual_assistant"` | Como assistente virtual explicitamente |
| `"user_clone"` | Como clone do próprio usuário/vendedor |

### `handoff_policy` — O que fazer ao escalar para humano

| Valor | Comportamento |
|---|---|
| `"disable_bot"` | Desabilita o bot completamente ao fazer handoff |
| `"keep_active_notify"` | Mantém bot ativo mas notifica o operador (padrão) |
| `"ignore"` | Não faz nada — handoff apenas implícito |

### `offer_pack` — Sub-campos do JSON de oferta

O campo `offer_pack` é um objeto JSON livre, armazenado como `JSON` no SQLAlchemy. A normalização garante que seja sempre um `dict` ou `null`. A estrutura interna **não tem schema fixo** — é preenchida conforme a configuração de cada usuário. Campos comuns observados no código:

| Sub-campo (inferido) | Tipo esperado | Descrição |
|---|---|---|
| *(livre)* | *qualquer* | Este campo é totalmente flexível — o backend aceita qualquer dict válido. A estrutura é definida pelo usuário e injetada no contexto do LLM pelo orquestrador. |

> **Nota:** Para garantir que um sub-campo específico apareça aqui, seria necessário analisar como o `offer_pack` é consumido no `backend-crm/services/ai_orchestrator/orchestrator.py`.

---

## 4. Mapeamento: necessidade do frontend → campo exato da API

| O frontend precisa exibir/editar | Endpoint | Campo exato |
|---|---|---|
| **Nome do agente** (como se apresenta ao lead) | `GET /ai-profiles/me` | `name` |
| **Nome da empresa** | `GET /ai-profiles/me` | `brand_name` |
| **Forma de vender** (consultivo, passivo, ativo) | `GET /ai-profiles/me` | `agent_mode` (enum: `sdr_scheduler`, `closer`, `consultivo`, `agenda`, `direto`) |
| **Modo de identidade** (humano do time, assistente virtual, clone) | `GET /ai-profiles/me` | `identity_mode` (enum: `human_agent`, `virtual_assistant`, `user_clone`) |
| **Tom de comunicação** (normal, formal, descontraído) | `GET /ai-profiles/me` | `tone_of_voice` (texto livre — não é enum, o usuário escreve) |
| **Texto completo do perfil / system prompt** | `GET /ai-profiles/me` | Combinação de: `offer_description` + `goals` + `custom_instructions` (o orquestrador monta o prompt a partir desses campos) |
| **Lista de palavras-chave de opt-out** | ❌ **Não existe** | Não há campo para isso. Ver seção 5. |
| **Comportamento ao receber mídia inválida** | ❌ **Não existe** | Não há campo para isso. Ver seção 5. |

> **Atenção:** O "system prompt" não é um campo único e armazenado. Ele é construído dinamicamente pelo `backend-crm/services/ai_orchestrator/orchestrator.py` combinando múltiplos campos do `ai_profile`. O que o usuário edita diretamente é `custom_instructions` — o resto é estruturado.

---

## 5. Configurações existentes no sistema ainda não mapeadas pelo frontend

### Configurações do `ai_profile` que provavelmente estão ocultas ou subutilizadas:

| Campo | O que controla | Status provável no frontend |
|---|---|---|
| `requires_handoff` | Se todo lead exige handoff ao final do fluxo | Provavelmente não exposto — boolean simples de alto impacto |
| `human_in_loop` | Se mensagens precisam de aprovação antes de enviar | Provavelmente não exposto — feature enterprise relevante |
| `handoff_custom_text` | Mensagem enviada ao lead no momento do handoff | Provavelmente não exposto — configurável mas raramente visto |
| `hybrid_flow_style` | Ordem do fluxo híbrido (oferta antes/depois de agendar) | Só relevante em modo híbrido; possível que não apareça se `template_key != hybrid_scheduler` |
| `presentation_variant` | Abordagem de apresentação (`sales` vs `scheduler`) | Pode estar oculto atrás de `template_key` em UX simplificada |
| `timezone` | Fuso horário do agente (afeta horários de envio e agendamento) | Frequentemente esquecido em UIs de configuração |

### Configurações do `agents` (runner) sem UI evidente:

| Campo | O que controla |
|---|---|
| `capabilities` | Quais tipos de job o runner local pode processar — lista editável mas raramente exposta ao usuário |

### Configurações que o DIAGNOSTICO identificou como ausentes no sistema:

| Configuração desejada | Status | Onde deveria ficar |
|---|---|---|
| Palavras-chave de opt-out | ❌ Não implementado | Novo campo em `ai_profile` — ex: `opt_out_keywords: string[]` |
| Comportamento para mídia inválida | ❌ Não implementado | Novo campo em `ai_profile` — ex: `media_fallback_message: string` |
| Janela de tempo para retomada de qualificação | ❌ Não implementado | Novo campo em `ai_profile` — ex: `qualification_resume_window_hours: int` |
| Thresholds de follow-up configuráveis por agente | ⚠️ Hardcoded no código | Poderia migrar para `ai_profile` como `followup_schedule: object` |

---

## 6. Fluxo de leitura recomendado para o frontend

Para montar a tela de configuração de um agente, o frontend deve chamar **dois endpoints em paralelo**:

```
// Dados de infraestrutura (runner status, capabilities)
GET /api/agents/                   → backend-crm:8000
Authorization: Bearer <token>

// Dados de configuração de IA (personalidade, comportamento)
GET /ai-profiles/me                → backend-core:8001
Authorization: Bearer <mesmo token>
```

Para salvar alterações na configuração de IA:
```
PUT /ai-profiles/me                → backend-core:8001
Content-Type: application/json
Body: { ...campos a atualizar... }
```

> O `PUT /ai-profiles/me` aceita atualização parcial — apenas campos presentes no body são alterados (`exclude_unset=True` na serialização, `backend-core/app/api/ai_profiles.py:262`).

---

*Gerado por análise de código-fonte — sem alterações no sistema*
*Branch: `feature/etapa-8-n8n-orion` — backend-crm + backend-core*
