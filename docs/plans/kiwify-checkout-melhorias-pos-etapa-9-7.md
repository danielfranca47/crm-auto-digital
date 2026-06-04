# Melhorias Pós-Implementação: Checkout e Webhook Kiwify

> **Contexto:** documento escrito após a graduação da etapa-9-7 (Upgrade de Plano: Checkout e
> Webhook de Activação). Serve de referência para priorizar implementações futuras relacionadas
> com o fluxo de compra, activação de planos e experiência do novo cliente.

---

## O que foi implementado (base de referência)

A etapa-9-7 transformou o processo de activação de planos de manual para automático:

- **Frontend** (`frontend-crm/src/pages/Assinatura.tsx`): botões de checkout activos com URLs
  Kiwify por plano, data de renovação visível, aviso de sobreposição de planos, banner
  `?upgraded=1` pós-compra.

- **Webhook Kiwify** (`backend-crm/routes/webhooks.py`): recebe eventos da Kiwify, valida
  HMAC-SHA1, mapeia nome do plano para `plan_code`, e chama o backend-core.

- **Activação automática** (`backend-core/app/api/subscriptions.py` →
  `kiwify_subscription_event`): activa, renova ou cancela subscription no DB sem intervenção
  manual.

- **Auto-criação de conta** (Fase 5 da etapa-9-7): se o email do comprador não existir no
  sistema, cria `User` com senha temporária aleatória (14 chars) e envia email de boas-vindas
  com credenciais via `render_welcome_email` em `backend-core/app/services/email_service.py`.

**Resultado prático:** cliente paga na Kiwify → conta criada (se nova) → plano activo → email
com credenciais entregue. Zero intervenção manual.

---

## Pontos de melhoria identificados

### M1 — Plano `crm_scale` inexistente na base de dados

**Prioridade: ALTA — bloqueia vendas reais**

O código em `backend-crm/routes/webhooks.py` (linha ~581) já mapeia `"Plano Scale"` →
`crm_scale`. No entanto, o plano `crm_scale` **não existe na tabela `plans`** do
`backend-core/core.db`.

Se um cliente comprar o Plano Scale hoje, o webhook retorna:
```json
{"ok": true, "action": "skipped", "reason": "plan_not_found"}
```

O cliente pagou mas não tem acesso. Não há erro visível — vai para logs silenciosamente.

**O que fazer:**
- Inserir o plano `crm_scale` na tabela `plans` com os limites correctos (via
  `seed_initial_data` em `backend-core/app/db.py` ou script de migração)
- Definir os limites em `plan_limits` (max_leads, max_ia_conversas_monthly, etc.)
- Actualizar `docs/architecture/plans-limits.md` com os valores

**Referências de código:**
- `backend-core/app/db.py` → `seed_initial_data()` — onde os planos são criados no startup
- `backend-core/app/models/plan.py` — modelo `Plan` e `PlanLimits`
- `docs/architecture/plans-limits.md` → "Planos comerciais activos"

---

### M2 — Página de boas-vindas para novos compradores

**Prioridade: ALTA — impacto directo na primeira impressão**

Actualmente o redirect pós-compra configurado na Kiwify aponta para
`/assinatura?upgraded=1`. Esta página foi desenhada para utilizadores existentes a fazer
upgrade — mostra o plano actual, datas de renovação e botões de mudança de plano.

Um cliente novo (primeira compra) chega a esta página sem ainda ter sessão, sem saber o
que fazer, e com o banner "Plano activado com sucesso!" que não explica os próximos passos.

**O que fazer:**
- Criar rota pública `/welcome` em `frontend-crm/src/App.tsx`
- Componente `Welcome.tsx` com: confirmação de activação, instruções de primeiro login,
  link directo para `/login`, e primeiros passos sugeridos (ligar WhatsApp, configurar agente)
- Alterar o redirect pós-compra no painel Kiwify para `/welcome` (para novos compradores)
- O `/assinatura?upgraded=1` pode continuar a ser o redirect para upgrades (utilizadores
  existentes que já têm sessão activa)

**Referências de código:**
- `frontend-crm/src/App.tsx` — onde registar a nova rota pública (junto com `/login`,
  `/register`, `/reset-password`)
- `docs/architecture/auth-email.md` → "Rotas Públicas no Frontend-CRM"
- Nota em `docs/implementations/etapa-9-7-upgrade-checkout-webhook.md` (já removido, mas
  o contexto está neste ficheiro)

---

### M3 — Forçar mudança de senha no primeiro login

**Prioridade: ALTA — segurança**

A senha temporária gerada pelo fluxo Kiwify (14 chars aleatórios) é enviada por email em
texto claro. O sistema não tem nenhum mecanismo que force o utilizador a alterá-la após o
primeiro login. Se o email for comprometido, a conta fica vulnerável indefinidamente.

**O que fazer:**
- Adicionar campo `must_change_password: Boolean` ao modelo `User`
  (`backend-core/app/models/user.py`) — setado a `True` quando a conta é criada via Kiwify
  ou pelo admin
- No `GET /users/me` (ou num middleware), incluir `must_change_password` na resposta
- No frontend-crm, interceptar essa flag após login e redirigir para uma página de
  definição de nova senha antes de continuar
- Alternativamente (mais simples): usar o fluxo de `forgot-password` já existente —
  após criar a conta, enviar automaticamente um email de "define a tua senha" em vez da
  senha temporária em claro

**Referências de código:**
- `backend-core/app/models/user.py` — modelo User (adicionar campo)
- `backend-core/app/api/auth.py` — `GET /users/me`, geração de JWT
- `backend-core/app/api/subscriptions.py` → `kiwify_subscription_event()` linhas ~244–265
  — onde o User é criado e o email enviado
- `docs/architecture/auth-email.md` → "Modelo User", "Endpoints de Auth"

---

### M4 — Email de confirmação de activação para clientes existentes (upgrade)

**Prioridade: MÉDIA**

Quando um cliente existente faz upgrade (ex.: Start → Growth), o plano é activado
correctamente mas **não é enviado nenhum email de confirmação**. O template
`render_subscription_activated_email` já existe e está completo — simplesmente não está
a ser chamado no caminho de `action == "activate"` para utilizadores existentes.

O cliente sabe que o plano activou apenas se entrar na plataforma — não recebe nenhum
sinal de confirmação após o pagamento.

**O que fazer:**
- Em `backend-core/app/api/subscriptions.py`, no bloco `# activate (ou renew sem sub activa)`
  (linha ~300), após o `db.commit()`, chamar `render_subscription_activated_email` com
  o `plan.name` e o `current_period_end` da nova sub, e enviar via `send_email`
- O mesmo padrão já existe para o fluxo de renovação (`renew`) — é só replicar para `activate`

**Referências de código:**
- `backend-core/app/api/subscriptions.py` → `kiwify_subscription_event()` linha ~300
- `backend-core/app/services/email_service.py` →
  `render_subscription_activated_email(name, plan_name, period_end, login_url)`
- `docs/architecture/auth-email.md` → "Serviço de Email" (tabela de templates)

---

### M5 — Sem retries nem alertas em falhas de webhook

**Prioridade: MÉDIA — risco operacional**

O endpoint `POST /webhooks/kiwify` em `backend-crm/routes/webhooks.py` não tem:
- **Fila de retry:** se o backend-crm estiver offline quando a Kiwify dispara o evento,
  o evento perde-se. A Kiwify faz até 5 reenvios com backoff, mas se o servidor ficar
  offline por mais tempo (deploy, crash), eventos podem não ser recuperados.
- **Alerta ao admin:** quando `kiwify_subscription_event` retorna `skipped` por
  `plan_not_found` ou outros erros inesperados, vai apenas para os logs. Não existe
  notificação activa.

**O que fazer (opções):**
- **Opção simples:** logar os `skipped` numa tabela `webhook_events` (com payload,
  timestamp, motivo) e expor no painel admin para revisão manual
- **Opção mais robusta:** criar um job de retry para eventos falhos — similar ao padrão de
  jobs já existente em `backend-crm/services/jobs_service.py`
- Independentemente da opção escolhida, o caso M1 (`plan_not_found` para `crm_scale`)
  resolve o motivo mais provável de `skipped`

**Referências de código:**
- `backend-crm/routes/webhooks.py` → `kiwify_webhook()` — onde os skips acontecem
- `backend-crm/services/jobs_service.py` — padrão de fila com lease e retry, pode
  servir de modelo
- `backend-core/app/api/admin.py` — onde expor uma rota de revisão de eventos perdidos

---

### M6 — Fluxo de upgrade entre planos é confuso para o utilizador

**Prioridade: BAIXA — UX**

A Kiwify não suporta upgrade com proration automático. O fluxo actual para um cliente
que quer mudar de Start para Growth:
1. Comprar o Plano Growth (nova subscrição independente)
2. Cancelar o Plano Start manualmente pelo email da Kiwify
3. O sistema activa o Growth e cancela o Start internamente

Este processo não é explicado de forma clara na página `/assinatura`. Existe apenas
o aviso de sobreposição genérico. Um utilizador sem contexto pode ficar com os dois
planos activos e pagar duas vezes por um período.

**O que fazer:**
- Na página `Assinatura.tsx`, ao detectar que o utilizador já tem um plano activo e
  clica num plano diferente, mostrar um modal com os 3 passos acima descritos de forma
  visual e clara
- Considerar adicionar um link directo para o email de cancelamento da Kiwify (disponível
  no histórico de compras do cliente)

**Referências de código:**
- `frontend-crm/src/pages/Assinatura.tsx` — lógica de checkout e aviso de sobreposição
- `docs/architecture/plans-limits.md` → "Página de Assinatura"

---

## Tabela de priorização resumida

| # | Melhoria | Prioridade | Esforço estimado | Bloqueia vendas? |
|---|---|---|---|---|
| M1 | Criar plano `crm_scale` no DB | ALTA | Baixo (seed + limites) | ✅ Sim |
| M2 | Página de boas-vindas `/welcome` | ALTA | Médio (nova página frontend) | Não |
| M3 | Forçar mudança de senha | ALTA | Médio (campo + frontend guard) | Não |
| M4 | Email de activação para upgrades | MÉDIA | Baixo (3 linhas de código) | Não |
| M5 | Retries + alertas de falhas webhook | MÉDIA | Médio (tabela + painel admin) | Não |
| M6 | Modal de upgrade mais claro | BAIXA | Baixo (só frontend) | Não |

**Recomendação de sequência:** M1 (resolve risco imediato de venda perdida) → M4
(baixíssimo esforço, alta percepção de qualidade pelo cliente) → M2 + M3 (antes de
ter volume real de novos clientes a chegar pelo checkout).
