# Mapa Geral de Arquitectura

Guia de navegação para os documentos de arquitectura. Use este ficheiro para
decidir qual doc ler antes de trabalhar numa área, e se deve actualizar um
existente ou criar um novo.

---

## Documentos existentes e áreas cobertas

| Documento | Área | Actualizar quando... |
|---|---|---|
| [`sales-flow.md`](sales-flow.md) | Camada 7 — Fluxo de Venda: fases (p0–p5), blocos tipados, triggers (phase/kw/intent), fire_once, suppress_llm_response, dispatch de system_actions | Novo tipo de bloco, novo flag de trigger, mudança no modelo sequencial, novo destino de acção |
| [`llm-architecture.md`](llm-architecture.md) | Motor de decisão: LLM Mãe, LLM Filhas, contratos (MotherDecision, ChildResult, DecisionOutput), guardrails, fluxo de execução | Novo campo nos contratos, nova LLM Filha, novo guardrail, mudança no `compose_decision_output` |
| [`webhooks.md`](webhooks.md) | Pipeline inbound WhatsApp: webhook UazAPI, filtro de grupos, normalização de messageType, áudio/mídia, bot_disabled, buffer, ContextBundle | Novo tipo de mensagem suportado, novo comportamento de fallback de mídia, nova fonte de `bot_disabled`, mudança no buffer |
| [`pipeline-phases.md`](pipeline-phases.md) | Fases de qualificação, apresentação e fechamento por agent_mode; campos do AI Profile que chegam ao LLM; guardrails anti-loop; hardcodes | Novos campos obrigatórios de qualificação, novo behavior por agent_mode, novo guardrail de fase |
| [`agents.md`](agents.md) | AI Profile (schema, campos, enums, offer_pack) e Agentes Locais (tabela, endpoints, job types, fila); toggle bot por lead | Novo campo no AI Profile, novo agent_mode/template_key, novo job type, novo motivo de `bot_disabled` |
| [`followup.md`](followup.md) | Arquitetura de follow-up: estados (idle/scheduled/paused/completed), reconciliador, circuit breaker, jobs tick, modal de transição | Mudança na máquina de estados, novo tipo de tick, nova lógica de reconciliação/circuit breaker |
| [`playground-parity.md`](playground-parity.md) | Paridade Playground ↔ WhatsApp real: `enrich_context_bundle`, campos do ContextBundle, campos da `PlaygroundChatResponse` | Novo campo no ContextBundle que afecta o LLM, novo campo na resposta do playground |
| [`admin-agents-contract.md`](admin-agents-contract.md) | Contrato AdminAgents frontend ↔ backend: campos expostos em `GET /admin/agents/overview` e `GET /admin/agents/users/{id}` | Novo campo no AI Profile que deve ser exibido no painel admin |
| [`leads-schema.md`](leads-schema.md) | Schema de nome do lead: regra "companyName OU contactName obrigatório" (CHECK + Pydantic + form), pontos de criação e seus fallbacks, convenção de exibição `leadDisplayName` | Novo ponto de criação de lead, mudança na regra de nome obrigatório, novo componente de exibição do nome do lead |
| [`humanization.md`](humanization.md) | Humanização comportamental: delay de resposta, typing indicator, quebra de mensagem por pontuação, janela de horário, áudio de voz (myaudio/ptt) | Mudança no cálculo de delay, novo campo de availability, novo tipo de mídia, mudança no split de mensagens |
| [`auth-email.md`](auth-email.md) | Auth e gestão de utilizadores: endpoints de register/login/forgot-password/reset/change-password, modelo User (campos), PasswordResetToken, email SMTP via Resend, rotas públicas frontend-crm, painel admin de utilizadores | Novo endpoint de auth, mudança no modelo User, novo campo de config SMTP, novo template de email, nova rota pública |
| [`plans-limits.md`](plans-limits.md) | Feature gates por plano: `follow_up_enabled`, `playground_monthly_limit` em entitlements; `plan_gates.py`; tabela `playground_usage_monthly`; campo `playground_monthly` em `/usage`; padrão de toast upgrade CTA | Novo campo de limite em `plan_limits`, novo gate numa rota do CRM, novo campo em `/usage` |
| [`agenda.md`](agenda.md) | Agenda de compromissos: vistas mensal/semanal/diária, posicionamento CSS grid, slot-click, ScheduleAppointmentDialog, API appointments, tabela `appointments`, side-effects de criar/cancelar/reagendar, cancelamento/reagendamento via IA, eventos Google (badge, somente-leitura, sync), título e lembrete de reunião gerados por IA (tom/nicho, retry, early vs. final) | Nova vista ou constante de grid, novo campo em AppointmentOut, mudança na interacção slot-click, novo side-effect de criação/cancelamento, mudança no comportamento de eventos Google, mudança no prompt/retry do título ou lembrete via IA |
| [`google-calendar.md`](google-calendar.md) | Integração Google Calendar: OAuth2 por utilizador, serviço push/pull (fail-silent), fluxo de tokens, endpoint google-sync, upsert + cleanup | Novo scope OAuth, nova função do serviço, mudança no algoritmo de sync, novo campo mapeado do Google Event |
| [`billing-efi.md`](billing-efi.md) | Gateway de pagamento Efí Bank: checkout sob demanda, cliente OAuth2, webhook de confirmação, activação/renovação/cancelamento de subscriptions, variáveis de ambiente | Nova oferta/plano, mudança no fluxo de checkout ou webhook, novo campo de status Efí, mudança na lógica de `payment_event` |
| [`knowledge-base.md`](knowledge-base.md) | Base de Conhecimento: categorias guiadas, `knowledge_items`/`knowledge_item_media`, categorias `allowMultiple` (`service_pricing_table`), formato `structured_v1`, agregação para o LLM, wizard de onboarding, ingestão de materiais por IA (`source_type='ai_extracted'`) | Nova categoria guiada, nova categoria `allowMultiple`, mudança no formato estruturado, mudança em `_load_knowledge_items()`, mudança no wizard ou na esteira de ingestão (extractors/classifier/worker) |
| [`agent-local-app.md`](agent-local-app.md) | App desktop agent-local: auth passwordless, pesquisa Google Maps (proxy/chave própria/Selenium), prospecção WhatsApp individual/lote, Kanban remoto (automação Fase 10) e local (não-assinante), painel Assistente IA, geração de copy remota/local, prompt personalizado | Novo ecrã/painel no app, novo modo de pesquisa, mudança no fluxo de prospecção ou Kanban local/remoto, novo campo propagado na geração de copy |

---

## Mapa de componentes → documentos

```
WhatsApp → UazAPI webhook
  └─ webhooks.md           ← filtro de grupo, áudio, media_fallback, buffer
       └─ inbound_handler
            └─ guardrail   ← bot_disabled (agents.md)
            └─ orchestrator (ContextBundle)
                 └─ playground-parity.md

decision_engine.decide()
  ├─ LLM Mãe + Filhas      ← llm-architecture.md
  └─ _evaluate_sales_flow_phases
       └─ sales-flow.md    ← blocos, triggers, fire_once, dispatch

Pipeline de fases
  └─ pipeline-phases.md    ← qualification, presentation, closing por agent_mode

AI Profile / Agentes
  └─ agents.md             ← schema, offer_pack, bot toggle, agentes locais

Follow-up
  └─ followup.md           ← estados, reconciliador, circuit breaker

Painel Admin
  └─ admin-agents-contract.md
```

---

## Decisão rápida: actualizar existente vs criar novo

### Actualizar doc existente

A maioria das features altera áreas já documentadas. Antes de criar um ficheiro novo, verificar se encaixa num existente:

| A mudança afecta... | Documento a actualizar |
|---|---|
| Agenda (vistas, posicionamento, slot-click, ScheduleAppointmentDialog, AppointmentOut) | `agenda.md` |
| Eventos Google na agenda (badge, somente-leitura, sync button) | `agenda.md` + `google-calendar.md` |
| Auth endpoints, User model, password reset, email service, rotas públicas do frontend-crm | `auth-email.md` |
| Google Calendar OAuth (endpoints, tokens, scopes, env vars) | `auth-email.md` + `google-calendar.md` |
| Google Calendar service (push/pull, retry, mapeamento de campos) | `google-calendar.md` |
| Delay de resposta, typing indicator, quebra de mensagem, janela de horário, myaudio | `humanization.md` |
| Novo bloco/trigger/flag no Fluxo de Venda | `sales-flow.md` |
| Novo campo em MotherDecision, ChildResult ou DecisionOutput | `llm-architecture.md` |
| Nova LLM Filha ou guardrail de decisão | `llm-architecture.md` |
| Novo tipo de mensagem WhatsApp suportado | `webhooks.md` |
| Mudança no comportamento de áudio ou mídia inválida | `webhooks.md` |
| Novo campo no AI Profile | `agents.md` |
| Novo motivo para `bot_disabled` | `agents.md` + `webhooks.md` |
| Novos campos obrigatórios de qualificação | `pipeline-phases.md` |
| Novo comportamento por `agent_mode` | `pipeline-phases.md` |
| Campo novo no ContextBundle que afecta o LLM | `playground-parity.md` |
| Campo novo na `PlaygroundChatResponse` | `playground-parity.md` |
| Mudança no reconciliador de follow-up | `followup.md` |
| Novo campo no overview ou detalhe de utilizador do painel admin | `admin-agents-contract.md` |
| Regra de nome obrigatório do lead (companyName/contactName), novo ponto de criação de lead, convenção de exibição `leadDisplayName` | `leads-schema.md` |
| Checkout, webhook Efí, activação/renovação/cancelamento de subscriptions | `billing-efi.md` |
| Nova categoria da Base de Conhecimento, mudança em `knowledge_items`/agregação para o LLM | `knowledge-base.md` |
| App desktop agent-local (auth, pesquisa Maps, prospecção WhatsApp, Kanban local/remoto, Assistente IA, copy local/remota) | `agent-local-app.md` |

### Criar novo documento

Criar `docs/architecture/<nome>.md` quando a feature:
- Introduz uma área de responsabilidade **sem doc existente** (ex.: novo serviço, novo domínio de negócio)
- É grande o suficiente para não caber como secção num doc existente (regra prática: >3 conceitos distintos, >5 arquivos de código envolvidos)
- Tem comportamento não-trivial que futuros contribuidores precisarão de entender antes de alterar

**Exemplos que justificariam um novo doc:**
- Sistema de billing/pagamentos
- Pipeline de prospecção com IA (novo serviço)
- Autenticação multi-tenant (se arquitectura mudar significativamente)
- Integração com CRM externo (novo domínio)

---

## Regra de manutenção

Os docs de arquitectura são um **espelho do código actual** — enxutos e confiáveis.

- Reescrever a secção afectada (não acrescentar parágrafos de "antes era X, agora é Y")
- Sem histórico de implementação — isso pertence ao `docs/implementations/`
- Verificar antes de cada commit se a mudança afecta uma área documentada aqui
