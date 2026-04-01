# Otimização do Agente Híbrido Agendador

> Documento de rastreio das correções aplicadas após o teste `massagem-sensi-vitae` (score 2/10).
> Última atualização: 2026-04-01 — Teste 3 (Cenário A) executado. Score 3/5. Problemas 7, 8 e 9 identificados.

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

## Resultado Teste 2 — Cenário A (2026-03-31 ~21:30 UTC)

> Lead sandbox `id=73`. Servidores reiniciados com código das otimizações.

### Cenário A — Cliente normal pergunta serviços e agenda
- [ ] Turno 1: Agente apresenta serviços e valores (Terapêutica + Exótica + Lingam opcional)
- [ ] Turno 2: Agente confirma localização (Faro, Centro Comercial Algarb)
- [x] Turno 3: Captura `availability_window: "quinta-feira à tarde"` ✅ (mas não confirma nem informa 45€)
- [ ] Turno 4: Agente confirma 16h
- [ ] Turno 5: Agente envia confirmação estruturada de reserva + Sala 2

**Score Cenário A: 1/5** (ligeira melhoria — Fix #1 funciona, Fix #3 não funciona)

---

## Problemas identificados no Teste 2

### Problema 4 — MODO PASSIVO conflita com ESCOPO do prompt filho ✅ RESOLVIDO (Fix #5)

**Causa raiz:** O bloco `_passive_block` era injectado no final da linha `RECUSAS:` do prompt filho `_build_child_prompt_qualification`. Antes desta linha existiam duas instruções directamente contraditórias:
- `ESCOPO: Você APENAS faz perguntas de qualificação. Não apresenta ofertas.`
- `RECUSAS: Nunca cite preços.`

O LLM resolvia o conflito a favor das instruções que apareciam primeiro no prompt, ignorando o `MODO PASSIVO ACTIVADO`.

**Solução aplicada (2026-04-01):** Fix #5 — ver secção abaixo.

---

### Problema 5 — `price_acceptance` inadequado para negócio de preço fixo ✅ RESOLVIDO (Fix #4)

**Causa raiz:** O campo `price_acceptance` estava hardcoded nos campos obrigatórios de `agent_mode=agenda` para qualquer negócio. Para um negócio com tabela de preços explícita em `offer_description`, este campo:
1. Gerava perguntas como "Que valor você pretende investir?" — confusas e inadequadas
2. Bloqueava a progressão mesmo quando o cliente escolheu um serviço com preço definido
3. Era pedido repetidamente (3 vezes no Teste 2) mesmo com sinal de fecho claro

**Solução aplicada (2026-04-01):** Fix #4 — campo `qualification_required_fields` no ai_profile. O operador pode agora configurar quais campos são obrigatórios (ou nenhum) sem alterar código. Para a Sensi Vitae, configurar `["service_interest", "availability_window"]` remove o `price_acceptance` da obrigação.

---

### Fix #4 — `qualification_required_fields` configurável por ai_profile (2026-04-01)

**Motivação:** Os problemas 1 e 5 revelaram que os campos obrigatórios hardcoded por `agent_mode` não servem todos os nichos. Em vez de continuar a remover campos do código, a solução foi tornar a lista configurável pelo operador via ai_profile.

**Ficheiros alterados:**
- `backend-core/app/models/ai_profile.py` — nova coluna `qualification_required_fields` (JSON, nullable)
- `backend-core/app/db.py` — migração automática via `ensure_ai_profile_columns()`
- `backend-executors/app/contracts/qualification_contract.py` — `required_fields_for_mode()` e `compute_missing_fields()` aceitam `required_fields_override`
- `backend-executors/app/services/decision_engine.py` — `_get_required_fields_override()` lê o override do `context["ai_profile"]`; `_build_mode_contract_context()` usa o override
- `backend-executors/app/services/meta_prompter.py` — gera `qualification_phrasing` com base nos campos custom
- `backend-crm/services/qualification_guardrails.py` — `can_advance_from_qualification()` lê override do ai_profile; ignora score threshold quando lista é `[]`
- `frontend-crm/src/components/agente/CamadaQualificacao.tsx` — card + modal "Campos de qualificação" na Camada 2
- `frontend-crm/src/types/agente.ts` — campo `qualification_required_fields` no tipo `AgentConfig`
- `frontend-crm/src/services/api.ts` — campo no payload de load e save

**Comportamento:**

| Valor configurado | Resultado |
|---|---|
| `null` (padrão) | Usa defaults do modo — nada muda para agentes existentes |
| `["service_interest", "availability_window"]` | Só exige estes 2 campos; sem `price_acceptance` |
| `[]` (lista vazia) | Agente totalmente passivo — sem qualificação obrigatória |

**Configuração recomendada para Sensi Vitae:** `["service_interest", "availability_window"]`

---

### Problema 6 — Sinal de fecho ("fica combinado") não reconhecido ✅ RESOLVIDO (Fix #6)

**Causa raiz:** O mother decision engine não detectava frases de confirmação/fecho como trigger para rotar para `apresentation`. Quando o cliente dizia "Perfeito, fica combinado", o mother mantinha `qualification` porque `price_acceptance` estava em falta e a PRIORIDADE 1 era obrigatória sem excepção.

**Solução aplicada (2026-04-01):** Fix #6 — ver secção abaixo.

---

### Fix #5 — `response_style=passive` corrigido no prompt filho qualification (2026-04-01)

**Motivação:** O modo passivo não tinha efeito porque as instruções contraditórias (`ESCOPO`, `RECUSAS`) apareciam antes do bloco passivo no prompt filho.

**Ficheiro alterado:** `backend-executors/app/services/decision_engine.py` — função `_build_child_prompt_qualification`

**Mudanças:**
- Removido `_passive_block` que era appendado ao final de `RECUSAS:`
- Novo `_passive_header`: bloco passivo injectado ANTES do `PAPEL:` (primeiro conteúdo do prompt) — garantia de precedência
- `_escopo_line` condicional:
  - `active`: `"Você APENAS faz perguntas de qualificação. Não agenda reuniões. Não faz pitch. Não apresenta ofertas."`
  - `passive`: `"Responder perguntas directas do cliente PRIMEIRO, usando offer_description e custom_instructions. Depois qualificar de forma natural. Pode apresentar serviços e valores quando perguntado. Não agenda reunião nesta fase."`
- `_recusas_line` condicional:
  - `active`: inclui `"Nunca cite preços."`
  - `passive`: remove proibição de preços; adiciona `"Se a resposta não estiver em offer_description ou custom_instructions, diz que vais verificar (→ handoff)."`

**Impacto esperado:** Turno 1 apresenta serviços e valores; Turno 2 responde sobre localização.

---

### Fix #6 — Detecção de sinais de fecho no mother prompt (2026-04-01)

**Motivação:** O cliente dizer "fica combinado" (T5, Teste 2) não era suficiente para avançar de `qualification` para `apresentation`, mesmo com sinal de compra explícito.

**Ficheiro alterado:** `backend-executors/app/services/decision_engine.py` — função `_build_mother_prompt`

**Mudanças:**
- PRIORIDADE 1: adicionada `EXCEÇÃO FECHO` — quando a mensagem contém sinal explícito de confirmação/booking ("fica combinado", "perfeito", "pode ser", "fechado", "aceito", "tá bom", "ok então", "combinado", "confirmado" ou equivalentes) E `agent_mode=agenda/sdr_scheduler`:
  - interpreta `price_acceptance='yes'` e `meeting_scheduled=true`
  - `route_to = "apresentation"` mesmo com `missing_fields` não vazio
- REGRA OBRIGATÓRIA DE QUALIFICAÇÃO: actualizada com nota da excepção de fecho
- Adicionado Exemplo 11 nos exemplos do mother prompt (AGENDA com sinal de fecho)

**Impacto esperado:** T5 "Perfeito, fica combinado então" → mother rota para `apresentation` e filha envia confirmação estruturada de reserva + morada.

---

## Resultado Teste 3 — Cenário A (2026-04-01)

> Lead sandbox `id=75`. Bug do schema Pydantic corrigido antes do teste (ver Problema 7 do Fix #4 abaixo).

### Cenário A — Cliente normal pergunta serviços e agenda
- [ ] Turno 1: Agente apresenta serviços e valores (Terapêutica + Exótica + Lingam opcional) ← **Fix #5 ainda falha**
- [x] Turno 2: Agente confirma localização (Faro, Centro Comercial Algarb + Sala 2) ✅
- [ ] Turno 3: Agente confirma disponibilidade quinta-feira à tarde + valor 45€ ← confirma quinta ✅ mas sem preço e tom SDR ❌
- [x] Turno 4: Agente confirma 16h + menciona Daniel + avança para `apresentation` ✅
- [ ] Turno 5: Agente envia confirmação estruturada de reserva + Sala 2 ← dá morada ✅ mas sem confirmação estruturada ❌

**Score Cenário A: 3/5** (melhoria de +2 face ao Teste 2)

---

## Problemas identificados no Teste 3

### Problema 7 — Fix #5 (passive mode) ainda falha no T1 — pergunta directa sobre serviços

**Causa provável:** O mother prompt não classifica "quais são os serviços e valores?" como pergunta directa que activa `next_action_hint=reply`. A detecção de "pergunta directa" no bloco passive do mother parece limitada a perguntas de localização/existência, não a perguntas de catálogo.

**Impacto:** T1 pede disponibilidade em vez de apresentar a oferta — primeira impressão negativa.

---

### Problema 8 — Confirmação estruturada não enviada no T5

**Causa provável:** O prompt filho `apresentation` (fase de fecho) não tem instrução explícita para gerar confirmação no formato recibo quando `agent_mode=agenda` detecta sinal de fecho. A `custom_instruction` n.º 6 existe mas não é seguida neste contexto.

**Impacto:** Reserva confirmada verbalmente mas sem o formato estruturado (✅ Experiência / Horário / Dia / Massagista) que o operador espera receber.

---

### Problema 9 — Tom SDR/B2B inadequado para nicho de massagem

**Causa provável:** `generated_prompt_parts` gerados pelo meta-prompter com tom B2B que não reflecte o `niche` e `tone_of_voice` configurados. T3: "vamos mapear a tua situação e definir um plano de ação" — linguagem completamente errada para spa.

**Solução proposta:** Forçar re-geração dos `generated_prompt_parts` após actualizações ao perfil, ou auditar o que o meta-prompter gera para este nicho.

---

## Checklist de validação — Teste 3 (Cenários B e C — pendente)

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
| Nenhuma pergunta de `price_acceptance` (preço já visível em offer_description) | Obrigatório |
| Confirmação estruturada enviada (pelo menos 1 cenário) | Obrigatório |
| Modo passivo activo — responde antes de perguntar | Obrigatório |

---

## Regressão esperada

| Comportamento | Deve manter-se |
|---|---|
| `response_style=active` (padrão) | Qualificação activa — sem alteração |
| `qualification_required_fields=null` (padrão) | Comportamento anterior mantido para todos os agentes existentes |
| `agent_mode=consultivo` | Campos obrigatórios não alterados (6 campos) — a menos que override seja configurado |
| `agent_mode=direto` | Campos obrigatórios não alterados (3 campos) — idem |
| Tom "querido/a" | Presente em todos os cenários |
| `is_playground=true` nos leads sandbox | Leads não aparecem no Kanban |
