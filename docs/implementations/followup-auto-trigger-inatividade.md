# Follow-up automático por inatividade (M2)

**Branch:** `main`
**Status:** Fases 1–3 (disparo automático em `apresentation`/`agendamento`, com os dois
bugs encontrados ao vivo já corrigidos) validadas em 23/06/2026 — checks obrigatórios
`[x]`/`[⏭️]`. Falta apenas o check-in automático de `client-list` (mencionado como
"Fase 2" na secção Abordagem, abaixo — passa a ser **Fase 4** numerada, já que as
Fases 2 e 3 acabaram usadas para os fixes encontrados nos testes) — ainda não
iniciado, depende de mini-diagnóstico próprio.
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

**Não é exclusivo do Híbrido Agendador.** As fases `p3a`/`p3b` ficam activas para
qualquer perfil com `agent_mode` no grupo "agenda" (`agent_mode in {"agenda",
"sdr_scheduler"}`), independente do `template_key`/`agent_type` —
`backend-executors/app/services/decision_engine.py:3817` lista
`_SCHEDULING_AGENT_TEMPLATES = {"sdr_padrao", "hybrid_scheduler"}` explicitamente.
O SDR (`sdr_padrao`, `agent_type=agent_1`) também entra em `agendamento`, com o mesmo
risco de ficar parado lá sem recuperação. A correcção desta fase não tem nenhum
`if agent_type == ...` — é a mesma query para qualquer lead, então já cobre o SDR
sem mudança adicional (confirmado empiricamente, ver nota na Fase 3).

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

Nenhuma das duas correcções (Fase 2 e Fase 3) tem `if agent_type`/`if followup_variant`
— são o mesmo caminho de código para qualquer lead elegível. Confirmado directamente
após o fechamento da Fase 3 (23/06/2026): lead real `id=297`, `agent_type=agent_1`,
`category=agendamento`, mesma inactividade simulada. `scan_inactive_leads_for_auto_followup()`
chamado directamente (sem esperar o ciclo do reconciler) → `{"scanned": 3, "started": 1,
"items": [{"lead_id": 297, "followup_variant": "sdr_scheduler"}]}`. Contrato resultante:
`followup_variant="sdr_scheduler"`, `followup_goal="reengage"` (default correcto do SDR,
distinto do `reengage_conversation` do híbrido), `max_attempts=4` (default do
`sdr_scheduler`, vs. `3` do `hybrid_scheduler`), `trigger="auto_inactivity"`, sem erro de
lock. Dados de teste removidos após a verificação.

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9689fb1` | corrige ordem commit→create_job no disparo automático |

---

## Checks de Validação

### Cenário P1 — Toggle desligado por default não muda nada
- [x] Conta sem o toggle activado continua com follow-up só por gesto manual
- [x] Confirmar: nenhum lead em `apresentation`/`agendamento` é movido automaticamente
- **Validado em:** 23/06/2026 — `GET /ai-profiles/resolve` confirmou
  `followup_auto_trigger_enabled=False`, `followup_auto_trigger_inactivity_days=3`
  (defaults aplicados pela migração, sem nenhuma acção do operador).

### Cenário P2 — Disparo automático funciona (hybrid_scheduler)
- [x] Activar toggle no AI Profile, limiar = 1 dia
- [x] Lead real (não-playground), qualificação completa, sem mensagem inbound há > 1 dia
- [x] Aguardar ciclo do reconciler (≤60s)
- [x] Confirmar: `category` vira `follow-up`, `followup_contract.trigger="auto_inactivity"`
- [x] Confirmar marca visível na Central de Follow-ups
- **Validado em:** 23/06/2026 — toggle ligado/salvo via UI (`PUT /ai-profiles/me`
  confirmado como coluna de topo, fora do `offer_pack`); persistência confirmada após
  reload da página. Lead de teste `id=296` (`agendamento`, ver P5) processado pelo
  reconciler após o fix da Fase 3 — badge "AUTO" visível na lista e "Origem: Automático
  (inatividade)" visível no detalhe (`/follow-ups/:id/edit`, aba Contexto).

### Cenário P3 — Idempotência e cooldown
- [x] O lead não é re-processado pelo scan depois de mudar de categoria (exclusão
      natural da query por `category IN ('apresentation','agendamento')`)
- [⏭️] Cenário completo de `max_attempts_reached` → cooldown → re-elegibilidade não foi
      exercitado ao vivo (exigiria simular 3 tentativas sem resposta) — a lógica do
      campo `followup_auto_trigger_last_fired_at` foi revisada em código, não testada
      ponta-a-ponta nesta sessão.

### Cenário P4 — Guardrail de qualificação respeitado
- [⏭️] Não exercitado ao vivo — a conta de teste tem `qualification_required_fields=[]`,
      que faz `can_advance_from_qualification()` retornar sempre `True` (mesmo
      comportamento do fluxo manual). A chamada usa a mesma função já validada no
      fluxo manual de `start-followup`; sem caso de teste com campos obrigatórios
      configurados nesta sessão.

### Cenário P5 — Funciona também para lead parado em `agendamento` (Fase 2)
- [x] Lead em `agendamento` (hybrid_scheduler), qualificação completa, inactivo > limiar
- [x] Confirmar: recebe contrato automático igual ao cenário P2
- [⏭️] `pre-agendamento` não foi testado ao vivo (sem lead real nessa categoria
      disponível) — exclusão confirmada por revisão de código (`WHERE category IN
      ('apresentation', 'agendamento')` não inclui `pre-agendamento`).
- **Validado em:** 23/06/2026 — lead `id=296` criado directamente em `agendamento`
  (`agent_type=agent_3`), `lastMovement` retrocedido 3 dias. `followup_contract`
  resultante: `followup_variant=hybrid_scheduler`, `followup_goal=reengage_conversation`,
  `trigger=auto_inactivity`. Dados de teste removidos após validação (lead, jobs e
  prospection_logs associados); toggle do AI Profile revertido a `Desativado`.

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
