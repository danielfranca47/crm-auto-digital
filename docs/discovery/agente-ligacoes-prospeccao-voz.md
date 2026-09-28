# Agente de ligações de prospecção ativa (voz com IA) — vale a pena e como?

---

**Status:** Em investigação — análise preliminar feita, aguardando 3 respostas do utilizador
**Origem:** pedido do utilizador em 28/09/2026 + briefing do arquiteto de soluções
(`C:\projetos\modelos-agents\briefings\2026-09-28-agente-ligacoes-prospeccao.md`, fora do repo)
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (se as ligações forem para vender o
próprio CRM); M5 se virar produto para os clientes
**Área do sistema:** backend-crm (fila de jobs, appointments, Kanban) / backend-core (entitlements,
aceite de termo) / frontend-crm (campanha, termo) / fornecedor externo de voz + telefonia

---

## Pergunta a responder

Faz sentido termos um agente que liga sozinho para uma lista de leads, faz a abordagem (cold call)
e agenda a call de demonstração — primeiro em beta só para a conta `autodigital157@gmail.com`,
depois como produto pago? Se sim, construímos a voz ou compramos?

## O que já se sabe

- **Já existe quase tudo menos a voz:** Kanban de leads com `origin` inbound/outbound
  ([leads-schema.md](../architecture/leads-schema.md)), importação por planilha, agenda com
  sincronização Google Calendar ([agenda.md](../architecture/agenda.md),
  [google-calendar.md](../architecture/google-calendar.md)), agendamento feito pela IA no WhatsApp,
  follow-up automático ([followup.md](../architecture/followup.md)), fila de jobs com retry
  (`services/jobs_service.py`).
- **Liberar só para uma conta já é possível:** feature gates por plano via `/me/entitlements` +
  `services/plan_gates.py` ([plans-limits.md](../architecture/plans-limits.md)).
- **Não existe nada de telefonia/voz em tempo real no sistema** — é a parte nova.

---

## Evidência no código

Ver "O que já se sabe". O trabalho novo seria: um tipo de job `voice.call.outbound`, endpoints que a
plataforma de voz chama durante a ligação (`consultar_horarios_livres`, `agendar_demo` reaproveitando
`appointments`, `registrar_opt_out`, `transferir_para_humano`), um webhook de fim de chamada
(transcrição + resultado → Kanban), campo de consentimento no lead, lista de "não ligar", aceite do
termo de responsabilidade registado (data, versão) e um gate novo em `plan_limits`.

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| Retell AI / Vapi (plataformas de voz IA) | Fazem a parte difícil (ouvir, falar, interrupções, caixa postal) e chamam as nossas funções por API. ~US$ 0,05–0,07/min só a plataforma; total real US$ 0,12–0,31/min | Sim — é a opção recomendada; qualidade do português tem de ser testada |
| Twilio (telefonia BR) | Ligação para celular BR US$ 0,0663/min; número BR US$ 4,25/mês | Sim — número ligado à plataforma de voz |
| OpenAI Realtime + Twilio (construir) | Voz em tempo real feita por nós | Não agora — economiza pouco por minuto e custa semanas; só acima de 20–30 mil min/mês |
| Anatel / LGPD | Bloqueio de quem faz ligações curtas em massa; prefixo 0303 em transição (opcional desde ago/2025, MPF pede volta); LGPD exige base legal, aviso de gravação e respeitar quem pede para não ser contactado | Sim — regras têm de estar no código, não só no termo |
| AI Act UE (art. 50) | Obrigatório dizer que é IA desde 02/08/2026 | Só se houver leads em Portugal/UE; adotar o aviso como padrão também no Brasil |

## Opções de solução

### Opção A — Uma pessoa liga, com apoio do CRM (sem código novo no início)
- **O que é:** 1–2 semanas de ligações humanas com roteiro, 50–100 leads, resultado registado no Kanban.
- **Prós:** custo zero de desenvolvimento, sem risco, gera demos já e mede a taxa real de conversão.
- **Contras:** não é o "agente que liga sozinho" nem vira produto.
- **Esforço:** 0 fases.

### Opção B — IA de voz comprada (Retell/Vapi) + campanha controlada pelo nosso CRM
- **O que é:** a plataforma faz a conversa; o nosso código decide quem ligar, quando, quantas vezes,
  e só deixa agendar horários livres de verdade.
- **Prós:** entrega o agente de ligações; reaproveita agenda, Kanban e WhatsApp (quem não atende
  recebe follow-up no WhatsApp).
- **Contras:** custo por minuto alto (~R$ 0,80–1,20/min); dependência de fornecedor; rejeição a robô.
- **Esforço:** ~3 fases (~60–100 h).

### Opção C — Construir a voz nós mesmos (OpenAI Realtime + Twilio)
- **Prós:** custo por minuto um pouco menor.
- **Contras:** semanas de engenharia na parte mais difícil; mais risco de falhas.
- **Esforço:** 5+ fases. Descartada por agora.

## Recomendação

**A e depois B, em sequência.** Primeiro 1–2 semanas de ligações humanas para saber quantas demos
saem a cada 100 ligações e quais objeções aparecem (isso vira o "gabarito" para testar a IA). Depois,
beta da Opção B só para `autodigital157@gmail.com`, com todas as regras de segurança no código.
Só vira produto se o custo por demo compensar **e** 3–5 clientes disserem que pagam o adicional.

Pontos em que a análise discorda da ideia inicial:
1. **"Cold call" e "tenho autorização" são coisas diferentes.** Com autorização é um contacto de
   retorno (seguro e converte melhor). Lista do Google Maps/comprada não tem autorização — aí a IA
   não deve ligar sozinha.
2. **O termo de responsabilidade é necessário, mas não basta.** O número e a conta de telefonia são
   nossos: se um cliente abusar, o bloqueio atinge todos. E pela LGPD podemos responder junto. Por
   isso: consentimento obrigatório por lead, lista de "não ligar", limite de ligações por dia, janela
   de horário, número separado por cliente no produto.
3. **A IA diz logo no início que é assistente virtual e que a ligação é gravada.**
4. **Nunca incluir no plano de R$ 147.** Um uso moderado (300 min/mês) custa R$ 250–360 — mais que o
   plano. Vender como adicional pré-pago, ex.: R$ 2,00–2,50/min (pacote 300 min ≈ R$ 600–750/mês).

**Custo estimado do beta:** ~R$ 540–790/mês em minutos (≈500 leads, até 3 tentativas) → ~R$ 20–90
por demo agendada. Preços vêm de sites agregadores: confirmar na página oficial antes de fechar.

## Pontuação RICE (preliminar)

| R | I | C | E | Score |
|---|---|---|---|---|
| 1 | 2 | 0.5 | 3 | 0.33 |

- **R = 1:** beta para uma conta.
- **I = 2:** pode gerar demos e clientes (M1), mas só se a taxa de conversão se confirmar.
- **C = 0.5:** todas as taxas de conversão são de fornecedores americanos, em inglês; nada medido em
  português com o nosso público.
- **E = 3:** Opção B em ~3 fases (a Opção A não tem código).

## Veredito proposto

**Pendente das respostas abaixo.** Tendência: **Plans** para a Opção B, com a Opção A (ligações
humanas) a começar já, fora do código. Se a lista não tiver autorização real → **Descartar** a IA
ligando sozinha e ficar só na Opção A.

## Perguntas ao utilizador

1. **De onde vêm os leads que vão receber as ligações, e como deram a autorização?** (pediram
   contacto num formulário / são clientes antigos / lista do Google Maps ou comprada?) — decide se a
   IA pode ligar sozinha.
2. **Quem pagaria por isto no produto?** Os massoterapeutas/terapeutas de hoje pagariam ~R$ 600/mês
   a mais por ligações? Ou é para outro tipo de cliente? E a conta `autodigital157` vai ligar para
   vender o próprio CRM ou é um cliente com outro público?
3. **Há alguém que consiga ligar para 50–100 leads com roteiro nas próximas 1–2 semanas, antes de
   construirmos a IA?** E quanto aceita pagar por demo agendada?

Menores: haverá leads em Portugal? Prazo desejado para o beta?

## Em aberto

- Retell/Vapi vendem número brasileiro próprio ou só via Twilio? (validar no 1.º dia do beta)
- Bland, Synthflow e ElevenLabs Agents não foram comparados a fundo — incluir no teste de voz PT-BR.
- Regras atuais de horário de telemarketing e se o "Não Me Perturbe" se aplica a um SaaS — parecer
  jurídico antes do produto (não bloqueia o beta).

## Fontes

- [Twilio Voice Pricing Brazil](https://www.twilio.com/en-us/voice/pricing/br)
- [CloudTalk – Retell pricing](https://www.cloudtalk.io/retell-ai-pricing/)
- [Retell – AI voice agent pricing breakdown](https://www.retellai.com/blog/ai-voice-agent-pricing-full-cost-breakdown-platform-comparison-roi-analysis)
- [CloudTalk – Vapi pricing](https://www.cloudtalk.io/blog/vapi-ai-pricing/)
- [Cekura – Vapi pricing](https://www.cekura.ai/blogs/vapi-ai-pricing)
- [Layer3 – OpenAI Realtime pricing](https://www.layer3labs.io/guides/openai-realtime-api-pricing)
- [OpenAI – gpt-realtime](https://developers.openai.com/api/docs/models/gpt-realtime)
- [Estado de Minas – bloqueio de telemarketing abusivo (09/05/2026)](https://www.em.com.br/emfoco/2026/05/09/operadoras-como-vivo-claro-e-tim-passam-a-seguir-novas-regras-da-anatel-para-bloqueio-temporario-de-ligacoes-de-telemarketing-abusivo/)
- [Anatel – prefixo 0303](https://www.gov.br/anatel/pt-br/regulado/numeracao/telemarketing-ativo-prefixo-0303)
- [InfoMoney – 0303 deixa de ser obrigatório](https://www.infomoney.com.br/consumo/chamadas-de-telemarketing-nao-precisam-mais-usar-prefixo-0303-decide-anatel/)
- [MPF – recomenda volta do 0303](https://www.mpf.mp.br/o-mpf/unidades/pr-go/noticias/mpf-recomenda-que-anatel-restabeleca-uso-obrigatorio-do-prefixo-0303-para-telemarketing)
- [Correio Braziliense – canais de robôs suspensos](https://www.correiobraziliense.com.br/cbradar/bloqueio-prefixo-0303-telemarketing-anatel/)
- [2CX – exigências regulatórias para operações ativas 2026](https://2cx.com.br/exigencias-regulatorias-para-operacoes-ativas-2026/)
- [Del Grande – gravação de ligação e LGPD](https://delgrande.com.br/blog/como-adequar-a-gravacao-de-ligacao-a-lgpd/)
- [AI Act – artigo 50](https://artificialintelligenceact.eu/article/50/)
- [Comissão Europeia – FAQ art. 50](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act)
- [MarketsandMarkets – voice AI cold call](https://www.marketsandmarkets.com/AI-sales/voice-ai-can-agents-successfully-cold-call)
- [VoiceInfra – AI cold calling](https://voiceinfra.ai/use-cases/ai-cold-calling)
- [Martal – cold call statistics](https://martal.ca/cold-call-statistics-lb/)
