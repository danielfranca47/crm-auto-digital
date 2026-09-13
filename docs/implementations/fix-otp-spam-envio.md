# Rate-limit no envio de OTP (anti-spam)

**Branch:** `fix/otp-spam-envio`
**Status:** Em andamento

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
- [ ] Chamar `POST /auth/request-access` 3x seguidas para o mesmo email existente → todas succeed (200)
- [ ] 4ª chamada dentro de 10 min → 429 "Muitas tentativas..."
- [ ] Confirmar (via log/DB) que nenhum OTP novo foi inserido/enviado nessa 4ª chamada

### Cenário C2 — Janela expira
- [ ] Após o bloqueio, esperar (ou simular) o `locked_until` expirar → nova chamada volta a funcionar

### Cenário C3 — `register-passwordless` (email existente) também limitado
- [ ] Mesmo teste do C1 usando `POST /auth/register-passwordless` para um email já cadastrado

### Testes automatizados (pytest)
- [ ] `test_otp_spam_send_protection.py` passa localmente, junto com `test_otp_brute_force_protection.py` (regressão)

---

## Ajustes Possíveis Pós-Implementação

- Limite por IP (fora de escopo — mesma limitação já documentada em `auth-email.md`: sem infra
  confiável de extração de IP atrás do proxy da Railway).
- Números exatos (`MAX_OTP_SENDS=3`, `OTP_SEND_WINDOW_MINUTES=10`) podem ser ajustados depois
  se se mostrarem restritivos demais para uso legítimo.
