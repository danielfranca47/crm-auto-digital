# Fila automática — turno do dia e avaliador em modo sombra

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** Fase 3 do plano aprovado em 04/10/2026 (`feat-fila-automatica.md`)

---

## Motivação

O que o turno da noite deixa numa branch `claude/<slug>` ainda não foi visto a
funcionar: na cloud não há browser nem os dados locais. Falta quem teste, quem
avalie e quem diga ao utilizador, em linguagem simples, se aquilo resolve a dor
inicial.

Comportamento desejado: com o PC ligado, o comando `/fila-validar` segue a
secção "Turno do dia" de
[`docs/ops/fila-automatica.md`](../ops/fila-automatica.md) — traz a branch,
corre os testes, valida os checks via browser, corre o script do que sobe
sempre e lança o avaliador. Nesta fase o avaliador está em **modo sombra**: dá
o veredito e o relatório, mas quem decide o merge é o utilizador, e cada caso
entra no placar.

## Área do sistema

- Comando local `/fila-validar` (conteúdo registado em `docs/ops/local-dev.md`,
  secção "Comandos slash locais").
- `docs/ops/fila-automatica.md`: secções "Turno do dia", "Avaliador", "Placar
  do modo sombra" e tabela "Estado atual".
- `docs/plans/modo-auto-melhorias-futuras.md`, item M1.

## Próximo passo

Este ficheiro ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)**. A
decidir nesse passo:

- Como lançar o avaliador como sessão separada, só de leitura, sem o histórico
  de quem testou.
- Confirmar que uma sessão sem ecrã lançada **a partir da pasta principal** não
  mostra o aviso "this workspace has not been trusted" — é a solução proposta
  para o M1 de `modo-auto-melhorias-futuras.md`; se se confirmar, o M1 sai de
  `docs/plans/`.
- Onde o relatório fica para o utilizador o ler sem abrir a branch.

**Dependências:** `feat-fila-turno-da-noite` (é quem produz as branches) e o
verificador de comandos (`feat-verificador-comandos-barreiras-duras`) em `main`.

`Autonomia: manual` porque mexe nas regras do próprio agente.
