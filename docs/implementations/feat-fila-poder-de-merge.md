# Fila automática — dar poder de merge ao avaliador

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** Fase 4 do plano aprovado em 04/10/2026 (contrato: `docs/ops/fila-automatica.md`)

---

## Motivação

Em modo sombra o utilizador ainda decide cada merge. O objetivo final é ele
entrar só para o que o agente não conseguiu validar.

Comportamento desejado: um item aprovado pelo avaliador, que não toque em
nenhuma categoria que sobe sempre e tenha todos os checks validados, é
graduado, mergeado em `main`, enviado (o que faz o deploy) e limpo — sem o
utilizador. Tudo o resto continua a parar e a gerar relatório.

## Condições para começar (todas)

- [ ] `feat-backup-volumes-producao` graduado — existe backup diário e
      reposição testada.
- [ ] Placar do modo sombra com **5 vereditos seguidos** a concordar com o
      utilizador (`docs/ops/fila-automatica.md`).
- [x] `main` protegida contra push forçado no GitHub (push normal continua
      igual) — feito em 04/10/2026 com o "sim" do utilizador: ruleset
      `main - sem push forcado` (id `24438757`), regra `non_fast_forward`.
- [ ] "Sim" explícito do utilizador para ligar o poder de merge.

## Área do sistema

- `docs/ops/fila-automatica.md`: linha "Poder de merge do avaliador" e secção
  "Turno do dia".
- Definições do repositório no GitHub.

## Próximo passo

Este ficheiro ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)**, e
só passa quando as condições acima estiverem cumpridas. A validar nessa
altura: um item aprovado chega a produção sozinho e a worktree some; um item
de categoria que sobe **não** é mergeado mesmo com veredito favorável.

`Autonomia: manual` porque mexe nas regras do próprio agente.
