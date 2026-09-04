# Notificação in-app (banner) de desconexão do WhatsApp

**Branch:** `feat/notificacao-desconexao-in-app`
**Status:** Em andamento

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`alerta-desconexao-whatsapp.md`. Hoje o único aviso de queda de conexão é por
email. Uma notificação dentro do próprio CRM tornaria o aviso mais visível
para quem usa o sistema durante o dia e não checa email com frequência.

---

## Problemas Identificados (estado anterior)

1. **Sem superfície de notificação de conta:** o sistema de notificações do
   `frontend-crm` (tabela `notifications`, `backend-crm/routes/notifications.py`,
   hook `frontend-crm/src/hooks/useNotifications.ts`) é 100% lead-cêntrico —
   usado só para decorar cards de lead no Kanban (`KanbanBoard.tsx`). Não
   existe sino, banner ou qualquer alerta a nível de conta/utilizador, além
   do email.

2. **Endpoint de status existente não serve para polling global:**
   `GET /api/whatsapp/status` (`backend-crm/routes/whatsapp_connect.py:296-352`)
   chama a UazAPI ao vivo (`status_core_whatsapp_instance`) a cada request.
   Hoje só é usado durante a tela de Conexão com QR pendente, por uma janela
   curta. Rodar isso globalmente a cada ~60s em toda aba de todo usuário
   multiplicaria a carga na UazAPI sem necessidade.

---

## Abordagem

O `WhatsappConnection.status` (backend-core) já fica atualizado sem custo de
API externa: é escrito pelo webhook `connection-event`
(`backend-core/app/api/whatsapp_instances.py:313-397`) toda vez que a UazAPI
avisa uma mudança real de conexão. O campo `disconnect_alert_sent_at`
(nullable) já existe e já resolve o problema de distinguir "nunca conectou"
de "estava conectado e caiu" — é setado só numa queda real (linha 365) e
limpo só numa reconexão real após queda prévia (linha 387), mesma condição
usada hoje para decidir se envia o email de reconexão.

```
Webhook connection-event (backend-core)
  → grava status + disconnect_alert_sent_at (já existe, sem mudança)

Frontend-crm (polling leve, ~60s, em qualquer página)
  → GET /api/whatsapp/connection-alert (backend-crm, novo)
      → lê GET /whatsapp-connections/me (backend-core, já existe — leitura de banco, sem UazAPI)
      → disconnected = status inativo AND disconnect_alert_sent_at preenchido
  ├─ disconnected=true  → banner vermelho persistente (App.tsx, mesmo padrão do UsageAlertBanner)
  └─ disconnected=false → nenhum banner
```

Banner reflete estado ao vivo (sem "marcar como lido") — desaparece sozinho
quando `disconnect_alert_sent_at` é limpo na reconexão. Decisão consciente:
evita duplicar a lógica de transição de estado (hoje só existe no
backend-core) dentro do backend-crm só para popular uma linha na tabela
`notifications`, que exigiria uma chamada service-to-service extra do core
pro crm a cada evento.

---

## Plano de Implementação

### Fase 1 — Endpoint de alerta (backend-core + backend-crm)

**Objetivo:** expor `disconnected: bool` de forma barata (sem tocar UazAPI)

| Arquivo | O que muda |
|---|---|
| `backend-core/app/api/whatsapp_connections.py` | `WhatsappConnectionOut` ganha `disconnect_alert_sent_at`; `_format_connection_response` passa a serializar |
| `backend-crm/routes/whatsapp_connect.py` | Nova rota `GET /api/whatsapp/connection-alert` → `{ disconnected: bool, since: str|null }` |

```python
# backend-core/app/api/whatsapp_connections.py — ANTES
class WhatsappConnectionOut(BaseModel):
    ...
    status: str
    token_masked: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# DEPOIS
class WhatsappConnectionOut(BaseModel):
    ...
    status: str
    disconnect_alert_sent_at: Optional[datetime] = None
    token_masked: Optional[str] = None
    created_at: datetime
    updated_at: datetime
```

```python
# backend-crm/routes/whatsapp_connect.py — nova rota
_ACTIVE_STATUSES = {"active", "connected", "loggedin", "logged_in"}

@router.get("/connection-alert")
def whatsapp_connection_alert(current_user: CurrentUser = Depends(require_crm_access)):
    connection = _resolve_instance_id(current_user)
    if not connection:
        return {"disconnected": False, "since": None}

    status_value = (connection.get("status") or "").strip().lower()
    since = connection.get("disconnect_alert_sent_at")
    disconnected = status_value not in _ACTIVE_STATUSES and bool(since)
    return {"disconnected": disconnected, "since": since if disconnected else None}
```

### Fase 2 — Banner no frontend-crm

**Objetivo:** exibir o aviso em qualquer página autenticada

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | Novo método `api.crm.whatsappConnectionAlert()` |
| `frontend-crm/src/hooks/useWhatsappConnectionAlert.ts` | Novo hook — React Query, `refetchInterval: 60_000` |
| `frontend-crm/src/components/WhatsappDisconnectBanner.tsx` | Novo componente — modelado em `UsageAlertBanner.tsx` |
| `frontend-crm/src/App.tsx` | Monta `<WhatsappDisconnectBanner />` ao lado de `<UsageAlertBanner />` (linha ~106) |

---

## Checks de Validação

### Cenário P1 — Sem conexão nunca criada
- [ ] Chamar `GET /api/whatsapp/connection-alert` com usuário sem `WhatsappConnection`
- [ ] Confirmar: `{ disconnected: false, since: null }`, sem erro 404 vazando pro frontend

### Cenário P2 — Conectado normalmente
- [ ] Usuário com `status="active"` e `disconnect_alert_sent_at=null`
- [ ] Confirmar: `{ disconnected: false }`

### Cenário P3 — Desconectado (queda real)
- [ ] Forçar no banco local `status="inactive"` e `disconnect_alert_sent_at=<timestamp>`
- [ ] Confirmar: `{ disconnected: true, since: "<timestamp>" }`

### Cenário C1 — Banner aparece e some (browser)
- [ ] Com backend-crm/backend-core rodando localmente e usuário logado no frontend-crm
- [ ] Simular queda (Cenário P3) → recarregar/aguardar refetch (60s)
- [ ] Confirmar: banner vermelho aparece em qualquer página do CRM, com link para `/ai-profile`
- [ ] Simular reconexão (`disconnect_alert_sent_at=null`, `status="active"`) → aguardar refetch
- [ ] Confirmar: banner some

---

## Ajustes Possíveis Pós-Implementação

- Herda o mesmo risco de "flapping" já identificado em
  `cooldown-email-desconexao-whatsapp.md` (ainda não implementado): se a
  conexão oscilar rápido, o banner aparece/some no mesmo ritmo do email. Não
  é um risco novo desta feature.
