Tarefa: Criar Spec + Plano de Implementação do Playground de Testes
Contexto

Criar o arquivo .md em /docs

O sistema é um CRM com agentes de vendas por IA que operam via WhatsApp. A arquitetura usa um padrão Mãe+Filha: uma LLM Mãe roteia o lead para a fase do funil (qualification, apresentation, follow-up, closing) e uma LLM Filha especializada gera a resposta.
Atualmente, para testar o comportamento dos agentes, é necessário ter um número WhatsApp configurado, uma instância ativa no provider (UazAPI), e enviar mensagens reais. Isto torna os testes lentos, dependentes de infraestrutura externa, e impossíveis de automatizar.
O que precisamos
Um endpoint REST de playground (POST /api/playground/chat) que permita simular conversas completas com qualquer agente configurado, sem depender do WhatsApp nem de nenhuma infraestrutura externa.
Requisitos funcionais

Receber uma mensagem de texto e um ai_profile_id, e retornar o mesmo DecisionOutput que o pipeline real produz — incluindo mother_decision, child_result, e estado atualizado do lead.
Reutilizar o máximo do pipeline existente — o endpoint deve chamar o mesmo decision_engine.decide() que o inbound_handler real chama. A diferença é que não envia mensagem pelo WhatsApp e não depende de webhook, provider, instância ou número de telefone.
Gerir leads de teste — deve ser possível criar um lead de teste (sandbox) que não polua o CRM real, ou reutilizar um lead existente para testes. O lead de teste deve manter estado entre chamadas (qualification_state, category, histórico) para permitir simular conversas multi-turno.
Retornar informação de debug completa — além da mensagem que seria enviada ao lead, retornar: decisão da Mãe (route_to, confidence, reason, signals), resultado da Filha (message_text, field, signals_structured), estado atual do lead (category, qualification_state, missing_fields, filled_fields), e o decision_trace completo.
Funcionar sem autenticação de WhatsApp — zero dependência de UazAPI, webhooks, validação de número, ou qualquer provider de mensageria.
Suportar chamadas sequenciais — cada chamada deve atualizar o estado do lead para que a próxima chamada continue de onde parou (simular conversa real multi-turno).

Requisitos técnicos

Analisar o código-fonte actual (especialmente inbound_handler.py, decision_engine.py, executor.py, guardrail.py, build_context_bundle()) para entender o que precisa ser reutilizado e o que precisa ser contornado (bypass) para funcionar sem WhatsApp.
Identificar todas as dependências que o pipeline atual tem do provider WhatsApp e propor como contorná-las no modo playground.
Propor o schema de request e response do endpoint.
Propor como criar/gerir leads de teste (sandbox) sem poluir dados reais — talvez um flag is_playground no lead, ou uma tabela separada, ou leads temporários com cleanup automático.
Propor onde colocar a rota (em qual serviço/backend) considerando a arquitetura existente.

Como será consumido
O endpoint será consumido por:

Scripts de teste chamados via Claude Code em modo headless (claude -p "corre o teste do agente X" → script faz cURL ao endpoint)
Testes manuais via cURL ou Postman durante desenvolvimento
Futuro frontend de playground (já iniciado mas pendente) que mostrará um chat UI no browser
Testes automatizados em batch — correr cenários pré-definidos por agente × nicho e validar comportamento

O que espero como output

Spec técnica completa do endpoint: rota, request schema, response schema, fluxo interno, dependências.
Plano de implementação com tarefas ordenadas, ficheiros a criar/alterar, e estimativa de esforço.
Identificação de riscos e decisões que precisem ser tomadas (ex: como isolar leads de teste, se precisa de migração de banco, etc.)

Documentação de referência
Consultar os seguintes ficheiros do projecto para entender a arquitetura:

backend-executors/app/services/decision_engine.py — motor de decisão (Mãe + Filhas)
backend-crm/services/ai_orchestrator/orchestrator.py — orquestrador do fluxo inbound
backend-crm/routes/executor.py — monta o ContextBundle e chama o decision_engine
backend-crm/services/inbound_handler.py — handler do webhook WhatsApp (ponto de entrada actual)
backend-crm/services/guardrail.py — cria/promove lead, define categoria inicial
backend-crm/services/qualification_state.py — estado de qualificação do lead
backend-crm/services/field_extractor.py — extração de campos da conversa
backend-crm/services/followup_state.py — estado de follow-up
backend-executors/app/services/llm_service.py — cliente LLM
backend-executors/app/services/orchestrator_models.py — schemas MotherDecision, ChildResult, DecisionOutput