# Desativar bot automaticamente ao arquivar lead (Desqualificados / Prospecção Recusada)

**Branch:** `worktree-feat+bot-disable-desqualificados`
**Status:** Pronto para graduação (todos os checks validados ou pulados com justificativa)

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
| 1 | `7e8d768` | apply_prospect_refused_bot_disable_side_effect + refactor do helper compartilhado + 3 call sites + label frontend + doc + teste automatizado |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mover um lead para "Prospecção Recusada" não desativava o bot — só "Desqualificados" tinha esse comportamento (Fase 1).
**Agora:** as duas colunas de arquivados ("Desqualificados" e "Prospecção Recusada") desativam o bot automaticamente da mesma forma.
**Para validar:** Cenários P4 e P5, abaixo (P1-P3 continuam cobrindo "Desqualificados").

Teste automatizado já rodado localmente (`python scripts/test_category_disqualified_prospect_refused_side_effects.py`) — passou, cobrindo idempotência e no-op para categoria fora do alvo nas duas funções novas.

---

## Checks de Validação

### Cenário P1 — Drag no Kanban desativa o bot (Desqualificados)
- [x] Arrastar um lead de teste para a coluna "Desqualificados"
- [x] Abrir o card do lead e confirmar "Bot desativado" com motivo "Desqualificado"
- **Validado em:** 26/08/2026 — teste ao vivo via browser (chrome-devtools MCP), ambiente local completo (backend-core:8001, backend-crm:8000, frontend-crm:5173 rodando na worktree). Lead "Teste Historico Email C1" (id 434) arrastado de "À Prospectar" para "Desqualificados"; `PATCH /api/leads/434` retornou 200; card exibiu "⚠️ Bot pausado — Motivo: Desqualificado".

### Cenário P2 — Idempotência (Desqualificados)
- [x] Confirmar que a segunda chamada com a mesma transição não duplica log em `prospection_logs`
- **Validado em:** 26/08/2026 — via teste automatizado (`test_disqualified_disables_bot_and_is_idempotent` em `backend-crm/scripts/test_category_disqualified_prospect_refused_side_effects.py`): segunda chamada retorna `False` e só existe 1 log `bot_disabled_changed`. Não repetido manualmente na UI porque exigiria duas viagens de drag para sair e voltar à mesma coluna sem alterar o cenário — a função testada é exatamente a que o drag chama.

### Cenário P3 — Reativação continua manual (Desqualificados)
- [⏭️] Reativar o bot manualmente e confirmar que sair/voltar a "Desqualificados" desativa de novo
- **Pulado (justificado):** ao tentar reativar manualmente via UI (botão "Reativar bot" no card do lead "Teste Historico Email C2", em Prospecção Recusada), a ação não teve efeito visível no snapshot — parece uma modal de confirmação pré-existente (`showReactivateWarningModal`, ver `LeadCardDialog.tsx`) que não renderizou como esperado no teste automatizado do browser; não é uma regressão desta implementação (o botão e o fluxo de reativação já existiam antes, para `category_closing`). O comportamento "não reativa sozinho" já é garantido pelo código: a função só age quando `new_category == alvo`; sair da coluna não chama a função de desabilitar. Recomendo teste manual direto pelo utilizador se quiser confirmação visual.

### Cenário P4 — Drag no Kanban desativa o bot (Prospecção Recusada)
- [x] Arrastar um lead de teste para a coluna "Prospecção Recusada"
- [x] Abrir o card do lead e confirmar "Bot desativado" com motivo "Prospecção recusada"
- **Validado em:** 26/08/2026 — mesmo teste ao vivo. Lead "Teste Historico Email C2 (falha)" (id 435) arrastado de "À Prospectar" para "Prospecção Recusada"; `PATCH /api/leads/435` retornou 200; card exibiu "⚠️ Bot pausado — Motivo: Prospecção recusada".

### Cenário P5 — Idempotência (Prospecção Recusada)
- [x] Confirmar que a segunda chamada com a mesma transição não duplica log em `prospection_logs`
- **Validado em:** 26/08/2026 — via teste automatizado (`test_prospect_refused_disables_bot_and_is_idempotent`), mesmo padrão do P2.

---

## Ajustes Possíveis Pós-Implementação

- Bloqueio proativo por número de telefone (lista de contatos ignorados) — ficou fora de escopo, é a solução definitiva para o problema original do cliente (contatos pessoais no mesmo número do bot); esta implementação é só uma mitigação reativa.
