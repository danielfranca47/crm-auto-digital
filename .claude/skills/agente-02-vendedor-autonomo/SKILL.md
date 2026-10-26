---
name: agente-02-vendedor-autonomo
description: Agente 02 · Vendedor Autônomo — critérios de sucesso e cenários de teste para diagnosticar o agente de uma conta que vende pelo bot (pitch, objeções, link de pagamento, carrinho abandonado). Chamada pela diagnosticar-agente, ou quando se pede para testar o pitch, o link de pagamento ou a recuperação de carrinho de um Agente 02.
---

# Agente 02 · Direto — Vendedor Autônomo

Parte do fluxo da skill `diagnosticar-agente` (regras fixas, bancada, triagem e entregas estão lá).

**Factos do sistema** — preset, guardrail de preço e intenção, bot ativo no fecho, arranque do carrinho
abandonado, gateways, prometido vs. código, ficheiros:
[`docs/architecture/agentes/agente-02-vendedor-autonomo.md`](../../../docs/architecture/agentes/agente-02-vendedor-autonomo.md).
Lê-o antes de escrever critérios ou instruções.

## Critérios-padrão (juntar aos da conta; ⚠ = crítico)

- No máximo 2 perguntas de fit; ⚠ quem já quer comprar não fica preso na qualificação.
- Pitch: solução → benefícios → prova social → oferta, com os factos da conta.
- ⚠ Preço, âncora e garantia iguais aos da conta; nenhum desconto inventado.
- Um turno, uma ação: confirmar **ou** enviar o link — nunca "posso enviar o link?" com o link no mesmo turno.
- ⚠ O link enviado é o URL real da conta (o `--resumo` conta links; confirma o URL na transcrição).
- Objeção respondida com o argumento da conta e volta a avançar, sem repetir o pitch inteiro.
- ⚠ Depois de "já paguei", não volta a vender.
- Recusa clara → encerra com educação.
- Outbound: o pitch abre espelhando a dor confirmada.

## Cenários (adaptar à conta)

| Cenário | Persona | Esperado |
|---|---|---|
| `p-<real>` | uma por conversa de referência | o roteiro observado |
| `p-compra-rapida` | "quero comprar, como pago?" logo no início | link na hora |
| `p-objecao-preco` | acha caro, pede desconto | âncora, garantia ou parcelas da conta |
| `p-objecao-confianca` | "é seguro?", "tem garantia?" | factos da conta e retoma a oferta |
| `p-vou-pensar` | indeciso | resposta de indecisão; recuperação só depois do link |
| `p-duvida-produto` | pergunta técnica a meio | Base de Conhecimento e retoma |
| `p-pagou` | "já paguei" | não reenvia a oferta |
| `p-recusa` | "não tenho interesse" | encerra |
| `p-out-dor` / `p-out-sem-dor` | outbound | pitch espelha a dor / encerra |

Carrinho abandonado: enviar o link e avançar o tempo com `POST /api/playground/leads/{lead_id}/skip-wait`.

## Atenção neste agente

- O carrinho abandonado arranca com **qualquer** link enviado pelo bot (não só o de pagamento): um link do
  site num cenário de dúvidas também o dispara.
- Os prompts do sistema contradizem-se sobre placeholders no link; se aparecer `[link]` em vez do URL, é
  código, não configuração.

## Exemplo trabalhado

Ainda não há nenhum. Regista aqui a pasta da bancada do primeiro diagnóstico.
