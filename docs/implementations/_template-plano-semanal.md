# Plano de Sprint — [EXEMPLO PREENCHIDO]

> **Exemplo concreto preenchido:** este arquivo mostra como fica um plano de sprint na prática.
> Leia-o antes de gerar o seu — mostra como estruturar cada seção.
> Gerado com base nos arquivos em `docs/plans/` em 04/06/2026.

**Data de geração:** 04/06/2026
**Arquivos analisados:** `kiwify-checkout-melhorias-pos-etapa-9-7.md` · `pipeline-configurable-fields.md`
**Status:** Aguardando aprovação

---

## Diagnóstico — Todos os itens auditados

| # | Item | Arquivo de origem | Prioridade declarada | Status no sistema |
|---|---|---|---|---|
| M1 | Criar plano `crm_scale` no DB | kiwify (M1) | ALTA | ❌ Não existe — `seed_initial_data()` não tem `crm_scale` |
| M2 | Página de boas-vindas `/welcome` | kiwify (M2) | ALTA | ❌ Não existe — sem rota pública `/welcome` no App.tsx |
| M3 | Forçar mudança de senha 1º login | kiwify (M3) | ALTA | ❌ Não existe — sem campo `must_change_password` no User |
| M4 | Email de activação para upgrades | kiwify (M4) | MÉDIA | 🟡 Parcial — template existe, não é chamado em `activate` |
| M5 | Retries + alertas de falhas webhook | kiwify (M5) | MÉDIA | ❌ Não existe |
| M6 | Modal de upgrade mais claro | kiwify (M6) | BAIXA | ❌ Não existe |
| C | Instruções de follow-up por agente | pipeline-configurable-fields (Etapa C) | ALTA | ❌ Não existe — campos ainda não adicionados ao AI Profile |

**Correlações identificadas:**
- M1 + M5 têm sinergia: M1 resolve o `plan_not_found` que é o motivo principal dos `skipped` em M5. Implementar M1 primeiro reduz o escopo de M5.
- M2 + M3 têm sinergia: ambos afectam o fluxo do novo cliente pós-compra. Podem ir no mesmo sprint pois não partilham arquivos.
- C é independente de todos os anteriores.

---

## Perguntas respondidas pelo admin

> *Nenhuma pergunta foi necessária neste sprint — todos os itens tinham contexto suficiente
> no código e nas docs para priorizar sem decisão do fundador.*

*(Exemplo de resposta registada quando há perguntas:)*
> **P: O preço do Plano Scale está confirmado para adicionar ao seed?**
> R (admin, 04/06/2026): "Não confirmado ainda — não criar o produto Kiwify por agora,
> mas pode criar o seed com os limites técnicos. O webhook de activação pode esperar."

---

## Sprint — Itens selecionados

### P1 — Criar plano `crm_scale` no DB

**Origem:** `docs/plans/kiwify-checkout-melhorias-pos-etapa-9-7.md` — seção M1
**Prioridade:** ALTA — bloqueia vendas reais do Plano Scale
**Esforço estimado:** baixo (seed + limites, 1 arquivo principal)
**Dependências:** nenhuma

**Contexto:**
O webhook Kiwify já mapeia `"Plano Scale"` → `crm_scale` em `backend-crm/routes/webhooks.py`
(linha ~581). No entanto, o plano `crm_scale` não existe na tabela `plans` do banco.
Resultado prático: cliente paga o Scale, webhook retorna `skipped: plan_not_found`, conta não
é activada. Nenhum erro visível — vai para logs silenciosamente.

**Entrega esperada:**
- Plano `crm_scale` inserido via `seed_initial_data()` em `backend-core/app/db.py`
- Limites definidos em `plan_limits` (max_leads=5000, max_ia_conversas_monthly=1500, max_instances=3)
- Documentação em `docs/architecture/plans-limits.md` atualizada

**Prompt para o processo de implementations:**
```
Gostaria de implementar o plano crm_scale no banco de dados.
Actualmente clientes que compram o Plano Scale ficam sem acesso — o webhook Kiwify
retorna skipped:plan_not_found silenciosamente porque o plano não existe no seed.

Contexto: o seed em backend-core/app/db.py → seed_initial_data() cria os planos
Start e Growth mas não o crm_scale. O modelo Plan e PlanLimits estão em
backend-core/app/models/plan.py. O webhook que faz o mapeamento está em
backend-crm/routes/webhooks.py linha ~581 (PLAN_NAME_TO_CODE).
Os limites do Scale são: max_leads=5000, max_ia_conversas_monthly=1500,
max_whatsapp_send_daily=200, max_instances=3, follow_up_enabled=True,
playground_monthly_limit=None.

Leia o guia de implementação e siga o processo.
```

---

### P2 — Forçar mudança de senha no primeiro login

**Origem:** `docs/plans/kiwify-checkout-melhorias-pos-etapa-9-7.md` — seção M3
**Prioridade:** ALTA — segurança (senha temporária enviada em claro por email)
**Esforço estimado:** médio (campo DB + middleware/guard frontend)
**Dependências:** nenhuma (independente de P1)

**Contexto:**
A senha temporária de 14 chars gerada em `backend-core/app/api/subscriptions.py` (linhas ~244–265)
é enviada em claro por email. Nenhum mecanismo força a troca após o primeiro login.
O risco: se o email for comprometido, a conta fica vulnerável indefinidamente.

Abordagem preferida (mais simples): usar o fluxo de `forgot-password` já existente —
em vez de enviar a senha temporária, enviar um link de definição de senha. Isso evita
adicionar `must_change_password` ao modelo e lógica de guard no frontend.

**Entrega esperada:**
- Fluxo de criação de conta via Kiwify envia email de "define a tua senha" em vez de senha em claro
- O utilizador chega à plataforma já com senha definida por si
- O fluxo de forgot-password não é alterado — é reaproveitado

**Prompt para o processo de implementations:**
```
Gostaria de corrigir o fluxo de criação de conta via Kiwify para não enviar
senha temporária em claro por email.

Contexto: em backend-core/app/api/subscriptions.py → kiwify_subscription_event()
(linhas ~244–265), quando um novo utilizador compra pelo Kiwify, o sistema gera
uma senha temporária aleatória de 14 chars e a envia por email via
render_welcome_email em backend-core/app/services/email_service.py.
Não há nenhum mecanismo que force a troca após o primeiro login.

A abordagem preferida é reutilizar o fluxo de forgot-password já existente:
em vez de gerar senha temporária, enviar um link de "define a tua senha" para
o email do comprador. Assim o utilizador nunca recebe uma senha em claro.
Verificar primeiro como forgot-password está implementado (backend-core/app/api/auth.py)
para entender o que pode ser reaproveitado.

Leia o guia de implementação e siga o processo.
```

---

### P3 — Instruções de follow-up por agente (Etapa C)

**Origem:** `docs/plans/pipeline-configurable-fields.md` — Etapa C
**Prioridade:** ALTA — impacto directo na qualidade das mensagens de follow-up
**Esforço estimado:** médio (3 novos campos + UI + injecção nos prompts)
**Dependências:** nenhuma

**Contexto:**
Actualmente todos os operadores recebem as mesmas mensagens de follow-up genéricas
(hardcoded nos playbooks). Os três campos `followup_sdr_instructions`,
`followup_recovery_instructions` e `followup_postsession_instructions` permitem ao operador
personalizar exactamente o que o bot diz em cada tipo de follow-up para o seu negócio.

O campo é nullable com fallback para o comportamento hardcoded — quem não preenche não
é afectado.

**Entrega esperada:**
- 3 campos String nullable no AI Profile (model + migration)
- Expostos via `AIProfileBase`/`AIProfileUpdate` no backend-core
- Incluídos no ContextBundle via `enrich_context_bundle()` no orchestrator
- Injectados no `_build_child_followup_prompt()` do decision_engine por variante
- Textarea por campo na secção Follow-Up do AI Profile no frontend

**Prompt para o processo de implementations:**
```
Gostaria de implementar as instruções de follow-up personalizáveis por agente
no AI Profile (Etapa C de pipeline-configurable-fields).

Contexto: os três tipos de agente (sdr_scheduler, cart_recovery, hybrid_scheduler)
têm instruções de follow-up hardcoded nos playbooks. O operador não tem como
personalizar o que o bot diz no follow-up para o seu nicho específico.

Os três novos campos do AI Profile:
- followup_sdr_instructions (Agent 1 — sdr_scheduler)
- followup_recovery_instructions (Agent 2 — cart_recovery)
- followup_postsession_instructions (Agent 3 — hybrid_scheduler)

Todos seguem o mesmo padrão: String nullable, injectado entre a instrução hardcoded
da variante e o custom_instructions global, com fallback para hardcoded se None.

Arquivos principais:
- backend-core/app/models/ai_profile.py — 3 novos campos
- backend-core/app/db.py — 3 migrations ensure_column() idempotentes
- backend-core/app/api/ai_profiles.py — expor em AIProfileBase e AIProfileUpdate
- backend-crm/services/ai_orchestrator/orchestrator.py — incluir no ContextBundle
- backend-executors/app/services/decision_engine.py → _build_child_followup_prompt()
- frontend-crm/src/pages/AiProfile.tsx — textarea por campo, condicional ao template_key

Documentação de referência completa em docs/plans/pipeline-configurable-fields.md
seção "Etapa C".

Leia o guia de implementação e siga o processo.
```

---

## Itens fora deste sprint

| Item | Motivo de exclusão |
|---|---|
| M2 — Página /welcome | Sinergia com M3 considerada, mas M3 é mais crítico — M2 vai para próximo sprint |
| M4 — Email de activação upgrades | Baixíssimo esforço, mas depende de M1 estar em produção para validar o fluxo completo |
| M5 — Retries + alertas webhook | M1 resolve o motivo principal dos skipped — reavaliar após M1 em produção |
| M6 — Modal de upgrade | Baixa prioridade — UX, sem impacto em receita ou segurança |

---

## Manutenção dos arquivos docs/plans/* após este sprint

Quando todos os itens do sprint estiverem implementados:

| Ação | Condição |
|---|---|
| Marcar M1, M3 como ✅ em `kiwify-checkout-melhorias-pos-etapa-9-7.md` | Após cada implementação respectiva |
| Marcar Etapa C como ✅ em `pipeline-configurable-fields.md` | Após implementação de P3 |
| `git rm docs/plans/pipeline-configurable-fields.md` | Quando Etapas C for a última pendente — verificar se A, B, D, E, F, G, H, I estão todas absorvidas |
| `git rm docs/plans/kiwify-checkout-melhorias-pos-etapa-9-7.md` | Apenas quando M1–M6 estiverem todos absorvidos |
