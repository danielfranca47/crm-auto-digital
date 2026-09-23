# Perguntas do lead fora da fase de apresentação

**Status:** Levantado
**Origem:** `levantamentos/2026-09-23-busca-vetorial-gemini.txt` — relato do utilizador: "às vezes pergunto uma informação, ele não responde"
**Meta ligada:** M2 — O agente responde certo e não perde leads
**Área do sistema:** backend-executors (decision_engine — prompt da Mãe e das filhas)

---

## Pergunta a responder

Quando o lead faz uma pergunta (preço, garantia, como funciona) nas fases de
qualificação ou fecho, o agente responde com o conhecimento cadastrado — ou cai no
"vou confirmar com a equipa" por não ter a FAQ disponível?

## O que já se sabe

- As FAQs e os dados comerciais (`objections_faq`, `service_faq`,
  `service_pricing_table`, `payment_policy`…) só entram nos prompts de
  **apresentação** e **follow-up** (`decision_engine.py:3288-3428`, `3843-3881`).
- **Qualificação** e **fecho** só recebem `business_info`
  (`decision_engine.py:3009`, `4105`) + o bloco "quando não souber responder"
  (`decision_engine.py:140`), que manda dizer "Vou confirmar essa informação com a
  equipa" e pedir handoff.
- A proteção atual é a Mãe: com pergunta direta do lead, deve encaminhar para
  apresentação mesmo com qualificação incompleta ("PRIORIDADE 1B",
  `decision_engine.py:2499`). Se a Mãe errar a classificação, o lead fica sem
  resposta.
- **Hipótese, não confirmada:** falta medir com que frequência isso acontece.
  Leitura de conversas reais de produção autorizada pelo utilizador (ver
  `_guia-discovery.md`, Passo 3): contar respostas "vou confirmar com a equipa" nas
  fases de qualificação e fecho e verificar se a resposta estava na base.
