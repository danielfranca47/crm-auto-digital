# Otimização do Agente Híbrido Agendador

> Documento de rastreio das correções aplicadas após o teste `massagem-sensi-vitae` (score 2/10).
> Data: 2026-03-31

---

## Problemas identificados

### Problema 1 — `location_preference` obrigatório para gabinete fixo

**Causa raiz:** O campo `location_preference` estava nos campos obrigatórios do `agent_mode=agenda`. Para negócios com localização física fixa, este campo não faz sentido — gera perguntas como "prefere em casa, estúdio ou outro lugar?" que são factualmente erradas.

**Ficheiros alterados:**
- `backend-crm/services/qualification_guardrails.py` — removido `location_preference` de `_MIN_REQUIRED_FIELDS["agenda"]`
- `backend-executors/app/contracts/qualification_contract.py` — idem (manter em sincronia)

**Campos obrigatórios `agenda` antes:**
```
service_interest, availability_window, location_preference, price_acceptance
```

**Campos obrigatórios `agenda` depois:**
```
service_interest, availability_window, price_acceptance
```

---

### Problema 2 — `custom_instructions` ignoradas pelo LLM

**Causa raiz:** O campo `custom_instructions` era passado apenas como metadata passiva no `ai_summary` do contexto. O LLM priorizava as regras de qualificação e ignorava as instruções personalizadas do operador (ex: "quando pedirem final feliz, redirecionar para Finalização Lingam").

**Ficheiro alterado:** `backend-executors/app/services/decision_engine.py`

**Mudança:** Nova função `_build_custom_instructions_block()` que injeta as instruções com bloco explícito de "prioridade máxima" nos prompts filho:
- `_build_child_prompt_qualification()` — injetado no final do prompt, antes de `_inject_generated_parts`
- `_build_child_prompt_apresentation()` — idem

**Formato do bloco injetado:**
```
INSTRUÇÕES PERSONALIZADAS DO OPERADOR (prioridade máxima — seguir à risca):
<conteúdo de custom_instructions>
```

---

### Problema 3 — Não existia modo de comunicação passivo

**Causa raiz:** A arquitectura só suportava um modo activo de qualificação — o agente sempre perguntava antes de responder, ignorando perguntas directas do cliente como "quais são os serviços?", "qual a localização?", "é feito por homem?".

**Solução implementada:** Novo campo `response_style` no `ai_profile` com dois valores:

| Valor | Comportamento |
|---|---|
| `active` (padrão) | Agente faz perguntas de qualificação — comportamento anterior mantido |
| `passive` | Agente responde primeiro às perguntas directas do cliente e depois qualifica de forma natural |

**Ficheiros alterados:**
- `backend-core/app/models/ai_profile.py` — novo campo `response_style` (String, default `active`)
- `backend-core/app/db.py` — migração idempotente via `ensure_ai_profile_columns()`
- `backend-core/app/api/ai_profiles.py` — novo enum `ResponseStyle`; campo em `AIProfileBase` e `AIProfileUpdate`
- `backend-executors/app/services/decision_engine.py`:
  - `_build_child_prompt_qualification()` — bloco condicional `MODO PASSIVO ACTIVADO` quando `response_style=passive`
  - `_build_mother_prompt()` — sinaliza à filha para usar `next_action_hint=reply` quando `response_style=passive` e a mensagem for uma pergunta directa
- `frontend-crm/src/types/agente.ts` — campo `response_style` no `AgentConfig`; label `RESPONSE_STYLE_LABELS`
- `frontend-crm/src/services/api.ts` — campo em `AiProfilePayload`, `getConfig` e `saveConfig`
- `frontend-crm/src/components/agente/CamadaIdentidade.tsx` — card + drawer "Modo de resposta" (visível apenas para `template_key=hybrid_scheduler`)

---

## Checklist de validação pós-implementação

Re-executar os 3 cenários do `massagem-sensi-vitae-input.md` com `response_style=passive`.

### Cenário A — Cliente normal pergunta serviços e agenda
- [ ] Turno 1: Agente apresenta serviços e valores (Terapêutica + Exótica + Lingam opcional)
- [ ] Turno 2: Agente confirma localização (Faro, Centro Comercial Algarb)
- [ ] Turno 3: Agente confirma disponibilidade quinta-feira à tarde + valor 45€
- [ ] Turno 4: Agente confirma 16h
- [ ] Turno 5: Agente envia confirmação estruturada de reserva + Sala 2

### Cenário B — Pedido de "final feliz"
- [ ] Turno 1: Saudação + apresentação breve de serviços
- [ ] Turno 2: Confirma que as sessões são feitas pelo Daniel
- [ ] Turno 3: **Crítico** — Redireciona para Finalização Lingam (+20€) sem linguagem sexualizada
- [ ] Turno 4: Informa valor total (ex: 50€ + 20€ = 70€)
- [ ] Turno 5: Confirmação de agendamento

### Cenário C — Cliente que muda horário
- [ ] Turno 1: Confirma serviço, pede horário
- [ ] Turno 2: Confirma 15h
- [ ] Turno 3: **Crítico** — Não aceita 8h, sugere manter 15h com justificação
- [ ] Turno 4: Responde ao "Pode ser?" de forma clara
- [ ] Turno 5: Confirma reserva às 15h + informa Sala 2

---

## Critérios de aprovação

| Critério | Meta |
|---|---|
| Score global (checklist acima) | ≥ 7/10 |
| `custom_instructions` aplicadas (Cenário B, T3) | Obrigatório |
| Nenhuma pergunta de `location_preference` | Obrigatório |
| Confirmação estruturada enviada (pelo menos 1 cenário) | Obrigatório |
| Modo passivo activo — responde antes de perguntar | Obrigatório |

---

## Regressão esperada

| Comportamento | Deve manter-se |
|---|---|
| `response_style=active` (padrão) | Qualificação activa — sem alteração |
| `agent_mode=consultivo` | Campos obrigatórios não alterados (6 campos) |
| `agent_mode=direto` | Campos obrigatórios não alterados (3 campos) |
| Tom "querido/a" | Presente em todos os cenários |
| `is_playground=true` nos leads sandbox | Leads não aparecem no Kanban |
