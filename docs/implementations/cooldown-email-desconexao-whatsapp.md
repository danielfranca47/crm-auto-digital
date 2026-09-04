# Cooldown/limite extra no email de desconexão do WhatsApp

**Branch:** `worktree-fix+cooldown-email-desconexao-whatsapp`
**Status:** Todos os cenários validados (04/09/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Hoje o único mecanismo
que evita reenviar o email repetidamente é a lógica de transição
(`active → inactive` dispara; eventos "disconnected" repetidos seguidos, com o
status já local `inactive`, não disparam de novo). Não existe uma protecção
adicional explícita (ex.: cooldown por tempo) para o caso de a conexão oscilar
repetidamente entre `active` e `inactive` em curto espaço de tempo (flapping),
o que geraria um email por ciclo.

---

## Problemas Identificados (estado anterior)

1. **Sem cooldown para flapping:** `connection_event()`
   (`backend-core/app/api/whatsapp_instances.py`) dispara o email sempre que
   detecta `was_active and not is_active`, sem janela mínima entre envios —
   se a sessão cair e reconectar várias vezes seguidas, cada ciclo gera um
   novo email.

---

## Diagnóstico (Plan Mode)

Decisões validadas com o utilizador:
- Janela de cooldown: **30 minutos**.
- Se o email de desconexão for suprimido pelo cooldown, o email de reconexão
  correspondente **também é suprimido** nesse ciclo — evita o utilizador
  receber "Lara reconectou" sem ter recebido o "Lara desconectou" equivalente.

---

## Abordagem

`disconnect_alert_sent_at` tinha dupla função: (1) marcar "há uma desconexão
em aberto" (banner in-app + gate do email de reconexão) e (2) ser limpo
(`None`) assim que a reconexão é confirmada — por isso não servia sozinho de
base para o cooldown, já que é zerado a cada ciclo de flapping.

Solução: nova coluna `last_disconnect_email_at`, independente, **nunca
limpa no reconnect** — guarda o timestamp do último email de desconexão
realmente enviado (ou tentado) para aquela conexão. `disconnect_alert_sent_at`
continua sempre atualizado (mesmo quando o email é suprimido), para o banner
e o "since" continuarem correctos.

```
was_active → not is_active (transição p/ desconectado)
  → sempre marca disconnect_alert_sent_at = now
  → cooldown expirado (last_disconnect_email_at nulo ou > 30min)?
      ├─ sim → envia email de desconexão, actualiza last_disconnect_email_at
      └─ não → NÃO envia email (log informativo), last_disconnect_email_at inalterado

not was_active → is_active (transição p/ reconectado), com disconnect_alert_sent_at preenchido
  → o email de desconexão deste ciclo foi realmente enviado?
      (last_disconnect_email_at >= disconnect_alert_sent_at)
      ├─ sim → envia email de reconexão
      └─ não (foi suprimido pelo cooldown) → NÃO envia email de reconexão
  → limpa disconnect_alert_sent_at = None (sempre)
```

---

## Plano de Implementação

### Fase 1 — Cooldown anti-flapping

**Objetivo:** evitar múltiplos emails de desconexão/reconexão quando a sessão
WhatsApp oscila (flapping) em curto espaço de tempo.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/whatsapp_connection.py` | Nova coluna `last_disconnect_email_at` (DateTime, nullable) |
| `backend-core/app/db.py` | `ensure_whatsapp_connections_columns()` passa a criar também `last_disconnect_email_at` (ALTER TABLE idempotente) |
| `backend-core/app/api/whatsapp_connections.py` | `last_disconnect_email_at` exposto em `WhatsappConnectionOut` |
| `backend-core/app/api/whatsapp_instances.py` | `connection_event()` reescrito com a lógica de cooldown acima; nova constante `_DISCONNECT_EMAIL_COOLDOWN = timedelta(minutes=30)` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3631bba` | Cooldown de 30min anti-flapping no email de desconexão/reconexão do WhatsApp |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se a conexão WhatsApp do utilizador oscilava entre conectada e
desconectada várias vezes seguidas num curto espaço de tempo, cada oscilação
disparava um novo par de emails ("Lara desconectou" + "Lara reconectou").

**Agora:** dentro de uma janela de 30 minutos, só o primeiro email de
desconexão é enviado; oscilações seguintes dentro dessa janela não geram
novo email (nem o de reconexão correspondente). O banner de "WhatsApp
desconectado" no CRM continua a aparecer normalmente em qualquer
desconexão, mesmo quando o email é suprimido pelo cooldown.

**Para validar:** Cenário C1, abaixo (já executado e validado nesta sessão).

---

## Checks de Validação

Não há ambiente de teste automatizado de webhook UazAPI real (depende de
evento externo) nem impacto em frontend/playground — validação feita via
simulação directa do endpoint `POST /whatsapp-instances/connection-event`
contra uma instância local do `backend-core` (SMTP desactivado
propositalmente para não disparar envios reais durante o teste).

### Cenário C1 — Ciclo de flapping completo
- [x] Conexão de teste criada com `status='connected'`
- [x] 1º evento `close` (was_active=True→False, sem email anterior) →
      tentativa de envio do email de desconexão registada no log,
      `disconnect_alert_sent_at` atualizado
- [x] `last_disconnect_email_at` simulado como "enviado agora" (para testar o
      par completo sem depender de SMTP real)
- [x] Evento `connected` (reconexão, par correspondente) → tentativa de envio
      do email de reconexão registada no log, `disconnect_alert_sent_at`
      limpo (`None`)
- [x] 2º evento `close` dentro da janela de 30min → **suprimido**:
      `last_disconnect_email_at` permanece inalterado, `disconnect_alert_sent_at`
      é atualizado normalmente (banner continua correto)
- [x] Evento `connected` seguinte (par cujo email de desconexão foi
      suprimido) → email de reconexão **também suprimido**;
      `disconnect_alert_sent_at` limpo (`None`) na mesma
- **Validado em:** 04/09/2026 — todas as transições de estado no banco
  (`status`, `disconnect_alert_sent_at`, `last_disconnect_email_at`)
  corresponderam exactamente ao comportamento esperado em cada uma das 6
  chamadas ao endpoint.

---

## Ajustes Possíveis Pós-Implementação

Nenhum. A janela de cooldown (30min) e o comportamento do email de
reconexão pareado foram decisões explícitas do utilizador nesta
implementação — não ficaram como trade-off em aberto.
