# Receção acrescenta uma promessa depois do cumprimento ("Vou passar as informações…")

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
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

Medido no 1.º turno do Playground de produção, 3x em paralelo: 3/3 (21h50, sem a saudação nova), 3/3 (21h45) e
2/3 (22h00, com a saudação nova). Outras frases vistas: "Vou ajudar com as informações que precisa.", "Vou já
ajudar com as informações sobre as Massagens.", "Vou passar as suas perguntas para a nossa equipa." Esta última
não é o fallback de handoff (`FALLBACK_DECISION`): esse substitui a resposta inteira, e aqui a frase vem depois
do cumprimento, por isso foi escrita pela própria Filha. Com "Olá" sozinho não acontece ("Como posso ajudar?" 3/3).

A regra existe no prompt ("Não responde, não promete verificar…", exemplo ❌ 3 de
`_build_child_prompt_recepcao`), mas o modelo de produção da conta (OpenRouter / Llama 3.3 70B) não a cumpre.

## Causa provável (a confirmar no Plan Mode)

`515734f` (`fix-recepcao-ignora-pergunta-extra`, deploy às 20h26 de 26/10): a receção passou a usar **sempre** o
`message_text`. Antes, quando a Filha preenchia `question_text`, a segunda frase era trocada pela pergunta, e a
promessa ficava escondida. As 10 corridas anteriores (PROD04–PROD07, B1, B2, PROD-B, até às 15h55) não mostram
promessa; a primeira corrida depois do deploy das 20h26 já a mostra.

Princípio 1 de `docs/architecture/prompt-engineering-principles.md`: regra que não pode falhar → guardrail de
código além do prompt (ex.: com `pending_commercial_text` preenchido, a receção envia só o cumprimento, e uma
frase de promessa — "vou passar/ajudar/verificar/enviar" — é cortada antes de enviar).

## Área do sistema

- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_recepcao` e `compose_decision_output`
  (tratamento do `message_text` da receção) — **instruções da IA**
- Docs: `docs/architecture/llm-architecture.md` ("Filha Recepção"), `docs/prompts_llms.md`

## Como validar

- 1.º turno no Playground de produção, 3x em paralelo, com "Gostaria de mais informações sobre as Massagens"
  e com "Olá, queria saber os preços": nenhuma promessa depois do cumprimento.
- Regressão: `p-ruben` e `p-micas` (pedido junto com o cumprimento segue para a 2.ª decisão) e as instruções da
  Fase 0 do Fluxo de Venda continuam a ser cumpridas na receção.
