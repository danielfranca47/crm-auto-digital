# Alerta de desconexão do WhatsApp

**Branch:** `fix/alerta-desconexao-whatsapp`
**Status:** Todos os cenários validados (24/08/2026) — pronto para graduação

---

## Motivação

Dois usuários em produção (gabrielsmith.original@gmail.com,
aydebarbaraqod@gmail.com) reportaram que o agente para de responder no dia
seguinte à conexão via QR code, mesmo com o aparelho ainda listado como
"conectado" no WhatsApp do telemóvel do cliente.

Causa raiz identificada: a UazAPI já é instruída a avisar sobre dois tipos de
evento — `"messages"` e `"connection"` — sempre que um cliente
conecta/reconecta (`backend-crm/routes/whatsapp_connect.py:198`). Ou seja, a
UazAPI já envia um evento `connection` quando a sessão cai — só que o endpoint
que recebe o webhook descartava qualquer evento fora de
`{"messages", "message"}` (`backend-crm/routes/webhooks.py:248`):

```python
if event not in {"messages", "message"}:
    return {"status": "ignored", "reason": "event_not_messages"}
```

Consequência dupla: (1) `WhatsappConnection.status` (backend-core) nunca era
atualizado quando a sessão caía de verdade — ficava congelado em
"conectado"/"active" indefinidamente, porque o único outro caminho de escrita
é sob demanda (`GET /whatsapp-instances/status`, chamado só enquanto a tela de
Conexão está aberta com QR pendente); (2) ninguém era avisado — nem o cliente,
nem o admin. Quando o envio de mensagem falhava por causa disso, o executor
tentava de novo até 3x e desistia silenciosamente (só log técnico,
`backend-executors/app/runners/whatsapp.py:1086-1094`).

**Nota operacional (fora do código):** esta correção é só para daqui para a
frente — não reenvia sozinha um evento `connection` para conexões que já
caíram no passado (a UazAPI não reenvia webhooks antigos). Para os dois
usuários já afetados, o passo prático é pedir para eles reconectarem agora.

---

## Problemas Identificados (estado anterior)

1. **Evento `connection` descartado:** `backend-crm/routes/webhooks.py:248` —
   qualquer evento fora de `{"messages","message"}` retorna `ignored` sem
   nenhuma ação, incluindo o evento `connection` que a própria UazAPI já
   envia.
2. **Status da conexão nunca atualizado em segundo plano:**
   `backend-core/app/models/whatsapp_connection.py` — `status` só é escrito em
   `init`/`connect` (na resposta da UazAPI) ou sob demanda em
   `GET /whatsapp-instances/status`. Sem processo em segundo plano, fica
   "congelado".
3. **Nenhum alerta ao usuário:** falhas de envio por conexão inativa
   (`backend-executors/app/runners/whatsapp.py:1077-1094`) só geram log
   técnico — o cliente não é avisado para reconectar.

---

## Abordagem

```
UazAPI → POST /webhooks/whatsapp/uazapi   (event="connection")
  → backend-crm (routes/webhooks.py):
      loga payload bruto (formato do evento connection não documentado hoje)
      → core_client.report_whatsapp_connection_event(instance_id, raw_payload)
          → backend-core: POST /whatsapp-instances/connection-event (novo,
            protegido por X-Service-Token)
              → uazapi_admin.extract_connection_meta(raw) → status_value
              → connections_service.get_connection_by_instance(instance_id)
              → compara normalize_connection_status_for_crm(status ANTES)
                vs (status DEPOIS)
              → grava o novo status sempre (corrige o "congelamento")
              → SE a transição foi active → inactive:
                  busca User pelo user_id da connection
                  renderiza + envia email (best-effort, try/except)
  ← sempre 200 para a UazAPI (mesmo se o core estiver fora, best-effort)
```

Email dispara só na transição active→inactive (não em todo evento
"disconnected" repetido) — o segundo evento já vê o status local como
"inactive" e não repete o envio. Reconexões (inactive→active) só atualizam o
status, sem email de confirmação.

---

## Plano de Implementação

### Fase 1 — Processar evento connection + alertar por email

**Objetivo:** parar de descartar o evento `connection` da UazAPI, manter o
status real da conexão atualizado, e avisar o dono da conta por email quando
a sessão cai.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/webhooks.py` | Trata `event == "connection"` antes do filtro que descarta eventos não-`messages`: loga payload, chama `core_client.report_whatsapp_connection_event`, sempre responde 200 |
| `backend-crm/core_client.py` | Nova função `report_whatsapp_connection_event(instance_id, raw_payload)` |
| `backend-core/app/api/whatsapp_instances.py` | Nova rota `POST /whatsapp-instances/connection-event` (service-token) |
| `backend-core/app/services/email_service.py` | Nova `render_whatsapp_disconnected_email(name, login_url)` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `42732ee` | webhook trata event="connection", repassa ao core, nova rota connection-event, email de alerta |

**Detalhes do commit `42732ee`:**
- `backend-crm/routes/webhooks.py` — novo bloco antes do filtro `event_not_messages`: loga payload bruto do evento `connection`, chama `report_whatsapp_connection_event` (try/except, sempre responde 200)
- `backend-crm/core_client.py` — nova `report_whatsapp_connection_event(instance_id, raw_payload)`
- `backend-core/app/api/whatsapp_instances.py` — nova rota `POST /whatsapp-instances/connection-event`: extrai status via `uazapi_admin.extract_connection_meta`, actualiza `WhatsappConnection.status`, dispara email na transição active→inactive
- `backend-core/app/services/email_service.py` — nova `render_whatsapp_disconnected_email(name, login_url)`, seguindo o padrão visual das outras `render_*_email`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando a sessão do WhatsApp de um cliente caía, o sistema não ficava
sabendo — a UazAPI já avisava, mas o aviso era descartado sem nenhuma ação. O
status ficava congelado como "conectado" e ninguém era alertado.

**Agora:** o mesmo aviso da UazAPI é processado: o status real é actualizado
no banco, e quando a conexão passa de activa para inactiva, o dono da conta
recebe um email pedindo para reconectar.

**Para validar:** Cenários C1 e C2, abaixo.

---

## Checks de Validação

### Cenário C1 — Evento connection com sessão caída atualiza status e envia email
- [x] Com uma connection existente no banco do backend-core com `status="active"`
- [x] Simular `POST /webhooks/whatsapp/uazapi?secret=...` com `event="connection"`
      e payload indicando desconectado
- [x] Confirmar: `WhatsappConnection.status` deixou de normalizar como "active"
- [x] Confirmar: tentativa de envio de email ocorreu (log), sem quebrar a resposta 200
- **Validado em:** 24/08/2026 — backend-core (porta 8001) e backend-crm (porta
  8000) rodando localmente contra bancos SQLite isolados (frescos, na
  worktree), com `SMTP_HOST` vazio de propósito para não disparar email real
  via o provedor de produção (Resend). Criado user + `whatsapp_connections`
  com `status="active"` (instance_id=`test-instance-1`). POST simulado com
  `{"event":"connection","instance":"test-instance-1","status":"disconnected"}`
  → resposta `{"status":"ok","reason":"connection_event_processed"}`; banco
  confirmado com `status="disconnected"`; log do core mostrou
  `connection_event: falha ao enviar email de desconexão user_id=1 error=SMTP
  não configurado` — confirma que a tentativa de envio foi disparada
  corretamente pela transição active→inactive, e que a falha (esperada, sem
  SMTP configurado no teste) foi tratada como best-effort sem quebrar a
  resposta 200.

### Cenário C2 — Evento repetido não duplica o email
- [x] Repetir o mesmo evento "disconnected" duas vezes seguidas
- [x] Confirmar: o disparo de email só ocorre na primeira vez
- **Validado em:** 24/08/2026 — reenviado o mesmo payload; resposta 200 OK
  novamente, mas sem nova linha de log de tentativa de email (a connection já
  estava `disconnected`, então `was_active` era `False` — sem transição, sem
  disparo). Status no banco permaneceu `disconnected`.

### Cenário C3 — Payload real (ambiente de teste real da UazAPI)
- [x] Confirmar o payload real do evento `connection` contra a UazAPI de
      verdade (não simulado)
- [x] Confirmar que `extract_connection_meta` extrai `status_value`
      corretamente do payload real
- **Validado em:** 24/08/2026 — teste ao vivo com instância de teste dedicada
  (`teste-alerta-desconexao-c3`, criada e depois apagada da UazAPI só para
  este teste) e número de WhatsApp descartável do próprio utilizador
  (+351961649355), via túnel ngrok apontando o webhook para o backend-crm
  local. Conectado por código de pareamento, depois desconectado
  deliberadamente duas vezes (remover aparelho no telefone) para observar o
  payload real do evento `connection`. Ver detalhes e o payload capturado na
  Fase 1.1, abaixo — este teste revelou e permitiu corrigir um bug real antes
  de ir para produção.

---

## Fase 1.1 — Diagnóstico + Correção: `instance_id` mal resolvido no evento connection (24/08/2026)

### Problema identificado

O teste ao vivo (Cenário C3) revelou que o payload real do evento `connection`
tem um formato diferente do evento `messages` nesse ponto específico: em vez
de `payload["instance"]` ser a *string* com o instance_id (como é para
`messages`), no evento `connection` a UazAPI aninha o **objeto inteiro** da
instância ali:

```json
{
  "BaseUrl": "https://digitalpro.uazapi.com",
  "EventType": "connection",
  "event_id": "acb90d3a-d874-47dd-8734-9da810cd9eba",
  "instance": {
    "name": "teste-alerta-desconexao-c3",
    "status": "disconnected",
    "lastDisconnect": "2026-08-24 21:20:34.748Z",
    "lastDisconnectReason": "401: logged out from another device"
  },
  "instanceName": "teste-alerta-desconexao-c3",
  "owner": "351961649355",
  "token": "...",
  "type": "LoggedOut"
}
```

`backend-crm/routes/webhooks.py:112` (`instance_id = payload.get("instance")
or payload.get("instanceName")`) — código pré-existente, usado por todo o
handler — assumia que `payload["instance"]` era sempre uma string. Para o
evento `connection`, isso resultava num **dict** sendo usado como
`instance_id`, que o Pydantic de `ConnectionEventPayload.instance_id: str`
(backend-core) rejeitava com `422 Unprocessable Content` — capturado pelo
try/except best-effort (sem quebrar a resposta 200 à UazAPI), mas a
atualização de status e o email **nunca chegavam a rodar**. Confirmado nos
logs do teste: 4 tentativas com `422`/`falha ao repassar ao core` antes da
correção.

### Correção

Resolução de `instance_id` feita localmente dentro do bloco `if event ==
"connection"` (não altera a variável `instance_id` global usada por
`messages`, para não arriscar o pipeline já em produção): se
`payload["instance"]` for um dict, usa `.get("name")` (com fallback
`instanceId`/`id`); senão, usa como string diretamente. Também mudei o log de
captura do payload bruto de `logger.info` para `logger.warning` — descoberta
lateral do mesmo teste: o `backend-crm` não configura nível do root logger em
lugar nenhum, então **todo `logger.info` do serviço é invisível hoje**, local
e em produção (ver Ajuste Possível abaixo). `warning` garante visibilidade
imediata sem depender dessa correção maior.

| Arquivo | Mudança |
|---|---|
| `backend-crm/routes/webhooks.py` | Resolução de `instance_id` específica para `event=="connection"` (trata `payload["instance"]` como dict ou string); log de captura do payload passa de `info` para `warning` |

Validado com um segundo ciclo completo (conectar → desconectar de propósito)
após a correção: evento processado com `200 OK` (sem 422), status gravado
corretamente no banco (`connected` → `disconnected`), e email disparado
exatamente uma vez na transição real (log:
`connection_event: falha ao enviar email de desconexão user_id=1 error=SMTP
não configurado` — esperado, SMTP desligado de propósito no teste).

### Commits Fase 1.1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9cd10c0` | fix: resolver instance_id do evento connection como objeto aninhado |

---

## Ajustes Possíveis Pós-Implementação

- **Verificação periódica de status (health-check)** — rede de segurança para
  o caso de o webhook não ser entregue. Prioridade urgente — ver
  `docs/implementations/whatsapp-status-healthcheck.md`.
- **`logger.info` invisível em todo o `backend-crm`** — descoberto durante o
  teste do Cenário C3: nenhum lugar do serviço configura o nível do root
  logger (`logging.basicConfig` ou equivalente), então todo log `INFO` do
  código da aplicação (não só o meu) fica invisível tanto local quanto em
  produção, mesmo com `uvicorn --log-level info` (essa flag só afeta os
  loggers internos do uvicorn). Vale um ajuste app-wide separado — maior que
  o escopo desta implementação, e com possível efeito colateral de tornar os
  logs de produção mais verbosos (todo INFO pré-existente passaria a
  aparecer), por isso não incluído aqui sem decisão explícita do utilizador.
- Notificação de "reconectado com sucesso" (inactive→active) — silencioso por
  agora.
- UI in-app (sino/notificação no CRM) — o sistema de notificações hoje é
  100% lead-cêntrico; construir uma superfície de notificação de conta é
  escopo maior, fora desta iteração.
- Cooldown/rate-limit de email além do que a lógica de transição já garante
  naturalmente.
