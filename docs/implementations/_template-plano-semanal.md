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

> **P (experiência): Quando um cliente existente faz upgrade de plano, deve receber
> email de confirmação automático ou apenas ver o plano actualizado na plataforma?**
> R (admin, 04/06/2026): "Sim, deve receber email — o cliente precisa de saber que o
> pagamento foi processado e que o acesso foi activado."

> **P (estratégia): O Plano Scale vai à venda via Kiwify neste sprint?**
> R (admin, 04/06/2026): "Não ainda — criar o seed com os limites técnicos, mas não
> mapear no webhook por agora. O webhook de activação pode esperar o preço ser confirmado."

---

## Sprint — Itens selecionados

### P1 — Criar plano `crm_scale` no DB

**Origem:** `docs/plans/kiwify-checkout-melhorias-pos-etapa-9-7.md` — seção M1
**Prioridade:** ALTA — bloqueia vendas reais do Plano Scale
**Esforço estimado:** baixo (seed + limites, 1 arquivo principal)
**Dependências:** nenhuma

**Contexto:**
O webhook Kiwify já está preparado para activar o Plano Scale quando um cliente compra,
mas o plano `crm_scale` não existe no banco de dados. Resultado prático: cliente paga,
webhook retorna `skipped: plan_not_found`, conta não é activada. Nenhum erro visível —
vai para logs silenciosamente.

**Entrega esperada:**
- Cliente que compra o Plano Scale recebe o plano activo após o webhook processar o evento
- O plano Scale existe no banco com os limites definidos pelo fundador
- O webhook de activação não é alterado — já está correcto

**Prompt para o processo de implementations:**
```
Gostaria de registar o plano crm_scale no banco de dados do backend-core.
Actualmente clientes que compram o Plano Scale ficam sem acesso — o webhook Kiwify
retorna skipped:plan_not_found silenciosamente porque o plano não existe no banco.

Comportamento actual: webhook Kiwify recebe evento de compra do Scale, tenta activar
o plano crm_scale, não o encontra no banco, retorna skipped. Cliente fica sem acesso.
Comportamento desejado: plano crm_scale existe no banco com os limites definidos,
activação automática funciona normalmente ao receber o evento Kiwify.

Os limites confirmados do Scale: max_leads=5000, max_ia_conversas_monthly=1500,
max_whatsapp_send_daily=200, max_instances=3, follow_up_enabled=True,
playground_monthly_limit=None.

Área do sistema: backend-core (modelo de planos e inicialização do banco).
Nota: o webhook de activação não precisa de alteração — o problema está apenas no
registro do plano.

Leia o guia de implementação e siga o processo.
```

---

### P2 — Forçar mudança de senha no primeiro login

**Origem:** `docs/plans/kiwify-checkout-melhorias-pos-etapa-9-7.md` — seção M3
**Prioridade:** ALTA — segurança (senha temporária enviada em claro por email)
**Esforço estimado:** médio (campo DB + middleware/guard frontend)
**Dependências:** nenhuma (independente de P1)

**Contexto:**
Quando um novo cliente compra pelo Kiwify, o sistema gera uma senha temporária aleatória
e a envia em texto claro por email. Nenhum mecanismo força a troca após o primeiro login.
O risco: se o email for comprometido, a conta fica vulnerável indefinidamente.

**Entrega esperada:**
- Novo cliente recebe um email que o conduz a definir a própria senha
- A senha nunca circula em claro por email
- O acesso à plataforma exige que o utilizador tenha definido a própria senha

**Prompt para o processo de implementations:**
```
Gostaria de corrigir o fluxo de criação de conta via Kiwify para não enviar
senha temporária em claro por email.
Actualmente existe risco de segurança: se o email do novo cliente for comprometido,
a conta fica vulnerável indefinidamente porque a senha nunca precisa ser trocada.

Comportamento actual: quando um novo utilizador compra pelo Kiwify, o sistema gera
uma senha aleatória e a envia por email em texto claro como credencial de acesso.
Não há mecanismo que force a troca após o primeiro login.
Comportamento desejado: o novo utilizador recebe um link para definir a própria senha,
sem senha gerada automaticamente em claro. O acesso à plataforma só funciona após
a definição da senha pelo próprio utilizador.

Área do sistema: backend-core (fluxo de criação de conta via webhook Kiwify e
serviço de email). Verificar se já existe infraestrutura de link de definição de
senha (ex.: fluxo de recuperação de senha) que possa ser reaproveitada.

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
- O operador pode escrever instruções específicas do seu negócio para cada tipo de
  follow-up (Agent 1, 2, 3) directamente no AI Profile
- O bot usa essas instruções nas mensagens de follow-up em vez das genéricas
- Quem não preencher o campo continua a receber o comportamento anterior inalterado

**Prompt para o processo de implementations:**
```
Gostaria de implementar campos de instruções de follow-up personalizáveis por agente
no AI Profile.
Actualmente todos os operadores recebem as mesmas mensagens de follow-up genéricas,
independentemente do seu negócio, nicho ou tom.

Comportamento actual: os prompts de follow-up para os três tipos de agente
(sdr_scheduler, cart_recovery, hybrid_scheduler) são instruções genéricas hardcoded
na plataforma. O operador não tem como personalizar o que o bot diz no follow-up.
Comportamento desejado: o AI Profile passa a ter um campo de texto livre por tipo
de agente. Quando preenchido pelo operador, o bot usa essas instruções nas mensagens
de follow-up. Quando vazio, o comportamento hardcoded é mantido (fallback).

Os três campos a criar:
- followup_sdr_instructions (Agent 1)
- followup_recovery_instructions (Agent 2)
- followup_postsession_instructions (Agent 3)

Área do sistema: backend-core (modelo AI Profile) + backend-crm (orquestrador de IA) +
backend-executors (decision engine que gera os prompts de follow-up) + frontend-crm
(página de configuração do AI Profile).
Documentação de referência completa: docs/plans/pipeline-configurable-fields.md seção C.

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
