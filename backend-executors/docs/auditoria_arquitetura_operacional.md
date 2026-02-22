# Auditoria técnica de arquitetura (LLM Mãe/Filha + Executor + CRM)

## Escopo analisado
- `backend-executors/app/services/decision_engine.py`
- `backend-executors/app/services/orchestrator_models.py`
- `backend-executors/app/services/llm_service.py`
- `backend-executors/app/runners/whatsapp.py`
- `backend-executors/app/services/meeting_scheduler.py`
- `backend-crm/routes/executor.py`
- `backend-crm/services/jobs_service.py`
- `backend-crm/services/lead_category_policy.py`
- `backend-crm/services/whatsapp_inbound/inbound_handler.py`
- `backend-crm/services/whatsapp_inbound/guardrail.py`
- `backend-crm/services/ai_orchestrator/orchestrator.py`

## 1) Mapeamento da arquitetura atual

### Onde a LLM Mãe é chamada
A chamada da LLM Mãe acontece no executor, em `decision_engine.decide()`, por meio de `llm_service.generate_mother_route(mother_prompt)`.

### Onde o output da Mãe é processado
No mesmo `decide()`, o retorno bruto é:
1. parseado (`_extract_json_payload`),
2. normalizado (`_normalize_null_strings`),
3. validado no schema `MotherDecision.model_validate(...)`,
4. usado para rotear a filha e compor a decisão final (`compose_decision_output`).

### Contrato atual entre Mãe e Executor
Contrato tipado em `MotherDecision`:
- `route_to` (qualification|apresentation|follow-up|closing)
- `perceived_category` (mesmo conjunto + null)
- `confidence` (0..1)
- `reason` (string)

### Contrato atual entre Executor e Filha
Contrato tipado em `ChildResult`:
- `message_text`
- `did_complete_phase`
- `recommended_next_category`
- `outcome`
- `kanban_highlight`
- `signals` (lista de strings)
- `confidence` (0..1)

O executor transforma Mãe + Filha em `DecisionOutput` e envia ao CRM no `result_payload`.

### Onde guardrails validam estágio
Existem camadas diferentes:
- No executor (`decision_engine`):
  - `apply_mother_category_guardrails` para avanço/retrocesso/jump de etapas.
  - `_apply_child_micro_adjustment` para micro avanço sugerido pela filha em qualification.
  - `_sanitize_category_decision` para validar categoria permitida no contexto.
- No CRM (`jobs_service.apply_suggested_category`):
  - valida categoria contra `LEAD_CATEGORIES_SET`.
  - exige sinal inbound para persistir mudança.
  - aplica side effect ao entrar em closing (`apply_closing_bot_disable_side_effect`).

### Onde categorias do funil são definidas e persistidas
- Definição canônica em `LEAD_CATEGORIES` (`jobs_service.py`).
- Disponibilizadas ao executor via contexto (`/api/whatsapp/execution-context` em `routes/executor.py` coloca `allowed_lead_categories` em metadata).
- Persistência de mudança no `complete_job_internal` via `apply_suggested_category`.
- Promoção inicial de inbound (`to-prospect`/`in-progress` -> `qualification`) em `whatsapp_inbound/guardrail.py`.

## 2) Avaliação de evolução (contract e modelos)

### Adicionar campos estruturados ao output da Mãe (signals/objective)
**Viável com baixo acoplamento técnico.**
- O parse da Mãe já passa por payload dict e validação Pydantic.
- Expandir `MotherDecision` para campos adicionais é direto.
- Ponto de atenção: hoje existe dependência textual do `reason` para `meeting_scheduled` (string marker), então ao estruturar sinais a migração precisa manter compatibilidade temporária.

### Executor suporta expansão do contrato?
**Sim, parcialmente pronto.**
- Já existe `decision_trace` para observabilidade e `signals` no output final.
- A composição de decisão é centralizada em `compose_decision_output`, o que facilita inserir `objective`/`next_action` mais granular.
- Porém há decisões hardcoded por rota (`next_action = ask_qualification se qualification senão reply`) que limitam flexibilidade sem ajuste.

### Filhas já recebem contexto para operar por objetivo?
**Parcialmente sim.**
- Recebem lead, ai_profile (incluindo `agent_mode`), playbook, metadata e history.
- Não recebem explicitamente um campo estruturado `objective` vindo da Mãe; hoje inferem pela `route_to` e por `reason` textual.

### Sistema permite comportamentos por perfil de agente?
**Sim para 2 perfis, não completo para 3 modelos propostos.**
- `agent_mode` é injetado no contexto e usado nos prompts (sdr_scheduler/closer).
- Há guardrail específico de SDR para bloquear escalada a closing e automação de reunião para SDR.
- Não há modo consultivo explícito e tipado no contrato atual.

## 3) Complexidade de adaptação incremental

### Módulos que seriam tocados
- Executor:
  - `orchestrator_models.py`
  - `decision_engine.py`
  - `meeting_scheduler.py`
  - possivelmente `schemas/decision.py`
- CRM:
  - `routes/executor.py` (se novo payload exigir persistência extra)
  - `services/jobs_service.py` (validação/persistência de novos sinais)
- Opcional observabilidade:
  - logs/prospection_logs se quiser auditar novo contract estruturado

### Há forte acoplamento entre decisão e texto?
**Sim, moderado.**
- `meeting_scheduled` depende de substring em `reason` da Mãe.
- Prompts e regras estão embutidos em strings longas dentro de `decision_engine.py`.
- `next_action` final depende da rota, não de um objeto de intenção mais rico.

### Risco de quebrar guardrails
**Médio.**
- Guardrails de estágio existem em duas camadas (executor + CRM). Alterar sem compatibilidade pode causar conflito de interpretação.
- Se migrar rapidamente para signals estruturados e remover fallback textual, pode quebrar agenda automática e side effects.

### Necessidade de alterar banco
**Para adaptação mínima: não obrigatória.**
- Com `decision_trace` e `result` JSON já existentes, dá para trafegar novos campos sem migration imediata.
- Se o objetivo for analytics/auditoria forte por colunas indexáveis, aí sim exigirá migration.

## 4) Complexidade de refatoração completa

### O que teria que ser reescrito
- Toda a modelagem de prompts em `decision_engine.py` (Mãe + filhas + regras por rota).
- Composição de decisão e guardrails para usar contrato novo fim-a-fim (sem dependência em `reason` textual).
- Fluxo de meeting scheduler baseado em sinais estruturados.

### O que seria descartado
- Marcadores semânticos textuais (`meeting_scheduled` no reason).
- Parte das regras duplicadas entre prompt e pós-processamento atual.

### Riscos de regressão
- Regressão de roteamento de categoria (funil errado).
- Perda de idempotência comportamental em inbound/outbound.
- Regressão em automações SDR (agendamento + bot_disabled).
- Maior chance de drift entre executor e CRM durante transição.

## 5) Conclusão objetiva

## Caminho mais rápido
**Adaptar incrementalmente** (não refazer).

### Justificativa técnica
- Já existe separação funcional Mãe/Filha com validação tipada e guardrails.
- Já existe suporte parcial a especialização de filhas (qualification/apresentation) e fallback para outras rotas.
- Já existe trilha de decisão (`decision_trace`) e campo `signals` no output final.
- O maior débito está no acoplamento textual de `reason`, que pode ser mitigado por evolução compatível (dual-read: structured fields + fallback textual) sem reescrever todo o pipeline.

### Checklist mínimo recomendado
1. Expandir `MotherDecision` para `agent_mode`, `signals`, `objective`, `next_action` estruturados.
2. Manter compatibilidade: se campos novos ausentes, usar comportamento atual.
3. Fazer `meeting_scheduler` consumir primeiro sinal estruturado, com fallback para `reason` legado.
4. Promover seleção explícita de filha por etapa (incluindo follow-up/closing especializados) mantendo fallback genérico.
5. Introduzir modo `consultivo` em `agent_mode` com regras explícitas de prompt/guardrail.
6. Consolidar validação de transição de estágio para reduzir duplicidade executor+CRM (ou manter duplicidade com responsabilidade clara).
7. Adicionar testes de contrato (Mãe->Executor e Executor->CRM) cobrindo backward compatibility.
