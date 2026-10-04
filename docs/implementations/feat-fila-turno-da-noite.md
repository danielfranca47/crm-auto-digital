# Fila automática — turno da noite (rotina na cloud)

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** Fase 2 do plano aprovado em 04/10/2026 (`feat-fila-automatica.md`)

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

**Dependência:** a correção dos testes do backend-crm
(`fix-testes-backend-crm-a-falhar`) tem de estar em `main` — sem isso a noite
não distingue um teste que ela partiu de um que já falhava.

`Autonomia: manual` porque mexe nas regras do próprio agente.
