# Fix: instâncias fantasmas na UazAPI

**Branch:** `fix/uazapi-instancias-fantasmas`
**Status:** Em andamento

---

## Motivação

No painel da própria UazAPI existiam 6 instâncias, quase todas
`disconnected`, várias duplicadas por usuário (ex.: `crm-1-3ef4efd6` e
`crm-1-dc82969b` para o mesmo `user_id=1`). Isso já causou um `429 Too Many
Requests` real ao tentar conectar uma instância de colaborador — o limite do
plano é de 3 dispositivos, e instâncias fantasmas ocupam vaga mesmo
desconectadas.

Objetivo do utilizador: o painel da UazAPI deve refletir só o que cada
usuário realmente usa hoje — ao conectar uma instância nova, a anterior
(mesmo telefone, agora desconectada) deve deixar de existir lá.

---

## Problemas Identificados (estado anterior)

1. **Reconexão com erro gera instância nova e abandona a antiga**
   (`backend-crm/routes/whatsapp_connect.py:244-262`, `connect_whatsapp`):
   quando `connect_core_whatsapp_instance()` falha com 5xx, o código gera um
   `_generate_instance_id()` novo, chama `/instance/init` de novo e
   sobrescreve o ponteiro — a instância antiga nunca é apagada nem
   desconectada na UazAPI.

   Consequência extra (não só cosmética): `upsert_connection()`
   (`backend-core/app/services/whatsapp_connections.py`) resolve por
   `instance_id`, nunca por `user_id` (de propósito — suporta múltiplas
   instâncias por conta). Cada "reinit" cria uma **linha órfã** em
   `whatsapp_connections`. E `get_connection_for_user()` — usada por
   `GET /whatsapp-connections/resolve-by-user`, consumida pelo
   `backend-executors` para saber de qual instância o agente real deve
   enviar mensagem — faz `.filter(user_id, role='agent').first()` sem
   `ORDER BY`. Com múltiplas linhas `role='agent'` para o mesmo usuário, não
   há garantia de resolver para a mais recente.

2. **Remover colaborador monitorado nunca desconecta a instância**
   (`backend-crm/routes/collab_monitor.py:295-312`,
   `DELETE /api/collab-monitor/instances/{id}`) — já documentado como
   "remove o cadastro (não desconecta a instância no core)". Toda remoção
   de colaborador monitorado vira fantasma garantido.

3. **Não existe nenhuma função no código que apague/desconecte uma
   instância na UazAPI** — `backend-core/app/services/uazapi_admin.py` só
   tem `init_instance`, `connect_instance`, `get_status`,
   `configure_webhook`. A única forma de limpar hoje é manualmente no
   painel deles.

(Verificado: `POST /instances/{id}/reconnect` do collab monitor reutiliza o
mesmo `instance_id` sempre — não gera fantasma. Mesma coisa para
`connect_whatsapp`/`qr/refresh` no fluxo normal quando não há erro 5xx.)

---

## Abordagem

```
Causa 1 (reinit) e Causa 2 (delete colaborador)
  → ambas precisam de uma função para apagar instância na UazAPI
  → uazapi_admin.delete_instance() [DELETE /instance, header "token"]
      → rota de serviço: DELETE /whatsapp-instances/{instance_id} (backend-core)
          → core_client.delete_core_whatsapp_instance() (backend-crm)
              → chamada não-bloqueante no reinit (Causa 1)
              → chamada não-bloqueante no delete de colaborador (Causa 2)

Limpeza dos 6 fantasmas já existentes hoje
  → rota admin dedicada (sempre remove localmente, mesmo se a UazAPI falhar)
  → botão "Apagar" em frontend-admin/AdminInstances.tsx
```

Confirmado via código-fonte do node n8n open-source `n8n-nodes-uazapi`
(`UazApi.node.js`) que a UazAPI expõe `DELETE /instance` (header `token`,
igual ao padrão já usado por `connect_instance`/`get_status`) e
`GET /instance/all` (header `admintoken`, não usado neste fix).

---

## Plano de Implementação

### Fase 1 — Capacidade de apagar instância (uazapi_admin + rota de serviço)

**Objetivo:** ter uma função testada e confiável para apagar uma instância
na UazAPI, antes de plugá-la nos dois pontos que geram fantasma.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/services/uazapi_admin.py` | Nova função `delete_instance()` — `DELETE {base}/instance`, header `token`, mesmo padrão de `connect_instance()`/`get_status()` |
| `backend-core/app/services/whatsapp_connections.py` | Nova função `delete_connection_by_instance(db, instance_id)` |
| `backend-core/app/api/whatsapp_instances.py` | Nova rota `DELETE /whatsapp-instances/{instance_id}` (protegida por `_require_service_token`) |
| `backend-crm/core_client.py` | Nova função `delete_core_whatsapp_instance(instance_id)` |

**Teste ao vivo obrigatório antes de generalizar:** chamar `delete_instance()`
contra uma instância fantasma real já existente para confirmar o formato da
resposta (corpo JSON vs. vazio) e ajustar `_request()`/`delete_instance()`
se necessário.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `28fb9b4` | `delete_instance()` + rota de serviço + `delete_connection_by_instance()` + `delete_core_whatsapp_instance()` + testes |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não existia nenhuma forma, no código, de apagar uma instância
WhatsApp na UazAPI — só manualmente no painel deles.

**Agora:** existe uma função (`delete_instance`) e uma rota interna
(`DELETE /whatsapp-instances/{instance_id}`) que apagam a instância na
UazAPI e removem a linha correspondente no nosso banco. Ainda não está
plugada em nenhum fluxo do usuário — isso acontece nas Fases 2 e 3. Também
corrigi um detalhe: a função interna que lê a resposta da UazAPI agora
tolera uma resposta sem corpo (comum em operações de `DELETE`), sem afetar
as outras chamadas que já funcionavam.

**Para validar:** Cenário V1 e V5, abaixo — ambos já validados. V1 (teste ao
vivo) inclusive já apagou de verdade um dos 6 fantasmas reais do painel da
UazAPI (`crm-1-dc82969b`) — o painel já está com 5 instâncias em vez de 6.

### Fase 2 — Corrige Causa 1 (reinit abandona instância antiga)

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/whatsapp_connect.py` | No bloco de reinit (linhas 244-262), após sucesso com `new_instance_id`, chama `delete_core_whatsapp_instance(old_instance_id)` em `try/except` não-bloqueante (mesmo padrão do `_set_whatsapp_webhook` logo abaixo) |
| `docs/architecture/whatsapp-connection.md` | Documentar a limpeza automática no reinit |

### Fase 3 — Corrige Causa 2 (delete de colaborador não desconecta)

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/collab_monitor.py` | Em `delete_collab_monitor_instance`, antes de apagar o cadastro local, chama `delete_core_whatsapp_instance()` em `try/except` não-bloqueante |
| `docs/architecture/collab-monitor.md` | Reescrever a linha que hoje diz "não desconecta a instância no core" |

### Fase 4 — Ferramenta de limpeza manual (painel admin)

**Objetivo:** permitir apagar os 6 fantasmas já existentes hoje, e servir de
válvula de escape manual para qualquer caso futuro que escape das Fases 2/3.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/admin.py` | Nova rota `DELETE /admin/instances/{instance_id}` — apaga na UazAPI e **sempre** remove a linha local (ação explícita do admin) |
| `frontend-admin/src/services/api.ts` | Nova função `deleteInstance(instanceId)` |
| `frontend-admin/src/pages/AdminInstances.tsx` | Botão "Apagar" (ícone `Trash2`) ao lado do "Reconectar", com confirmação |

---

## Fora do escopo (deliberado)

- **Agente Espião** (`spy_agent.py`) tem padrão de conexão temporária
  parecido, mas não foi reportado como problema e já está documentado como
  isolado — fica para iteração futura se também acumular fantasmas.
- Constraint de banco `UNIQUE(user_id, role)` — a Fase 2 já garante 1 linha
  viva por vez na prática; uma constraint rígida arriscaria quebrar em cima
  de linhas duplicadas que já existem hoje em produção.
- `disconnect_instance()` (logout sem apagar) — sem caso de uso identificado
  neste fix.

---

## Checks de Validação

### Cenário V1 — `delete_instance()` funciona contra instância real
- [x] Chamar `delete_instance()` (ou a rota de serviço) contra uma das
      instâncias fantasmas reais existentes hoje
- [x] Confirmar: instância some do painel da UazAPI
- **Validado em:** 08/09/2026 — chamei `delete_instance()` diretamente
  (script descartável, token obtido via `GET /instance/all` com
  `admintoken`, sem tocar no banco de produção) contra `crm-1-dc82969b`
  (fantasma sem telefone/owner, claramente morta — visível no screenshot
  original). Resposta real: `{"info": "The device has been successfully
  disconnected and the instance has been deleted from the database.",
  "response": "Instance Deleted"}` — vem com corpo JSON normal (não vazio;
  a tolerância a corpo vazio em `_request()` seguiu como defesa, mas não foi
  exercida aqui). Confirmado via `GET /instance/all` logo depois: total caiu
  de 6 para 5 instâncias, `crm-1-dc82969b` não aparece mais. Uma tentativa
  de `GET /instance/status` com o mesmo token depois do delete retorna `401
  Invalid token` (não `404`) — a UazAPI invalida o token junto com a
  instância; o tratamento de `404` na rota de serviço continua válido como
  defesa para o caso de tentar apagar de novo algo que já sumiu.
  **Nota:** a linha correspondente em `whatsapp_connections` (produção)
  ainda existe — só apaguei o lado UazAPI diretamente via script, sem passar
  pela rota do backend-core (que exigiria banco local, que esta worktree não
  tem). Essa linha órfã será limpa pela ferramenta da Fase 4.

### Cenário V2 — Reinit limpa a instância antiga (Causa 1)
- [ ] Forçar o caminho de reinit em `connect_whatsapp` (ex.: instance_id
      inválido/expirado propositalmente)
- [ ] Confirmar nos logs `whatsapp reinit` e no painel da UazAPI que a
      instância antiga foi removida
- **Pendente**

### Cenário V3 — Remover colaborador limpa a instância (Causa 2)
- [ ] Cadastrar um colaborador de teste no monitoramento (frontend-crm)
- [ ] Remover pelo frontend-crm
- [ ] Confirmar: instância some do painel da UazAPI
- **Pendente**

### Cenário V4 — Limpeza manual via painel admin
- [ ] No frontend-admin → Instâncias, usar o botão "Apagar" num dos 6
      fantasmas reais existentes hoje
- [ ] Confirmar: some da nossa listagem e do painel da UazAPI
- **Pendente**

### Cenário V5 — Testes automatizados
- [x] `backend-core/tests/test_uazapi_admin.py` — casos para `delete_instance`
      (sucesso, corpo vazio, 404)
- [x] `backend-core/tests/test_uazapi_client_retry.py` — sem regressão (retry
      429/503 continua cobrindo todos os consumidores de `_request()`)
- **Validado em:** 08/09/2026 — 12/12 em `test_uazapi_admin.py`, 12/12 em
  `test_uazapi_client_retry.py`
