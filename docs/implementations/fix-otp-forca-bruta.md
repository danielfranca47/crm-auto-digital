# Proteger o código de verificação (OTP) contra força bruta

**Branch:** `fix/otp-forca-bruta`
**Status:** Em andamento
**Sprint:** `docs/plans/plano-sprint-2026-09-12.md` (item P2)
**Origem:** `docs/plans/seguranca-melhorias-futuras.md` (M1)

---

## Motivação

O código de verificação (OTP) de 6 dígitos vale por 15 minutos e nada impedia que alguém
tentasse todas as combinações possíveis nesse intervalo — sem nenhum contador de tentativas
falhas nem limite por IP/conta. Achado da auditoria de segurança de 15/07/2026, confirmado
ainda sem correção na auditoria de 12/09/2026.

Comportamento anterior: `POST /auth/verify-otp` (`backend-core/app/api/auth.py:351-372`)
gerava o código com `secrets.randbelow(900_000) + 100_000` (1 milhão de combinações) e
validava contra o valor guardado sem nenhum contador de tentativas falhas nem rate limit.

Risco concreto: caminho direto para tomar conta de qualquer utilizador, sem precisar de
mais nenhuma falha.

---

## Diagnóstico (Passo 0)

**Já existe?** Não. `verify_otp_endpoint` só fazia `SELECT ... WHERE email AND code AND
used=0 AND expires_at > now`, sem contador nem lockout. Não há nenhuma infra de rate-limit
no `backend-core` (`slowapi`/middleware) nem extração de IP de cliente em nenhum lugar do
backend — um limite por IP exigiria construir do zero uma extração confiável atrás do proxy
da Railway (risco de confiar num header `X-Forwarded-For` spoofável sem essa infra já
validada). A proteção ficou **por conta (email)**, que é o que a tabela `auth_otps` já
indexa naturalmente e cobre o risco real (tomar conta do utilizador).

**Nota sobre o processo:** esta worktree já continha uma implementação não commitada de uma
sessão anterior (mesma ideia, execução ligeiramente diferente) quando este Plan Mode foi
concluído. Ao revisar esse código antes de documentar/commitar, encontrei uma falha real de
segurança nele — descrita abaixo em "Correção aplicada ao WIP encontrado" — corrigida antes
do commit da fase.

**Riscos e dependências:**
- Risco de UX: utilizador legítimo que erra o código 5x fica bloqueado 15 min — mitigado
  porque o bloqueio expira sozinho, sem ação manual.
- Fora de escopo (registado para triagem futura, ver "Ajustes Possíveis" abaixo): rate-limit
  no *envio* de OTP contra flood de emails é um vetor diferente (spam, não força bruta da
  verificação).

---

## Abordagem

```
POST /auth/request-access | /auth/register-passwordless | /auth/verify-otp
  → _check_otp_lockout(email): se auth_otp_lockouts.locked_until > now → 429
  → (request-access/register-passwordless) gera OTP novo normalmente
  → (verify-otp) valida código
      ├─ certo  → login normal + _clear_otp_failures(email) (limpa histórico de falhas)
      └─ errado → _register_otp_failure(email)
                    ├─ ainda abaixo do limite → grava failed_attempts++, 400 (igual a antes)
                    └─ atinge MAX_OTP_ATTEMPTS → zera contador + grava locked_until = now+15min, 400
```

O contador de falhas (`failed_attempts`) vive na tabela `auth_otp_lockouts` (por email),
**não** na linha do OTP em `auth_otps` — motivo na próxima seção.

---

## Plano de Implementação (fase única)

### Fase 1 — Contador de falhas + lockout por email

**Objetivo:** bloquear `verify-otp` (e o envio de novos OTPs) por 15 min após 5 tentativas
erradas seguidas, por email.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/db.py` | Nova função `ensure_auth_otp_lockouts_table()` — cria `auth_otp_lockouts (email TEXT PRIMARY KEY, failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until DATETIME)` |
| `backend-core/app/main.py` | Chama `ensure_auth_otp_lockouts_table()` no `on_startup`, ao lado de `ensure_auth_otps_table()` |
| `backend-core/app/api/auth.py` | Constantes `MAX_OTP_ATTEMPTS=5`, `OTP_LOCKOUT_MINUTES=15`; helpers `_check_otp_lockout`, `_register_otp_failure`, `_clear_otp_failures`; chamados em `request_access`, `register_passwordless` e `verify_otp_endpoint` |
| `backend-core/tests/test_otp_brute_force_protection.py` | Suite unitária (sqlite em memória) cobrindo os 6 cenários abaixo |

**Por que os 3 endpoints e não só `verify-otp`:** bloquear só a verificação deixaria o
atacante continuar recebendo OTPs novos durante o bloqueio (spam ao dono real da conta, e
sem necessidade real). Bloquear os 3 fecha essa sobra sem custo adicional.

**Correção aplicada ao WIP encontrado — por que o contador não pode viver em `auth_otps`:**
a primeira versão (da sessão anterior) guardava `attempts` como coluna da própria linha do
OTP. Como `_generate_and_store_otp` insere uma linha nova a cada `request-access`/
`register-passwordless`, um atacante conseguia: errar o código `MAX_OTP_ATTEMPTS - 1` vezes
(nunca atingindo o limite), pedir um OTP novo (ainda não bloqueado, gera linha nova com
`attempts=0`), e repetir indefinidamente — o lockout nunca era gravado. Corrigido movendo o
contador para `auth_otp_lockouts`, indexado só por email, que sobrevive a qualquer novo
pedido de OTP. Coberto pelo teste
`test_regenerating_otp_does_not_reset_failed_attempts` (reproduz o cenário do bypass e
confirma que agora bloqueia).

#### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a registrar após o commit)_ | Lockout por email em request-access/register-passwordless/verify-otp |

---

## Checks de Validação

Sem UI web para este fluxo (OTP é consumido só pelo `agent-local` desktop) — validação via
suite automatizada (`pytest`), que já exercita os cenários reais end-to-end contra os
endpoints (não são só testes de unidade isolados — chamam `request_access`/
`verify_otp_endpoint` diretamente com uma sessão SQLAlchemy real, sqlite em memória).

### Cenário C1 — Tentativas erradas até o limite
- [x] Gerar OTP, errar `MAX_OTP_ATTEMPTS` vezes seguidas
- [x] Confirmar 429 na tentativa seguinte (`verify-otp` e `request-access`)
- **Validado em:** 13/09/2026 — `test_wrong_code_reaching_limit_locks_account`, `pytest` verde

### Cenário C2 — Bloqueio expira sozinho
- [x] Simular `locked_until` no passado
- [x] Confirmar que uma nova tentativa (com o código certo) volta a funcionar
- **Validado em:** 13/09/2026 — `test_lockout_expires_after_window`, `pytest` verde

### Cenário C3 — Sucesso limpa o histórico de falhas
- [x] Errar algumas vezes (abaixo do limite), depois acertar
- [x] Confirmar que `auth_otp_lockouts` não tem mais linha para o email
- **Validado em:** 13/09/2026 — `test_successful_login_clears_failure_history`, `pytest` verde

### Cenário C4 — Fluxo normal sem impacto
- [x] `request-access` → `verify-otp` com código certo na 1ª tentativa
- **Validado em:** 13/09/2026 — `test_correct_code_succeeds`, `pytest` verde

### Cenário C5 — Regeneração de OTP não reseta o contador (regressão do bug encontrado)
- [x] Errar `MAX_OTP_ATTEMPTS - 1` vezes, pedir OTP novo, errar mais 1 vez → bloqueia
- **Validado em:** 13/09/2026 — `test_regenerating_otp_does_not_reset_failed_attempts`, `pytest` verde

### Cenário C6 — Abaixo do limite não bloqueia
- [x] Errar `MAX_OTP_ATTEMPTS - 1` vezes, confirmar que `request-access` ainda funciona
- **Validado em:** 13/09/2026 — `test_wrong_code_below_limit_does_not_lock`, `pytest` verde

---

## Ajustes Possíveis Pós-Implementação

- Rate-limit no *envio* de OTP (`request-access`/`register-passwordless`) contra flood de
  emails para uma vítima — vetor diferente (spam), fora do escopo desta correção (que mira
  força bruta da verificação). Sugestão para triagem na graduação: migrar para
  `docs/plans/` se considerado não-urgente.
- Limite por IP além de por conta — hoje não implementado por falta de infra confiável de
  extração de IP atrás do proxy da Railway (ver Diagnóstico). Se no futuro essa infra
  existir para outro propósito, reavaliar.
