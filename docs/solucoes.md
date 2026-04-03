# PROPOSTAS DE SOLUÇÃO — Alinhamento de Guardrails com Intenção de Comportamento

## Contexto

O documento `pretencoes.md` define o comportamento desejado: o agente **nunca** deve bloquear a resposta ao utilizador, a qualificação deve ser complementar à conversa, e o **AI Profile é a única fonte de verdade**.

O diagnóstico (`diagnostic_guardrails.md`) revela que a implementação atual contradiz essas intenções em vários pontos. Este documento propõe soluções concretas, ordenadas por impacto e risco.

---

## MAPA DE CONFLITOS IDENTIFICADOS

| # | Conflito | Arquivo(s) | Impacto |
|---|---|---|---|
| C1 | `REGRA OBRIGATÓRIA` no prompt da mãe força `route_to="qualification"` quando `missing_fields` não vazio | `decision_engine.py` ~929 | Alto — bloqueia resposta |
| C2 | Filha qualification em modo `active` pergunta **sem verificar** se o lead fez uma pergunta | `decision_engine.py` ~1170 | Alto — ignora pergunta do lead |
| C3 | Campos obrigatórios hardcoded em dois ficheiros separados | `qualification_contract.py`, `qualification_guardrails.py` | Médio — duplicação, risco de divergência |
| C4 | `_apply_mode_guardrails` reverte `suggested_category` mesmo que a LLM tenha decidido avançar | `decision_engine.py` ~682 | Alto — sobrescreve decisão da IA |
| C5 | `apply_mode_overrides` injeta `must_collect` fixo para modo `agenda` sem consultar AI Profile | `orchestrator.py` ~101 | Médio — ignora AI Profile |
| C6 | `can_advance_from_qualification` bloqueia movimentação Kanban via API | `qualification_guardrails.py` ~139 | Baixo (afeta UI, não resposta do agente) |
| C7 | `response_style` padrão é `"active"` — força qualificação antes de responder | `decision_engine.py` ~1170 | Alto — comportamento padrão errado |

---

## PROPOSTA 1 — Inverter Prioridade no Prompt da Mãe

**Problema:** C1, C7

**O que mudar:**
Substituir a `REGRA OBRIGATÓRIA DE QUALIFICAÇÃO` no prompt da mãe (`_build_mother_prompt`, ~929) pela lógica inversa:

```
ANTES:
"PRIORIDADE 1 (obrigatória — sistema sobrescreve mesmo se você retornar outra):
 - missing_fields NÃO vazio → route_to = 'qualification'"

DEPOIS:
"PRIORIDADE 1: Sempre responde à mensagem do cliente.
 PRIORIDADE 2: Se a mensagem do cliente não contiver uma pergunta direta
   E missing_fields não estiver vazio, prefere route_to = 'qualification'.
 NUNCA retornes route_to='qualification' se o cliente fez uma pergunta direta.
 NUNCA usas route_to='qualification' como único conteúdo de resposta."
```

**Arquivos a alterar:**
- `backend-executors/app/services/decision_engine.py` — função `_build_mother_prompt`

**Riscos:**
- A LLM pode deixar de qualificar leads com frequência — a pressão de qualificação é reduzida.
- Leads em modos que exigem dados para avançar (ex.: `agenda` sem `availability_window`) podem avançar prematuramente para `closing`.
- Mitigação: manter os guardrails pós-LLM (`_apply_mode_guardrails`) como rede de segurança, mas apenas para a decisão de categoria — nunca para a resposta.

---

## PROPOSTA 2 — Separar Decisão de Categoria da Decisão de Resposta

**Problema:** C1, C2, C4

**Conceito:**
A mãe decide `route_to` (onde o lead vai no pipeline), mas isso **não deve determinar** se o agente responde ou pergunta. A resposta ao utilizador deve ser independente da categoria sugerida.

**O que mudar:**
1. Mãe continua a retornar `route_to` para gestão de pipeline.
2. Adicionar ao output da mãe um campo separado: `reply_mode = "answer" | "qualify" | "both"`.
3. A filha usa `reply_mode`, não `route_to`, para decidir se pergunta ou responde.

```python
# Novo campo no schema de output da mãe
{
  "route_to": "qualification",
  "reply_mode": "answer",        # ← resposta priorizada mesmo que route_to=qualification
  "next_action_hint": "reply"
}
```

**Arquivos a alterar:**
- `backend-executors/app/services/decision_engine.py` — `_build_mother_prompt`, `_build_child_prompt_qualification`
- `backend-executors/app/services/llm_service.py` — schema de `MotherDecision`

**Riscos:**
- Alteração de schema de output da LLM mãe — pode introduzir parsing instável (LLM pode ignorar o novo campo).
- Requer testes extensivos para garantir que `reply_mode` é consistentemente retornado.
- Mitigação: validação de schema com Pydantic + fallback para `reply_mode="both"` quando ausente.

---

## PROPOSTA 3 — Mudar Default de `response_style` para `"passive"`

**Problema:** C2, C7

**O que mudar:**
Alterar o fallback de `response_style` no executor de `"active"` para `"passive"` em todas as leituras:

```python
# ANTES (decision_engine.py ~1170)
response_style = (ai_profile.get("response_style") or "active").strip().lower()

# DEPOIS
response_style = (ai_profile.get("response_style") or "passive").strip().lower()
```

No modo `passive`, a filha **responde primeiro** e só qualifica depois — o que está alinhado com `pretencoes.md`.

**Arquivos a alterar:**
- `backend-executors/app/services/decision_engine.py` — todas as leituras de `response_style` com fallback

**Riscos:**
- Mudança de comportamento silenciosa para todos os utilizadores sem AI Profile configurado.
- Utilizadores com `agent_mode=agenda` podem deixar de qualificar ativamente, perdendo dados necessários para agendamento.
- Mitigação: migração gradual — primeiro apenas para novos AI Profiles; notificar utilizadores existentes.

---

## PROPOSTA 4 — Unificar Campos Obrigatórios numa Fonte Única

**Problema:** C3

**O que mudar:**
Eliminar a duplicação de `MIN_REQUIRED_FIELDS` / `_MIN_REQUIRED_FIELDS` entre executor e CRM. Criar uma fonte única partilhada:

**Opção A — Shared package:**
Mover `MIN_REQUIRED_FIELDS` para um pacote partilhado (ex.: `shared/qualification_schema.json`) lido por ambos os serviços na startup.

**Opção B — AI Profile como única fonte:**
Tornar `qualification_required_fields` obrigatório no AI Profile. Se ausente, usar lista vazia (sem campos obrigatórios hardcoded).

**Opção C — Backend-core como fonte:**
O executor e o CRM consultam o AI Profile via `backend-core` para obter os campos obrigatórios, eliminando as constantes locais.

**Arquivos a alterar:**
- `backend-executors/app/contracts/qualification_contract.py` — remover constante `MIN_REQUIRED_FIELDS`
- `backend-crm/services/qualification_guardrails.py` — remover constante `_MIN_REQUIRED_FIELDS`
- AI Profile schema no `backend-core` — tornar `qualification_required_fields` campo padrão

**Riscos:**
- Opção A: complexidade de sincronização de versões entre serviços.
- Opção B: rompe comportamento para utilizadores sem o campo configurado.
- Opção C: dependência de rede em tempo real no executor — se o core estiver indisponível, a qualificação falha.
- Mitigação: cache local do AI Profile no executor (já existe parcialmente via `context`).

---

## PROPOSTA 5 — Tornar `_apply_mode_guardrails` Configurável via AI Profile

**Problema:** C4

**O que mudar:**
Adicionar uma flag no AI Profile para desativar ou personalizar os guardrails pós-LLM:

```python
# AI Profile
{
  "enforce_category_guardrails": true  # default: true
}

# decision_engine.py _apply_mode_guardrails
if not ai_profile.get("enforce_category_guardrails", True):
    return decision  # skip guardrails
```

**Alternativa mais granular:**
Adicionar `guardrail_fields` ao AI Profile — lista de campos cujo preenchimento bloqueia avanço de categoria:

```json
{
  "guardrail_fields": ["availability_window"]
}
```

**Arquivos a alterar:**
- `backend-executors/app/services/decision_engine.py` — função `_apply_mode_guardrails`
- `backend-core/app/models/` — AI Profile model (novo campo)

**Riscos:**
- Se desativado, leads podem avançar para `closing` sem os dados mínimos de negócio.
- Utilizadores técnicos que sabem o que fazem ficam desbloqueados; utilizadores menos técnicos podem configurar incorretamente.
- Mitigação: documentar o campo; manter `enforce_category_guardrails=true` como default.

---

## PROPOSTA 6 — Corrigir `apply_mode_overrides` para Respeitar AI Profile

**Problema:** C5

**O que mudar:**
Em `orchestrator.py`, antes de fazer `merged.update({"must_collect": [...]})` para modo `agenda`, verificar se o AI Profile já define `must_collect` ou `qualification_required_fields`:

```python
# orchestrator.py ~101 — ANTES
elif agent_mode_normalized == "agenda":
    merged.update({
        "must_collect": ["service_interest", "availability_window", "location_preference", "price_acceptance"],
    })

# DEPOIS
elif agent_mode_normalized == "agenda":
    if not ai_profile.get("qualification_required_fields"):  # só aplica se AI Profile não definiu
        merged.update({
            "must_collect": ["service_interest", "availability_window", "location_preference", "price_acceptance"],
        })
```

**Arquivos a alterar:**
- `backend-crm/services/ai_orchestrator/orchestrator.py` — função `apply_mode_overrides`

**Riscos:**
- Baixo risco — é uma verificação condicional, não remove o comportamento existente para a maioria dos casos.
- Utilizadores com `qualification_required_fields=[]` (lista vazia) podem ficar sem `must_collect` definido.
- Mitigação: tratar lista vazia separadamente de `None`.

---

## PROPOSTA 7 — Reescrever Prompt da Filha de Qualificação

**Problema:** C2

**O que mudar:**
O escopo atual da filha em modo `active` é:

> "Você APENAS faz perguntas de qualificação."

Mudar para:

> "Responde SEMPRE à mensagem do cliente antes de qualificar.
>  Se o cliente fez uma pergunta, responde-a primeiro usando offer_description e custom_instructions.
>  Depois, se houver campos em falta, adiciona uma pergunta de qualificação natural no final.
>  Nunca respondes APENAS com uma pergunta de qualificação."

**Arquivos a alterar:**
- `backend-executors/app/services/decision_engine.py` — função `_build_child_prompt_qualification`

**Riscos:**
- A LLM pode diluir a pergunta de qualificação ou omiti-la.
- Mensagens ficam mais longas (resposta + pergunta).
- Mitigação: ajustar `max_chars` para o modo qualification; testar com playgrounds antes de deploy.

---

## PROPOSTA 8 — Separar Guardrail de Kanban da Lógica de Resposta do Agente

**Problema:** C6

**Contexto:**
`can_advance_from_qualification` (CRM) bloqueia movimentação manual no Kanban. Isso é razoável como proteção de UI, mas não deve influenciar a resposta do agente.

**O que mudar:**
Garantir que `can_advance_from_qualification` é chamado **apenas** na rota de mudança manual de categoria (`/api/leads/:id/category` ou equivalente), e **nunca** na pipeline de IA. Verificar se existe algum ponto onde o CRM chama esta função influenciando o job do executor.

Se o guardrail do CRM já está isolado na API de movimentação manual, nenhuma alteração é necessária — apenas documentar explicitamente a separação.

**Arquivos a verificar:**
- `backend-crm/routes/leads.py` — confirmar que `can_advance_from_qualification` só é chamado em rotas manuais
- `backend-crm/services/qualification_guardrails.py`

**Riscos:**
- Baixo — é uma verificação de isolamento, não uma alteração de comportamento.

---

## PROPOSTA 9 — Frontend: Expor `response_style` no AI Profile

**Problema:** C7 (superfície de controlo)

**O que mudar:**
Na página `AiProfile.tsx`, adicionar um toggle visível para `response_style`:

```
Modo de resposta:
  ○ Ativo — o agente conduz a qualificação (pergunta primeiro)
  ● Passivo — o agente responde o cliente (qualifica naturalmente)
```

Atualmente o campo existe no backend mas pode não estar exposto na UI, levando utilizadores a ficarem com o default `active` sem saber.

**Arquivos a alterar:**
- `frontend-crm/src/pages/AiProfile.tsx`
- `frontend-crm/src/services/api.ts` (se o campo não estiver no contrato de update)

**Riscos:**
- Baixo risco técnico — é UI sobre campo já existente.
- Risco de UX: os nomes "Ativo/Passivo" podem confundir utilizadores. Usar linguagem de negócio: "Conduz a conversa / Segue o ritmo do cliente".

---

## PROPOSTA 10 — Adicionar `qualification_required_fields` como Campo Padrão no AI Profile

**Problema:** C3, C5

**O que mudar:**
No `backend-core`, garantir que ao criar/atualizar um AI Profile, `qualification_required_fields` tem um valor padrão por modo (em vez de `null`). Isso permite que os guardrails do executor e do CRM leiam sempre do AI Profile, eliminando gradualmente as constantes hardcoded.

**Exemplo:**
```python
# Ao criar AI Profile com agent_mode="agenda"
default_fields = {
    "agenda": ["service_interest", "availability_window", "price_acceptance"],
    "consultivo": ["service_interest", "urgency", "decision_role", ...],
    "direto": ["service_interest", "availability_window", "price_acceptance"],
}
ai_profile["qualification_required_fields"] = default_fields.get(agent_mode, [])
```

**Arquivos a alterar:**
- `backend-core/app/routes/` — endpoint de criação/update de AI Profile
- `backend-core/app/models/ai_profiles.py`

**Riscos:**
- Migração de dados: AI Profiles existentes sem o campo ficarão com `null` — adicionar migration que popula o campo com os valores hardcoded atuais.
- Utilizadores com AI Profiles antigos não são afetados se os guardrails mantiverem o fallback para as constantes locais durante a transição.

---

## RESUMO — PRIORIZAÇÃO SUGERIDA

| Proposta | Impacto | Risco | Esforço | Prioridade |
|---|---|---|---|---|
| P1 — Inverter prioridade no prompt da mãe | Alto | Médio | Baixo | **1** |
| P7 — Reescrever prompt filha qualification | Alto | Médio | Baixo | **2** |
| P3 — Mudar default response_style para passive | Alto | Alto | Muito baixo | **3 (com cuidado)** |
| P9 — Expor response_style no AI Profile (frontend) | Médio | Baixo | Baixo | **4** |
| P6 — Corrigir apply_mode_overrides | Médio | Baixo | Baixo | **5** |
| P5 — Guardrails configuráveis via AI Profile | Médio | Médio | Médio | **6** |
| P2 — Separar reply_mode de route_to | Alto | Alto | Alto | **7 (futuro)** |
| P4 — Unificar campos numa fonte única | Médio | Médio | Alto | **8 (futuro)** |
| P10 — qualification_required_fields padrão no core | Médio | Baixo | Médio | **9** |
| P8 — Verificar isolamento guardrail Kanban | Baixo | Baixo | Muito baixo | **10 (auditoria)** |

---

## NOTAS FINAIS

- **P1 + P7** juntos são o caminho mais rápido para alinhar o comportamento com `pretencoes.md` sem redesenhar a arquitetura.
- **P3** é a mudança de menor esforço com maior impacto imediato, mas requer comunicação clara aos utilizadores existentes.
- **P2** (separar `reply_mode` de `route_to`) é a solução arquitetural mais correta a longo prazo, mas exige refactoring do schema de output da LLM mãe e testes extensivos.
- **P4** (fonte única de campos) deve ser considerada um objetivo de médio prazo — a duplicação atual é um risco de divergência silenciosa.
