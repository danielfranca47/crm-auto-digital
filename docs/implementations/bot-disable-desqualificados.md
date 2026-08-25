# Desativar bot automaticamente ao arquivar lead (Desqualificados / Prospecção Recusada)

**Branch:** `worktree-feat+bot-disable-desqualificados`
**Status:** Em andamento

---

## Motivação

Um cliente relatou que contatos pessoais (não-leads) escrevem no mesmo número
usado pelo bot, e o bot responde a eles como se fossem leads. Hoje não existe
bloqueio por número de telefone — só o flag `bot_disabled` por lead, ligado
manualmente na UI ou por regras automáticas específicas (`closing`,
`media_fallback`, reunião confirmada, fim de check-in).

Como mitigação prática, o utilizador quer que, ao mover um lead para uma das
colunas de arquivados — **"Desqualificados"** (`category = "disqualified"`,
Fase 1) e **"Prospecção Recusada"** (`category = "prospect-refused"`, Fase 2)
— o bot seja desativado automaticamente para aquele lead, sem precisar do
clique manual em "Desativar bot".

Isso espelha o padrão que já existe para `closing`
(`apply_closing_bot_disable_side_effect()` em
`backend-crm/services/lead_category_policy.py`), com funções irmãs mais
simples (sem as condicionais de `agent_mode`/`outcome`, que só fazem sentido
para `closing`). As duas novas funções (`disqualified` e `prospect-refused`)
compartilham um helper interno `_disable_bot_for_category_entry()` para
evitar duplicar a lógica de update + log.

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
| 1 | `fc5a389` | side-effect de bot_disabled ao entrar em disqualified + 3 call sites + label frontend + doc |

---

### Relatório da Fase 1 — o que mudou na prática

**Antes:** ao arrastar um lead para a coluna "Desqualificados" no Kanban, o bot continuava respondendo normalmente àquele número — era preciso lembrar de clicar em "Desativar bot" manualmente no card.
**Agora:** mover um lead para "Desqualificados" (pelo Kanban, automaticamente pela IA, ou pelo outcome pós-reunião) desativa o bot para aquele lead na mesma hora, mostrando "Bot desativado — Desqualificado" no card.
**Para validar:** Cenários P1, P2 e P3, abaixo.

---

### Fase 2 — Estender para a coluna "Prospecção Recusada"

**Objetivo:** aplicar exatamente o mesmo comportamento da Fase 1 também quando o lead é movido para `category = "prospect-refused"`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/lead_category_policy.py` | Extrai helper interno `_disable_bot_for_category_entry()` (reusado por closing/disqualified); nova função `apply_prospect_refused_bot_disable_side_effect()` |
| `backend-crm/routes/leads.py` | Chama a nova função junto às demais (drag-and-drop do Kanban) |
| `backend-crm/services/jobs_service.py` | Chama a nova função junto às demais (movimentação automática via IA/keyword) |
| `backend-crm/services/appointment_outcomes.py` | Chama a nova função junto à de disqualified (`move_lead_to`) |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Rótulo "Prospecção recusada" para `bot_disabled_reason === "category_prospect_refused"` |
| `docs/architecture/agents.md` | Atualiza a fonte de desativação para cobrir as duas categorias arquivadas |
| `backend-crm/scripts/test_category_disqualified_prospect_refused_side_effects.py` | Novo script de teste automatizado (idempotência + no-op fora do alvo) para as duas funções novas |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _pendente_ | apply_prospect_refused_bot_disable_side_effect + refactor do helper compartilhado + 3 call sites + label frontend + doc + teste automatizado |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mover um lead para "Prospecção Recusada" não desativava o bot — só "Desqualificados" tinha esse comportamento (Fase 1).
**Agora:** as duas colunas de arquivados ("Desqualificados" e "Prospecção Recusada") desativam o bot automaticamente da mesma forma.
**Para validar:** Cenários P4 e P5, abaixo (P1-P3 continuam cobrindo "Desqualificados").

Teste automatizado já rodado localmente (`python scripts/test_category_disqualified_prospect_refused_side_effects.py`) — passou, cobrindo idempotência e no-op para categoria fora do alvo nas duas funções novas.

---

## Checks de Validação

### Cenário P1 — Drag no Kanban desativa o bot (Desqualificados)
- [ ] Arrastar um lead de teste para a coluna "Desqualificados"
- [ ] Abrir o card do lead e confirmar "Bot desativado" com motivo "Desqualificado"
- **Pendente**

### Cenário P2 — Idempotência (Desqualificados)
- [ ] Mover o mesmo lead novamente dentro de "Desqualificados" (sem sair da coluna) ou reenviar o mesmo PUT
- [ ] Confirmar que não duplica log em `prospection_logs`
- **Pendente**

### Cenário P3 — Reativação continua manual (Desqualificados)
- [ ] Reativar o bot manualmente no lead desqualificado
- [ ] Mover o lead para outra coluna e de volta para "Desqualificados" — confirmar que desativa de novo
- **Pendente**

### Cenário P4 — Drag no Kanban desativa o bot (Prospecção Recusada)
- [ ] Arrastar um lead de teste para a coluna "Prospecção Recusada"
- [ ] Abrir o card do lead e confirmar "Bot desativado" com motivo "Prospecção recusada"
- **Pendente**

### Cenário P5 — Idempotência (Prospecção Recusada)
- [ ] Mover o mesmo lead novamente dentro de "Prospecção Recusada" ou reenviar o mesmo PUT
- [ ] Confirmar que não duplica log em `prospection_logs`
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

- Bloqueio proativo por número de telefone (lista de contatos ignorados) — ficou fora de escopo, é a solução definitiva para o problema original do cliente (contatos pessoais no mesmo número do bot); esta implementação é só uma mitigação reativa.
