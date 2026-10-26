# Levantamento — Escuta do WhatsApp para medir vendas de tráfego pago

**Data:** 2026-10-26
**Origem:** conversa do utilizador (Daniel) com o Claude durante a gestão de
tráfego de uma cliente terapeuta (massagem holística em Amsterdã, Google Ads).

## Contexto (dados anonimizados)

- A cliente roda Google Ads (Search) com meta de CPA de €4 por **contato de
  mensagem** — a conversão registada é o clique no link `wa.me` das landing
  pages ("Solicitar cotação").
- O CPA por **venda** (sessão marcada) não é conhecido: as conversas acontecem
  no WhatsApp da própria terapeuta, que atende sozinha, e nada volta para o
  Google Ads nem fica registado.

## Pedido do utilizador (resumo fiel)

> "A conversão por venda ainda não conseguimos apurar este dado, precisaríamos
> de um CRM de captura dessas informações para a cliente. Estou querendo
> disponibilizar meu CRM, mas ainda falta colocar essa funcionalidade só de
> escuta lá, ainda não sei se tem."

## Observações levantadas na conversa

1. Já existe o Monitoramento de colaborador (instância WhatsApp `role=monitor`,
   só leitura, cria leads e classifica estágio).
2. Não há ligação do lead à campanha/landing page de origem.
3. Não há envio de vendas de volta para o Google Ads.
4. O valor da venda não é registado por lead.
5. Cuidados: conexão via UazAPI (não oficial) no número principal da
   terapeuta; conversas de clientes passam pela OpenAI (classificação,
   transcrição) — GDPR (cliente na UE).
