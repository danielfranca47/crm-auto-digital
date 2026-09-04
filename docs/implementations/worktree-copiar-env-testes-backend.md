# Documentar cópia manual de `.env` em worktrees novas para rodar testes de backend

**Branch:** `feat/worktree-copiar-env-testes-backend`
**Status:** Todos os cenários validados (04/09/2026)

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-sales-flow-recepcao-p0-nao-dispara.md` (achado lateral, confirmado ao
vivo em 23/08/2026, durante a primeira execução da suíte de testes do
`backend-executors` numa worktree nova).

`EnterWorktree` cria a worktree a partir de `origin/<branch base>`, mas
`backend-executors/.env` é gitignored e por isso não é copiado automaticamente
— a worktree nasce só com `.env.example`. Sem o `.env` real, 2 testes
pré-existentes falhavam (`test_p0_trigger_already_fired_advances_normally`,
`test_no_sequential_trigger_in_p0_behaves_like_baseline`) — não por bug de
produto, mas por falta de configuração local. Copiar o `.env` da pasta
principal para a worktree resolveu os dois.

`.venv` também não é herdado (mesmo motivo: gitignored). Nesta sessão os
testes rodaram com o Python global do sistema (pacotes já presentes;
`pytest` foi instalado nele durante a sessão) — outra worktree pode precisar
criar seu próprio `.venv` se depender de versões pinadas específicas do
`requirements.txt`.

**Risco se não documentado:** alguém (humano ou Claude, numa sessão futura)
pode diagnosticar "bug" ou "regressão" numa worktree nova quando na verdade
falta só esse passo manual de configuração local.

---

## Problemas Identificados (estado anterior)

1. **Sem documentação do passo manual:** não havia nenhuma nota em
   `docs/ops/` (ou em `CLAUDE.md`) avisando que uma worktree nova precisa
   copiar `.env` manualmente antes de rodar a suíte de testes.
2. **Escopo confirmado nesta implementação:** o mesmo problema afeta os 3
   backends, não só `backend-executors` — `backend-core/.env`,
   `backend-crm/.env` (e `backend-crm/.env.local`) e `backend-executors/.env`
   são todos gitignored, e os 3 têm pasta `tests/`. Confirmado via
   `git check-ignore`.

---

## Abordagem

Documentação pura, sem mudança de código:

1. **`docs/ops/local-dev.md`** (guia de setup local já existente) — nova
   seção "Worktree nova precisa de `.env` copiado manualmente antes de testar
   backend", logo após a seção existente sobre `.env.local`. Cobre: por que
   acontece, quais backends são afetados, o passo manual (copiar `.env`), a
   nota sobre `.venv` (não herdado pelo mesmo motivo — cada `venv`/`.venv` tem
   seu próprio `.gitignore` interno com `*`), e o sintoma para reconhecer o
   problema (testes falhando por config/conexão, não por lógica de negócio,
   logo na primeira execução).
2. **`CLAUDE.md`**, seção "Estratégia de branch por implementação" →
   "Criação" — uma linha apontando para a nota acima.

---

## Plano de Implementação

### Fase 1 — Documentação

**Objetivo:** registrar o passo manual de cópia de `.env`/`.venv` em worktrees
novas, para os 3 backends, no lugar onde já se documenta setup local.

| Arquivo | O que muda |
|---|---|
| `docs/ops/local-dev.md` | Nova seção sobre cópia manual de `.env`/`.venv` em worktrees novas |
| `CLAUDE.md` | Pointer de uma linha na seção "Estratégia de branch por implementação" → "Criação" |
| `docs/implementations/worktree-copiar-env-testes-backend.md` | Preenchimento deste arquivo (era só esqueleto) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `56c08b5` | Documentação da cópia manual de `.env`/`.venv` em worktrees novas |

**Detalhes do commit `56c08b5`:**
- `docs/ops/local-dev.md` — nova seção "Worktree nova precisa de `.env` copiado manualmente antes de testar backend"
- `CLAUDE.md` — pointer de uma linha na seção "Criação"
- `docs/implementations/worktree-copiar-env-testes-backend.md` — preenchimento do arquivo (diagnóstico, abordagem, plano)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não havia nenhum aviso escrito sobre o `.env` não ser copiado
automaticamente para uma worktree nova — quem se deparasse com testes de
backend falhando numa worktree recém-criada não tinha como saber, sem
investigar do zero, que era só falta desse arquivo local.

**Agora:** `docs/ops/local-dev.md` explica o porquê (arquivo gitignored, não
herdado por `EnterWorktree`), quais backends são afetados e o passo manual
de cópia; `CLAUDE.md` aponta para essa nota no ponto onde a worktree é
criada.

**Para validar:** Cenário C1, abaixo — já validado retroativamente, pois o
fato documentado foi comprovado ao vivo antes desta implementação existir.

---

## Checks de Validação

### Cenário C1 — Nota é suficiente para evitar o falso-diagnóstico
- [x] O fato documentado (2 testes falhando por `.env` ausente numa worktree
      nova, resolvido copiando o arquivo) já foi confirmado ao vivo em
      23/08/2026, durante a implementação de
      `fix-sales-flow-recepcao-p0-nao-dispara.md`.
- **Validado em:** 04/09/2026 — validação retroativa: a causa raiz e a
  correção já estavam comprovadas por essa execução real; esta implementação
  apenas documenta o que já foi observado, não introduz comportamento novo a
  testar. Revisão de texto confirma que as duas seções (`local-dev.md` e
  `CLAUDE.md`) são autossuficientes para alguém sem contexto seguir o passo.

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado nesta iteração.
