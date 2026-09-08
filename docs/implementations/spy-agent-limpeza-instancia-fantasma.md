# Agente Espião — instância isolada + limpeza de instância fantasma

**Branch:** `fix/spy-agent-instancia-isolada`
**Status:** Todos os cenários validados (08/09/2026) — pendente: auditoria de contas já afetadas em produção (ver seção abaixo), a rodar antes da graduação

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/uazapi-instancias-fantasmas.md` (já removido do
disco, migrado para `docs/architecture/whatsapp-connection.md`).

Naquela implementação, corrigimos duas causas confirmadas de instância
fantasma na UazAPI (reinit de `whatsapp_connect.py` abandonando a instância
antiga; remoção de colaborador monitorado nunca desconectando na UazAPI) —
ver [`docs/architecture/whatsapp-connection.md`](../architecture/whatsapp-connection.md#apagar-instância--limpeza-de-fantasmas).
Ficou pendente confirmar se o Agente Espião (`backend-crm/routes/spy_agent.py`)
tinha o mesmo problema.

A investigação em Plan Mode confirmou o vazamento pedido **e** encontrou um
bug mais grave, na mesma área de código, que precisava ser corrigido
primeiro para que a limpeza fosse segura.

---

## Problemas Identificados (estado anterior)

1. **Fantasma confirmado:** `DELETE /api/spy-agent/instance-config`
   (`backend-crm/routes/spy_agent.py:558-573`) apagava só a linha local
   `spy_agent_config` — nunca chamava `delete_core_whatsapp_instance()`.
   Diferente de `collab_monitor.py::delete_collab_monitor_instance`
   (linha 296-322), que já faz essa limpeza non-blocking na UazAPI.

2. **Bug mais grave, raiz do problema acima:** o botão "Conectar fone de
   observação" (`frontend-crm/src/components/agente/SpyAgentSetup.tsx::handleConnectSpyInstance`)
   chamava `api.crm.whatsappConnect()` — o mesmo `POST /api/whatsapp/connect`
   usado pela conexão principal do CRM (`backend-crm/routes/whatsapp_connect.py`).
   Esse endpoint resolve a conexão **já existente** do usuário via
   `_resolve_instance_id()` → `GET /whatsapp-connections/me` →
   `get_connection_for_user(role='agent')` (`backend-core/app/services/whatsapp_connections.py:19-27`)
   antes de criar uma nova. Ou seja: se o usuário já tinha o WhatsApp
   principal conectado (caso comum, já que Agente Espião fica dentro do
   AiProfile de quem já usa o CRM), o "fone de observação" acabava sendo
   salvo como sendo a **mesma instância** do agente real — não um fone
   separado, apesar do texto da UI dizer "Conecte um telefone diferente do
   seu CRM".

   Consequência ativa: `backend-crm/routes/webhooks.py:296` verifica
   `is_spy_instance(instance_id)` **antes** do pipeline normal de inbound.
   Enquanto essa configuração existisse, toda mensagem real do WhatsApp do
   usuário era desviada só para `spy_agent_messages` — o agente de IA real
   nunca era acionado, o bot ficava mudo silenciosamente para os clientes
   reais, sem qualquer erro visível.

   Por isso apagar a instância fantasma sem corrigir isso primeiro seria
   perigoso: na maioria dos casos reais, "a instância espiã" e "a instância
   do agente principal" eram a mesma linha — apagar apagaria a conexão real
   do usuário.

3. **Reconexão reclassificava a role:** `POST /reconnect`
   (`spy_agent.py:612`) chamava `init_core_whatsapp_instance(user_id,
   spy_instance_id)` sem passar `role`, caindo no default `"agent"` — cada
   reconexão por token expirado revertia a linha de volta para
   `role="agent"` no core.

---

## Abordagem

```
Conectar fone de observação → POST /api/spy-agent/connect (novo, dedicado)
  → gera instance_id novo (spy-{user_id}-{sufixo}), nunca reaproveita o principal
  → init_core_whatsapp_instance(role="spy") + connect_core_whatsapp_instance
  → persiste spy_agent_config imediatamente (permite reaproveitar /reconnect)
  → retorna QR

Reconectar / renovar QR → POST /api/spy-agent/reconnect (já existia)
  → reinit agora passa role="spy" explicitamente

Remover fone de observação → DELETE /api/spy-agent/instance-config
  → apaga linha local
  → delete_core_whatsapp_instance(spy_instance_id) non-blocking (novo)
```

---

## Plano de Implementação

### Fase 1 — Endpoint de conexão dedicado (isolamento)

**Objetivo:** garantir que o "fone de observação" seja sempre uma instância
UazAPI nova e isolada (`role="spy"`), nunca reaproveitando a instância
principal.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/spy_agent.py` | Novo endpoint `POST /connect`; `POST /reconnect` passa `role="spy"` no reinit |
| `frontend-crm/src/services/api.ts` | Novo método `spyAgent.connect()` |
| `frontend-crm/src/components/agente/SpyAgentSetup.tsx` | `handleConnectSpyInstance`, `startPolling`, `handleRefreshQr` passam a usar os endpoints dedicados do Agente Espião |

```python
# ANTES — reaproveitava a conexão principal do usuário
resp = await api.crm.whatsappConnect()  # POST /api/whatsapp/connect

# DEPOIS — sempre cria instância nova e isolada
resp = await api.spyAgent.connect({})   # POST /api/spy-agent/connect
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b34406d` | backend: `POST /connect` dedicado + `role="spy"` no reinit; frontend: usa endpoints dedicados |

**Detalhes do commit `b34406d`:**
- `backend-crm/routes/spy_agent.py` — novo `POST /connect` (gera instance_id
  próprio, `role="spy"`, apaga a instância antiga na UazAPI de forma
  não-bloqueante se já havia uma diferente configurada); `POST /reconnect`
  passa `role="spy"` no reinit por token expirado; helpers extraídos
  (`_upsert_spy_instance_config`, `_set_spy_webhook`, `_build_connect_response`,
  `_generate_spy_instance_id`, `_sanitize_phone`) reaproveitados pelos
  endpoints já existentes (`/instance-config`, `/start`, `/reconnect`)
- `frontend-crm/src/services/api.ts` — novo `spyAgent.connect()`
- `frontend-crm/src/components/agente/SpyAgentSetup.tsx` —
  `handleConnectSpyInstance` usa `api.spyAgent.connect()` em vez de
  `api.crm.whatsappConnect()`; `handleRefreshQr` usa `api.spyAgent.reconnect()`
  em vez de `api.crm.whatsappRefreshQr()`; polling de conexão usa
  `api.spyAgent.reconnectStatus()` (checa a instância espiã específica) em
  vez de `api.crm.whatsappStatus()` (checava a instância principal)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** ao clicar "Conectar fone de observação" no Agente Espião, se o
usuário já tinha o WhatsApp principal do CRM conectado, o sistema
silenciosamente reaproveitava essa mesma conexão como sendo o "fone espião"
— sem mostrar erro. A partir daí, mensagens reais de clientes paravam de
chegar ao bot de vendas (iam só para o histórico interno do Agente Espião),
sem qualquer aviso.

**Agora:** o botão sempre cria uma conexão WhatsApp nova e separada,
exclusiva para observação — nunca reaproveita o número principal do CRM. O
bot de vendas real continua funcionando normalmente, independente do Agente
Espião estar configurado ou não.

**Para validar:** Cenários P1 (isolamento), P2 (mensagens reais não são
desviadas) e P3 (refresh/reconnect mantém a instância), abaixo.

---

### Fase 2 — Limpeza de instância fantasma ao remover

**Objetivo:** ao remover o fone de observação, apagar também a instância na
UazAPI (agora seguro, pois a Fase 1 garante isolamento).

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/spy_agent.py` | `DELETE /instance-config` lê a linha antes de apagar, chama `delete_core_whatsapp_instance()` non-blocking depois |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b78ece8` | backend: apaga a instância na UazAPI ao remover a config local |

**Detalhes do commit `b78ece8`:**
- `backend-crm/routes/spy_agent.py` — `delete_instance_config` lê
  `spy_instance_id` antes de apagar a linha local; depois de apagar,
  chama `delete_core_whatsapp_instance()` em `try/except` não-bloqueante
  (falha só gera `logger.warning`, nunca impede a remoção local)

### Relatório da Fase 2 — o que mudou na prática

**Antes:** ao clicar no ícone de lixeira para remover o "fone de
observação", o sistema só esquecia a configuração internamente — a conexão
WhatsApp continuava ativa na UazAPI para sempre, consumindo uma instância
sem que ninguém mais a usasse ou soubesse que ela existia.

**Agora:** remover o fone de observação também desconecta e apaga essa
instância na UazAPI, igual já acontece hoje ao remover um colaborador
monitorado.

**Para validar:** Cenário P4 (limpeza no remove) e P5 (troca sem passar pelo
remove), abaixo.

---

## Fase 3 — Diagnóstico + Correção: bugs revelados pelo teste ao vivo (08/09/2026)

### Problema identificado

Testando o Cenário P1 contra a UazAPI real (usuário de teste com WhatsApp
principal já conectado), o QR apareceu corretamente na primeira renderização,
mas assim que o `queryClient.invalidateQueries` disparava (logo após
`POST /connect` retornar), a tela pulava direto para o card "já configurado"
(status "Inactive") — escondendo o QR antes de dar tempo de escanear.

Causa raiz: a Fase 1 passou a persistir `spy_agent_config` imediatamente ao
gerar o QR (decisão deliberada, para permitir que "Novo QR code" reaproveite
`/reconnect` em vez de precisar de um endpoint extra). Mas o ternário em
`SpyAgentSetup.tsx` checava `instanceConfig?.configured` **antes** de
`pendingConnect` — assim que a query invalidada confirmava que a config já
existia (mesmo sem o WhatsApp ter sido escaneado ainda), esse branch vencia.

Efeito colateral do mesmo ponto: o botão "Cancelar" durante o QR só limpava
estado local (`setPendingConnect(null)`) — a instância já tinha sido criada
de verdade na UazAPI (com QR real, token real) e ficava órfã, nunca
escaneada, nunca limpa.

Também notado durante o teste: para usar código de pareamento (alternativa
ao QR), a resposta de `/connect` e `/reconnect` não extraía `pair_code` do
payload da UazAPI — só QR era suportado, mesmo a request já aceitando
`phone`.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-crm/routes/spy_agent.py` | `_PAIR_KEYS` + extração de `pair_code` em `_build_connect_response` (paridade com `whatsapp_connect.py`/`collab_monitor.py`) |
| `frontend-crm/src/components/agente/SpyAgentSetup.tsx` | Ordem do ternário trocada: `pendingConnect` checado antes de `instanceConfig?.configured`; `handleCancelConnect` agora chama `api.spyAgent.removeInstanceConfig()` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `910f355` | fix: prioridade de renderização do QR + limpeza no cancelar + suporte a pair_code |

### Relatório da Fase 3 — o que mudou na prática

**Antes:** ao conectar o fone de observação, a tela do QR podia desaparecer
sozinha antes de dar tempo de escanear; cancelar a conexão no meio do
processo deixava uma instância fantasma na UazAPI (o mesmo tipo de problema
que esta implementação inteira existe para corrigir, só que num ponto novo
introduzido pela própria Fase 1).

**Agora:** o QR fica visível até ser escaneado ou expirar de propósito;
cancelar limpa a instância criada, sem deixar rastro. Também é possível
conectar via código de pareamento (mesmo padrão já usado na conexão
principal), não só QR.

**Para validar:** coberto pelos mesmos Cenários P1 e P3 abaixo (re-executados
após a correção).

---

## Checks de Validação

### Cenário P1 — Isolamento da instância espiã
- [x] Com usuário de teste já com WhatsApp principal conectado, abrir Agente Espião → "Conectar fone de observação"
- [x] Confirmar: `instance_id` retornado é diferente do instance_id principal
- [x] Confirmar: `role='spy'` na tabela `whatsapp_connections` do core
- **Validado em:** 08/09/2026 — usuário de teste (user_id=15, `crm-15-88e456ef`/role=agent/connected já existente) → `/connect` criou `spy-15-f684bee9`/role=spy, totalmente separado. Ponta a ponta com pareamento real (telefone 5547992163692): instância final `spy-15-f6622df7` chegou a `status=connected` sem afetar a instância principal.

### Cenário P2 — Mensagens reais não são desviadas
- [x] Com o fone espião conectado (instância separada confirmada), simular mensagem real ao número principal
- [x] Confirmar: pipeline normal roda (nada cai em `spy_agent_messages`)
- **Validado em:** 08/09/2026 — webhook simulado (`POST /webhooks/whatsapp/uazapi`) para `crm-15-88e456ef` criou lead normalmente (`lead_id=512`, `origin=whatsapp_inbound`, job enfileirado); webhook para `spy-15-f6622df7` foi capturado isoladamente em `spy_agent_messages` (`spy_msg_id=20`). Dados de teste removidos depois.

### Cenário P3 — Refresh/reconnect mantém a mesma instância
- [x] Deixar QR expirar, clicar "Novo QR code"
- [x] Confirmar: reconecta a mesma instância espiã (não gera outra)
- [x] Confirmar: `role` continua `spy` mesmo após reconexão por token expirado
- **Validado em:** 08/09/2026 — QR expirou naturalmente, "Novo QR code" gerou novo QR mantendo `instance_id=spy-15-f684bee9` e `role=spy` inalterados no core.

### Cenário P4 — Limpeza no remove
- [x] Remover a instância espiã pela lixeira
- [x] Confirmar: instância deixou de existir na UazAPI
- [x] Confirmar: `GET /api/spy-agent/instance-config` volta a `configured: false`
- **Validado em:** 08/09/2026 — testado duas vezes: (1) instância nunca escaneada (`spy-15-f684bee9`) removida da tabela `whatsapp_connections` do core por completo ao clicar na lixeira; (2) instância real conectada (`spy-15-f6622df7`, WhatsApp 5547992163692) também removida por completo após uso, confirmando limpeza real na UazAPI (não só local).

### Cenário P5 — Troca sem passar pelo remove (defensivo)
- [x] Com fone já configurado, forçar nova chamada a `/connect`
- [x] Confirmar: instância antiga é apagada na UazAPI (non-blocking)
- **Validado em:** 08/09/2026 — havia uma instância órfã (`spy-15-1a9bcc71`, nunca escaneada) de uma sessão de browser interrompida; nova chamada a `/connect` (com `phone`, gerando pareamento) apagou essa instância antiga automaticamente antes de criar `spy-15-f6622df7`.

---

## Auditoria de contas já afetadas (produção)

Antes desta correção, algumas contas já em produção podem ter
`spy_agent_config.spy_instance_id` igual ao `instance_id` da conexão
principal (`role='agent'`) — ou seja, bots reais possivelmente mudos agora
mesmo. Depois do deploy, cruzar `spy_agent_config.spy_instance_id`
(backend-crm) com `whatsapp_connections` onde `role='agent'` (backend-core)
para o mesmo `user_id`. Qualquer linha coincidente indica uma conta afetada
— remediar apagando a linha `spy_agent_config` daquela conta (não a
instância UazAPI, que é a conexão real) e avisar o utilizador afetado para
reconectar o fone de observação pela nova UI.

---

## Ajustes Possíveis Pós-Implementação

- `POST /instance-config` (registro manual) e `POST /start` com
  `spy_instance_id` explícito continuam existindo sem alteração — não são
  usados pelo fluxo principal do frontend atual, fora de escopo desta
  correção.
