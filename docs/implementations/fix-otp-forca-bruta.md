# Proteger o código de verificação (OTP) contra força bruta

**Status:** Aguardando Plan Mode
**Sprint:** `docs/plans/plano-sprint-2026-09-12.md` (item P2)
**Origem:** `docs/plans/seguranca-melhorias-futuras.md` (M1)

---

## Motivação

O código de verificação (OTP) de 6 dígitos vale por 15 minutos e nada impede que alguém
tente todas as combinações possíveis nesse intervalo — sem nenhum contador de tentativas
falhas nem limite por IP/conta. Achado da auditoria de segurança de 15/07/2026, confirmado
ainda sem correção na auditoria de 12/09/2026.

Comportamento actual: `POST /auth/verify-otp` (`backend-core/app/api/auth.py:351-372`)
gera o código com `secrets.randbelow(900_000) + 100_000` (1 milhão de combinações) e
valida contra o valor guardado sem nenhum contador de tentativas falhas nem rate limit.

Comportamento desejado: depois de um número razoável de tentativas erradas, novas
tentativas ficam bloqueadas (por conta e/ou por IP) pelo tempo que fizer sentido — um
script não consegue mais testar todas as combinações dentro da janela de validade do
código.

Risco concreto: caminho direto para tomar conta de qualquer utilizador, sem precisar de
mais nenhuma falha.

Nota: não há decisão de produto pendente aqui — o limite exacto de tentativas e o tempo
de bloqueio ficam a critério do Plan Mode desta implementação (detalhe técnico).

---

## Área do sistema

`backend-core` — autenticação (`app/api/auth.py`).

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida, responder as 3 perguntas do Passo 0, e só depois
de aprovado seguir para a criação de branch + worktree (Passo 1).
