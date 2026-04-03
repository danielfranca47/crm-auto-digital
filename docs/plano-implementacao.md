# Plano de Implementação — Qualificação Dinâmica e AI Profile como Fonte Única de Verdade

> Gerado em: 2026-04-03
> Baseado em: `pretencoes.md`, `solucoes.md`, diagnóstico do código atual

---

## Diagnóstico Executivo

O sistema atual tem a estrutura correta no modelo de dados (`qualification_required_fields` existe no AIProfile, o CRM já lê esse campo), mas tem **quatro** camadas de contradição que impedem que a intenção chegue ao comportamento:

| Camada | Problema real |
|---|---|
| **Backend — guardrails** | `_MIN_REQUIRED_FIELDS` hardcoded em `qualification_guardrails.py` sobrescreve a escolha do usuário quando o AI Profile não tem override |
| **Backend — prompting** | `decision_engine.py` força `route_to="qualification"` antes de responder o lead (C1, C2, C7 de `solucoes.md`) |
| **Frontend — UI** | `CamadaQualificacao.tsx` não diferencia obrigatório vs opcional, não adapta ao `agent_mode`, não permite campos personalizados |
| **Dados — dois sistemas paralelos** | `f1/f2/f3_questions` e `qualification_required_fields` são desconexos — um diz o que perguntar, o outro diz o que checar, mas nenhum fala com o outro |

O plano é dividido em **5 fases sequenciais**, do menor risco ao maior esforço, cada uma entregando valor independente.

---

## Diagnóstico do Contrato de Qualificação (problema central)

Este é o ponto mais importante do plano e precisava ser nomeado com clareza.

### O estado atual em `agente.ts`

```typescript
// Camada 2 — Qualificação (em AgentConfig)
f1_questions: string[];   // armazenadas em offer_pack — só texto, ex: "Você está em SP?"
f2_questions: string[];   // armazenadas em offer_pack — só texto
f3_questions: string[];   // armazenadas em offer_pack — só texto

// Camada 2 — Qualificação avançada
qualification_required_fields: string[] | null;  // coluna separada — só keys, ex: ["service_interest"]
```

### O problema

Estes são **dois sistemas completamente desconexos**:

- `f1/f2/f3_questions` → dizem ao agente **o que perguntar** (texto da pergunta em linguagem natural). Vivem no `offer_pack` como arrays de strings sem estrutura.
- `qualification_required_fields` → dizem ao guardrail **o que verificar** (chaves de campo como `"availability_window"`). Vivem em coluna separada do AI Profile.

Não há nenhum link entre os dois. O agente pode ter configurado a pergunta "Qual horário funciona para você?" em `f2_questions`, mas o guardrail verifica `availability_window` em `qualification_required_fields` — e estes dois nunca se falam. O resultado é que:

1. O usuário preenche as perguntas em F1/F2/F3 achando que está configurando a qualificação
2. O guardrail ignora completamente essas perguntas e usa sua própria lista de chaves
3. Os campos hardcoded dos guardrails não têm correspondência com as perguntas do usuário

### A solução: um contrato unificado com semântica diferente por agente

Os três arquétipos de agente têm intenções distintas para a qualificação:

| Agente | `agent_mode` | Semântica das perguntas |
|---|---|---|
| **A1 — SDR** | `sdr_scheduler` | Pipeline sequencial: F1 filtra perfil, F2 aprofunda intenção, F3 qualifica 4Ps. A estrutura de filtros é parte do método de vendas. |
| **A2 — Direto** | `closer` / `direto` | Lista plana. Poucas perguntas objetivas, sem estágios. Foco em fechar. |
| **A3 — Híbrido** | `agenda` | Lista plana. Foco em capturar disponibilidade para agendar. |

**A solução unifica o schema de dados mas preserva a UX por agente:**

```typescript
interface QualificationField {
  key: string;           // "availability_window" | "custom_nome_do_pet" | ...
  label: string;         // "Disponibilidade" | "Nome do pet"
  question?: string;     // pergunta para modo ativo: "Qual horário funciona?"
  passive_hint?: string; // dica para modo passivo: "Inferir se lead mencionar horário"
  mode: 'required' | 'optional' | 'off';
  group?: 'f1' | 'f2' | 'f3'; // APENAS para SDR — qual filtro este campo pertence
}

qualification_fields: QualificationField[];
```

O campo `group` é o que permite ao SDR continuar tendo a UI de "Filtro 1 / Filtro 2 / Filtro 3" — os filtros são uma **vista agrupada** dos mesmos campos. Para os outros agentes, `group` é ignorado e a UI exibe lista plana.

**O que cada campo faz no sistema:**

| `mode` | Modo ativo | Modo passivo | Guardrail (Kanban) |
|---|---|---|---|
| `required` | Agente pergunta ativamente usando `question` | Agente tenta inferir; se não conseguir, sugere suavemente | Bloqueia avanço se não preenchido |
| `optional` | Agente pergunta se surgir oportunidade | Agente capta passivamente se o lead mencionar | Não bloqueia |
| `off` | Agente ignora | Agente ignora | Ignora |

**Para campos do sistema (predefinidos):** `key` é um slug padrão como `"availability_window"`. O extraction engine já sabe como extraí-los.

**Para campos personalizados:** `key` é `"custom_" + slug(label)`. O agente usa `question` para perguntar e `key` para armazenar em `data_json` de `lead_qualification_state`.

### Backward compatibility

- `qualification_required_fields` passa a ser **derivado** de `qualification_fields.filter(f => f.mode === 'required').map(f => f.key)`. Backend-crm e executores continuam lendo `qualification_required_fields` sem qualquer alteração.
- `f1_questions`, `f2_questions`, `f3_questions` em `offer_pack` ficam como campos legados derivados. O orquestrador passa a preferir `qualification_fields[].question` por agente. Para SDR, `f1_questions` = questions de campos com `group='f1'`, e assim por diante.
- Registros antigos continuam funcionando via fallback até o usuário salvar pela nova UI.

---

## O que foi decidido (e porquê)

### Decisão 1: `qualification_required_fields=null` passa a significar "sem campos obrigatórios"
Hoje, `null` faz fallback para `_MIN_REQUIRED_FIELDS`. A intenção declarada é que o AI Profile seja a única fonte de verdade. Se o usuário não configurou nenhum campo, o sistema não deve inventar um. O onboarding/UI oferece sugestões por modo, mas a decisão final é do usuário.

### Decisão 2: Unificar f1/f2/f3_questions + qualification_required_fields em `qualification_fields`
Em vez de adicionar uma terceira estrutura separada (`qualification_optional_fields`), unificar tudo num único array `QualificationField[]`. Cada campo tem: `key`, `label`, `question` (para modo ativo), `passive_hint` (para modo passivo), `mode: required|optional|off` e `group?: f1|f2|f3`. O campo `group` preserva a estrutura de filtros do SDR sem afetar outros agentes. `qualification_required_fields` passa a ser derivado desta estrutura, mantendo backward compatibility com guardrails existentes. **A UI do SDR (cards F1/F2/F3) não muda — continua igual, mas agora cada pergunta dentro do filtro tem a marcação de obrigatória/opcional.**

### Decisão 3: Campos personalizados via `key = "custom_" + slug(label)`
Usuário pode adicionar campos livres além dos predefinidos. Frontend gera a key automaticamente a partir do label. O extraction engine do executor identifica campos `custom_*` e usa o `question` configurado para extraí-los via LLM, armazenando o resultado no `data_json` de `lead_qualification_state`.

### Decisão 4: Adiar P2 (separar `reply_mode` de `route_to`) para depois das fases 1–3
P2 tem o maior esforço e o maior risco de instabilidade no schema da LLM. P1 + P7 + P3 (de `solucoes.md`) resolvem o comportamento imediato sem redesenhar a arquitetura. P2 entra como Fase 4 (melhoria arquitetural).

### Decisão 5: `response_style` default passa para `"passive"` apenas para novos usuários
Mudar o default para todos quebraria silenciosamente usuários existentes. A mudança se aplica: (a) novos registros de AI Profile, (b) onboarding wizard, (c) usuários que explicitamente não definiram `response_style`. Usuários existentes com `response_style` já salvo não são afetados.

---

## Fase 1 — Backend: AI Profile como Única Fonte de Verdade
**Duração estimada:** 1 sessão  
**Risco:** Baixo — mudança aditiva + remoção de fallback controlada  
**Valor entregue:** Guardrails do Kanban e do executor respeitam 100% o que o usuário configurou

### 1.1 — `backend-crm/services/qualification_guardrails.py`

**O que fazer:**
- Remover o dicionário `_MIN_REQUIRED_FIELDS` hardcoded
- Alterar `required_fields_for_mode()` para retornar lista vazia quando `required_fields_override` é `None`
- Remover fallback para `_MIN_REQUIRED_FIELDS.get(agent_mode_normalized, ...)`

**Resultado:** Kanban não bloqueia movimentação manual quando o usuário não configurou campos — a menos que ele configure campos obrigatórios explicitamente.

**Risco e mitigação:** Leads que antes eram bloqueados pelo guardrail agora avançam livremente. Isso é o comportamento DESEJADO. Usuários que quiserem bloquear avançam de forma manual ou configuram os campos obrigatórios no AI Profile.

```python
# ANTES
def required_fields_for_mode(agent_mode_normalized, required_fields_override=None):
    if required_fields_override is not None:
        return list(required_fields_override)
    return list(_MIN_REQUIRED_FIELDS.get(agent_mode_normalized, _MIN_REQUIRED_FIELDS["agenda"]))

# DEPOIS
def required_fields_for_mode(agent_mode_normalized, required_fields_override=None):
    if required_fields_override is not None:
        return list(required_fields_override)
    return []  # Sem configuração = sem obrigação
```

### 1.2 — `backend-executors/app/contracts/qualification_contract.py`

**O que fazer:**
- Idêntico ao passo 1.1 — remover `MIN_REQUIRED_FIELDS` hardcoded
- Alterar fallback para lista vazia quando AI Profile não define campos

### 1.3 — `backend-crm/services/ai_orchestrator/orchestrator.py` — `apply_mode_overrides`

**O que fazer (P6 de solucoes.md):**
- Modificar o bloco `elif agent_mode_normalized == "agenda"` para não sobrescrever `must_collect` quando o AI Profile já define `qualification_required_fields`

```python
# DEPOIS
elif agent_mode_normalized == "agenda":
    profile_fields = ai_profile.get("qualification_required_fields")
    if profile_fields is None:  # Não configurado → sem override automático
        pass  # Não injeta must_collect hardcoded
    elif len(profile_fields) > 0:
        merged.update({"must_collect": profile_fields})
    # lista vazia explícita = modo passivo, não injeta must_collect
```

### 1.4 — `backend-core/app/api/ai_profiles.py` — Default em criação

**O que fazer (P10 de solucoes.md — parcial):**
- Ao criar um novo AI Profile via wizard, popular `qualification_required_fields` com sugestão por modo (como dado inicial editável, não como hardcode permanente)
- A sugestão fica visível no frontend; o usuário pode editar antes de salvar

```python
# Em _upsert_ai_profile, bloco de criação:
_DEFAULT_QUAL_FIELDS = {
    "sdr_scheduler": ["service_interest", "availability_window"],
    "agenda":        ["service_interest", "availability_window"],
    "consultivo":    ["service_interest", "urgency", "decision_role"],
    "closer":        ["service_interest", "price_acceptance"],
    "direto":        ["service_interest", "price_acceptance"],
}
if not profile and data.get("qualification_required_fields") is None:
    mode = str(data.get("agent_mode") or "agenda")
    data["qualification_required_fields"] = _DEFAULT_QUAL_FIELDS.get(mode, [])
```

---

## Fase 2 — Backend: Corrigir Comportamento do Agente (Prompting)

**Duração estimada:** 1–2 sessões  
**Risco:** Médio — altera prompts da LLM, requer teste antes de deploy  
**Valor entregue:** Agente responde SEMPRE, qualificação ocorre como complemento natural

### 2.1 — `backend-executors/app/services/decision_engine.py` — Prompt da mãe (P1)

**O que fazer:**
- Localizar `_build_mother_prompt` (~linha 929)
- Substituir a `REGRA OBRIGATÓRIA` pela lógica invertida descrita em P1 de `solucoes.md`

**Regra nova:**
```
PRIORIDADE 1: Responda sempre a mensagem do cliente.
PRIORIDADE 2: Se a mensagem não contiver pergunta direta E houver campos pendentes,
              prefira route_to="qualification".
NUNCA retorne route_to="qualification" se o cliente fez uma pergunta direta.
NUNCA use route_to="qualification" como único conteúdo da resposta.
```

### 2.2 — `backend-executors/app/services/decision_engine.py` — Default response_style (P3)

**O que fazer:**
- Alterar todas as leituras de `response_style` com fallback `"active"` para `"passive"`
- Afeta apenas usuários que não salvaram explicitamente o campo (null no banco)

```python
# ANTES
response_style = (ai_profile.get("response_style") or "active").strip().lower()
# DEPOIS
response_style = (ai_profile.get("response_style") or "passive").strip().lower()
```

**Mitigação de risco:** Como o AI Profile já tem `server_default="active"` no modelo SQLAlchemy, usuários existentes têm `"active"` salvo no banco e não são afetados. Apenas registros com `null` explícito (edge case) mudam.

### 2.3 — `backend-executors/app/services/decision_engine.py` — Prompt da filha (P7)

**O que fazer:**
- Localizar `_build_child_prompt_qualification` (~linha 1170)
- Reescrever escopo do prompt de `"Você APENAS faz perguntas"` para `"Responde primeiro, qualifica depois"`

**Regra nova do prompt:**
```
Responde SEMPRE à mensagem do cliente antes de qualificar.
Se o cliente fez uma pergunta, responde usando offer_description e custom_instructions.
Depois, se houver campos em falta, adicione UMA pergunta de qualificação natural ao final.
Nunca respondas APENAS com uma pergunta de qualificação.
Em modo passivo: nunca faças perguntas diretas. Apenas responde e, se oportuno,
sugere informação de forma indireta ("se quiser me contar mais sobre X, consigo ajudar melhor").
```

### 2.4 — `backend-executors/app/services/decision_engine.py` — Injetar `qualification_optional_fields` no contexto (novo)

**O que fazer:**
- Quando `response_style=passive`, injetar os campos opcionais no contexto como "informações que o agente deve INFERIR da conversa, sem perguntar diretamente"
- Quando `response_style=active`, injetar como "perguntas a fazer quando o assunto surgir naturalmente"

---

## Fase 3 — Backend + Frontend: Contrato Unificado de Qualificação

**Duração estimada:** 2 sessões (backend + frontend juntos, pois o schema é compartilhado)  
**Risco:** Médio — nova estrutura de dados; requer migração de registros existentes  
**Valor entregue:** Um único lugar onde o usuário define o que o agente pergunta, como infere, e o que bloqueia avanço. Fim da duplicação f1/f2/f3 vs qualification_required_fields.

### 3.1 — Novo schema: `QualificationField`

O contrato compartilhado entre frontend e backend:

```typescript
// frontend-crm/src/types/agente.ts
interface QualificationField {
  key: string;           // "availability_window" | "custom_nome_do_pet" | ...
  label: string;         // "Disponibilidade" | "Nome do pet"
  question?: string;     // Pergunta para modo ativo: "Qual horário funciona?"
  passive_hint?: string; // Dica para modo passivo: "Inferir se lead mencionar horário"
  mode: 'required' | 'optional' | 'off';
}
```

```python
# backend-core/app/models/ai_profile.py — nova coluna
qualification_fields = Column(JSON, nullable=True)
# Estrutura: List[{"key": str, "label": str, "question": str|None,
#                  "passive_hint": str|None, "mode": "required"|"optional"|"off"}]
```

**Campos do sistema predefinidos** (que o extraction engine já sabe extrair):

| key | label sugerida |
|---|---|
| `service_interest` | Serviço de interesse |
| `availability_window` | Disponibilidade |
| `price_acceptance` | Aceitação de preço |
| `location_preference` | Preferência de local |
| `urgency` | Urgência |
| `decision_role` | Decisor |
| `budget_or_price_acceptance` | Orçamento |
| `constraints` | Restrições |

**Campos personalizados:** key gerada como `"custom_" + slug(label)`. Ex: label "Nome do pet" → key `"custom_nome_do_pet"`. O executor usa `question` para extrair e `key` para armazenar em `data_json`.

### 3.2 — `backend-core/app/models/ai_profile.py`

**O que adicionar:**
```python
qualification_fields = Column(JSON, nullable=True)
# Mantém qualification_required_fields existente para backward compat
# (guardrails leem qualification_required_fields, derivado pelo frontend antes de salvar)
```

Migração: coluna nullable, sem impacto em registros existentes. Registros antigos com `qualification_required_fields` e f1/f2/f3 em `offer_pack` continuam funcionando via fallback.

### 3.3 — `backend-core/app/api/ai_profiles.py`

**O que adicionar:**
- `qualification_fields: Optional[List[dict]] = None` em `AIProfileBase`, `AIProfileUpdate` e `AIProfileOut`
- No endpoint de update: quando `qualification_fields` é recebido, derivar e salvar automaticamente `qualification_required_fields` como lista das keys com `mode="required"`

```python
# Em _upsert_ai_profile:
if "qualification_fields" in data and data["qualification_fields"] is not None:
    fields = data["qualification_fields"]
    data["qualification_required_fields"] = [
        f["key"] for f in fields
        if isinstance(f, dict) and f.get("mode") == "required"
    ]
```

Isso mantém `qualification_required_fields` sempre atualizado para os guardrails, sem mudar nenhum código de backend-crm ou backend-executors.

### 3.4 — `backend-crm/services/ai_orchestrator/orchestrator.py`

**O que adicionar:**
- Ler `qualification_fields` do AI Profile (além de `qualification_required_fields`)
- Construir dois blocos para injeção no prompt:
  - **`must_collect_with_questions`**: campos `mode=required` com seus `question` e `passive_hint`
  - **`nice_to_collect`**: campos `mode=optional` com seus `question` e `passive_hint`

```python
# Exemplo de injeção no contexto do prompt
qual_fields = ai_profile.get("qualification_fields") or []
must_collect = [f for f in qual_fields if f.get("mode") == "required"]
nice_to_collect = [f for f in qual_fields if f.get("mode") == "optional"]

# Serializar para o prompt:
# "Informações OBRIGATÓRIAS:
#  - Disponibilidade: pergunta 'Qual horário funciona para você?' | inferir: 'se lead mencionar horário'"
# "Informações DESEJÁVEIS (capturar se surgir):
#  - Nome do pet: pergunta 'Qual o nome do seu pet?' | inferir: 'se lead mencionar o nome'"
```

### 3.5 — `frontend-crm/src/types/agente.ts` — Atualização do tipo `AgentConfig`

**O que mudar:**
```typescript
// ADICIONAR — contrato unificado (substitui f1/f2/f3 conceitualmente)
qualification_fields: QualificationField[];

// MANTER como legado (ainda lido por código antigo, derivado de qualification_fields)
f1_questions: string[];
f2_questions: string[];
f3_questions: string[];
qualification_required_fields: string[] | null;
```

`qualification_fields` vazio em registros antigos → frontend mostra UI de migração sugerindo importar f1/f2/f3 existentes como campos do novo formato.

### 3.6 — Lógica de serialização no frontend (antes de salvar via API)

Quando o usuário salva `qualification_fields`, o frontend deve:
1. Enviar `qualification_fields` (novo campo)
2. Derivar e enviar `qualification_required_fields` = keys onde mode="required"
3. Derivar e enviar f1/f2/f3_questions a partir das questions dos campos (para compatibilidade com prompts legados no executor que ainda leem offer_pack)

Isso garante que ambas as versões do backend (com e sem suporte ao novo schema) funcionem corretamente durante a transição.

---

## Fase 4 — Frontend: CamadaQualificacao Dinâmica e Didática

**Duração estimada:** 2 sessões  
**Risco:** Baixo — apenas UI (Fase 3 entrega o schema, Fase 4 consome)  
**Valor entregue:** UI distinta por tipo de agente — SDR mantém estrutura de filtros; outros agentes ganham lista enriquecida. Todos ganham distinção obrigatório/opcional e campos personalizados.

### 4.1 — Toggle `response_style` visível (P9 de solucoes.md)

Mover o toggle para o topo da Camada 2, pois ele determina como a seção inteira é apresentada. A posição muda a semântica visual dos campos:

```
┌─ COMO O AGENTE COLETA INFORMAÇÕES ─────────────────────────┐
│  ○ Conduz a conversa        ● Segue o ritmo do cliente      │
│  Pergunta ativamente        Responde e infere               │
└─────────────────────────────────────────────────────────────┘
```

Este toggle salva `response_style: 'active' | 'passive'` no AI Profile.

### 4.2 — UI do Agente 1 (SDR) — Estrutura de filtros PRESERVADA

**Para `agent_mode = 'sdr_scheduler'`, a UI de F1/F2/F3 não muda estruturalmente.** Os cards de filtro continuam idênticos ao que existe hoje. O que muda é que cada pergunta dentro do filtro ganha uma marcação de obrigatória/opcional.

```
┌─ FILTROS DE QUALIFICAÇÃO ─────────────────────────────────────────┐
│                                                                    │
│  [Filtro 1 · Perfil e fit]   3 perguntas  ›                       │
│  Localização · uso pessoal · decisor                              │
│                                                                    │
│  [Filtro 2 · Intenção e dor]  2 perguntas  ›                      │
│  Abertas · exploratórias · contexto                               │
│                                                                    │
│  [Filtro 3 · 4Ps]            4 perguntas  ›                       │
│  Poder · prioridade · preço · timing                              │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

Ao abrir um filtro (modal existente), cada pergunta passa a ter duas informações adicionais:

```
01  [●] Você está em [cidade/região]?
         ↳ Obrigatório — lead não avança sem responder

02  [○] Isso é para uso pessoal ou profissional?
         ↳ Opcional — coletado se surgir

[+ Adicionar pergunta ao Filtro 1]
```

O usuário clica no indicador `[●]/[○]` para alternar entre obrigatório/opcional/desligado. A pergunta com `mode=off` fica visualmente esmaecida e pode ser removida.

**Mapeamento de dados para SDR:**
- Perguntas em F1 → `QualificationField` com `group='f1'`
- Perguntas em F2 → `QualificationField` com `group='f2'`
- Perguntas em F3 → `QualificationField` com `group='f3'`
- Campos predefinidos (availability_window, service_interest etc.) ficam na lista de campos rastreados pelo guardrail

**Experiência de modo passivo para SDR:**

Quando `response_style=passive`, os cards de filtro mudam de rótulo:

```
[Filtro 1 · Perfil e fit]  → [Sinais a capturar · Perfil e fit]
"Perguntas que o agente faz"  → "O que o agente busca entender"
```

O modal abre e mostra o campo `passive_hint` no lugar de `question`, explicando como o SDR deve inferir cada dado sem perguntar diretamente.

### 4.3 — UI dos Agentes 2 e 3 — Lista plana enriquecida

**Para `agent_mode = 'closer'/'direto'/'agenda'/'consultivo'`, a UI é uma lista plana** — sem a estrutura de filtros do SDR:

**Quando `response_style=active`:**
```
┌─ O QUE O AGENTE DEVE DESCOBRIR ──────────────────────────────────┐
│  [agenda] Foco em agendar. Disponibilidade é o campo essencial.  │
│  [direto] Filtro rápido. Menos campos, mais conversão.           │
│                                                                   │
│  [●  Obrigatório ] Disponibilidade  "Qual horário funciona?"  ›  │
│  [○  Opcional    ] Serviço          "O que você busca?"       ›  │
│  [×  Desligado   ] Orçamento        —                            │
│  [+  Custom      ] Nome do pet      "Qual o nome?"            ›  │
│                                                                   │
│  [+ Adicionar campo]                                             │
└───────────────────────────────────────────────────────────────────┘
```

**Quando `response_style=passive`:**
```
┌─ O QUE O AGENTE PRECISA SABER ────────────────────────────────────┐
│  O agente não pergunta diretamente — capta naturalmente.          │
│                                                                   │
│  [●  Essencial ] Disponibilidade  "Inferir se mencionar horário" ›│
│  [○  Desejável ] Serviço          "Inferir pelo contexto"       › │
│  [×  Ignorar   ] Orçamento        —                              │
│                                                                   │
│  [+ Adicionar campo]                                             │
└───────────────────────────────────────────────────────────────────┘
```

### 4.4 — Editor de campo (drawer compartilhado entre SDR e outros)

Clicar em qualquer campo abre drawer:

```
┌─ EDITAR CAMPO ──────────────────────────────────────────────┐
│ Nome do campo   [Disponibilidade               ]            │
│                                                             │
│ Importância  ○ Obrigatório  ● Opcional  ○ Desligado        │
│                                                             │
│ Pergunta (modo ativo)                                       │
│ [Qual o melhor horário para você?              ]            │
│                                                             │
│ Como inferir (modo passivo)                                 │
│ [Se mencionar horário, data ou "semana que vem"]            │
└─────────────────────────────────────────────────────────────┘
```

Para SDR: o drawer também mostra em qual filtro o campo está (F1/F2/F3), com opção de mover.

### 4.5 — Campos personalizados

Botão "+ Adicionar campo" (em qualquer modo/agente) abre drawer com campos em branco. Para SDR, pergunta também em qual filtro incluir (F1/F2/F3). Frontend gera `key = "custom_" + slug(label)`.

### 4.6 — Sugestões por `agent_mode`

Quando o usuário troca de modo na Camada 1, banner na Camada 2:

```
⚙ Sugestão para "Agendador"
  Campos típicos para este tipo de agente foram pré-selecionados.
  [Aplicar sugestão]  [Manter atual]
```

Para SDR, a sugestão vem pré-distribuída nos filtros F1/F2/F3. Para outros agentes, vem como lista plana. Sugestões vivem no frontend — não são hardcode no backend.

---

## Fase 5 — Verificação e Isolamento (Auditoria)

**Duração estimada:** meia sessão  
**Risco:** Nenhum — apenas leitura de código  
**Valor entregue:** Confirmar que nenhum outro ponto reintroduz guardrails hardcoded

### 5.1 — Verificar isolamento do guardrail do Kanban (P8 de solucoes.md)

- Confirmar que `can_advance_from_qualification` é chamado **apenas** em rotas de movimentação manual de categoria em `backend-crm/routes/leads.py`
- Garantir que nunca é chamado dentro do pipeline de IA (inbound handler, orchestrator, decision engine)
- Se encontrado em pipeline de IA → remover

### 5.2 — Verificar que não há outros pontos de hardcode

Buscar por todos os usos de:
- `MIN_REQUIRED_FIELDS` (qualquer variação)
- `service_interest`, `availability_window`, `price_acceptance` fora do contrato de qualificação
- `must_collect` hardcoded no orchestrator

---

## Sequência de Implementação Recomendada

```
Fase 1 (backend fonte única) → testar guardrails Kanban
    ↓
Fase 2 (prompting) → testar no playground com casos reais
    ↓
Fase 3 (campos opcionais) → teste de integração backend
    ↓
Fase 4 (frontend) → pode ser paralelo à Fase 3
    ↓
Fase 5 (auditoria) → antes do deploy em produção
```

As Fases 1 e 5 são as mais importantes para o objetivo 4 (única fonte de verdade).
As Fases 3 e 4 juntas resolvem os objetivos 1, 2 e 3.
A Fase 2 resolve o comportamento da conversa (sem bloqueio de respostas).

---

## Riscos Residuais e Mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| LLM mãe continua forçando qualification mesmo após P1 | Média | Testar no playground; se persistir, adicionar P2 (reply_mode) como segunda camada |
| Usuários existentes com campos null ficam sem qualificação ativa | Baixa | `server_default="active"` garante que maioria tem `response_style` salvo; UI exibe banner de configuração |
| Campos personalizados com keys duplicadas | Baixa | Frontend valida `key` único antes de adicionar ao array |
| `qualification_fields` null em registros antigos | Nenhum | Coluna nullable; orquestrador faz fallback para f1/f2/f3 + `qualification_required_fields` antigos |
| Serialização dupla (qualification_fields + derivados) pode dessincronizar | Média | Lógica de derivação centralizada em uma única função utilitária no frontend; testada com jest |
| Remoção do fallback hardcoded causa regressão em testes | Média | Verificar e atualizar testes que dependiam do fallback antes de merge |
| Migração de f1/f2/f3 para novo formato pelo usuário nunca acontece | Baixa | UI funciona com ambos os formatos; não forçar migração, apenas sugerir |

---

## O que NÃO fazer neste plano

- Não implementar P2 (separar reply_mode de route_to) agora — alto risco, baixo ganho marginal dado P1+P7
- Não criar um shared package entre serviços para campos — dependência de sincronização desnecessária; AI Profile no backend-core já é o ponto central
- Não adicionar validação de schema complexa nos campos personalizados — o usuário é responsável pelo naming, o sistema apenas passa adiante
- Não criar feature flags — o sistema ou é a fonte de verdade ou não é; metade-metade cria confusão

---

## Checklist de Entrega por Fase

### Fase 1 — Backend: fonte única
- [ ] `qualification_guardrails.py`: remover `_MIN_REQUIRED_FIELDS`, fallback = `[]`
- [ ] `qualification_contract.py` (executors): idem
- [ ] `orchestrator.py` (`apply_mode_overrides`): não sobrescreve quando AI Profile tem campos
- [ ] `ai_profiles.py` (core): sugestões por modo no create como ponto de partida editável

### Fase 2 — Backend: prompting
- [ ] `decision_engine.py`: prompt da mãe — prioridade invertida (P1)
- [ ] `decision_engine.py`: default `response_style` = `"passive"` para null (P3)
- [ ] `decision_engine.py`: prompt da filha — responde antes, qualifica depois (P7)
- [ ] `decision_engine.py`: injetar `qualification_fields[]` com question/passive_hint no contexto
- [ ] Teste playground: pergunta direta → agente responde primeiro
- [ ] Teste playground: sem pergunta + campos pendentes → qualifica naturalmente

### Fase 3 — Contrato unificado
- [ ] `agente.ts`: adicionar `QualificationField` interface e `qualification_fields` em `AgentConfig`
- [ ] `agente.ts`: manter `f1/f2/f3_questions` e `qualification_required_fields` como campos legados
- [ ] `ai_profile.py` (model): coluna `qualification_fields` (JSON, nullable)
- [ ] `ai_profiles.py` (API): campo nos schemas de create/update/out
- [ ] `ai_profiles.py` (API): derivar `qualification_required_fields` automaticamente do `qualification_fields` ao salvar
- [ ] `orchestrator.py`: ler `qualification_fields`, construir blocos `must_collect` e `nice_to_collect` com questions
- [ ] Frontend: lógica de serialização (salvar `qualification_fields` + derivar `qualification_required_fields` + derivar f1/f2/f3 para compat)

### Fase 4 — Frontend: UI dinâmica
- [ ] Toggle `response_style` no topo da Camada 2 (linguagem de negócio)
- [ ] **SDR (`sdr_scheduler`)**: cards F1/F2/F3 preservados — cada pergunta ganha badge obrigatório/opcional
- [ ] **SDR**: modal de filtro mostra `question` (ativo) ou `passive_hint` (passivo) por pergunta
- [ ] **Outros agentes**: `CamadaQualificacao.tsx` renderiza lista plana de campos com mesmo editor
- [ ] Editor de campo unificado (drawer com label + mode + question + passive_hint)
- [ ] Três estados por campo: Obrigatório / Opcional / Desligado (toggle no card ou no drawer)
- [ ] Campos personalizados livres — SDR pergunta em qual filtro incluir; outros vão para lista plana
- [ ] Sugestões por `agent_mode` — SDR sugestão distribuída em F1/F2/F3; outros em lista
- [ ] Explicação contextual por `agent_mode` + `response_style` (banner no topo da seção)

### Fase 5 — Auditoria
- [ ] Confirmar `can_advance_from_qualification` isolado em rotas manuais (`routes/leads.py`)
- [ ] grep: nenhuma ocorrência de `MIN_REQUIRED_FIELDS` ou campos hardcoded fora do contrato
- [ ] grep: `must_collect` hardcoded → deve existir apenas como derivado de `qualification_fields`
- [ ] Testes unitários atualizados (sem fallback hardcoded, sem mock de campos fixos)
