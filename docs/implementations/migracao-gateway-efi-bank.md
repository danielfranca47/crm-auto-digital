# Migração de Gateway de Pagamento: Kiwify → Efí Bank

**Branch:** `main`
**Status:** Fases 1 e 2 implementadas e testadas localmente — pendente teste com pagamento real (Cenário C1)

---

## Motivação

A conta Kiwify do utilizador teve bloqueio de saque por questões de documentação/verificação.
Decisão: migrar o gateway de pagamento para a Efí Bank, onde já existe conta validada (Efí Pro,
pessoa física). Sem clientes pagantes ativos hoje — corte limpo, sem gateway duplo.

Pesquisa prévia confirmou: Kiwify cobra 8,99% + R$2,49/venda vs. Efí 3,49% flat no cartão — além
de resolver o bloqueio de saque. Achado importante durante a implementação: o link de checkout de
assinatura da Efí (`payment_url`) é uma página **hospedada** onde o próprio cliente preenche nome,
CPF, email, telefone e dados do cartão — confirmado visualmente no sandbox. Isso descartou a
necessidade, prevista inicialmente, de construir um formulário de checkout próprio com
tokenização de cartão — reduz bastante o escopo da Fase 2.

---

## Problemas Identificados (estado anterior)

1. **Toda a lógica de pagamento acoplada à Kiwify**, espalhada por 3 backends e 2 frontends —
   mapeado exaustivamente (arquivos e linhas no plano aprovado desta implementação).
2. **Handler de webhook duplicado morto:** `backend-core/app/api/webhooks_kiwify.py` — uma versão
   mais antiga do mesmo fluxo, não referenciada por nada em produção (o fluxo real passa por
   `backend-crm/routes/webhooks.py` → `backend-core/app/api/subscriptions.py`). Não tinha
   auto-criação de utilizador nem suporte a "Growth Fundador"/Scale.
3. **Bug latente descoberto durante o teste desta implementação:** o endpoint interno de eventos
   de pagamento só criava conta nova quando `action == "activate"`. Como o webhook da Efí não
   distingue de forma confiável "1ª cobrança" de "renovação" (ver Abordagem), enviar `action:
   "renew"` para um email desconhecido resultava em `skipped: user_not_found` — cliente pago,
   conta nunca criada. Corrigido nesta fase (ver Fase 1).

---

## Abordagem

```
Landing/checkout (futuro, Fase 2)
  → backend gera link de assinatura Efí sob demanda (POST /v1/plan/:id/subscription/one-step/link)
  → cliente é redirecionado para payment_url (página hospedada da Efí)
  → cliente preenche nome/CPF/email/telefone/cartão na própria página da Efí

Efí aprova pagamento
  → POST form-encoded para /webhooks/efi (backend-crm), campo `notification` = token
  → GET /v1/notification/:token → lista de mudanças de status (charge/subscription)
  → para cada mudança relevante (status "paid" → renew; "canceled"/"expired" → cancel):
      → GET /v1/charge/:id (ou /v1/subscription/:id) → custom_id (=plan_code) + customer.email
      → POST /internal/subscriptions/payment-event (backend-core) { email, plan_code, action }
          → activa/renova/cancela subscription; cria User se necessário (activate OU renew)
```

**Decisão de design (validada por teste):** em vez de tentar classificar com certeza se uma
cobrança "paid" é a 1ª ou uma renovação (o payload da Efí não deixa isso trivialmente claro sem
mais uma chamada extra), o webhook sempre envia `action: "renew"` para qualquer cobrança paga.
O endpoint interno já sabia estender uma subscrição ativa existente ou, na ausência dela, criar
uma nova — bastou ensiná-lo a também criar o `User` novo nesse caminho (antes só criava em
`action == "activate"`). Testado localmente nos dois sentidos (ver Checks).

**Decisão de arquitetura:** sem abstração genérica de múltiplos gateways — a Efí substitui a
Kiwify, não coexiste com ela. O endpoint interno do backend-core já era essencialmente agnóstico
de gateway; só precisou perder o nome "kiwify".

---

## Plano de Implementação

### Fase 1 — Fundação backend (testável sem UI)

**Objetivo:** o backend sabe falar com a Efí e o endpoint interno de activate/renew/cancel deixa
de ter a marca "Kiwify".

| Arquivo | O que mudou |
|---|---|
| `backend-crm/services/efi_client.py` *(novo)* | Cliente OAuth2 (Basic Auth → `access_token` cacheado em memória); `create_plan()`, `create_subscription_link()`, `resolve_notification()`, `get_charge()`, `get_subscription()` |
| `backend-core/app/api/subscriptions.py` | `KiwifyEventRequest`→`PaymentEventRequest`; rota `/internal/subscriptions/kiwify-event`→`/internal/subscriptions/payment-event`; **fix**: auto-criação de `User` agora cobre `action in {"activate","renew"}`, só `"cancel"` pula utilizador desconhecido |
| `backend-core/app/api/webhooks_kiwify.py` | **Removido** — duplicado morto |
| `backend-core/app/api/__init__.py` | Remove import/registo do router acima |
| `backend-core/app/config.py` | Remove `KIWIFY_WEBHOOK_SECRET`/`KIWIFY_PRODUCT_ID` (sem uso — backend-core não fala mais com gateway nenhum diretamente) |
| `backend-crm/routes/webhooks.py` | `POST /webhooks/kiwify` (HMAC) → `POST /webhooks/efi` (token + consulta). Resolve `plan_code`/email via `get_charge`/`get_subscription`, chama `payment-event` |
| `backend-core/.env.example`, `backend-core/.env` | Remove variáveis Kiwify (não usadas por mais nada) |
| `backend-crm/.env.example`, `backend-crm/.env` | Troca `KIWIFY_WEBHOOK_SECRET` por `EFI_CLIENT_ID`, `EFI_CLIENT_SECRET`, `EFI_SANDBOX` |

**Planos criados no sandbox Efí** (via `efi_client.create_plan`, para uso nos testes/Fase 2):

| plan_code (nosso) | Nome no Efí | plan_id sandbox | Repetições |
|---|---|---|---|
| `crm_start` | Plano Start - Lara AI | `70460` | ilimitadas |
| `crm_growth` | Plano Growth - Lara AI | `70461` | ilimitadas |
| `crm_growth` (campanha) | Plano Growth Fundador - Lara AI | `70462` | 12 |

> Nota: são IDs do ambiente sandbox/homologação — ao migrar para produção, os planos precisam ser
> recriados com as credenciais de produção (novos `plan_id`s).

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `08b931b` | Cliente Efí, endpoint interno renomeado + corrigido, webhook novo, remoção do handler morto |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** todo o sistema de pagamento (site, CRM, emails automáticos) dependia só da Kiwify —
código, variáveis de ambiente e nomes de função com "kiwify" espalhados por 3 serviços.
**Agora:** o backend já sabe autenticar na Efí, criar planos de assinatura, gerar links de
checkout e processar as notificações de pagamento — tudo testado com as credenciais reais de
sandbox. O endpoint interno que ativa/renova/cancela contas ficou mais robusto (corrige um bug que
faria clientes pagarem sem receber acesso). Ainda não há botão nenhum ligado a isso — essa é a
Fase 2.
**Para validar:** Cenários P1 e C1, abaixo.

---

## Checks de Validação

### Cenário P1 — Fluxo completo testado localmente (sem pagamento real)
- [x] Autenticação OAuth2 no sandbox (`POST /v1/authorize`) retorna `access_token`
- [x] Criação de plano (`POST /v1/plan`) funciona via `efi_client.create_plan`
- [x] Geração de link de assinatura (`.../subscription/one-step/link`) retorna `payment_url`
- [x] `payment_url` visitado no browser — confirmado visualmente que é página hospedada com
      formulário próprio (nome, CPF, email, telefone, cartão, endereço)
- [x] `POST /internal/subscriptions/payment-event` com `action=activate` em email novo → cria
      utilizador + subscrição
- [x] Mesmo endpoint com `action=renew` em email já existente com subscrição ativa → estende
      `current_period_end`
- [x] Mesmo endpoint com `action=renew` em email **novo** (simula o caminho real do webhook Efí)
      → cria utilizador + subscrição corretamente (bug corrigido nesta fase)
- [x] Mesmo endpoint com `action=cancel` em email desconhecido → `skipped/user_not_found` (não
      cria conta à toa)
- **Validado em:** 03/07/2026 — testes via curl contra `backend-core` local (`.venv`, porta 8001)
  e chamadas diretas ao sandbox Efí via Python/httpx.

### Cenário C1 — Pagamento real de teste na Efí (ponta a ponta)
- [ ] Completar um pagamento real de baixo valor no `payment_url` de um plano de teste, com
      `notification_url` apontando para um endereço público real (`backend-crm` implantado)
- [ ] Confirmar que `POST /webhooks/efi` recebe o token e resolve a notificação
- [ ] Confirmar que `_resolve_efi_plan_and_email` extrai `plan_code` e `email` corretamente do
      `custom_id`/`customer.email` retornados por `get_charge`
- [ ] Confirmar que a conta é ativada e o email de boas-vindas chega
- **Pendente:** requer ambiente com URL pública (não testável em localhost) — ficará pendente até
  a Fase 2 (checkout real) ou um teste manual com túnel público

---

## Fase 2 — Checkout sob demanda + religar landing

**Objetivo:** botão da landing gera um link de checkout Efí válido e redireciona o visitante —
sem precisar de formulário de checkout próprio (ver Abordagem, descoberta da Fase 1).

| Arquivo | O que mudou |
|---|---|
| `backend-crm/routes/checkout.py` *(novo)* | `GET /checkout/efi/{offer_key}` — resolve a oferta (`start`/`growth`/`growth_fundador`) num dict com `plan_id` (lido de env var), `item_name`, `value_cents`, `custom_id`; chama `efi_client.create_subscription_link(...)`; responde `307` para o `payment_url`. 404 se a oferta ou o `plan_id` não estiverem configurados |
| `backend-crm/app.py` | Regista o router `checkout` |
| `backend-crm/services/efi_client.py` | **Fix** descoberto ao testar: `create_subscription_link` estava sem dois campos que a Efí exige em `settings` (`request_delivery_address`, `expire_at`) — API retornava 400. Corrigido, com `expire_at` calculado a partir de `link_valid_days` (default 30) |
| `backend-crm/.env`, `.env.example` | `EFI_PLAN_ID_START=70460`, `EFI_PLAN_ID_GROWTH=70461`, `EFI_PLAN_ID_GROWTH_FUNDADOR=70462` (sandbox) |
| `website/src/pages/CRMLandingV2.tsx` | CTAs de Start/Growth voltam a ter `checkoutUrl`, agora `{VITE_PUBLIC_API_BASE}/checkout/efi/{start\|growth_fundador}` |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f339ef3` | Endpoint de checkout + fix do efi_client + religar CTAs da landing |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** os botões da landing estavam desativados (pausados na Fase 1, por segurança, até a
Efí estar pronta).
**Agora:** clicar em "Ativar minha Lara" no Start ou no Growth gera, na hora, um link de checkout
novo na Efí e abre a página de pagamento hospedada deles, já com o plano e o preço corretos.
**Para validar:** Cenários P1 e P2, abaixo (ambos já testados e confirmados nesta sessão).

---

## Checks de Validação — Fase 2

### Cenário P1 — Endpoint de checkout gera link válido
- [x] `GET /checkout/efi/start` (sem seguir redirect) → `307` com `Location` apontando para
      `pagamento.gerencianet.com.br`/`sejaefi.com.br`
- [x] Mesmo teste para `growth_fundador` e `growth`
- [x] Oferta inexistente (`/checkout/efi/nao-existe`) → `404`
- **Validado em:** 03/07/2026 — `backend-crm` local (porta 8000, `.venv`), curl direto

### Cenário P2 — Botão da landing até a página de pagamento real
- [x] Landing local (`/lara-ia`) — `href` do CTA Start/Growth aponta para o endpoint de checkout
- [x] Clique no botão do Growth abre nova aba, redireciona até a página hospedada da Efí
- [x] Valor exibido na página de pagamento: **R$147,00** — confere com a campanha Fundador
- **Validado em:** 03/07/2026 — teste ao vivo via browser (chrome-devtools MCP), screenshot
  conferido

---

## Ajustes Possíveis Pós-Implementação

- A extração de `plan_code`/email para o caso de **cancelamento** (`identifiers.subscription_id`
  em vez de `charge_id`) foi implementada com base na documentação, mas nunca validada contra um
  payload real de notificação de cancelamento — vale confirmar no primeiro cancelamento real.
- Fase 3 (repontar `usage.py`, `subscription_jobs.py`, `Assinatura.tsx`, `UsageAlertBanner.tsx`
  para a Efí) e Fase 4 (limpeza de docs/arquitetura) seguem pendentes.
- Cenário C1 (pagamento real ponta a ponta, incluindo o webhook) continua pendente — precisa de
  `notification_url` pública (produção ou túnel), não testável em localhost.
