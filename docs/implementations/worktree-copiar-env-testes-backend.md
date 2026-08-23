# Documentar cópia manual de `.env` em worktrees novas para rodar testes de backend

**Branch:** (ainda não criada — nasce após Plan Mode aprovado)
**Status:** Aguardando Plan Mode

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

1. **Sem documentação do passo manual:** não há hoje nenhuma nota em
   `docs/ops/` (ou em `CLAUDE.md`) avisando que uma worktree nova de
   `backend-executors` (e possivelmente `backend-core`/`backend-crm`,
   a confirmar em Plan Mode) precisa copiar `.env` manualmente antes de rodar
   a suíte de testes.

---

## Abordagem

<A definir em Plan Mode — provavelmente uma nota curta em `docs/ops/`
(criar seção ou arquivo dedicado, ver estrutura existente de `docs/ops/`)
mais uma referência a partir de `CLAUDE.md`, seção "Estratégia de branch por
implementação". Confirmar em Plan Mode se o mesmo problema afeta
`backend-core`/`backend-crm`/frontends, ou é específico de
`backend-executors`.>

---

## Plano de Implementação

<A definir em Plan Mode.>

---

## Checks de Validação

<A definir em Plan Mode.>

---

## Ajustes Possíveis Pós-Implementação

<A definir após implementação.>
