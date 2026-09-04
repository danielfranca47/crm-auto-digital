# Notificação de reconexão bem-sucedida do WhatsApp

**Branch:** `feat/notificacao-reconexao-whatsapp`
**Status:** Todos os cenários validados (04/09/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/alerta-desconexao-whatsapp.md`. Aquela implementação
envia um email ao utilizador quando a conexão WhatsApp cai
(`active → inactive`), mas fica silenciosa na transição inversa
(`inactive → active`) — o utilizador reconecta e não recebe nenhuma
confirmação de que voltou a funcionar.

---

## Problemas Identificados (estado anterior)

1. **Sem confirmação de reconexão:**
   `backend-core/app/api/whatsapp_instances.py::connection_event()` só dispara
   email quando `was_active and not is_active`; a transição
   `not was_active and is_active` não tem nenhuma ação associada.

---

## Diagnóstico

**Já existe?** Não. `connection_event()` (linhas 308-367) só trata a
transição `was_active and not is_active` (linha 348). A transição inversa
não tem nenhuma ação associada.

**Risco identificado:** disparar o email sempre que `not was_active and
is_active` for verdade geraria falsos positivos — o primeiro `connect()` de
uma instância nova também produz essa transição (status local nasce
`"active"` por default no model, mas o status real inicial reportado pela
UazAPI pode ser `"connecting"` antes do primeiro evento `"connected"`). Sem
guarda, o utilizador receberia um email de "reconectado" logo na
configuração inicial.

**Decisão:** só enviar o email de reconexão quando a queda anterior **de
facto gerou** o email de desconexão — não em toda transição
`inactive → active`. Guardamos isso numa coluna nova.

---

## Abordagem

Coluna nullable `disconnect_alert_sent_at` (DATETIME/TIMESTAMPTZ) em
`whatsapp_connections`:

```
connection_event()
  status_value, was_active, is_active (como já existia)

  if was_active and not is_active:
      envia email de desconexão (já existia)
      → em caso de sucesso: connection.disconnect_alert_sent_at = utcnow()

  if not was_active and is_active and connection.disconnect_alert_sent_at:
      envia email de reconexão (novo)
      → connection.disconnect_alert_sent_at = None
```

Reconexões do fluxo normal de setup (primeira conexão) nunca setam a flag,
então nunca disparam o email de "voltou".

---

## Plano de Implementação

### Fase 1 — Email de reconexão + flag de queda notificada

**Objetivo:** disparar email de "WhatsApp reconectou" só quando a reconexão
segue uma queda que já tinha notificado o utilizador.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/whatsapp_connection.py` | Nova coluna `disconnect_alert_sent_at = Column(DateTime, nullable=True)` |
| `backend-core/app/db.py` | Nova função `ensure_whatsapp_connections_columns()` (padrão de `ensure_plan_limits_columns()`) |
| `backend-core/app/main.py` | Chama `ensure_whatsapp_connections_columns()` no `on_startup()` |
| `backend-core/app/services/email_service.py` | Nova função `render_whatsapp_reconnected_email(name, login_url)` |
| `backend-core/app/api/whatsapp_instances.py` | `connection_event()` seta a flag na desconexão e envia o email de reconexão quando aplicável |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `<preenchido após o commit>` | Coluna `disconnect_alert_sent_at`, email de reconexão, lógica em `connection_event()` |

**Detalhes do commit:**
- `backend-core/app/models/whatsapp_connection.py` — coluna nova `disconnect_alert_sent_at` (DateTime, nullable)
- `backend-core/app/db.py` — `ensure_whatsapp_connections_columns()`, migração idempotente (mesmo padrão de `ensure_plan_limits_columns()`)
- `backend-core/app/main.py` — chama a nova função no `on_startup()`
- `backend-core/app/services/email_service.py` — `render_whatsapp_reconnected_email()`, mesmo estilo visual do email de desconexão (heading verde, tom positivo)
- `backend-core/app/api/whatsapp_instances.py` — `connection_event()`: seta `disconnect_alert_sent_at` ao enviar o email de desconexão; novo bloco que envia o email de reconexão só quando a flag está preenchida, e limpa a flag depois

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando o WhatsApp do utilizador reconectava depois de cair, nada
acontecia — sem confirmação de que a Lara voltou a atender.

**Agora:** ao reconectar depois de uma queda que já tinha gerado o email de
aviso, o utilizador recebe um segundo email confirmando que a Lara voltou a
funcionar. Reconexões da configuração inicial (primeira vez que a instância
conecta) continuam silenciosas, como antes — só a *recuperação* de uma queda
real dispara o aviso.

**Para validar:** Cenário C1 e C2, abaixo.

---

## Checks de Validação

### Cenário C1 — Reconexão após queda real dispara email
- [x] Setup: conta de teste com WhatsApp conectado (`status` local = `active`)
- [x] Simular queda: `POST /whatsapp-instances/connection-event` com status
      inativo — confirmar email de desconexão enviado e
      `disconnect_alert_sent_at` preenchido no banco
- [x] Simular reconexão: novo `POST /whatsapp-instances/connection-event` com
      status ativo — confirmar email de reconexão enviado e
      `disconnect_alert_sent_at` volta a `NULL`
- **Validado em:** 04/09/2026 — testado ao vivo contra o backend-core local
  (porta isolada 8098, cópia local de `.env`/`core.db`, conta de teste
  `autodigital157@gmail.com`, user_id=15, instância `crm-15-88e456ef`).
  Disparo do evento `disconnected` marcou `disconnect_alert_sent_at` no banco
  sem erro nos logs (email de desconexão enviado); disparo seguinte do
  evento `connected` limpou a flag de volta para `NULL`, também sem erro nos
  logs (email de reconexão enviado). Conteúdo visual dos emails não foi
  conferido na caixa de entrada nesta sessão — só o disparo via SMTP sem
  falha.

### Cenário C2 — Primeira conexão (setup inicial) NÃO dispara email de reconexão
- [x] Setup: nova instância/conta sem `disconnect_alert_sent_at` setado
- [x] Fluxo normal de conexão até `connection-event` reportar `"connected"`
      pela primeira vez — confirmar que nenhum email de reconexão é enviado
- **Validado em:** 04/09/2026 — simulado ajustando a mesma connection de
  teste para `status='connecting'` com `disconnect_alert_sent_at=NULL`
  (estado equivalente a uma instância nunca notificada) e disparando o
  evento `connected`. Resultado: `status` foi para `connected`,
  `disconnect_alert_sent_at` permaneceu `NULL` — nenhuma tentativa de envio
  de email de reconexão (nenhum log de sucesso/falha associado).

---

## Ajustes Possíveis Pós-Implementação

- Itens irmãos já registados separadamente:
  `docs/implementations/cooldown-email-desconexao-whatsapp.md` (cooldown para
  flapping) e `docs/implementations/notificacao-desconexao-in-app.md`
  (notificação in-app).
