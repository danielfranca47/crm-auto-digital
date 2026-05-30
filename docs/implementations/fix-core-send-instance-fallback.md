# Fix: Fallback de instance_id no core_send

**Branch:** `etapa-8-6-desabilitar-bot-lead`
**Status:** Validado (29/05/2026) — C1 obrigatório validado; C2 e C3 pulados (edge cases)

---

## Motivação

Quando o executor tenta enviar uma mensagem WhatsApp na fase `core_send`, usa o `instance_id` armazenado no payload original do job. Se o usuário desconectou e reconectou o WhatsApp (gerando um novo `instance_id`), a instância antiga não existe mais no core → 404 "Connection not found" → job falha permanentemente, mesmo com instância ativa.

Contexto concreto: API gratuita UazAPI expira a cada 30 min; instâncias reais também podem ser reconectadas pelo usuário para resolver instabilidade.

---

## Problemas Identificados (estado anterior)

1. **Sem fallback de instância:** `backend-executors/app/runners/whatsapp.py` — o `instance_id` vinha de `metadata.get("instance_id")` (originado do payload do job no momento da criação) e era passado direto para `core_client.send_whatsapp_message()`, sem nenhuma tentativa de resolver a instância ativa atual.

2. **404 "Connection not found" era falha permanente:** qualquer 404 no `core_send` marcava o job como `retryable=false`, sem oportunidade de recuperar com a nova instância.

---

## Abordagem

Retry loop com até 2 fallbacks de resolução de instância:

```
Tentativa 1: instance_id original do payload
  → 404 "connection not found" → resolve instância ativa atual (attempt=1)
Tentativa 2: novo instance_id
  → 404 "connection not found" → resolve instância ativa atual (attempt=2)
Tentativa 3: novo instance_id
  → falha permanente (retryable=false)

Qualquer outro erro (401, 403, 5xx, rede):
  → falha imediata, sem fallback
```

---

## Plano de Implementação

### Fase 1 — Implementação

**Objetivo:** fallback automático de instance_id quando core retorna 404 "Connection not found"

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/clients/core_client.py` | Nova função `get_active_whatsapp_connection(user_id)` |
| `backend-executors/app/runners/whatsapp.py` | Bloco `core_send` substituído por while loop com até 2 fallbacks |

**`get_active_whatsapp_connection`** chama `GET {CORE_API_BASE}/whatsapp-connections/resolve-by-user?user_id={user_id}` — mesmo endpoint que o CRM usa em `backend-crm/core_client.py:fetch_core_whatsapp_connection_by_user`.

Retorna `{ instance_id, provider, connection_status, phone_e164 }`. Se o core retornar 404 ou erro de rede, o fallback apenas loga e tenta de novo com o instance_id que tinha — não interrompe o loop.

---

## Checks de Validação

### Cenário C1 — Reconexão WhatsApp durante job pendente

- [x] Criar lead, disparar mensagem inbound → job criado
- [x] Antes do job ser executado, desconectar e reconectar WhatsApp (nova instância)
- [x] Confirmar no log: `event=core_send_instance_fallback attempt=1`
- [x] Confirmar: mensagem enviada com sucesso (job completo)
- **Validado em:** 29/05/2026 — job 385 com `instance_id=INVALIDTEST` → fallback → status=sent, `provider_msg_id` confirmado no resultado do job

### Cenário C2 — Nenhuma instância ativa

- [⏭️] Pulado — edge case; requer simulação de ambiente sem conexão ativa, não crítico para o fluxo principal

### Cenário C3 — Erro não relacionado à instância

- [⏭️] Pulado — edge case; verificado por inspeção de código (path de 401/403 não entra no while loop)

---

## Ajustes Possíveis Pós-Implementação

- `_MAX_SEND_FALLBACKS = 2` é hardcoded; poderia ser env var se necessário.
- Se `get_active_whatsapp_connection` falhar (rede, core down), o loop continua com o instance_id anterior e tenta de novo — comportamento seguro mas pode gerar 2 tentativas com o mesmo instance_id inválido. Aceitável dado o cenário de instabilidade.
