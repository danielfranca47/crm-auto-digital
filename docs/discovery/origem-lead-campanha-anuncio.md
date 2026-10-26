# Como saber de qual campanha/anúncio/landing page veio cada lead que chega pelo WhatsApp?

> Estrutura em `_template-investigacao.md`. Processo em `_guia-discovery.md`.

---

**Status:** Levantado
**Origem:** `levantamentos/2026-10-26-escuta-vendas-trafego-pago.md` — observação 2
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (provável: prova de resultado para clientes que anunciam)
**Área do sistema:** backend-crm (leads, collab_monitor, webhooks)

---

## Pergunta a responder (L)

Quando um cliente clica no anúncio, cai na landing page e abre o WhatsApp, o
CRM consegue registar a origem (campanha, página, palavra-chave) desse lead,
para depois medir custo por venda por campanha?

## O que já se sabe (L)

**Confirmado no código:**
- O lead de monitor nasce com `origin='whatsapp_inbound'` fixo, sem campanha/página: `backend-crm/services/collab_monitor/monitor_inbound_handler.py:101-103`.
- O único ponto que guarda UTMs hoje é o formulário público do site: `backend-crm/routes/public.py:27-31` e `:102-111` (só no corpo do aviso ao admin).
- Não há campo `gclid` em nenhum lugar do `backend-crm` (busca por `gclid|utm_|offline conversion` em 26/10/2026).

**Hipóteses a verificar:**
- As landing pages da cliente já mandam um texto pré-preenchido diferente por página no link `wa.me` — a primeira mensagem do lead poderia identificar a origem sem mudar nada no site.
- Alternativa mais precisa: a landing page gerar um código curto por clique (ligado ao `gclid`) dentro do texto do WhatsApp.
