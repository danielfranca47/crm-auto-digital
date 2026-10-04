# Fila automática — turno da noite (rotina na cloud)

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** Fase 2 do plano aprovado em 04/10/2026 (contrato: `docs/ops/fila-automatica.md`)

---

## Motivação

As regras da fila automática já estão escritas em
[`docs/ops/fila-automatica.md`](../ops/fila-automatica.md), mas nada corre
sozinho: a fila continua parada até o utilizador dar o "start".

Comportamento desejado: todas as noites, com o PC do utilizador desligado, uma
rotina na cloud pega **um** item elegível, segue a secção "Turno da noite" e
deixa o resultado numa branch `claude/<slug>` — nunca em `main`.

## Área do sistema

- Uma rotina na cloud do Claude Code ligada ao repositório
  `danielfranca47/crm-auto-digital` (configuração externa — criada só com o
  "sim" do utilizador no momento).
- `docs/ops/fila-automatica.md`, secção "Turno da noite" e tabela "Estado atual".

## Próximo passo

Este ficheiro ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)**. A
decidir nesse passo:

- Como o ambiente da rotina instala o que os testes precisam (`pip`, `npm`).
- Confirmar que a rotina só consegue fazer push para `claude/*`.
- Primeiro disparo **à mão**, sobre um item pequeno que o utilizador conheça,
  antes de ligar o horário.
- Medir quanto do limite do plano Pro uma noite consome, e escolher a hora.
- Antes de ligar o horário: os itens que já estão a ser trabalhados à mão
  noutras worktrees mas que em `main` ainda dizem "Aguardando Plan Mode" sem
  `**Autonomia:** manual` (em 04/10/2026: `fix-disponibilidade-campo-duplo-sentido`
  e `otimizar-imagem-hero-lara-desktop`) têm de receber essa linha em `main`,
  senão a noite pega-os em duplicado.
- Aproveitar o diagnóstico para a verificação M3 de
  [`fila-automatica-melhorias-futuras.md`](../plans/fila-automatica-melhorias-futuras.md)
  (um push só de documentação reinicia produção?).

**Dependência:** a correção dos testes do backend-crm — **cumprida**, está em
`main` desde 04/10/2026 (`python -m pytest tests/ -q` em `backend-crm`: tudo
aprovado). Sem isso a noite não distinguiria um teste que ela partiu de um que
já falhava.

`Autonomia: manual` porque mexe nas regras do próprio agente.
