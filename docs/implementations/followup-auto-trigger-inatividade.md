# Follow-up automático por inatividade (M2)

**Branch:** `main`
**Status:** Em andamento
**Plano:** `docs/plans/followup-proativo-e-cancelamento-agenda.md` (M2)

---

## Motivação

Hoje só existe UM jeito de iniciar um `followup_contract` para Agent 1 (`sdr_scheduler`)
ou Agent 3 (`hybrid_scheduler`): o operador arrastar manualmente o card no Kanban de
`apresentation` para `follow-up` e preencher o `FollowUpTransitionModal`. Não existe
nenhuma varredura periódica que detecte "lead/paciente sem atividade há N dias" e crie o
contrato por conta própria — o reconciliador (`followup_reconciler.py`) só atua sobre
contratos **já criados**.

Escopo confirmado com o utilizador (Plan Mode, AskUserQuestion): o M2 cobre dois
gatilhos automáticos:

1. **Lead silencioso em `apresentation`** — automatiza o gesto manual já existente.
2. **Cliente inativo em `client-list`** — "check-in" de paciente recorrente (ex.:
   massoterapia) sem sessão/contacto há N dias.

---

## Problemas Identificados (estado anterior)

1. **Sem gatilho automático:** `services/followup_reconciler.py` só processa contratos
   `followup_status='active'` já existentes — não há varredura de leads inativos.
2. **Sem config no AI Profile:** não existe toggle nem limiar de inatividade configurável
   por operador.
3. **Sem marca de origem na UI:** o campo `trigger` já existe no formato do contrato
   (`"manual_crm_transition"`), mas a Central de Follow-ups não o exibe — não há como o
   operador distinguir um follow-up automático de um manual.

---

## Abordagem

```
Reconciler loop (60s, app.py)
  → reconcile_due_followups()           [já existia — contratos já activos]
  → scan_inactive_leads_for_auto_followup()  [NOVO — detecta e inicia novos contratos]
        ├─ candidatos: category='apresentation', sem contrato activo
        ├─ AI Profile do user: followup_auto_trigger_enabled?
        ├─ inatividade >= followup_auto_trigger_inactivity_days?
        │     sinal = MAX(última msg inbound em `messages`, leads.lastMovement)
        ├─ qualificação completa? (mesmo guardrail do start-followup manual)
        ├─ agent_type elegível (agent_1/agent_3)?
        ├─ fora do cooldown (followup_auto_trigger_last_fired_at)?
        └─ sim a tudo → start_followup_for_inactivity()
              trigger="auto_inactivity", followup_goal="reengage"/"reengage_conversation"
```

Fase 2 (check-in de `client-list`) terá o seu próprio mini-diagnóstico antes de codar —
decisões de variante dedicada, sinal de inatividade (última sessão vs. última mensagem) e
tom/cadência mais suaves ainda não foram fechadas.

---

## Plano de Implementação

### Fase 1 — Disparo automático por inatividade em `apresentation`

**Objetivo:** automatizar o gesto manual existente para `sdr_scheduler`/`hybrid_scheduler`.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | 2 colunas: `followup_auto_trigger_enabled` (bool, default false), `followup_auto_trigger_inactivity_days` (int, default 3) |
| `backend-core/app/db.py` | `ensure_ai_profile_columns()` — 2 entradas novas (migração idempotente SQLite+Postgres) |
| `backend-core/app/api/ai_profiles.py` | 2 campos em `AIProfileBase` e `AIProfileUpdate` |
| `backend-crm/database.py` | `ensure_column(leads, "followup_auto_trigger_last_fired_at", "DATETIME")` — cooldown anti-repetição |
| `backend-crm/services/followup_state.py` | nova `start_followup_for_inactivity()` + `resolve_auto_inactivity_variant()` |
| `backend-crm/services/followup_reconciler.py` | nova `scan_inactive_leads_for_auto_followup()` |
| `backend-crm/app.py` | `_reconciler_loop()` chama a nova função a cada ciclo |
| `frontend-crm/src/types/agente.ts` | 2 campos em `AgentConfig` + `DEFAULT_AGENT_CONFIG` |
| `frontend-crm/src/services/api.ts` | `getConfig()`/`saveConfig()` — coluna de topo (nunca `offer_pack`); `FollowUpContract.trigger` |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | novo card + drawer "Follow-up automático" (toggle + dias) |
| `frontend-crm/src/pages/FollowUpCenter.tsx` | badge quando `followup_contract.trigger === "auto_inactivity"` |
| `frontend-crm/src/pages/FollowUpEdit.tsx` | mesma marca na vista de detalhe |

**Defaults usados quando não há input do operador (caso automático):**
`meeting_or_session_happened=None`, `outcome=None`, `proposal_sent=False`,
`followup_goal="reengage"` (sdr_scheduler) / `"reengage_conversation"`
(hybrid_scheduler) — valores que já existem como opção válida no modal manual
("reunião não aconteceu"), sem precisar de novo estado no `decision_engine`.

---

## Checks de Validação

### Cenário P1 — Toggle desligado por default não muda nada
- [ ] Conta sem o toggle activado continua com follow-up só por gesto manual
- [ ] Confirmar: nenhum lead em `apresentation` é movido automaticamente

### Cenário P2 — Disparo automático funciona (hybrid_scheduler)
- [ ] Activar toggle no AI Profile, limiar = 1 dia
- [ ] Lead em `apresentation`, qualificação completa, sem mensagem inbound há > 1 dia
- [ ] Aguardar ciclo do reconciler (≤60s)
- [ ] Confirmar: `category` vira `follow-up`, `followup_contract.trigger="auto_inactivity"`
- [ ] Confirmar marca visível na Central de Follow-ups

### Cenário P3 — Idempotência e cooldown
- [ ] Rodar o scan de novo no mesmo ciclo não duplica/recria o contrato
- [ ] Após o contrato fechar por `max_attempts_reached`, o lead não é re-disparado
      imediatamente no ciclo seguinte

### Cenário P4 — Guardrail de qualificação respeitado
- [ ] Lead em `apresentation` com qualificação incompleta NÃO recebe contrato automático

---

## Ajustes Possíveis Pós-Implementação

- Fase 2 (check-in `client-list`) ainda não tem variante de contrato, cadência nem
  instrução hardcoded definidas — entra com mini-diagnóstico próprio.
- Sinal de inatividade usa `lastMovement` como fallback quando não há mensagem inbound
  registada — pode ser tocado por edição manual do operador no card (risco baixo, mas
  documentado).
- Campos novos nascem numa secção isolada da UI ("Follow-up automático"), propositalmente
  não integrados aos campos antigos — pensados para serem absorvidos pelo M3 (camada
  dedicada) quando esse item avançar.
