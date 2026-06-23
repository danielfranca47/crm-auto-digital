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

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `5aaf0f2` | backend (colunas + scan + gatilho) + frontend (toggle + marca de origem) |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o follow-up de um lead em "Apresentação" só começava se o operador
lembrasse de arrastar o card manualmente para a coluna "Follow-up" e preencher o
formulário. Se ele esquecesse, o lead simplesmente ficava parado ali, sem ninguém
tentar recuperar a conversa.

**Agora:** existe um interruptor novo no Perfil de IA ("Follow-up automático", na
Camada 3) que, quando ligado, faz o sistema reparar sozinho quando um lead fica
calado em "Apresentação" por X dias (configurável) e iniciar o follow-up por conta
própria — sem o operador precisar fazer nada. Continua desligado por padrão, então
nenhuma conta existente é afetada até o operador decidir ativar. Quando o disparo é
automático, a Central de Follow-ups mostra uma marca "auto" ao lado do nome do lead,
e a tela de detalhe mostra "Origem: Automático (inatividade)" — para diferenciar do
que foi iniciado manualmente.

**Para validar:** Cenários P1 a P4, abaixo.

---

## Fase 2 — Diagnóstico + Correção: faltava cobrir `agendamento` (23/06/2026)

### Problema identificado

Antes de iniciar o teste ao vivo, inspecionei os leads reais da conta de teste
(`template_key=hybrid_scheduler`, `agent_mode=agenda`) e descobri que o pipeline tem
dois estágios entre `apresentation` e `follow-up` que a Fase 1 não cobria:
`pre-agendamento` (fase `p3a`) e `agendamento` (fase `p3b`) — só activos para o grupo
`agenda` (`sales-flow.md`). Praticamente todos os leads reais da conta de teste
estavam parados em `agendamento`, não em `apresentation` — exactamente o cenário de
"paciente que parou de responder no meio do agendamento" que o M2 deveria cobrir para
o Híbrido Agendador.

Causa raiz: a Fase 1 assumiu (com base no fluxo manual de `start-followup`, que só
permite a transição a partir de `apresentation`) que esse era o único estágio
"silenciável" antes do follow-up — sem saber da existência de `pre-agendamento`/
`agendamento`.

Investigação adicional: `pre-agendamento` já tem mecanismo de recuperação automática
próprio — `_schedule_preagendamento_checkin()` (`backend-crm/routes/executor.py`),
disparado por um sinal estruturado do LLM filho. `agendamento`, por outro lado, não
tem nenhum mecanismo de recuperação — o comentário em
`backend-executors/app/services/decision_engine.py:429` ("no_reply_trigger é gerido
pelo followup_state — não avaliado aqui") confirma que a intenção do sistema sempre
foi essa fase ser coberta pelo followup_state, mas isso nunca foi conectado.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-crm/services/followup_reconciler.py` | `scan_inactive_leads_for_auto_followup()`: `WHERE category = 'apresentation'` → `WHERE category IN ('apresentation', 'agendamento')`. `pre-agendamento` fica de fora (mecanismo dedicado já existe). |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a2f5625` | amplia elegibilidade do scan para incluir `agendamento` |

---

## Fase 3 — Diagnóstico + Correção: `database is locked` no disparo automático (23/06/2026)

### Problema identificado

No primeiro teste ao vivo (lead real `id=296`, `agendamento`, inatividade simulada de 3
dias, toggle ligado em 1 dia), o reconciler detectou o lead correctamente mas falhou
repetidamente (18 ciclos consecutivos) com `sqlite3.OperationalError: database is
locked` ao tentar criar o job de pré-geração da mensagem. A transacção do lead era
revertida automaticamente (rollback do `with get_connection() as conn`), então não
houve corrupção de dados — só o disparo nunca completava.

Causa raiz: `start_followup_for_inactivity()` chamava `create_job()` **antes** do
`conn.commit()` do chamador (`scan_inactive_leads_for_auto_followup`). `create_job()`
abre a sua própria conexão SQLite para inserir na tabela `jobs` — com a transacção do
`UPDATE leads` ainda aberta (lock de escrita), a segunda conexão não conseguia escrever.
O padrão correcto já existia em `start_followup_transition` (`leads.py`): `conn.commit()`
sempre antes de chamar `create_job()`. A função nova não replicou essa ordem.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-crm/services/followup_state.py` | `start_followup_for_inactivity()`: removida a chamada a `create_job()` |
| `backend-crm/services/followup_reconciler.py` | `scan_inactive_leads_for_auto_followup()`: `create_job()` movido para depois do `conn.commit()` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9689fb1` | corrige ordem commit→create_job no disparo automático |

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

### Cenário P5 — Funciona também para lead parado em `agendamento` (Fase 2)
- [ ] Lead em `agendamento` (hybrid_scheduler), qualificação completa, inactivo > limiar
- [ ] Confirmar: recebe contrato automático igual ao cenário P2
- [ ] Confirmar: lead em `pre-agendamento` NÃO recebe (mecanismo dedicado próprio)

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
