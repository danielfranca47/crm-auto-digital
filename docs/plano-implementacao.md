# Plano de Implementação — Qualificação Dinâmica e AI Profile como Fonte Única de Verdade

> Gerado em: 2026-04-03
> Baseado em: `pretencoes.md`, `solucoes.md`, diagnóstico do código atual

---

## Diagnóstico Executivo

O sistema atual tem a estrutura correta no modelo de dados (`qualification_required_fields` existe no AIProfile, o CRM já lê esse campo), mas tem três camadas de contradição que impedem que a intenção chegue ao comportamento:

| Camada | Problema real |
|---|---|
| **Backend — guardrails** | `_MIN_REQUIRED_FIELDS` hardcoded em `qualification_guardrails.py` sobrescreve a escolha do usuário quando o AI Profile não tem override |
| **Backend — prompting** | `decision_engine.py` força `route_to="qualification"` antes de responder o lead (C1, C2, C7 de `solucoes.md`) |
| **Frontend — UI** | `CamadaQualificacao.tsx` não diferencia obrigatório vs opcional, não adapta ao `agent_mode`, não permite campos personalizados |

O plano é dividido em **4 fases sequenciais**, do menor risco ao maior esforço, cada uma entregando valor independente.

---

## O que foi decidido (e porquê)

### Decisão 1: `qualification_required_fields=null` passa a significar "sem campos obrigatórios"
Hoje, `null` faz fallback para `_MIN_REQUIRED_FIELDS`. A intenção declarada é que o AI Profile seja a única fonte de verdade. Se o usuário não configurou nenhum campo, o sistema não deve inventar um. O onboarding/UI oferece sugestões por modo, mas a decisão final é do usuário.

### Decisão 2: Adicionar `qualification_optional_fields` ao AI Profile
Campos opcionais são coletados quando surgem naturalmente na conversa, mas não bloqueiam avanço e não são perguntados ativamente (em modo passivo). Isso resolve o pedido do item 3 sem criar uma estrutura de dados complexa.

### Decisão 3: Campos personalizados via `label` no frontend, mapeados para `key` interno
Em vez de restringir ao conjunto fixo de 8 campos, o usuário pode nomear campos livremente. O frontend salva como `{key: "custom_1", label: "Nome do pet"}` e o backend usa a label no prompt. A key é gerada automaticamente. O executor usa a label para injetar no prompt da LLM.

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

## Fase 3 — Backend: Adicionar `qualification_optional_fields` + Campos Personalizados

**Duração estimada:** 1 sessão  
**Risco:** Baixo — adição de coluna nullable + ajuste no frontend  
**Valor entregue:** Usuário diferencia o que é obrigatório do que é desejável; campos personalizados livres

### 3.1 — `backend-core/app/models/ai_profile.py`

**O que adicionar:**
```python
qualification_optional_fields = Column(JSON, nullable=True)
# Estrutura: [{"key": "pet_name", "label": "Nome do pet"}]
# Para campos personalizados. Para campos padrão: [{"key": "urgency", "label": "Urgência"}]
```

A migração é idempotente — coluna nullable, sem valor default, não quebra registros existentes.

### 3.2 — `backend-core/app/api/ai_profiles.py`

**O que adicionar:**
- Adicionar `qualification_optional_fields: Optional[List[dict]] = None` em `AIProfileBase` e `AIProfileUpdate`
- Adicionar `qualification_optional_fields` em `AIProfileOut`

### 3.3 — `backend-crm/services/ai_orchestrator/orchestrator.py`

**O que adicionar:**
- Ler `qualification_optional_fields` do AI Profile
- Injetar no contexto do prompt como "campos desejáveis mas não obrigatórios — coletar se surgir naturalmente"

---

## Fase 4 — Frontend: CamadaQualificacao Dinâmica e Didática

**Duração estimada:** 2–3 sessões  
**Risco:** Baixo — apenas UI, não altera lógica de backend  
**Valor entregue:** UI condicional, didática, com distinção obrigatório/opcional e campos personalizados

### 4.1 — Toggle `response_style` em `CamadaIdentidade.tsx` ou nova seção

**O que fazer (P9 de solucoes.md):**
- Adicionar toggle visível com linguagem de negócio:
  - "Conduz a conversa" (active) — agente pergunta ativamente
  - "Segue o ritmo do cliente" (passive) — agente responde e infere

### 4.2 — `CamadaQualificacao.tsx` — Condicional por modo

**O que fazer:**
O componente deve mudar completamente de semântica baseado em `response_style`:

**Quando `response_style=active`:**
```
Seção: "Perguntas que o agente faz"
Explicação: "O agente perguntará estas informações durante a conversa. 
             Obrigatórias = lead não avança sem responder.
             Opcionais = pergunta se surgir oportunidade."
```

**Quando `response_style=passive`:**
```
Seção: "O que o agente precisa saber"
Explicação: "O agente não pergunta diretamente, mas capta estas informações 
             naturalmente durante a conversa.
             Essenciais = agente usa para personalizar respostas.
             Desejáveis = enriquece o lead se mencionado."
```

### 4.3 — `ModalQualFields` — Três estados por campo

**O que mudar:**
- Substituir toggle binário por três estados: **Obrigatório** | **Opcional** | **Desligado**
- Campos obrigatórios → `qualification_required_fields`
- Campos opcionais → `qualification_optional_fields`

**UX:**
```
[Obrigatório ●] Disponibilidade — Lead não avança sem informar horário
[Opcional    ○] Orçamento       — Coletado se surgir, não bloqueia
[Desligado   ×] Decisor         — Não relevante para este negócio
```

### 4.4 — Campos personalizados livres

**O que adicionar:**
- Botão "Adicionar campo personalizado" abre um drawer com:
  - Campo: Nome do campo (ex: "Nome do pet", "Raça", "Bairro")
  - Tipo: Obrigatório | Opcional
- Frontend gera `key = "custom_" + slug(label)` para campos novos
- Campos personalizados e campos padrão ficam na mesma lista, distinguidos visualmente

### 4.5 — Sugestões por modo no onboarding

**O que adicionar:**
- Quando o usuário muda `agent_mode`, a Camada 2 mostra uma sugestão de campos pré-selecionados com badge "Sugerido para este modo"
- Usuário pode aceitar, remover ou adicionar antes de salvar
- Isso substitui o hardcode do backend — a sugestão vive no frontend, a decisão final é do usuário

### 4.6 — Camada 2 contextual por `agent_mode`

**Adaptações por tipo:**

| agent_mode | Título da seção | Explicação contextual |
|---|---|---|
| `sdr_scheduler` | Qualificação e agenda | "O SDR qualifica e agenda. Defina o que ele deve descobrir antes de marcar." |
| `agenda` | Dados para agendamento | "O agente foca em agendar. Disponibilidade é essencial." |
| `consultivo` | Diagnóstico consultivo | "O consultor aprofunda contexto. Campos como urgência e decisor são críticos." |
| `closer` / `direto` | Filtro rápido | "O closer vai direto. Poucos campos, alta conversão." |

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
| Usuários existentes com campos null ficam sem qualificação ativa | Baixa | server_default="active" no banco garante que maioria tem response_style salvo; notificar via UI |
| Campos personalizados com keys duplicadas | Baixa | Frontend valida unicidade antes de salvar |
| `qualification_optional_fields` null em registros antigos | Nenhum | Coluna nullable, tratada como lista vazia |
| Remoção do fallback hardcoded causa regressão em testes | Média | Verificar e atualizar testes que dependiam do fallback |

---

## O que NÃO fazer neste plano

- Não implementar P2 (separar reply_mode de route_to) agora — alto risco, baixo ganho marginal dado P1+P7
- Não criar um shared package entre serviços para campos — dependência de sincronização desnecessária; AI Profile no backend-core já é o ponto central
- Não adicionar validação de schema complexa nos campos personalizados — o usuário é responsável pelo naming, o sistema apenas passa adiante
- Não criar feature flags — o sistema ou é a fonte de verdade ou não é; metade-metade cria confusão

---

## Checklist de Entrega por Fase

### Fase 1
- [ ] `qualification_guardrails.py`: remover `_MIN_REQUIRED_FIELDS`, fallback = `[]`
- [ ] `qualification_contract.py` (executors): idem
- [ ] `orchestrator.py`: `apply_mode_overrides` respeita AI Profile
- [ ] `ai_profiles.py` (core): sugestões por modo no create (não hardcode permanente)

### Fase 2
- [ ] `decision_engine.py`: prompt da mãe invertido (P1)
- [ ] `decision_engine.py`: default `response_style` = `"passive"` (P3)
- [ ] `decision_engine.py`: prompt da filha reescrito (P7)
- [ ] Teste playground: mensagem com pergunta direta → agente responde antes de qualificar
- [ ] Teste playground: mensagem sem pergunta → agente qualifica naturalmente

### Fase 3
- [ ] `ai_profile.py` (model): coluna `qualification_optional_fields` adicionada
- [ ] `ai_profiles.py` (API): campo nos schemas de create/update/out
- [ ] `orchestrator.py`: campos opcionais injetados no contexto do prompt
- [ ] Migration: verificar que coluna nullable não quebra registros existentes

### Fase 4
- [ ] Toggle `response_style` visível na UI (linguagem de negócio)
- [ ] `CamadaQualificacao.tsx`: seção muda baseada em `response_style`
- [ ] `ModalQualFields`: três estados (obrigatório/opcional/desligado)
- [ ] Campos personalizados livres (add/remove)
- [ ] Sugestões por modo no onboarding (substituem hardcode do backend)
- [ ] Títulos e explicações contextuais por `agent_mode`

### Fase 5
- [ ] Auditoria: `can_advance_from_qualification` isolado em rotas manuais
- [ ] Auditoria: grep por hardcodes residuais em todos os serviços
- [ ] Testes atualizados para refletir o novo comportamento (sem fallback hardcoded)
