# Agente Espião — instância isolada + limpeza de instância fantasma

**Branch:** `fix/spy-agent-instancia-isolada`
**Status:** Em andamento

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

### Fase 2 — Limpeza de instância fantasma ao remover

**Objetivo:** ao remover o fone de observação, apagar também a instância na
UazAPI (agora seguro, pois a Fase 1 garante isolamento).

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/spy_agent.py` | `DELETE /instance-config` lê a linha antes de apagar, chama `delete_core_whatsapp_instance()` non-blocking depois |

---

## Checks de Validação

### Cenário P1 — Isolamento da instância espiã
- [ ] Com usuário de teste já com WhatsApp principal conectado, abrir Agente Espião → "Conectar fone de observação"
- [ ] Confirmar: `instance_id` retornado é diferente do instance_id principal
- [ ] Confirmar: `role='spy'` na tabela `whatsapp_connections` do core

### Cenário P2 — Mensagens reais não são desviadas
- [ ] Com o fone espião conectado (instância separada confirmada), simular mensagem real ao número principal
- [ ] Confirmar: pipeline normal roda (nada cai em `spy_agent_messages`)

### Cenário P3 — Refresh/reconnect mantém a mesma instância
- [ ] Deixar QR expirar, clicar "Novo QR code"
- [ ] Confirmar: reconecta a mesma instância espiã (não gera outra)
- [ ] Confirmar: `role` continua `spy` mesmo após reconexão por token expirado

### Cenário P4 — Limpeza no remove
- [ ] Remover a instância espiã pela lixeira
- [ ] Confirmar: instância deixou de existir na UazAPI
- [ ] Confirmar: `GET /api/spy-agent/instance-config` volta a `configured: false`

### Cenário P5 — Troca sem passar pelo remove (defensivo)
- [ ] Com fone já configurado, forçar nova chamada a `/connect`
- [ ] Confirmar: instância antiga é apagada na UazAPI (non-blocking)

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
