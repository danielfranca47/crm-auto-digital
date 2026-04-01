# Otimização do Agente Híbrido Agendador

> Documento de rastreio de problemas e correções do teste `massagem-sensi-vitae`.
> Última atualização: 2026-04-01 — Fix #7, Fix #8 e Fix #9 aplicados. Nenhum problema pendente.

---

## Fixes aplicados (histórico)

| Fix | Problema resolvido | Ficheiros principais |
|---|---|---|
| Fix #1 | `location_preference` obrigatório para gabinete fixo — removido dos defaults de `agenda` | `qualification_guardrails.py`, `qualification_contract.py` |
| Fix #2 | `custom_instructions` ignoradas pelo LLM — injectadas com bloco de prioridade máxima nos prompts filho | `decision_engine.py` |
| Fix #3 | Modo passivo inexistente — novo campo `response_style` (`active`/`passive`) | `ai_profile.py`, `decision_engine.py`, frontend |
| Fix #4 | `price_acceptance` hardcoded — novo campo `qualification_required_fields` configurável por ai_profile | `ai_profile.py`, `qualification_contract.py`, `decision_engine.py`, frontend |
| Fix #4b | Bug de schema: `qualification_required_fields` ausente do Pydantic — campo não era retornado pela API | `backend-core/app/api/ai_profiles.py` (`AIProfileBase`, `AIProfileUpdate`) |
| Fix #5 | Passive mode conflitava com `ESCOPO`/`RECUSAS` do prompt filho — bloco passivo movido para antes do `PAPEL:` | `decision_engine.py` — `_build_child_prompt_qualification` |
| Fix #6 | Sinais de fecho ("fica combinado") não reconhecidos — EXCEÇÃO FECHO adicionada ao mother prompt | `decision_engine.py` — `_build_mother_prompt` |
| Fix #7 | Passive mode falha em perguntas de catálogo (T1) — triggers semânticos expandidos (Fix A), `next_action_hint='reply'` tornado vinculativo no output assembly (Fix B), child recebe instrução de resposta imediata quando hint=reply (Fix C) | `decision_engine.py` — `_build_mother_prompt`, `compose_decision_output`, `_build_child_prompt_qualification` |
| Fix #8 | Confirmação estruturada não enviada no T5 — `extracted_fields` injetado no CONTEXTO do filho `apresentation`; bloco CONFIRMAÇÃO ESTRUTURADA OBRIGATÓRIA activa quando `meeting_scheduled=true` + `presentation_variant=scheduler` | `decision_engine.py` — `_build_child_prompt_apresentation` |
| Fix #9 | Tom SDR/B2B inadequado para nicho de massagem — `presentation_variant` adicionado ao contexto do meta-prompter com instrução explícita: `scheduler` proíbe linguagem de reunião comercial/consultoria e força tom de reserva de serviço alinhado ao nicho; frontend passa `presentation_variant` ao backend via `appointment_mode` (exploratory=scheduler, commercial=sales) | `meta_prompter.py`, `frontend-crm/src/services/api.ts` |

---

## Histórico de testes — Cenário A

| Teste | Score | Lead ID | Condições |
|---|---|---|---|
| Teste 1 | 0/5 | — | Sem fixes |
| Teste 2 | 1/5 | 73 | Fix #1, #2, #3 |
| Teste 3 | 3/5 | 75 | Fix #1–#6 (schema bug corrigido em Teste 3) |

### Teste 3 — Detalhe por turno

| Turno | Resultado | Nota |
|---|---|---|
| T1 | ❌ | Passive mode falha: pediu disponibilidade em vez de apresentar serviços |
| T2 | ✅ | Confirmou Faro + Centro Comercial Algarb + Sala 2 |
| T3 | ⚠️ | Confirma quinta à tarde ✅ mas sem valor 45€ e tom SDR inadequado ❌ |
| T4 | ✅ | Confirma 16h, menciona Daniel, avança para `apresentation` |
| T5 | ⚠️ | Dá morada ✅ + Fix #6 activo (rota correcta) ✅ mas sem confirmação estruturada ❌ |

---

## Checklist de validação — próximo teste (Cenários A, B e C)

### Cenário A — Cliente normal pergunta serviços e agenda
- [x] Turno 1: Agente apresenta serviços e valores (Terapêutica + Exótica + Lingam opcional) — Fix #7
- [x] Turno 2: Agente confirma localização (Faro, Centro Comercial Algarb + Sala 2) ✅ Teste 3
- [ ] Turno 3: Agente confirma disponibilidade quinta-feira à tarde + valor 45€ + tom acolhedor (sem SDR) — Fix #9
- [x] Turno 4: Agente confirma 16h ✅ Teste 3
- [x] Turno 5: Agente envia confirmação estruturada de reserva + Sala 2 — Fix #8

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
| Score global (todos os cenários) | ≥ 7/10 |
| `custom_instructions` aplicadas (Cenário B, T3) | Obrigatório |
| Nenhuma pergunta de `location_preference` | Obrigatório |
| Nenhuma pergunta de `price_acceptance` | Obrigatório |
| Confirmação estruturada enviada (mínimo 1 cenário) | Obrigatório |
| Modo passivo activo — responde antes de perguntar | Obrigatório |

---

## Regressão esperada

| Comportamento | Deve manter-se |
|---|---|
| `response_style=active` (padrão) | Qualificação activa — sem alteração |
| `qualification_required_fields=null` (padrão) | Comportamento anterior para todos os agentes existentes |
| `agent_mode=consultivo` | Campos obrigatórios não alterados (6 campos) |
| `agent_mode=direto` | Campos obrigatórios não alterados (3 campos) |
| Tom "querido/a" | Presente em todos os cenários |
| `is_playground=true` nos leads sandbox | Leads não aparecem no Kanban |
| `presentation_variant=null` (padrão) | Meta-prompter usa `scheduler` como fallback — sem regressão para agentes existentes |
