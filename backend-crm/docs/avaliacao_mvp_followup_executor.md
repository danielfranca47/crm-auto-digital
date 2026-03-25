> **Atualização (19/03/2026):** para a proposta mínima do modal de transição sem implementação, ver `backend-crm/docs/mvp_followup_transition_context_contract.md`.

# Plano em etapas — motor de follow-up MVP (núcleo + UX + evolução)

## 1) Premissas e direção arquitetural (estado atual preservado)

Este plano mantém as decisões já aprovadas e aderentes ao código atual:

- `followup_contract` permanece como base operacional no lead.
- Reconciliador periódico detecta follow-ups vencidos.
- Execução confiável reaproveita a infraestrutura de `jobs` existente (claim/retry/backoff/worker).
- LLM filha de follow-up **não** será duplicada.
- A camada de UX (estado visível no card) fica separada da execução do scheduler.
- Inbound continua sendo o mecanismo que interrompe cadência automática.

## 2) Mapa rápido do que já existe hoje (para não duplicar)

- Transição assistida para follow-up já implementada via `/api/leads/start-followup`.
- Persistência de `followup_contract` já implementada no lead.
- Worker e execução baseada em `jobs` já implementados.
- Retry/backoff/polling/claim já implementados no fluxo de jobs.
- Rotas e modelos de decisão já contemplam `follow-up` no executor/decision engine.

> Regra de ouro do plano: toda etapa nova deve **integrar** com esses componentes, não recriá-los.

---

## Etapa 0 — Contrato operacional canônico de follow-up

**Objetivo da etapa**
Definir e padronizar o estado mínimo do follow-up para suportar scheduler, rastreabilidade e exibição no card.

**Tarefa sugerida**
- Evoluir `followup_contract` para um formato canônico com:
  - `status` (`active|closed|paused`)
  - `attempts`
  - `max_attempts`
  - `next_followup_at`
  - `last_followup_at`
  - `stop_reason`
  - `followup_variant`
  - `version`
- No `start-followup`, já iniciar `attempts=0`, calcular `max_attempts` por agente e definir primeiro `next_followup_at`.

**O que precisa ser validado**
- Contrato criado corretamente para `agent_1` e `agent_3`.
- Campos obrigatórios sempre presentes.
- Compatibilidade de leitura com contratos anteriores.

**Critério de aceite**
Todo lead iniciado em follow-up sai do endpoint com contrato operacional completo e pronto para reconciliação.

**Resultado esperado**
Fonte única de estado de follow-up no lead, com semântica estável para backend e frontend.

---

## Etapa 1 — Base de consulta para vencimentos (scheduler-safe)

**Objetivo da etapa**
Garantir consulta eficiente e segura de follow-ups vencidos.

**Tarefa sugerida**
- Adicionar colunas operacionais no `lead` (espelho do contrato), como:
  - `followup_status`
  - `next_followup_at`
- Criar índice para varredura periódica (`followup_status`, `next_followup_at`, `bot_disabled`, `user_id`).
- Sincronizar escrita entre `followup_contract` e colunas espelho.

**O que precisa ser validado**
- Query de vencidos retorna somente `status=active` e `next_followup_at <= now`.
- Leads com `bot_disabled=true` não entram como elegíveis.
- Escrita transacional mantém JSON e colunas espelho consistentes.

**Critério de aceite**
Existe query indexada e previsível para buscar vencidos, sem parsing pesado de JSON em loop.

**Resultado esperado**
Base técnica pronta para reconciliador periódico com baixo risco operacional.

---

## Etapa 2 — Reconciliador periódico (detecção + enqueue)

**Objetivo da etapa**
Introduzir o scheduler MVP sem criar fila paralela.

**Tarefa sugerida**
- Implementar reconciliador periódico no CRM para:
  - identificar vencidos elegíveis
  - aplicar deduplicação/claim lógico por lead
  - enfileirar job canônico de follow-up na tabela `jobs`
- O reconciliador **não** envia mensagem e **não** decide conteúdo.

**O que precisa ser validado**
- Sem geração duplicada de job para o mesmo lead/vencimento.
- Execuções concorrentes do reconciliador permanecem idempotentes.
- Logs operacionais registram detecção e enqueue.

**Critério de aceite**
Reconciliador consegue transformar vencidos em jobs canônicos de forma estável e auditável.

**Resultado esperado**
Ponte funcional entre estado no lead e pipeline já existente de execução por jobs.

---

## Etapa 3 — Job canônico de follow-up no worker atual

**Objetivo da etapa**
Executar follow-up automático no mesmo fluxo operacional já validado no sistema.

**Tarefa sugerida**
- Criar tipo canônico de job de follow-up.
- Habilitar worker atual para consumir esse tipo.
- Reaproveitar claim/complete/fail/retry/backoff existentes.

**O que precisa ser validado**
- Ciclo completo do job: claim → executar → complete/fail.
- Retries funcionam para falhas transitórias.
- Não há regressão do fluxo inbound já existente.

**Critério de aceite**
Follow-up roda com confiabilidade equivalente aos jobs já operacionais hoje.

**Resultado esperado**
Execução de follow-up sem novo executor paralelo e sem duplicação de mecanismos de robustez.

---

## Etapa 4 — Integração com LLM filha (sem duplicação)

**Objetivo da etapa**
Garantir separação correta: scheduler decide quando, IA decide o que enviar.

**Tarefa sugerida**
- Enriquecer contexto do executor com sinais do `followup_contract` (goal, outcome, variant, attempts).
- Reusar rota `follow-up` existente na decision engine.
- Ajustar guardrails por agente (`agent_1` vs `agent_3`) sem criar nova “LLM filha paralela”.

**O que precisa ser validado**
- Mensagens variam corretamente por variante/estado de follow-up.
- Contrato de output da decisão permanece compatível com executor atual.
- Sem regressão em qualification/apresentation/closing.

**Critério de aceite**
Executor passa a gerar mensagens de follow-up contextuais reaproveitando a pilha de IA já existente.

**Resultado esperado**
IA integrada ao motor MVP sem acoplamento indevido entre agendamento e geração de conteúdo.

---

## Etapa 5 — Stop conditions e interrupção por inbound

**Objetivo da etapa**
Impedir conflitos de automação durante conversa ativa e encerrar cadência com critérios universais.

**Tarefa sugerida**
- Implementar fonte única de stop conditions no CRM:
  - `inbound_reply`
  - `deal_closed`
  - `explicit_rejection`
  - `handoff_human` (`bot_disabled=true`)
  - `max_attempts_reached`
- No inbound, cancelar/pausar follow-up automaticamente.
- Após envio automático: `attempts++`, recalcular `next_followup_at` ou encerrar.

**O que precisa ser validado**
- Inbound interrompe scheduler imediatamente.
- Não ocorre novo enqueue após condição de parada.
- `stop_reason` e `status` ficam auditáveis.

**Critério de aceite**
Nenhuma mensagem automática é enviada para lead já interrompido/encerrado.

**Resultado esperado**
Cadência segura, previsível e compatível com conversa em tempo real.

---

## Etapa 6 — Estados visíveis de UX do follow-up (operacional)

**Objetivo da etapa**
Dar visibilidade imediata ao operador após a transição assistida, sem depender da execução do scheduler.

**Tarefa sugerida**
- Definir máquina de estado visual no CRM/frontend para card do lead:
  - `solicitacao_recebida`
  - `plano_em_preparacao`
  - `followup_ativo`
- Exibir feedback logo após fechamento do modal de transição.
- Persistir estado visual derivado do contrato (ou campo dedicado de UX), sem mover responsabilidade de execução para UI.

**O que precisa ser validado**
- Após `start-followup`, card reflete estado visível esperado.
- Estado visual evolui corretamente quando contrato muda para `active`.
- UX não dispara scheduler, apenas reflete estado.

**Critério de aceite**
Operador enxerga, no card, que o follow-up foi recebido e em que ponto operacional ele está.

**Resultado esperado**
Menos ambiguidade operacional no pós-modal e melhor confiança do usuário no fluxo.

---

## Etapa 7 — Visualização do plano no card do lead

**Objetivo da etapa**
Exibir uma prévia útil da cadência planejada, baseada em regras determinísticas do contrato.

**Tarefa sugerida**
- Adicionar no card/drawer de lead:
  - status do follow-up
  - próxima ação prevista
  - próxima data (`next_followup_at`)
  - tentativas (`attempts/max_attempts`)
  - resumo da cadência
- Construir visualização inicialmente por regras fixas derivadas do `followup_contract` (sem nova IA).

**O que precisa ser validado**
- Dados exibidos batem com contrato persistido.
- Alterações após cada envio/inbound refletem no card sem inconsistência.
- Funciona para `agent_1` e `agent_3`.

**Critério de aceite**
Card mostra plano de follow-up legível, confiável e sincronizado com o estado real do lead.

**Resultado esperado**
Visibilidade operacional completa para acompanhamento humano da cadência.

---

## Etapa 8 — Evolução posterior: planejador inteligente e anexos por lead

**Objetivo da etapa**
Preparar evolução de qualidade do follow-up sem bloquear o MVP inicial.

**Tarefa sugerida**
- Criar módulo posterior de “planner” que possa:
  - analisar contexto ampliado do lead
  - recomendar progressão de follow-up
  - sugerir materiais/argumentos
  - alimentar contexto adicional da LLM filha
  - suportar anexos por lead no futuro
- Manter planner como camada opcional e desacoplada do scheduler MVP.

**O que precisa ser validado**
- Motor MVP funciona integralmente sem planner.
- Quando habilitado, planner só enriquece contexto, sem assumir execução do scheduler.
- Sem regressão nos guardrails do fluxo principal.

**Critério de aceite**
Planner entra como melhoria incremental, sem virar dependência crítica do motor básico.

**Resultado esperado**
Roadmap evolutivo claro para inteligência adicional e materiais por lead.

---

## Etapa 9 — Testes E2E, observabilidade e readiness de rollout

**Objetivo da etapa**
Consolidar segurança de produção com testes ponta a ponta e métricas operacionais.

**Tarefa sugerida**
- Cobrir testes de:
  - contrato e transição assistida
  - reconciliador/idempotência
  - execução de job canônico
  - stop conditions/inbound
  - estados UX no card e visualização do plano
- Definir telemetria mínima:
  - `followup_due_found`
  - `followup_job_enqueued`
  - `followup_attempt_sent`
  - `followup_stopped`
  - `followup_ui_state_changed`

**O que precisa ser validado**
- Fluxo completo funciona para `agent_1` e `agent_3`.
- Não há duplicação de envio/job.
- UX permanece coerente com estado operacional real.

**Critério de aceite**
Suite de validação aprovada e indicadores de operação disponíveis para rollout controlado.

**Resultado esperado**
Motor de follow-up MVP pronto para execução incremental com rastreabilidade técnica e visibilidade de negócio.

---

## Resultado esperado da implementação completa

Ao final das etapas:

- O sistema terá um motor de follow-up MVP funcional, previsível e auditável.
- A execução seguirá o desenho aprovado: contrato no lead → reconciliador periódico → jobs existentes → worker/executor → IA gera mensagem → inbound interrompe.
- A UX terá estados claros e visualização do plano no card sem quebrar separação de responsabilidades.
- O planejador inteligente/anexos ficará mapeado como evolução posterior, sem bloquear o núcleo MVP.
