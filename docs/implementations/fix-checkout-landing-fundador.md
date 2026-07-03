# Fix: Checkout Kiwify na Landing V2 + Produto "Plano Growth Fundador"

**Branch:** `main`
**Status:** Cenário P1 validado (03/07/2026) — pendente: Cenário C1 (requer compra real de teste na Kiwify)

---

## Motivação

Auditoria do fluxo de aquisição (landing → checkout → ativação → email → primeiro login) revelou
que os botões de CTA da landing `CRMLandingV2.tsx` nunca foram ligados a nenhum checkout real —
apontam para `href="#"`. Ninguém consegue comprar a partir da landing hoje.

Durante a conversa, o utilizador criou na Kiwify um novo produto para a campanha "Fundador":
**"Plano Growth Fundador"**, R$147/mês, 12 cobranças fixas, checkout
`https://pay.kiwify.com.br/GAiuZT8`. O webhook de ativação só reconhece nomes de plano fixos
(`_KIWIFY_PLAN_MAP`) — sem uma entrada nova, uma compra desse produto passaria pela Kiwify mas
seria ignorada silenciosamente pelo nosso sistema (`plan_not_found`), deixando o cliente pago sem
acesso.

---

## Problemas Identificados (estado anterior)

1. **CTAs da landing sem link real:** `website/src/pages/CRMLandingV2.tsx:1134-1137` — `<a href="#">{plan.cta}</a>` em todos os planos, incluindo Start e Growth.
2. **Produto novo não reconhecido pelo webhook:** `backend-crm/routes/webhooks.py:581-587` — `_KIWIFY_PLAN_MAP` não contém `"Plano Growth Fundador"`.

---

## Abordagem

```
Landing V2 (visitante)
  → clica CTA no card Start   → https://pay.kiwify.com.br/gOjcexD
  → clica CTA no card Growth  → https://pay.kiwify.com.br/GAiuZT8  (Fundador, R$147)
       ↓ Kiwify aprova compra
  Kiwify webhook → backend-crm/routes/webhooks.py
       ↓ plan_name = "Plano Growth Fundador" → _KIWIFY_PLAN_MAP → "crm_growth"
  backend-core ativa subscription crm_growth (mesmos limites do Growth normal)
```

O job diário de expiração (`backend-core/app/jobs/subscription_jobs.py`) já cobre o aviso de
renovação para R$197 quando as 12 cobranças fixas da Kiwify terminarem — não precisa de código
novo para isso.

---

## Plano de Implementação

### Fase 1 — Backend: reconhecer "Plano Growth Fundador"

**Objetivo:** compra do novo produto Kiwify ativa automaticamente o plano `crm_growth`.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/webhooks.py` | Adicionar `"Plano Growth Fundador"` e `"Growth Fundador"` ao dict `_KIWIFY_PLAN_MAP`, apontando para `"crm_growth"` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d0674a5` | backend: reconhecer "Plano Growth Fundador" no `_KIWIFY_PLAN_MAP` |

**Detalhes do commit `d0674a5`:**
- `backend-crm/routes/webhooks.py` — adiciona `"Plano Growth Fundador"` e `"Growth Fundador"` ao dict, ambos mapeando para `crm_growth`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** uma compra do novo produto Kiwify "Plano Growth Fundador" (R$147/mês) passava pela Kiwify normalmente, mas ao chegar no nosso sistema era descartada silenciosamente — o cliente pagava e a conta nunca era ativada.
**Agora:** o sistema reconhece esse produto e ativa a conta automaticamente com o mesmo plano Growth (mesmos limites e funcionalidades), exatamente como já acontece para o Growth normal.
**Para validar:** Cenário C1, abaixo.

### Fase 2 — Frontend: ligar os CTAs da landing V2

**Objetivo:** botões "Ativar minha Lara" dos cards Start e Growth abrem o checkout Kiwify correto.

| Arquivo | O que muda |
|---|---|
| `website/src/pages/CRMLandingV2.tsx` | Campo `checkoutUrl` por plano; CTA usa `plan.checkoutUrl` (nova aba) em vez de `"#"`; Scale/Enterprise seguem sem link (comingSoon) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `8feccbb` | frontend: CTAs de Start/Growth apontam para o checkout Kiwify real |

**Detalhes do commit `8feccbb`:**
- `website/src/pages/CRMLandingV2.tsx` — adiciona `checkoutUrl` a cada plano (`gOjcexD` para Start, `GAiuZT8` para Growth Fundador, `undefined` para Scale/Enterprise); CTA abre em nova aba quando há link

### Relatório da Fase 2 — o que mudou na prática

**Antes:** os botões "Ativar minha Lara" da landing não levavam a lugar nenhum (`href="#"`) — ninguém conseguia comprar a partir da página.
**Agora:** o botão do Start abre o checkout do Plano Start (R$97), e o botão do Growth abre o checkout da campanha Fundador (R$147, produto "Plano Growth Fundador"), cada um em nova aba. Scale e Enterprise continuam sem link ativo, como já estava (em breve).
**Para validar:** Cenário P1, abaixo.

---

## Checks de Validação

### Cenário P1 — Botões da landing apontam para o link certo
- [x] Rodar a landing localmente (`cd website && npm run dev`)
- [x] Confirmar `href` do CTA no card Start → `https://pay.kiwify.com.br/gOjcexD`
- [x] Confirmar `href` do CTA no card Growth → `https://pay.kiwify.com.br/GAiuZT8`
- [x] Confirmar que Scale/Enterprise continuam sem link clicável
- **Validado em:** 03/07/2026 — testado via browser (rota `/lara-ia`, servidor local porta 5180). Os 4 CTAs conferidos por script: Start e Growth com `href` correto + `target="_blank"`; Scale e Enterprise com `href="#"` e `pointer-events-none` (bloqueados), como esperado.

### Cenário C1 — Webhook reconhece o novo produto
- [ ] Confirmar no código que `_KIWIFY_PLAN_MAP["Plano Growth Fundador"]` resolve para `"crm_growth"`
- [ ] Idealmente, confirmar com uma compra real de teste: Kiwify → webhook → ativação → email de boas-vindas

---

## Ajustes Possíveis Pós-Implementação

- Não há confirmação de que a Kiwify dispara evento explícito de cancelamento ao final das 12
  cobranças fixas (vs. simplesmente parar de renovar). O job diário de expiração cobre esse caso
  de qualquer forma — vale observar o comportamento real no primeiro ciclo de 12 meses.
- M2 (página `/welcome`), M3 (forçar troca de senha temporária) e M4 (email de confirmação em
  upgrade) continuam pendentes — `docs/plans/kiwify-checkout-melhorias-pos-etapa-9-7.md`, fora do
  escopo desta implementação.
