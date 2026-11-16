# Corrigir código sem prejudicar as outras contas

O sistema é multi-empresa e multi-agente. Uma correção pedida por uma conta corre no motor de
**todas**. Cada correção desta missão cumpre as 4 regras abaixo e chega ao merge com as 5 provas.

## Antes de escrever código

1. **Provar que é código** com a triagem (`diagnosticar-agente/references/triagem.md`). Tem de haver
   um turno concreto (`.json` da bancada) em que a IA recebe a informação certa e o sistema estraga o
   resultado, ou 3 formulações de configuração falhadas e registadas no README.
2. **Procurar se já existe**: `docs/implementations/`, `docs/plans/`, `git worktree list` e
   `git log --oneline -30`. Se outra conversa já está a mexer no mesmo código, a correção junta-se a
   essa ou espera por ela. Nunca correm duas em paralelo sobre a mesma função.
3. **Ficheiro de implementação** (`fix-…` ou `feat-…`) com `Status: Aguardando Plan Mode`,
   `Autonomia: manual`, a evidência medida (cenário, turno, taxa) e os checks, incluindo:
   - `C1` (produção): bateria `--prod` desta conta com 0 ocorrências;
   - `R1` (regressão): as outras contas sem diferença (ver abaixo).

## As 4 regras

1. **Genérica, nunca por cliente.** Nada de `if user_id == …`, de nome de empresa, de nicho ou de
   texto do cliente escrito no código. Se só esta conta precisa do comportamento, ele vem de um campo
   do AI Profile.
2. **O comportamento novo é opt-in quando muda o que outras contas fazem hoje.** Fica atrás de um
   campo novo do AI Profile cujo valor por omissão **reproduz o comportamento atual**. Ao criar o
   campo:
   - migração idempotente (`ensure_column`);
   - o ecrã do AI Profile, se o cliente o tiver de ver ou mudar;
   - `docs/architecture/admin-agents-contract.md` e `frontend-admin/src/pages/AdminAgents.tsx`
     (regra do CLAUDE.md).
   A exceção é um **bug verdadeiro para todos**: o sistema faz algo errado em qualquer conta (ex.:
   comparar horários como texto). Aí a correção vale para todos, e o ficheiro de implementação
   explica porque é bug em qualquer conta.
3. **Paridade Playground ↔ WhatsApp.** Um campo novo que afeta a IA entra por
   `enrich_context_bundle()` em `services/ai_orchestrator/orchestrator.py`, nunca num só builder
   (`docs/architecture/playground-parity.md`). Sem isto, o Playground passa e o WhatsApp real
   falha.
4. **Instruções da IA (prompts de Mãe/Filha)**: antes de mexer, lê
   `docs/architecture/prompt-engineering-principles.md` e `docs/prompts_llms.md`. Um texto novo num
   prompt partilhado afeta todas as contas desse agente. Prefere um bloco condicional, ligado ao campo
   ou à fase, a mudar o texto base.

## As 5 provas antes do merge

**No modo colaborador** (sem bancada local), as provas 2 e 3 fazem-se como está em
`modo-colaborador.md`, secção 5: opt-in por omissão, 0 falhas novas nos testes, teste novo, validação
em produção depois do deploy e revert imediato se algo piorar.

| # | Prova | Como |
|---|---|---|
| 1 | Testes automáticos do serviço tocado passam | `python -m pytest tests/ -q` no backend tocado (ver `docs/ops/local-dev.md`; numa worktree nova, copiar `.env` antes) |
| 2 | O problema desta conta desapareceu | bancada com o código da worktree: `preparar_bancada.py <slug> --codigo-de <branch>`; bateria dos cenários que o expõem, com 3 repetições dos de conteúdo |
| 3 | **As outras contas não mudaram** | bateria de regressão (abaixo), comparada com `main` |
| 4 | A categoria foi verificada | `python scripts/fila/categorias_que_sobem.py`: se sobe (instruções da IA, envio real, base de dados, pagamento), o merge é feito só com o "sim" explícito do utilizador |
| 5 | Os docs refletem o código | `docs/architecture/` das áreas tocadas atualizado antes do commit final |

## Bateria de regressão (prova 3)

Objetivo: mostrar que, **com o valor por omissão**, as outras contas se comportam como em `main`.

1. **Contas a cobrir:** pelo menos uma por cada tipo de agente (`agent_mode`) que passa no código
   tocado. Usa primeiro as bancadas que já existem em `.claude/agentes/*/` (cada uma tem
   `cenarios.json` e um histórico de baterias). Se faltar um tipo, usa a conta de teste local
   (`docs/implementations/_conta-teste-local.md`) com o preset desse agente e os cenários da
   biblioteca da skill `agente-0X-…`.
2. **Duas corridas iguais:** uma com o código de `main` e outra com o da worktree
   (`--codigo-de`), com os mesmos cenários e rótulos `REG-main` e `REG-<branch>`, e
   `simular.py --resumo` de cada.
3. **Comparar** rotas, categoria final, guardrails aplicados, marcações gravadas e falhas da IA.
   Uma diferença que não seja explicada pela variação normal da IA (confirma repetindo 3 vezes)
   bloqueia o merge até ser explicada ou corrigida.
4. **Nunca correr `--prod` em contas de outros clientes** sem o "sim" do utilizador, porque cria
   leads de teste nessas contas. A regressão faz-se na bancada local.
5. Regista o resultado no ficheiro de implementação (check `R1`) e no README da bancada.

## Depois do merge

- Confirma que o deploy chegou: `simular.py <pasta> --prod-acao versao` tem de mostrar o commit
  publicado no `crm`, no `core` e no `executors`. O `worker backend-executors` sai do mesmo commit; no
  modo dono também se pode procurar o código dentro do container.
- Se nasceu um campo novo, liga-o **só na conta de trabalho** (`--aplicar-prod` no modo colaborador,
  `aplicar_producao.sh` no modo dono), sempre com backup.
- Corre a bateria `--prod` completa desta conta e valida o `C1`.
