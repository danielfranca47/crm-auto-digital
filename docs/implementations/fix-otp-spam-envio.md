# Rate-limit no envio de OTP (anti-spam)

**Status:** Aguardando Plan Mode

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

Nota: o limite exacto (quantos OTPs por quanto tempo) fica a critério do Plan Mode desta
implementação (detalhe técnico).

---

## Área do sistema

`backend-core` — autenticação (`app/api/auth.py`, endpoints `request-access` e
`register-passwordless`). Provavelmente reaproveita ou estende a tabela `auth_otp_lockouts`
introduzida em `fix-otp-forca-bruta`.

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o contexto
acima como ponto de partida, responder as 3 perguntas do Passo 0, e só depois de aprovado
seguir para a criação de branch + worktree (Passo 1).
