# Receção acrescenta uma promessa depois do cumprimento ("Vou passar as informações…")

**Branch:** `worktree-fix+recepcao-promessa-apos-cumprimento`
**Status:** Todos os cenários validados (26/10/2026)
**Autonomia:** manual
**Origem:** testes de produção de `fix-saudacao-hora-local` (26/10/2026, 21h40–22h00, conta Sensi Vitae).

---

## Motivação

Quando o cliente não cumprimenta e faz logo um pedido ("Gostaria de mais informações sobre as Massagens"), a
receção responde com o cumprimento **mais uma promessa que ninguém cumpre**, e a mensagem seguinte (2.ª decisão)
contradiz-a com uma pergunta:

> Boa noite! Sou a Lara, do Sensi Vitae.
> Vou passar as informações sobre as massagens para você.
> [2.ª decisão] Posso enviar a nossa tabela de preços?

Medido no 1.º turno do Playground de produção, 3x em paralelo: 3/3 (21h50), 3/3 (21h45) e 2/3 (22h00). Outras
frases vistas: "Vou ajudar com as informações que precisa.", "Vou já ajudar com as informações sobre as
Massagens.", "Vou passar as suas perguntas para a nossa equipa." Com "Olá" sozinho não acontece ("Como posso
ajudar?" 3/3).

---

## Problemas Identificados (estado anterior)

1. **A suspeita inicial (`515734f`) não é a causa.** Medição local de 26/10 com a Filha Recepção real e o perfil de
   produção da conta, 5x por mensagem, guardando o JSON cru. A promessa vem dentro do `message_text`, com
   `should_ask=false` e `question_text` vazio. Nesses casos a regra de antes do `515734f` (`question_text` ganha)
   também enviava o `message_text`. A regra de antes e a de depois só dão resultados diferentes em 1 de 15 corridas.

   | Mensagem | Promessa no cru | `question_text` preenchido | Antes ≠ depois |
   |---|---|---|---|
   | "Gostaria de mais informações sobre as Massagens" | 2/5 | 0/5 | 0/5 |
   | "Olá, queria saber os preços" | 4/5 | 1/5 | 1/5 |
   | "Olá" | 0/5 | 0/5 | 0/5 |

2. **A receção escreve uma 2.ª frase sobre o pedido, e o texto da Fase 0 decide qual.** Mesmo código, só muda a
   orientação da Fase 0 (6 corridas por mensagem). Com o texto atual ("…A resposta ao pedido do cliente segue
   noutra mensagem logo a seguir.", com `strict`, que desde `ec200d4`/18h04 vale "SEGUIR À RISCA" e temperatura
   0.2) saem promessas. Com o texto anterior ("…por isso não acrescente mais nada.") a receção quase sempre
   antecipa "Posso enviar a nossa tabela de preços?". A regra "Não responde, não promete"
   (`_build_child_prompt_recepcao`, secção "O QUE VOCÊ NÃO FAZ" e ❌ 3) falha com todos os textos testados.
3. **Nenhum código corta promessas.** Em `compose_decision_output` a Recepção só tinha
   `_drop_trailing_question` (com `lead_already_answered`).
4. Correção ao diagnóstico de origem: a conta usa **OpenAI gpt-4o-mini** desde 25/10 (`llm_provider=openai`), não
   Llama 3.3 via OpenRouter.

---

## Abordagem

Princípio 1 (`docs/architecture/prompt-engineering-principles.md`): uma regra que o prompt já pede e o modelo não
cumpre passa para código.

```
Filha Recepção → message_text + pending_commercial_text
  ├─ pending vazio ("Olá")          → mensagem intacta ("…Como posso ajudar?")
  └─ pending preenchido (pedido)    → _drop_promise_sentences(message_text)
        ├─ sobram frases            → cumprimento/apresentação sem a promessa
        └─ só havia promessa        → "<Bom dia|Boa tarde|Boa noite>!" (_local_greeting)
     + requeue_pending_message (2.ª decisão responde ao pedido)
```

Uma frase é promessa quando começa por compromisso na 1.ª pessoa: vou, irei, vamos, já lhe/te envio, deixe-me,
aguarde, em breve (pt); voy, te paso, déjame, enseguida (es); I'll, let me, we will (en).

**Prompt sem mudanças (decisão medida).** Foram testadas duas mudanças, 6 corridas por mensagem:
- parágrafo positivo com o motivo ("a sua mensagem acaba no cumprimento; a seguinte responde ao pedido"): a Filha
  passou a prometer mais (4/5) e o "Olá" perdeu o "Como posso ajudar?" em 3/5;
- só um exemplo ❌ com "Vou passar as informações sobre as massagens": o modelo copiou-o à letra em 4/6.

As duas foram retiradas (Princípio 7).

---

## Plano de Implementação

### Fase 1 — Guardrail de promessa na Recepção

**Objetivo:** com um pedido pendente, a receção nunca envia uma promessa depois do cumprimento.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_PROMISE_SENTENCE_RE` + `_drop_promise_sentences()` ao lado de `_drop_trailing_question`; no bloco da Recepção de `compose_decision_output`, com `pending_commercial_text` corta as promessas (fallback para o cumprimento do período) e regista `recepcao_promise_stripped` no `decision_trace` |
| `backend-executors/tests/test_requeue_pending_message_routing.py` | 5 testes: promessa cortada com pedido; "Olá" sem pedido intacto; só promessa → cumprimento; pergunta da Fase 0 mantém-se; variantes pt/es/en |
| `docs/architecture/llm-architecture.md` | "Filha Recepção": regra do guardrail e porquê de não estar no prompt |
| `docs/architecture/prompt-engineering-principles.md` | Princípio 1, "onde já aplicamos": guardrails da Recepção |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `31481bb` | Guardrail de promessa na Recepção + testes + docs |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando o cliente começava com um pedido ("queria saber os preços"), a receção respondia muitas vezes
"Boa noite! Sou a Lara. Vou enviar a nossa tabela de preços.", e logo a seguir vinha outra mensagem a perguntar
"Posso enviar a nossa tabela de preços?". Ficava uma promessa que a mensagem seguinte contradizia.
**Agora:** nesses casos a receção envia só o cumprimento e a apresentação ("Boa noite! Sou a Lara, do Sensi
Vitae."). A frase "vou…" é cortada antes de sair, e quem responde ao pedido é a mensagem seguinte. Um "Olá"
sozinho continua a receber "Como posso ajudar?". As instruções da IA não mudaram, só o código que revê a resposta.
**Para validar:** Cenários L1 e B1 já feitos. Falta o Cenário P1 (Playground de produção), que precisa do merge em
`main`: esta branch toca instruções da IA, por isso só avança com o teu "sim".

---

## Checks de Validação

### Cenário L1 — Medição local (Filha real, perfil de produção, código da worktree)
- [x] "Gostaria de mais informações sobre as Massagens" 6x e "Olá, queria saber os preços" 6x: 0 promessas
  enviadas (a Filha escreveu-as em 7/12; o guardrail cortou todas)
- [x] "Olá" 6x: mensagem intacta, "Como posso ajudar?" em 5/6 (o prompt não mudou; na 6.ª o modelo não pôs a
  pergunta, variação que já existia)
- **Validado em:** 26/10/2026

### Cenário B1 — Regressão na bancada isolada (8110–8112, perfil de produção copiado para a conta de teste)
- [x] `p-micas`: o pedido segue para a 2.ª decisão e a conversa chega à marcação
- [x] `p-ruben`: idem; as instruções da Fase 0 (cumprimentar e apresentar-se como Lara) cumpridas na receção
- **Validado em:** 26/10/2026. Nas duas, a receção diz "Boa noite! Sou a Lara, do Sensi Vitae.", sem promessa. A
  2.ª decisão oferece a tabela e as duas conversas terminam com marcação gravada (qua 28/10 15h; ter 27/10 11h).
  Rastos: `.claude/agentes/sensi-vitae/tentativas/20261026-2223-promessa-f1-p-micas.md` e `…-2225-promessa-f1-p-ruben.md`.
  Visto de passagem, fora deste item: em p-micas a 2.ª decisão abriu com "Bom dia!" às 22h.

### Cenário P1 — Playground de produção (só depois do "sim" para o merge e do deploy)
- [x] 1.º turno 3x em paralelo com "Gostaria de mais informações sobre as Massagens": nenhuma promessa depois do
  cumprimento
- [x] 1.º turno 3x em paralelo com "Olá, queria saber os preços": nenhuma promessa depois do cumprimento
- [x] 1.º turno 3x em paralelo com "Olá": continua "Como posso ajudar?"
- **Validado em:** 26/10/2026, 22h35, depois do deploy de `4eed6a6`. 6/6 com pedido: "Boa noite! Sou a Lara, do
  Sensi Vitae." (uma vez com "Estou aqui para ajudar."), seguido da 2.ª decisão "Posso enviar a nossa tabela de
  preços?". Nenhuma promessa e nenhuma pergunta antecipada pela receção. 3/3 "Olá" → "…Como posso ajudar?".

---

## Ajustes Possíveis Pós-Implementação

- **A receção antecipa a pergunta do roteiro** ("Posso enviar a nossa tabela de preços?"), e a 2.ª decisão pode
  repeti-la. Não é promessa, por isso não é cortada. Com a configuração atual apareceu em 2/6 com "Olá, queria
  saber os preços". Um guardrail de perguntas teria de distinguir a pergunta pedida pelo dono na Fase 0 (ex.:
  "Val ou Daniel?"), o que é frágil. Candidato a `docs/plans/`.
- **Dono que pede de propósito uma frase com "vou…" na Fase 0** (ex.: "diga que vai enviar a tabela"): com pedido
  pendente, o guardrail corta-a. É aceitável porque a 2.ª decisão trata o pedido logo a seguir.
- **2.ª decisão com cumprimento do período errado** ("Bom dia!" às 22h, p-micas, rota `apresentation`). Não é da
  receção; candidato a `docs/plans/` se se repetir em produção.
- A orientação da Fase 0 da Sensi Vitae ("A resposta ao pedido do cliente segue noutra mensagem logo a seguir",
  com `strict`) é a que mais puxa a promessa. Com o guardrail deixa de importar, mas pode ser simplificada.
