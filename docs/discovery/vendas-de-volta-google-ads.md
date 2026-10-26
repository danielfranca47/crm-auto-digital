# Vale a pena devolver as vendas (e o valor) do CRM para o Google Ads como conversão offline?

> Estrutura em `_template-investigacao.md`. Processo em `_guia-discovery.md`.

---

**Status:** Levantado
**Origem:** `levantamentos/2026-10-26-escuta-vendas-trafego-pago.md` — observações 3 e 4
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (provável); M5 se virar recurso de plano
**Área do sistema:** backend-crm (leads, novo integrador) / possível backend-executors

---

## Pergunta a responder (L)

Se o CRM souber quais conversas viraram sessão paga (e por quanto), faz sentido
enviar isso de volta para o Google Ads, para a campanha otimizar por venda e
não só por clique no WhatsApp? E o mínimo viável é só registar o valor no CRM?

## O que já se sabe (L)

**Confirmado no código:**
- Não existe integração com Google Ads no `backend-crm` (busca por `google.?ads|offline.?conversion|gclid` em 26/10/2026).
- Não há valor de venda por lead; o único campo de valor é agregado: `metricas.valor_vendas` em `backend-crm/database.py:1172`.
- Já existe noção de estágio "cliente" (`client-list`) que o classificador do monitor pode atribuir.

**Hipóteses a verificar:**
- O Google Ads aceita conversões offline identificadas por telefone com hash (conversões otimizadas para leads), o que dispensaria `gclid` — a confirmar na documentação oficial e nos volumes mínimos.
- Para uma conta pequena (dezenas de vendas/mês) o ganho de otimizar por venda pode não compensar; medir CPA por venda num relatório já resolveria a dor imediata.
- Depende de `origem-lead-campanha-anuncio` e de `escuta-whatsapp-dono-terapeuta`.
