# Desativar bot automaticamente ao mover lead para "Desqualificados"

**Branch:** `worktree-feat+bot-disable-desqualificados`
**Status:** Em andamento

---

## Motivação

Um cliente relatou que contatos pessoais (não-leads) escrevem no mesmo número
usado pelo bot, e o bot responde a eles como se fossem leads. Hoje não existe
bloqueio por número de telefone — só o flag `bot_disabled` por lead, ligado
manualmente na UI ou por regras automáticas específicas (`closing`,
`media_fallback`, reunião confirmada, fim de check-in).

Como mitigação prática, o utilizador quer que, ao mover um lead para a coluna
**"Desqualificados"** (`category = "disqualified"`) no Kanban, o bot seja
desativado automaticamente para aquele lead — sem precisar do clique manual
em "Desativar bot".

Isso espelha o padrão que já existe para `closing`
(`apply_closing_bot_disable_side_effect()` em
`backend-crm/services/lead_category_policy.py`), com uma função irmã mais
simples (sem as condicionais de `agent_mode`/`outcome`, que só fazem sentido
para `closing`).

---

## Abordagem

```
Lead movido para category="disqualified" (drag no Kanban, IA, ou outcome pós-reunião)
  → apply_disqualified_bot_disable_side_effect(conn, lead_id, old_category, new_category)
      ├─ já estava em disqualified ou bot já desativado → no-op
      └─ transição para disqualified → bot_disabled=1, bot_disabled_reason='category_disqualified'
           → log em prospection_logs (bot_disabled_changed)
```

Reativação continua manual (mesmo comportamento unidirecional de `closing`).

---

## Plano de Implementação

### Fase 1 — Backend: side-effect + 3 pontos de chamada + label no frontend

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/lead_category_policy.py` | Nova função `apply_disqualified_bot_disable_side_effect()` |
| `backend-crm/routes/leads.py` | Chama a nova função após `apply_closing_bot_disable_side_effect` (drag-and-drop do Kanban) |
| `backend-crm/services/jobs_service.py` | Chama a nova função após `apply_closing_bot_disable_side_effect` (movimentação automática via IA/keyword) |
| `backend-crm/services/appointment_outcomes.py` | Chama a nova função após o `UPDATE ... category` de `move_lead_to` (outcome pós-reunião) |
| `frontend-crm/src/components/LeadCardDialog.tsx` | `botPauseReason`: rótulo "Desqualificado" para `bot_disabled_reason === "category_disqualified"` |
| `docs/architecture/agents.md` | Seção "Toggle de Bot por Lead": novo motivo + nova fonte de desativação |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _pendente_ | side-effect de bot_disabled ao entrar em disqualified + 3 call sites + label frontend + doc |

---

## Checks de Validação

### Cenário P1 — Drag no Kanban desativa o bot (caminho principal do pedido)
- [ ] Arrastar um lead de teste para a coluna "Desqualificados"
- [ ] Abrir o card do lead e confirmar "Bot desativado" com motivo "Desqualificado"
- **Pendente**

### Cenário P2 — Idempotência
- [ ] Mover o mesmo lead novamente dentro de "Desqualificados" (sem sair da coluna) ou reenviar o mesmo PUT
- [ ] Confirmar que não duplica log em `prospection_logs`
- **Pendente**

### Cenário P3 — Reativação continua manual
- [ ] Reativar o bot manualmente no lead desqualificado
- [ ] Mover o lead para outra coluna e de volta para "Desqualificados" — confirmar que desativa de novo
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

- Bloqueio proativo por número de telefone (lista de contatos ignorados) — ficou fora de escopo, é a solução definitiva para o problema original do cliente (contatos pessoais no mesmo número do bot); esta implementação é só uma mitigação reativa.
