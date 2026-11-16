---
name: agente-03-assistente-comercial
description: Agente 03 · Assistente Comercial — critérios de sucesso e cenários de teste para diagnosticar o agente de uma conta que marca sessões com um profissional (aquecimento, agendamento, confirmação, remarcação, lembretes, follow-up pós-sessão). Chamada pela diagnosticar-agente, ou quando se pede para testar o agendamento ou o pós-marcação de um Agente 03.
---

# Agente 03 · Híbrido — Assistente Comercial com Agendamento Inteligente

Parte do fluxo da skill `diagnosticar-agente` (regras fixas, bancada, triagem e entregas estão lá).

**Factos do sistema** — preset, `appointment_mode`, o que o código decide na agenda, lembretes, prometido vs.
código, limites medidos, ficheiros:
[`docs/architecture/agentes/agente-03-assistente-comercial.md`](../../../docs/architecture/agentes/agente-03-assistente-comercial.md).
Lê-o antes de escrever critérios ou instruções; a secção "Limites medidos" diz o que já se sabe que é código.

## Critérios-padrão (juntar aos da conta; ⚠ = crítico)

- Apresenta-se como assistente do profissional; usa o que o lead já disse.
- Quem não se encaixa recebe uma indicação alternativa.
- Aprofunda a dor e faz o aquecimento (prova social, como é a sessão) antes de marcar.
- ⚠ Data e hora gravadas = as aceites pelo cliente; ⚠ grava a **última** proposta aceite.
- ⚠ Nunca diz "marcado" sem `appointment_event` gravado.
- ⚠ Dentro do horário do profissional (a sessão inteira cabe) e sem sobreposição.
- Aceita um horário livre pedido, sem inventar escassez (com `confirm_exact`).
- Pergunta o que falta (tipo, duração, nome) antes de resumir.
- Pós-marcação: responde a preço e morada sem reabrir a venda; remarca só depois de o cliente aceitar.

## Cenários (adaptar à conta)

| Cenário | Persona | Esperado |
|---|---|---|
| `p-<real>` | uma por conversa de referência | o roteiro observado |
| `p-pedido-direto` | serviço + dia + hora numa mensagem | aceita se livre e grava |
| `p-aceita-2a` | recusa a 1.ª proposta, aceita a 2.ª | grava a 2.ª |
| `p-fora-horario` | domingo, antes da abertura, depois do fecho | motivo verdadeiro + alternativa válida |
| `p-ultimo-horario` | última hora com duração que passa o fecho | propõe a hora que cabe |
| `p-ocupado` (setup: evento ocupado) | horário ocupado e depois o seguinte | recusa o 1.º; aceita sessões seguidas |
| `p-sem-tipo` | pedido ambíguo | pergunta qual antes de marcar |
| `p-varias-perguntas` | 3 perguntas numa mensagem | responde a todas e avança |
| `p-relativo` | "amanhã", "sexta" | data certa |
| `pos-marcacao` | marca; pergunta preço; remarca; "já cheguei" | respostas certas |
| `p-saudacao` | de manhã e à noite | cumprimento do período certo |
| `p-out-pessoal` | outbound, desconfiado | tom pessoal, desperta a dor sem vender |

O `--resumo` assinala o dia divergente: escrito, proposto ou pedido face ao gravado.

## Exemplo trabalhado

`.claude/agentes/sensi-vitae/README.md` (fora do git): espaço de massagens, 2 terapeutas, 13 versões de
configuração e 7 baterias em produção. Referência para o nível de detalhe, não regra para outras contas.
