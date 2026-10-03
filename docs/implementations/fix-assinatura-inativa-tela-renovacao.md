# Assinatura inativa: ecrã de renovação em vez de "Sessão expirada"

**Branch:** `worktree-fix+assinatura-inativa-tela-renovacao` (`fix/assinatura-inativa-tela-renovacao`)
**Status:** Em andamento

---

## Motivação

Uma conta sem plano ativo (expirado, cancelado ou nunca subscrito) conseguia fazer
login, mas era expulsa de volta para `/login` com o aviso "Sessão expirada — Faça
login novamente". O aviso era falso — a sessão estava válida — e não dizia ao
cliente que o que faltava era renovar. A página `/assinatura`, onde ele renovaria,
também o expulsava. Resultado: ciclo sem saída, e um cliente que queria pagar não
conseguia.

Reportado em 03/10/2026 a partir de produção: `GET /api/notifications/unread` →
`403 {"detail":"Assinatura do produto CRM ausente ou inativa"}`, com o frontend a
mostrar "Sessão expirada".

Causa raiz: o handler global de erros do frontend tratava `401` (sessão inválida)
e `403` (sem acesso) como a mesma coisa, e não existia nenhuma verificação de
assinatura à entrada da app.

Comportamento pretendido (alinhado com o que plataformas de assinatura fazem —
Pipedrive, Notion, Stripe): o login funciona sempre; conta sem plano cai num ecrã
que explica o que aconteceu, garante que os dados estão guardados e tem um botão
para renovar.

---

## Problemas Identificados (estado anterior)

1. **401 e 403 tratados como iguais:** `frontend-crm/src/hooks/useApiErrorHandler.ts`
   mostrava "Sessão expirada" e fazia `navigate("/login")` para ambos.
2. **Quem disparava o ciclo:** `UsageAlertBanner` (no topo de todas as páginas do
   `AppShell`, incluindo `/assinatura`) usa `useUsage` → `GET /api/usage` → 403 de
   `backend-crm/security_core.py` (`require_crm_access`) → handler acima.
3. **Nenhuma verificação de assinatura à entrada:** `Protected` (`App.tsx`) só
   validava a sessão (`/users/me` no core).
4. **`/assinatura` escolhia a assinatura errada:** `products.find(product_code ===
   "crm")` pegava a primeira linha. Como cada ativação cancela a anterior e cria
   outra, um cliente ativo podia ver uma assinatura antiga cancelada. O estado
   aparecia em inglês cru ("expired"), e um plano expirado ficava marcado "Seu
   plano atual" com o botão desabilitado.
5. **Preço de Fundador não chegava à app:** `/me/entitlements` não expunha
   `origin_offer`; um botão "Renovar" dentro da app mandaria o Fundador para R$297
   em vez de R$197 (a regra só existia nos emails, em `subscription_jobs.py`).
6. **Mensagem ilegível em 403 de gate:** `extractDetail` só lia `detail` em texto;
   gates de plano devolvem `{error, message}` e o resultado era "[object Object]".
7. **Polling em vão:** `LeadsContext` pedia leads e estado do bot a cada 30s mesmo
   sem plano (403 silenciosos contínuos).

---

## Abordagem

```
login OK → Protected (valida sessão em /users/me)
  → SubscriptionGate → useSubscriptionStatus() → GET /me/entitlements (core)
      ├─ active   → app normal
      ├─ unknown  → app normal (core indisponível — fail-open)
      └─ expired / cancelled / none
           → qualquer rota redireciona para /assinatura
           → LockedShell (sem sidebar nem banners, só "Sair")
           → cartão: o que aconteceu + dados guardados + "Renovar agora"

403 a meio do uso → handler invalida ["entitlements"] → gate reage se o plano caducou
401               → "Sessão expirada" + /login (inalterado)
```

Decisões:
- **O 403 do backend-crm mantém-se** (não mudou para 402). O executor de WhatsApp
  tem lógica própria para 403 e os gates de plano também usam 403; a verificação à
  entrada resolve o caso sem mexer no contrato.
- **Fail-open:** se o core falhar na verificação, o estado é `unknown` e a app deixa
  entrar. Quem decide o acesso de facto continua a ser o backend-crm; um cliente
  pagante nunca deve ver o ecrã de "sem plano" por uma falha de rede.
- **Preço de Fundador só para `active`/`expired`:** mesmo critério dos emails de
  aviso/expiração. Uma assinatura `cancelled` recebe o link de preço normal.
- **`renewal_checkout_url` sem fallback:** o fallback dos emails é a própria página
  `/assinatura`; dentro da app isso seria um botão que abre a página onde o
  utilizador já está. Sem oferta, devolve `None` e o frontend faz scroll aos planos.

---

## Plano de Implementação

### Fase 1 — Ecrã de assinatura inativa e fim do falso "Sessão expirada"

**Objetivo:** conta sem plano ativo entra, vê o que aconteceu e consegue renovar.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/services/checkout_links.py` (novo) | `get_offer_checkout_url` (sem fallback) e `get_checkout_url` (com fallback, para emails) — regra do Fundador movida de `subscription_jobs.py` |
| `backend-core/app/jobs/subscription_jobs.py` | passa a importar `get_checkout_url` |
| `backend-core/app/api/subscriptions.py` | `ProductEntitlement.renewal_checkout_url` em `GET /me/entitlements` |
| `backend-core/tests/test_entitlements_renewal_url.py` (novo) | 6 testes: Fundador expirado, normal, cancelado, plano sem oferta, sem `CRM_PUBLIC_BASE_URL`, fallback dos emails |
| `frontend-crm/src/lib/subscription.ts` (novo) | `pickCrmSubscription` + rótulos em português |
| `frontend-crm/src/hooks/useSubscriptionStatus.ts` (novo) | React Query `["entitlements"]`; `state`, `product`, `hasAccess` |
| `frontend-crm/src/components/SubscriptionGate.tsx` (novo) | redireciona para `/assinatura` sem plano ativo |
| `frontend-crm/src/components/LockedShell.tsx` (novo) | layout sem sidebar/banners, com "Sair" |
| `frontend-crm/src/App.tsx` | gate dentro de `Protected`; `AppShell` usa `LockedShell` sem acesso |
| `frontend-crm/src/hooks/useApiErrorHandler.ts` | 401 ≠ 403; 403 revalida assinatura e mostra a mensagem real; `extractDetail` lê `detail.message` |
| `frontend-crm/src/pages/Assinatura.tsx` | usa o hook; cartão de plano inativo com "Renovar agora" / "Já paguei — atualizar" / "Falar com suporte"; estado traduzido; plano expirado deixa de ficar bloqueado como "atual" |
| `frontend-crm/src/contexts/LeadsContext.tsx` | polling só com acesso; 403 do polling revalida a assinatura |
| `frontend-crm/src/services/api.ts` | tipo `ProductEntitlement` / `EntitlementsResponse` |
| `docs/architecture/plans-limits.md`, `billing-efi.md` | secções "Conta sem plano activo", "Página de Assinatura" e links de checkout |

Validação automática feita na implementação: `pytest tests/test_entitlements_renewal_url.py`
(6 passam); `npm run build` passa; `tsc`/`eslint` sem erros novos nos arquivos tocados.
A suíte completa do backend-core tem 8 falhas em `test_ai_profile_agent_mode.py` e
`test_ai_profile_timezone_persistence.py` que já existem em `main` e não têm relação
com esta mudança.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `d443153` | Verificação de assinatura à entrada, ecrã de plano inativo com renovação, separação 401/403, link de renovação com preço de Fundador |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quem tinha o plano expirado, cancelado ou nunca tinha subscrito fazia
login e era mandado de volta para o login com o aviso "Sessão expirada". Não havia
forma de chegar à página de assinatura para renovar.

**Agora:** essa pessoa entra e cai directamente na página de Assinatura, com um
cartão a dizer o que aconteceu ("O teu plano Growth expirou em DD/MM"), que os
leads e conversas estão guardados, que a Lara está em pausa, e um botão "Renovar
agora" que abre o pagamento — com o preço de Fundador para quem o tem. Depois de
pagar, "Já paguei — atualizar" liberta a app sem novo login. "Sessão expirada" só
aparece quando a sessão expirou de facto.

**Para validar:** Cenários C1 a C8, abaixo. Os essenciais são C1, C2 e C4 (o C4
confirma que nada mudou para quem tem o plano em dia).

---

## Checks de Validação

Ambiente local, conta de `_conta-teste-local.md`; estados forçados na tabela
`subscriptions` do `core.db` local.

Validados em 03/10/2026 via browser (MCP chrome-devtools), em cópias dos bancos locais
dentro da worktree. O backend-core local correu com `CRM_PUBLIC_BASE_URL=http://localhost:8000`
definido só no processo (o `.env` local do core não tem a variável; sem ela
`renewal_checkout_url` vem `None`). O destino de "Renovar agora" foi lido interceptando
`window.open`, sem abrir o checkout da Efí.

### Cenário C1 — Conta sem plano
- [x] Setup: conta sem nenhuma linha em `subscriptions` (ex.: criada em "Criar conta") — 03/10/2026
- [x] Fazer login — 03/10/2026
- [x] Confirmar: cai em `/assinatura` com "Ainda não tens um plano ativo"; não aparece "Sessão expirada"; não volta ao login — 03/10/2026

### Cenário C2 — Plano expirado
- [x] Setup: assinatura `crm_growth` com `status='expired'` e `current_period_end` no passado — 03/10/2026
- [x] Fazer login — 03/10/2026
- [x] Confirmar: cartão "O teu plano Growth expirou em DD/MM/AAAA", com a frase dos dados guardados — 03/10/2026
- [x] Confirmar: "Renovar agora" abre `/checkout/efi/growth` em nova aba — 03/10/2026

### Cenário C3 — Bloqueio de navegação
- [x] Com conta inativa, abrir `/dashboard` directamente no endereço — 03/10/2026
- [x] Confirmar: volta a `/assinatura`; sem sidebar; botão "Sair" leva ao login — 03/10/2026
- [x] Confirmar na aba Network: não há pedidos repetidos ao backend-crm a devolver 403 — 03/10/2026 (40s de observação: zero pedidos ao backend-crm)

### Cenário C4 — Conta ativa (regressão)
- [x] Setup: conta com assinatura `active` e pelo menos uma antiga `cancelled` — 03/10/2026
- [x] Confirmar: Kanban carrega e atualiza sozinho; sidebar e banners normais — 03/10/2026 (leads e estado do bot repetem a cada 30s, todos 200)
- [x] Confirmar: `/assinatura` mostra o plano ativo (não a antiga cancelada), badge "Ativo", sem cartão de bloqueio — 03/10/2026

### Cenário C5 — Reativação
- [x] Com o ecrã de bloqueio aberto, mudar a assinatura para `active` no banco — 03/10/2026
- [x] Clicar "Já paguei — atualizar" — 03/10/2026
- [x] Confirmar: aviso "Plano ativo!", sidebar volta, app utilizável sem novo login — 03/10/2026
- [x] Repetir sem ativar: aviso "Pagamento ainda não confirmado" — 03/10/2026

### Cenário C6 — Sessão realmente expirada
- [x] Com sessão aberta, corromper o token `crm_token` no localStorage e recarregar — 03/10/2026
- [x] Confirmar: aparece "Sessão expirada" e vai para o login — 03/10/2026

### Cenário C7 — Fundador expirado
- [x] Setup: assinatura `crm_growth` `expired` com `origin_offer='growth_fundador'` — 03/10/2026
- [x] Confirmar: "Renovar agora" abre `/checkout/efi/growth_founder_renewal` — 03/10/2026

### Cenário C8 — Core indisponível na verificação (edge)
- [x] Bloquear `GET /me/entitlements` (DevTools → Network → block request URL) e recarregar com conta ativa — 03/10/2026 (bloqueio feito por script injectado na página, que faz o pedido falhar como falha de rede)
- [ ] Confirmar: a app deixa entrar normalmente — ❌ **FALHOU em 03/10/2026**, ver "Problemas encontrados na validação"

---

## Problemas encontrados na validação (03/10/2026)

1. **C8 — app presa em "Carregando…" com rajada de pedidos quando `/me/entitlements`
   falha.** Conta com plano ativo, verificação do plano a falhar: o ecrã nunca sai de
   "Carregando…" e o frontend repete sem parar `GET /me/entitlements` (cerca de 2 por
   segundo) e, a cada ciclo, `GET /api/leads`, `/api/bot-pause/status`, `/api/usage` e
   `/ai-profiles/me`. O fail-open descrito em "Abordagem" não acontece. Causa provável
   (lida no código, por confirmar na correção): `SubscriptionGate` esconde os filhos
   enquanto `isLoading`; quando o pedido falha mostra-os; ao montar, `AppShell` cria um
   novo observador da query em erro, que volta a pedir e repõe `isLoading`; o gate
   esconde os filhos de novo — ciclo. `LeadsContext` reage a cada troca de
   `subscriptionLoading` e dispara leads + estado do bot. **Bloqueia a graduação:** hoje,
   em `main`, uma falha do core nesta rota não afecta quem já está dentro da app.
2. **Token inválido continua guardado e o polling corre em `/login`.** Depois do C6, já
   no ecrã de login, `crm_token` continua no localStorage e `GET /api/leads` +
   `/api/bot-pause/status` continuam a sair a cada 30s (mais `/me/entitlements` a
   devolver 401). Já existia antes desta implementação; é o primeiro item de "Ajustes
   Possíveis", que ali diz "não causa ciclo" — causa pedidos repetidos.
3. **Catálogo de `/assinatura` mostra planos que não são vendidos.** A lista "Planos
   disponíveis" vem de `GET /plans?product_code=crm`, que devolve todos os planos com
   `is_active` — no banco local: CRM Free, CRM Basic, CRM Pro, Start, Growth e Interno.
   Só Start e Growth têm checkout. Já existia antes, mas agora é o ecrã onde cai quem não
   tem plano. Também aparecem códigos crus ("Crm_free"), "Monthly" e "Preço: — (definir no
   checkout)". Por confirmar se a tabela de produção tem os mesmos planos activos.
4. **Botão "Falar com suporte" não aparece no ambiente local** — depende de
   `VITE_WHATSAPP_UPGRADE_NUMBER`, que não está no `.env` local. Não é defeito; fica
   registado para quem validar localmente.

---

## Ajustes Possíveis Pós-Implementação

- **Faixa "o teu plano expira em N dias" dentro da app.** Ficou de fora: as
  assinaturas normais renovam sozinhas pela Efí todos os meses e o sistema não
  regista quais renovam automaticamente — a faixa alarmaria todos os pagantes todos
  os meses. Precisaria primeiro de saber distinguir renovação automática de
  renovação manual (Fundador em transição, trial).
- **Período de tolerância.** O job diário expira quem passou de `current_period_end`
  mesmo que a cobrança da Efí chegue horas depois; o cliente fica bloqueado nesse
  intervalo. Prática de mercado: 3 a 7 dias de tolerância. Decisão de negócio.
- **Modo só-leitura após expirar** (ver leads sem poder agir), em vez de bloqueio total.
- **Limpar o token em 401.** Hoje o token inválido fica guardado após "Sessão
  expirada"; não causa ciclo, mas é resíduo.
- **Mensagem do botão "Falar com suporte".** Reutiliza o modelo de mensagem de
  upgrade (`VITE_WHATSAPP_UPGRADE_MESSAGE_TEMPLATE`), que fala em "upgrade" e não em
  renovação.
