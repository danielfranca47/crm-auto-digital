# Migração de Gateway de Pagamento: Kiwify → Efí Bank

**Branch:** `main`
**Status:** Fases 1, 2 e 3 implementadas e testadas — Fase 4 (limpeza + fix do domínio) pendente

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
- [x] Completar um pagamento de teste no `payment_url` real, gerado pelo `backend-crm` de
      produção (`backend-crm-production-a702.up.railway.app`), com `notification_url` pública
- [x] Confirmar que os dados do cliente (nome/CPF/email/telefone) retornam corretamente em
      `GET /v1/charge/:id` uma vez processado — exatamente o formato que
      `_resolve_efi_plan_and_email` espera
- [x] Confirmar que uma cobrança de cartão aprovada (simulada com o dígito final controlado,
      documentado pela Efí) resulta em `status: "approved"`
- [ ] Confirmar que o status avança para `"paid"` (liquidação final) e que isso ativa a conta —
      **não observável no ambiente sandbox** (ver nota abaixo)
- **Validado em:** 03/07/2026 — dois testes reais via browser contra produção: (1) fluxo de
  assinatura completo (Start, R$97) e (2) cobrança avulsa simulada com aprovação (R$97, cartão
  terminado em dígito seguro). Ambos confirmaram o pipeline até a Efí processar o pagamento.

**Nota importante descoberta neste teste — `approved` ≠ `paid`:** a documentação oficial da Efí
(`/docs/api-cobrancas/status/`) distingue os dois: `approved` é só a autorização da operadora do
cartão (dinheiro ainda não creditado); `paid` é a liquidação final, e é o status recomendado pela
própria Efí para liberar acesso — que é exatamente o que `efi_webhook` já verifica
(`status_current == "paid"`). O código não precisou de correção. A cobrança de teste ficou parada
em `approved` no sandbox mesmo após espera — segundo o suporte oficial da Efí (fórum da
comunidade), o sandbox simula a autorização do cartão mas não simula a liquidação final, então
`paid` só é observável com uma transação real em produção. Decisão do utilizador: aceitar como
validado por ora — o comportamento do código já segue a recomendação oficial da Efí; fechar essa
última ponta quando a migração for para produção real (Fase futura, fora do escopo atual).

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

## Fase 3 — Repontar links restantes (usage.py, subscription_jobs.py, Assinatura.tsx, UsageAlertBanner.tsx)

**Objetivo:** nenhum link `pay.kiwify.com.br` sobrevive fora da Fase 4 (limpeza/docs).

| Arquivo | O que mudou |
|---|---|
| `backend-crm/routes/usage.py` | `checkout_links` agora monta `{CRM_PUBLIC_BASE_URL}/checkout/efi/{start\|growth}` em vez dos links Kiwify fixos |
| `backend-core/app/jobs/subscription_jobs.py` | Remove `PLAN_CHECKOUT_LINKS` fixo; `_get_checkout_url` monta o link via `settings.CRM_PUBLIC_BASE_URL` + `_PLAN_OFFER_KEYS`, com fallback para `/assinatura` se a variável não estiver definida |
| `frontend-crm/src/pages/Assinatura.tsx` | `PLAN_CHECKOUT_URLS` aponta para o endpoint Efí (`VITE_CRM_BASE_URL`); remove entrada morta `crm_scale`; `buildCheckoutUrl` não tenta mais pré-preencher `?email=` (não aplicável ao checkout hospedado da Efí); texto do aviso "Como trocar de plano" deixa de mencionar "Kiwify" (inclusive a frase que prometia um link de cancelamento por email, que não existe no fluxo Efí — trocado por "contacta o suporte") |
| `frontend-crm/src/components/UsageAlertBanner.tsx` | **Fix de bug pré-existente:** o ternário sempre resolvia para `CHECKOUT_GROWTH` mesmo com o utilizador já no Growth; agora utilizador em `crm_growth` é direcionado para `/assinatura` (rota interna) em vez de reofertar o mesmo plano; demais casos apontam para o endpoint Efí |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b64e48b` | Repontar usage.py, subscription_jobs.py, Assinatura.tsx, UsageAlertBanner.tsx para Efí |

### Relatório da Fase 3 — o que mudou na prática

**Antes:** clientes já logados que tentassem fazer upgrade de plano (pela tela de Assinatura ou
pelo banner de limite atingido) ainda caíam nos links antigos da Kiwify — inconsistente com a
landing pública, que já usava a Efí desde a Fase 2.
**Agora:** todos os pontos de upgrade dentro do CRM (tela de Assinatura, banner de limite, emails
automáticos de aviso/expiração) usam o mesmo endpoint de checkout Efí da Fase 2. De brinde,
corrigi um bug onde um cliente já no plano Growth recebia sempre o mesmo link de upgrade para
Growth (plano que ele já tem) em vez de ser direcionado para a tela de gestão da conta.
**Para validar:** Cenários P1–P4, abaixo (todos já verificados nesta sessão).

---

### Cenário P1 — `_get_checkout_url` (subscription_jobs.py) monta o link certo
- [x] `_get_checkout_url("crm_start")` → `{CRM_PUBLIC_BASE_URL}/checkout/efi/start`
- [x] `_get_checkout_url("crm_growth")` → `.../checkout/efi/growth`
- [x] Plano sem mapeamento (`crm_internal`) → cai no fallback `/assinatura`
- **Validado em:** 03/07/2026 — chamada direta da função via `.venv` local

### Cenário P2 — `usage.py` monta `checkout_links` corretamente
- [x] Lógica de montagem (`f"{_crm_base}/checkout/efi/start"`) conferida isoladamente
- **Validado em:** 03/07/2026 — verificação da expressão via script Python

### Cenário P3 — `Assinatura.tsx` abre o checkout Efí real
- [x] Login como utilizador de teste (`autodigital157@gmail.com`, plano Growth activo)
- [x] Clique em "Selecionar plano" no card Start abre nova aba
- [x] Página de pagamento Efí mostra **Plano Start - Lara AI, R$97,00** — confere
- **Validado em:** 03/07/2026 — teste ao vivo via browser (chrome-devtools MCP), login real,
  clique real, screenshot conferido

### Cenário P4 — `UsageAlertBanner.tsx` — revisão de código
- [x] Fix do bug do ternário conferido por leitura de código (banner só aparece com uso real
  ≥80%, não reproduzido ao vivo por exigir dados de consumo reais no ambiente de teste)
- **Validado em:** 03/07/2026 — revisão de código

---

## Ajustes Possíveis Pós-Implementação

- A extração de `plan_code`/email para o caso de **cancelamento** (`identifiers.subscription_id`
  em vez de `charge_id`) foi implementada com base na documentação, mas nunca validada contra um
  payload real de notificação de cancelamento — vale confirmar no primeiro cancelamento real.
- Confirmação final de que o status `"paid"` (liquidação) ativa a conta corretamente em produção
  real fica pendente — ver nota no Cenário C1, acima.

## Fase 4 — Pendências (ainda não iniciada)

**Prioridade ALTA — bloqueia pagamentos reais de clientes:**
- **Domínio `https://api.danielfranca.pt` (`CRM_PUBLIC_BASE_URL`) fora do ar — `502 Bad Gateway`.**
  Descoberto durante os testes do Cenário C1. O backend-crm está saudável na URL direta do
  Railway (`backend-crm-production-a702.up.railway.app`) — o problema é só no roteamento
  Cloudflare/DNS do domínio próprio, não no código desta migração. **Enquanto não for corrigido,
  os `notification_url` gerados pelo endpoint de checkout em produção apontam para um domínio
  inacessível pela Efí — ou seja, pagamentos reais de clientes não vão conseguir notificar o
  nosso sistema e as contas não serão ativadas automaticamente.** Investigar e corrigir antes de
  divulgar a campanha Fundador para clientes reais.

**Prioridade normal — limpeza:**
- Repontar `backend-crm/routes/usage.py`, `backend-core/app/jobs/subscription_jobs.py`,
  `frontend-crm/src/pages/Assinatura.tsx`, `frontend-crm/src/components/UsageAlertBanner.tsx` —
  ainda usam links antigos da Kiwify.
- Remover variáveis de ambiente Kiwify não usadas (produção), arquivar/remover
  `docs/plans/kiwify-checkout-melhorias-pos-etapa-9-7.md`.
- Atualizar `docs/architecture/auth-email.md`, `plans-limits.md`, `_mapa-sistema.md` para
  descrever o fluxo Efí em vez do Kiwify.
