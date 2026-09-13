# Rate-limit no envio de OTP (anti-spam)

**Branch:** `fix/otp-spam-envio`
**Status:** Todos os cenários validados (13/09/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de `fix-otp-forca-bruta.md`.

`POST /auth/request-access` e `POST /auth/register-passwordless` geram e enviam um OTP novo
por email sempre que chamados, sem nenhum limite de frequência — só ficam bloqueados depois
que `auth_otp_lockouts` acumula `MAX_OTP_ATTEMPTS` (5) tentativas **erradas de verificação**
(ver `docs/architecture/auth-email.md`, secção "Login Sem Senha (OTP)"). Ou seja, alguém pode
chamar `request-access` repetidamente para um email alheio e fazer esse email receber dezenas
de mensagens de código, sem nunca errar uma verificação e sem nunca acionar o lockout actual.

Comportamento desejado: limitar quantos OTPs um mesmo email pode receber num intervalo de
tempo, independente de haver tentativas de verificação erradas.

Risco concreto: incómodo/spam para o dono real do email (não é um vector de tomada de conta
como o da força bruta — o atacante nunca chega a saber o código), mas ainda assim um abuso
sem controlo hoje.

---

## Problemas Identificados (estado anterior)

1. **Sem limite de envio de OTP:** `_check_otp_lockout` (`backend-core/app/api/auth.py:301`)
   só verifica `locked_until`, que só é definido por `_register_otp_failure` — chamada
   exclusivamente a partir de `verify_otp_endpoint` quando o código enviado está errado.
   `request_access` (linha 340) e o ramo "email já existe" de `register_passwordless`
   (linha 358) geram e enviam um OTP novo a cada chamada, sem nenhum contador próprio.
2. **Nenhuma trilha de auditoria de volume de envio:** `auth_otp_lockouts` só guarda
   `failed_attempts`/`locked_until` — não existe coluna que registe quantos OTPs foram
   enviados num intervalo.

---

## Abordagem

Reaproveitar a tabela e o mecanismo já existentes (`auth_otp_lockouts` + `locked_until` +
mensagem 429 "Muitas tentativas...") em vez de criar uma tabela nova — mesmo padrão usado em
`fix-otp-forca-bruta`, só que contando **envios** em vez de **falhas de verificação**:

```
request_access / register_passwordless (ramo "email já existe")
  → _check_otp_lockout(email)          [já existe — bloqueia se locked_until no futuro]
  → _register_otp_send(email)          [NOVO — conta envio; se > MAX_OTP_SENDS na janela, seta locked_until e levanta 429]
  → _generate_and_store_otp + envio de email
```

- Janela deslizante fixa: no máximo `MAX_OTP_SENDS = 3` envios por email a cada
  `OTP_SEND_WINDOW_MINUTES = 10` minutos. Ao ultrapassar, marca
  `locked_until = now + OTP_LOCKOUT_MINUTES` (reaproveita a constante já existente, 15 min) —
  o mesmo `_check_otp_lockout` já usado nos 3 endpoints passa a bloquear automaticamente, sem
  mudar essa função.
- Um login bem-sucedido (`_clear_otp_failures`) já faz `DELETE FROM auth_otp_lockouts WHERE
  email = ...` — isso também limpa o contador de envios como efeito colateral aceitável
  (reinício "limpo" após login OK).
- O ramo de criação de conta nova em `register_passwordless` (email ainda não existe) não
  precisa do novo contador: cada email só passa por esse ramo uma vez (na 2ª chamada o email
  já existe e cai no ramo contado acima).

---

## Plano de Implementação

### Fase 1 — Rate-limit de envio de OTP

**Objetivo:** limitar quantos OTPs um mesmo email pode receber por janela de tempo, reutilizando
a tabela `auth_otp_lockouts` já existente.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/db.py` | Nova função `ensure_auth_otp_lockouts_send_columns()` — ALTER TABLE idempotente adicionando `otp_send_count` e `otp_send_window_started_at` a `auth_otp_lockouts` (dialect-aware sqlite/postgres, mesmo padrão de `ensure_subscription_columns`) |
| `backend-core/app/main.py` | Chama a nova função no startup, junto das outras `ensure_auth_otp_*` |
| `backend-core/app/api/auth.py` | Novas constantes `MAX_OTP_SENDS = 3`, `OTP_SEND_WINDOW_MINUTES = 10`; nova função `_register_otp_send(email, db)`; chamada em `request_access` e no ramo `if existing:` de `register_passwordless`, logo após `_check_otp_lockout` e antes de gerar o OTP |
| `backend-core/tests/test_otp_spam_send_protection.py` | Novo arquivo de teste (mesmo padrão de `test_otp_brute_force_protection.py`) |

---

## Checks de Validação

### Cenário C1 — Rate-limit bloqueia envio repetido
- [x] Chamar `POST /auth/request-access` 3x seguidas para o mesmo email existente → todas succeed (200)
- [x] 4ª chamada dentro de 10 min → 429 "Muitas tentativas..."
- [x] Confirmar (via log/DB) que nenhum OTP novo foi inserido/enviado nessa 4ª chamada
- **Validado em:** 13/09/2026 — servidor local (`backend-core`, porta 8091) rodando na worktree,
  DB copiado do dev local, email real de teste (`autodigital157@gmail.com`, ver
  `_conta-teste-local.md`). 3 chamadas retornaram 200 "Codigo enviado...", a 4ª retornou 429.
  Confirmado via SQL direto: `auth_otps` tinha só 3 linhas para o email (a 4ª chamada não gerou
  OTP novo), `auth_otp_lockouts.otp_send_count = 4` e `locked_until` ~15min no futuro.

### Cenário C2 — Janela expira
- [x] Após o bloqueio, esperar (ou simular) o `locked_until` expirar → nova chamada volta a funcionar
- **Validado em:** 13/09/2026 — `locked_until` e `otp_send_window_started_at` simulados no
  passado via SQL direto; chamada seguinte a `request-access` voltou a retornar 200.

### Cenário C3 — `register-passwordless` (email existente) também limitado
- [x] Mesmo teste do C1 usando `POST /auth/register-passwordless` para um email já cadastrado
- **Validado em:** 13/09/2026 — com o lockout do C1 ainda ativo, `register-passwordless` para o
  mesmo email também retornou 429 (mesmo `locked_until` compartilhado entre os 3 endpoints).

### Testes automatizados (pytest)
- [x] `test_otp_spam_send_protection.py` passa localmente, junto com `test_otp_brute_force_protection.py` (regressão) — **Validado em:** 13/09/2026 — `pytest tests/test_otp_spam_send_protection.py tests/test_otp_brute_force_protection.py` → 11 passed. Suíte completa também rodada (`pytest tests/`): as únicas falhas são 8 testes de `test_ai_profile_*` pré-existentes na `main` (confirmado rodando o mesmo arquivo fora desta branch), sem relação com esta mudança.

---

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f4c964e` | Rate-limit de envio de OTP (request-access + register-passwordless) |

**Detalhes do commit `f4c964e`:**
- `backend-core/app/db.py` — nova `ensure_auth_otp_lockouts_send_columns()`: adiciona `otp_send_count` e `otp_send_window_started_at` em `auth_otp_lockouts` (ALTER TABLE idempotente, sqlite/postgres)
- `backend-core/app/main.py` — chama a nova migração no startup
- `backend-core/app/api/auth.py` — novas constantes `MAX_OTP_SENDS=3`, `OTP_SEND_WINDOW_MINUTES=10`; nova `_register_otp_send()`; chamada em `request_access` e no ramo "email existente" de `register_passwordless`
- `backend-core/tests/test_otp_spam_send_protection.py` — novo, cobre limite/janela/reset
- `backend-core/tests/test_otp_brute_force_protection.py` — `setUp` atualizado para rodar a nova migração

### Relatório da Fase 1 — o que mudou na prática

**Antes:** era possível chamar `request-access` (ou `register-passwordless` para um email já
cadastrado) repetidamente e a pessoa dona daquele email recebia um código novo por email a cada
chamada, sem limite nenhum — só travava depois de 5 tentativas *erradas* de digitar o código, o
que nunca acontece se quem está a abusar nem chega a tentar adivinhar o código.

**Agora:** o mesmo email só pode receber no máximo 3 códigos a cada 10 minutos. Na 4ª tentativa
dentro dessa janela, o pedido é recusado (erro "Muitas tentativas...") e nenhum email novo é
enviado — a mesma mensagem e o mesmo bloqueio de 15 minutos já usados para tentativas erradas de
código.

**Para validar:** Cenários C1, C2 e C3, abaixo (testes automatizados já cobrem os mesmos
cenários via pytest — ver checkbox acima).

---

## Ajustes Possíveis Pós-Implementação

- Limite por IP (fora de escopo — mesma limitação já documentada em `auth-email.md`: sem infra
  confiável de extração de IP atrás do proxy da Railway).
- Números exatos (`MAX_OTP_SENDS=3`, `OTP_SEND_WINDOW_MINUTES=10`) podem ser ajustados depois
  se se mostrarem restritivos demais para uso legítimo.
