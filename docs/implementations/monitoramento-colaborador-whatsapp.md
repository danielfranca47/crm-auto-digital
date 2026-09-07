# Monitoramento de WhatsApp de Colaborador (base)

**Branch:** `feat/monitoramento-colaborador-whatsapp`
**Status:** Em andamento

---

## Motivação

Objetivo de negócio (planos Scale/Enterprise, ver
`docs/plans/scale-enterprise-roadmap.md`): permitir que uma conta conecte o
WhatsApp comercial de um colaborador da equipe apenas para **observação** —
sem que o agente de IA responda por ele — alimentando o CRM com os
leads/conversas desse colaborador para acompanhamento de performance.

Decisão de arquitetura (via UazAPI, não a API oficial da Meta — que não serve
para "espelhar" o uso normal de um número comercial já em uso): a instância
monitorada convive em paralelo com instâncias de agente, com separação
estrutural entre "ler" e "enviar" — o agente nunca pode responder no lugar do
colaborador.

Esta é a **base** de 4 funcionalidades planejadas para Scale/Enterprise. As
outras três (IA mãe classificando estágio do lead a partir da conversa
monitorada, tela estilo WhatsApp Web para navegar as conversas, e o gate
comercial `max_instances`/seed dos planos) ficam propositalmente fora de
escopo aqui — vêm depois desta base.

Decisões já validadas com o utilizador:
- Os leads capturados aparecem já nesta fase numa **coluna dedicada do
  Kanban** ("Monitorado"), em vez de ficarem invisíveis até a tela WhatsApp-Web
  existir.
- Se o mesmo telefone escrever para dois colaboradores monitorados diferentes,
  viram **leads separados**, um por colaborador — nunca misturados no mesmo
  card.

---

## Problemas Identificados (estado anterior)

1. **`upsert_connection()` sobrescreve em vez de criar linha nova
   (`backend-core/app/services/whatsapp_connections.py:42-79` e `:82-123`):**
   resolve a conexão existente por `user_id` (`get_connection_for_user()`,
   linha 19-20: `.filter(WhatsappConnection.user_id == user_id).first()`), não
   por `instance_id`. Criar uma 2ª instância para a mesma conta pelo fluxo
   normal (`POST /whatsapp-instances/init` ou `/connect`, chamados de
   `backend-core/app/api/whatsapp_instances.py:203` e `:265`) **sobrescreve**
   a linha existente (troca `instance_id` + token) em vez de adicionar uma
   nova. Bloqueador raiz de qualquer multi-instância, incluindo a comercial
   futura do roadmap Scale/Enterprise.

2. **`resolve-by-user` fica ambíguo com 2 conexões por conta
   (`backend-core/app/api/whatsapp_connections.py:187-211`):** usa o mesmo
   `get_connection_for_user()` (`.first()`, sem `order_by`). É chamado por
   `backend-executors/app/clients/core_client.py:82` para o executor
   descobrir de qual instância o **agente real** deve enviar. Com duas linhas
   para o mesmo `user_id`, o resolve poderia devolver a instância errada —
   risco direto de o agente "responder" pela instância do colaborador
   monitorado.

3. **Sem noção de "colaborador monitorado" em lugar nenhum do sistema:** a
   funcionalidade vizinha existente, o Agente Espião
   (`backend-crm/routes/spy_agent.py` + `services/spy_agent/*`), resolve
   parte da infraestrutura de "conectar uma 2ª instância e capturar mensagens
   sem tocar no pipeline de IA" (roteamento em
   `backend-crm/routes/webhooks.py:289`, handler isolado em
   `spy_inbound_handler.py`), mas serve a um propósito diferente: janela de
   observação **temporária** (14 dias, `spy_agent_runs`) para sugerir ajustes
   de **configuração do AI Profile** — nunca cria leads reais, é 1 instância
   por conta (`spy_agent_config.user_id UNIQUE`), sem conceito de
   colaborador. Não deve ser reaproveitado como está.

---

## Abordagem

```
backend-core: whatsapp_connections ganha `role` ('agent' | 'monitor')
  upsert_connection() passa a resolver por instance_id (não por user_id)
  get_connection_for_user() (usado por resolve-by-user, ou seja, pelo envio
    real do agente) filtra role='agent' — nunca pode devolver uma instância monitor

backend-crm: nova tabela collab_monitor_instances (user_id, instance_id,
  collaborator_name, status)
  novo endpoint de cadastro (nome do colaborador + conectar QR, reaproveitando
    connect_core_whatsapp_instance/init_core_whatsapp_instance, como o
    Agente Espião já faz)

Webhook UazAPI → routes/webhooks.py
  is_monitor_instance(instance_id)?  (mesma posição do is_spy_instance,
    ANTES do filtro from_me — precisamos capturar as mensagens que o
    colaborador manda, não só as que ele recebe)
    → services/collab_monitor/monitor_inbound_handler.py
        → find_or_create_monitor_lead() — chave (user_id, phone, instance_id)
            → nunca reaproveita o mesmo lead de outro colaborador monitorado
            → nasce na categoria "monitoring" (nova coluna dedicada do Kanban)
        → grava mensagem em `messages` (channel='whatsapp'), mesma tabela que
          alimenta o histórico visível no LeadCardDialog
            → mensagem do lead: model='inbound' (mesmo padrão do fluxo real)
            → mensagem do colaborador (fromMe=true): model='human_agent'
              (marcador novo, para nunca ser confundido com resposta da IA)
        → NUNCA chama guardrail.py / orchestrator.py / LLM
        → NUNCA enfileira job whatsapp.send.local
  ├─ senão (grupo, evento connection, etc.) → fluxo atual inalterado
  └─ senão is_spy_instance → fluxo atual do Agente Espião inalterado
  └─ senão → fluxo real do agente (inalterado)

Defesa em profundidade: qualquer rota de envio (whatsapp_send.py /
  core_client.send_whatsapp_message) rejeita explicitamente instance_id cujo
  role seja 'monitor'.
```

---

## Plano de Implementação

### Fase 1 — Corrigir upsert_connection + `role` (pré-requisito de segurança)

**Objetivo:** tornar seguro ter mais de uma instância WhatsApp por conta, sem
quebrar o envio real do agente.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/whatsapp_connection.py` | Nova coluna `role = Column(String, nullable=False, default="agent")` |
| `backend-core/app/services/whatsapp_connections.py` | `upsert_connection`/`upsert_connection_optional_token` passam a buscar por `instance_id` primeiro (criar linha nova quando ausente, nunca sobrescrever outra linha do mesmo `user_id`); `get_connection_for_user()` filtra `role == "agent"` |
| `backend-core/app/api/whatsapp_instances.py` | `init_instance`/`connect_instance` aceitam `role` opcional no payload (default `"agent"`, mantém compat) |
| Migração idempotente (`ensure_column`, padrão já usado no projeto) | Adiciona `role` com default `'agent'` às linhas existentes |

```python
# ANTES — resolve por user_id, sobrescreve qualquer conexão existente
def get_connection_for_user(db: Session, user_id: int) -> Optional[models.WhatsappConnection]:
    return db.query(models.WhatsappConnection).filter(models.WhatsappConnection.user_id == user_id).first()

# DEPOIS — só resolve conexões de agente (usado pelo envio real / resolve-by-user)
def get_connection_for_user(db: Session, user_id: int) -> Optional[models.WhatsappConnection]:
    return (
        db.query(models.WhatsappConnection)
        .filter(models.WhatsappConnection.user_id == user_id, models.WhatsappConnection.role == "agent")
        .first()
    )
```

```python
# ANTES — upsert_connection resolve por user_id (sobrescreve instância existente)
existing = get_connection_for_user(db, user_id)

# DEPOIS — resolve por instance_id (cria linha nova se a instância for outra)
existing = get_connection_by_instance(db, instance_id)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9d288f8` | fix: resolver conexão whatsapp por instance_id em vez de user_id + coluna `role` |

**Detalhes do commit `9d288f8`:**
- `backend-core/app/services/whatsapp_connections.py` — `upsert_connection`/`upsert_connection_optional_token` resolvem por `instance_id`; `get_connection_for_user()` filtra `role == "agent"`
- `backend-core/app/models/whatsapp_connection.py` — nova coluna `role`, default `"agent"`
- `backend-core/app/db.py` — migração idempotente da coluna `role` (SQLite + Postgres) + `CREATE TABLE` de bancos novos
- `backend-core/app/api/whatsapp_instances.py` — `init_instance`/`connect_instance` aceitam `role` opcional no payload (default `"agent"`)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se uma conta tentasse conectar uma 2ª instância WhatsApp (ex.: para monitorar um colaborador), o sistema sobrescrevia silenciosamente a instância principal do agente — trocava o número e o token de acesso, sem avisar nada. Além disso, o processo que decide "de qual número o agente deve enviar mensagens" ficaria ambíguo com duas instâncias na mesma conta.
**Agora:** cada instância é identificada pela sua própria identidade (`instance_id`), não mais pelo dono da conta — então conectar uma 2ª instância cria uma linha nova, sem tocar na primeira. Toda instância também ganhou uma etiqueta (`role`): `"agent"` (padrão, usada pelo agente para enviar) ou `"monitor"` (será usada pelo monitoramento de colaborador, ainda não construído). O processo de envio do agente só enxerga instâncias `"agent"`.
**Para validar:** Cenário C1 (abaixo) — ainda não é possível testar de ponta a ponta nesta fase porque a Fase 2 (cadastro de instância de colaborador) ainda não existe; o C1 completo só é testável depois da Fase 2.

### Fase 2 — Cadastro de instância de colaborador

**Objetivo:** permitir registrar N instâncias monitor por conta, cada uma com
nome do colaborador.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | Nova tabela `collab_monitor_instances` (`user_id`, `instance_id`, `collaborator_name`, `status`, `created_at`, `updated_at`) |
| `backend-crm/routes/collab_monitor.py` (novo) | `POST/GET/DELETE /api/collab-monitor/instances` — cadastra nome do colaborador, conecta QR (reaproveita `connect_core_whatsapp_instance`/`init_core_whatsapp_instance` com `role="monitor"`), lista instâncias, reconecta |
| `frontend-crm` | Tela mínima de cadastro (nome + QR) — sem a experiência "WhatsApp Web" completa, que fica para depois |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `cff1b73` | feat: cadastro de instâncias de colaborador para monitoramento |

**Detalhes do commit `cff1b73`:**
- `backend-crm/database.py` — nova tabela `collab_monitor_instances`
- `backend-crm/core_client.py` — `init_core_whatsapp_instance` aceita `role` opcional
- `backend-crm/routes/collab_monitor.py` — router `/api/collab-monitor` (criar/listar/remover/reconectar instância)
- `backend-crm/app.py` — registra o novo router
- `frontend-crm/src/pages/AiProfile.tsx` — nova aba "Monitoramento"
- `frontend-crm/src/components/agente/MonitoramentoColaboradores.tsx` (novo) — form de cadastro + QR + lista
- `frontend-crm/src/services/api.ts` — métodos `collabMonitor*`

### Relatório da Fase 2 — o que mudou na prática

**Antes:** não existia nenhuma forma de cadastrar o WhatsApp de um colaborador para monitoramento — só o agente principal tinha uma tela de conexão.
**Agora:** a aba "Monitoramento" (dentro de "Perfil de IA") permite dar um nome a um colaborador, conectar o WhatsApp dele via QR code, ver a lista de colaboradores cadastrados com status de conexão, reconectar ou remover.
**Atenção — ainda não é seguro testar com um número real em uso:** até a Fase 3 existir, mensagens recebidas por uma instância conectada aqui ainda passam pelo fluxo **normal do agente** (guardrail → IA → resposta automática), porque o roteamento que isola essas mensagens (`is_monitor_instance`) só é criado na próxima fase. Testar esta fase apenas com um número de WhatsApp de teste/sandbox, nunca com o WhatsApp real de um colaborador.
**Para validar:** ainda não há cenário de "Checks de Validação" aplicável isoladamente — o cadastro em si (formulário + QR aparecendo) pode ser conferido visualmente, mas os Cenários C1-C4 dependem da Fase 3.

### Fase 3 — Roteamento do webhook + ingestão real no CRM

**Objetivo:** mensagens da instância monitor viram leads/mensagens reais no
Kanban, sem nunca acionar IA ou envio.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/collab_monitor/monitor_inbound_handler.py` (novo) | `is_monitor_instance()`, `find_or_create_monitor_lead()`, gravação de mensagens (inbound e `human_agent`), sem guardrail/orchestrator/job de envio |
| `backend-crm/routes/webhooks.py` | Nova checagem `is_monitor_instance(instance_id)` na mesma posição de `is_spy_instance` (antes do filtro `from_me`) |
| `frontend-crm/src/data/mockData.ts` | Nova entrada em `KANBAN_COLUMNS`: `{ id: 'monitoring', title: 'Monitorado', leads: [], color: ... }` |
| `backend-crm/routes/whatsapp_send.py` (ou onde o envio real é validado) | Guard explícito: rejeita envio se o `instance_id` alvo tiver `role="monitor"` |

---

## Checks de Validação

### Cenário C1 — Conexão de colaborador não afeta o agente principal
- [ ] Conta de teste já com WhatsApp do agente conectado e funcionando
- [ ] Cadastrar e conectar uma 2ª instância (colaborador) via QR
- [ ] Confirmar: `GET /whatsapp-connections/resolve-by-user` continua devolvendo a instância do agente (não a do colaborador)
- [ ] Enviar uma mensagem de teste pelo agente e confirmar que chega pelo número certo

### Cenário C2 — Mensagens do colaborador viram lead real
- [ ] Enviar mensagem de um número de teste para o WhatsApp do colaborador monitorado
- [ ] Confirmar: lead aparece na coluna "Monitorado" do Kanban, com nome do colaborador visível
- [ ] Responder pelo próprio WhatsApp do colaborador (fromMe) e confirmar que a mensagem aparece no histórico do card

### Cenário C3 — Nunca dispara IA nem envio automático
- [ ] Confirmar nos logs/tabela de jobs: nenhum job `whatsapp.inbound.n8n` ou `whatsapp.send.local` criado para a instância monitor
- [ ] Confirmar que nenhuma resposta automática é enviada ao lead monitorado

### Cenário C4 — Leads separados por colaborador
- [ ] Mesmo número de telefone de teste manda mensagem para 2 colaboradores monitorados diferentes
- [ ] Confirmar: viram 2 leads distintos, um por colaborador, não o mesmo card

---

## Ajustes Possíveis Pós-Implementação

- IA mãe classificar automaticamente o estágio do lead monitorado e mover entre colunas do Kanban.
- Tela estilo WhatsApp Web (multi-telefone, filtro por colaborador/instância, mídia).
- Gate comercial de planos (`max_instances`, seed `crm_scale`/`crm_enterprise` — já mapeado em `docs/plans/scale-enterprise-roadmap.md`).
