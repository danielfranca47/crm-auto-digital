# Fila automática — arranque sozinho de dia e painel

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** Fase 5 do plano aprovado em 04/10/2026 (contrato: `docs/ops/fila-automatica.md`)

---

## Motivação

Com o turno do dia a funcionar, o utilizador ainda tem de escrever
`/fila-validar` e de abrir cada branch para saber o que aconteceu.

Comportamento desejado:

- o turno do dia arranca sozinho quando o PC está ligado;
- `/statusdev` mostra também as branches `claude/*`: o que foi feito de noite,
  o que entrou em produção, e o que espera a decisão do utilizador, com o
  relatório em linguagem simples.

## Área do sistema

- Agendamento local (rotina ligada ao PC, como a que a conta já tem).
- Comando local `/statusdev` (conteúdo registado em `docs/ops/local-dev.md`).
- `docs/ops/fila-automatica.md`, tabela "Estado atual".

## Próximo passo

Este ficheiro ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)**. A
decidir nesse passo: a que horas arranca, o que faz se o PC estiver desligado
a essa hora, e se o utilizador quer ser avisado quando há algo à espera dele.

**Dependência:** `feat-fila-turno-do-dia-avaliador`.

`Autonomia: manual` porque mexe nas regras do próprio agente.
