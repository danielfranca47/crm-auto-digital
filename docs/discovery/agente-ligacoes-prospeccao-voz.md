# Agente de ligações de prospecção ativa (voz com IA) — vale a pena e como?

---

**Status:** Pronta para decisão — falta confirmar endereço no Brasil e meta de sucesso do beta
**Origem:** pedido do utilizador em 28/09/2026 + briefing do arquiteto de soluções
(`C:\projetos\modelos-agents\briefings\2026-09-28-agente-ligacoes-prospeccao.md`, fora do repo) +
protótipo próprio `C:\projetos\ai-coldcall-agent-study` (fora do repo)
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (ligações para vender o próprio CRM);
M5 quando virar produto para os clientes
**Área do sistema:** backend-crm (fila de jobs, appointments, Kanban, consentimento) /
backend-executors (worker `voice`) / serviço novo `voice-gateway` / frontend-crm (campanha)

---

## Pergunta a responder

Faz sentido termos um agente que liga sozinho para leads, faz a abordagem e agenda a call de
demonstração — primeiro em beta só para a conta `autodigital157@gmail.com`, depois como produto
pago? Se sim, construímos a tecnologia de voz ou compramos?

## O que já se sabe

**Respostas do utilizador (29/09/2026):**
1. **Para quem liga:** clientes da carteira + leads que pediram contacto nos anúncios para saber
   mais da plataforma. Não é lista fria. A conta `autodigital157` é a operação comercial dele.
2. **Quem paga:** no beta, ele próprio (validar roteiro, fluxo no CRM, funil). No produto, quer
   **tecnologia própria** (não revender terceiro), para baratear e dar a cada cliente o seu número
   e plano.
3. **Etapa humana:** pode contratar um cold caller para fazer a operação e passar os dados.

**Respostas do utilizador (29/09/2026, 2.ª ronda):**
4. **Empresa:** sem CNPJ hoje; considera abrir MEI no próprio nome.
5. **Marca no MVP:** o próprio nome e o nome do produto — "Lara", assistente virtual de Daniel França.
6. **Volume:** ~10 leads/dia (~220/mês).

**Telefonia sem CNPJ (verificado):**
- A Twilio **dá número celular brasileiro a pessoa física** (documento de identidade + comprovante
  de endereço **no Brasil**). Números fixo/nacional e 0800 exigem CNPJ. Aprovação do cadastro em até
  3 dias úteis. → **O beta não depende de abrir empresa.**
- **O MEI não serve para este negócio:** desenvolvimento/licenciamento de software (CNAE 6201/6203)
  e teleatendimento/telemarketing (8220-2/00) **não são atividades permitidas ao MEI**. Vender o CRM
  ou o serviço de ligações como produto exige ME (Simples Nacional). Decisão para a fase de produto,
  com contabilista.
- **Ponto a confirmar com a Twilio:** a página de voz BR da Twilio ainda diz que quem é classificado
  como telemarketing tem de ligar de números 0303 (regra de 2022). A Anatel tornou o 0303 opcional
  desde ago/2025 para quem adere à "Chamada Verificada". Ligar para a própria carteira e para leads
  que pediram contacto é defensável como relacionamento, mas confirmar com o suporte Twilio antes do
  piloto real.

**No CRM já existe quase tudo menos a voz:** Kanban com `origin` inbound/outbound
([leads-schema.md](../architecture/leads-schema.md)), importação por planilha, agenda com Google
Calendar ([agenda.md](../architecture/agenda.md), [google-calendar.md](../architecture/google-calendar.md)),
agendamento pela IA no WhatsApp, follow-up ([followup.md](../architecture/followup.md)), fila de
jobs com lease/retry (`services/jobs_service.py`, executors fazem claim via
`/api/internal/jobs/{id}/claim`), liberação por conta via `plan_limits`
([plans-limits.md](../architecture/plans-limits.md)).

**Protótipo próprio (`ai-coldcall-agent-study`, agente "Lara"):**
- Twilio Media Streams + OpenAI Realtime (`gpt-realtime-2`, voz `marin`, `semantic_vad`, redução de
  ruído, transcrição) — **não** usa ElevenLabs (só aparece como decisão futura de voz).
- Já tem: disparo protegido por token, limite de chamadas por minuto/dia, gravação de chamadas e
  transcrição em SQLite, indicadores (`/kpis`), logging sem dados sensíveis.
- Roteiro "Lara" v1.2 para o mesmo nicho (massoterapeutas, psicólogos, dentistas, terapeutas).
- **Nunca fez uma ligação real** (conta Twilio/número não configurados); sem funções de agenda, sem
  desligar a chamada sozinho, sem deteção de caixa postal, sem campanha, sem integração com o CRM.
- **Problemas a corrigir antes de qualquer ligação real:**
  - a abertura do roteiro diz **"Aqui é o Daniel"** — a IA passa-se pelo dono e só admite ser IA se
    perguntarem (contradiz a própria secção IDENTIDADE do prompt);
  - a mensagem inicial da Twilio está em inglês ("Connecting with Compliance Agent"), herança do
    projeto original;
  - marca "Digital Pro" em vez de "Auto Digital"; mistura de português de Portugal e do Brasil;
  - possível incompatibilidade de versão na ligação à OpenAI (cabeçalho beta + formato GA).

---

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| Twilio (telefonia BR) | Celular BR US$ 0,0663/min, fixo US$ 0,031/min, número fixo US$ 4,25/mês. **Número fixo BR exige CNPJ + registo comercial + comprovante de endereço no Brasil**; celular aceita pessoa física com documento e endereço BR | Sim — é igual em todos os caminhos e é 40–70% do custo do minuto |
| OpenAI Realtime (o que o protótipo usa) | Voz em tempo real num só serviço; ~US$ 0,06–0,11/min, versão mini ~US$ 0,02–0,05/min | Sim — motor do beta |
| ElevenLabs Agents | **É uma plataforma comprada** (como Retell/Vapi): US$ 0,08/min + LLM à parte, usa o número Twilio do cliente. Baixou preço em maio/2026 | Plano B se o protótipo falhar no teste |
| ElevenLabs Flash (só a voz) + Deepgram (ouvir) + LLM | Pipeline montado por nós, ~US$ 0,10–0,12/min | Só com volume de produto |
| Retell / Vapi | US$ 0,12–0,31/min | Mais caros que ElevenLabs Agents |
| Anatel / LGPD / AI Act UE | Bloqueio de ligações curtas em massa; 0303 em transição; LGPD pede base legal, aviso de gravação e respeitar opt-out; UE obriga dizer que é IA desde 02/08/2026 | Regras no código e no roteiro |

## Opções de solução

### Opção A — Só cold caller humano + CRM
- **Prós:** sem código, sem risco, gera demos já.
- **Contras:** não atende ao objetivo de produto. O utilizador já decidiu usá-la como **etapa 0**
  (referência de conversão), não como solução final.

### Opção B — Plataforma comprada (ElevenLabs Agents) + Twilio + funções no CRM
- **Prós:** voz em PT testada por terceiros, menos manutenção; aceita número próprio por cliente.
- **Contras:** ~US$ 0,15–0,17/min; dependência de fornecedor; contraria o objetivo de tecnologia própria.
- **Esforço:** ~3 fases.

### Opção C1 — Protótipo próprio reforçado (Twilio + OpenAI Realtime) + funções no CRM ⭐
- **Prós:** já existe; custo ~US$ 0,09–0,18/min (mini/completo); tecnologia própria; a integração
  com o CRM é a mesma que a B precisaria — trocar de motor depois não refaz o CRM.
- **Contras:** nunca testado ao vivo; manutenção da camada de voz fica connosco.
- **Esforço:** ~4 fases (reforço, integração no backend-crm/executors, gateway, piloto).

### Opção C2 — Pipeline próprio em cascata (Deepgram + LLM + ElevenLabs Flash)
- **Prós:** custo parecido com C1-mini, voz ElevenLabs.
- **Contras:** teríamos de resolver turnos/latência entre 3 fornecedores. Só com volume de produto.

## Recomendação

**C1: usar o protótipo próprio no beta, com o cold caller a correr em paralelo como referência e a
B (ElevenLabs Agents) como plano de saída.**

1. **Etapa 0 (semanas 1–2):** cold caller liga para carteira + leads de anúncio e regista no Kanban.
   Dá a taxa de referência e 30–50 conversas que servem de "gabarito" para testar a IA.
2. **Etapa 1 (semanas 1–3, sem leads reais):** corrigir abertura (IA + marca + aviso de gravação),
   mensagem em inglês e português misturado; adicionar desligar a chamada, duração máxima e caixa
   postal; número Twilio BR + publicar no Railway; 30–50 ligações de teste (Realtime completo vs.
   mini). **Se falhar** (demora a responder, interrupções falsas, não desliga, erra a agenda) →
   o beta usa ElevenLabs Agents, sem mudar o CRM.
3. **Etapa 2 (semanas 3–5):** integração — no backend-crm: consentimento e opt-out por lead, job
   `voice.call.outbound` com as regras (horário, tentativas, tetos), endpoints de agenda
   (`consultar_horarios_livres`, `agendar_demo`), receção do resultado, liberação só para
   `autodigital157`; no backend-executors um worker `voice` que só dispara a ligação; o protótipo
   vira o serviço separado `voice-gateway` (o áudio fica aberto minutos por chamada — carga
   diferente do resto).
4. **Etapa 3 (semanas 5–8):** piloto real, começando pelos leads de anúncio de menor valor; revisão
   de 100% das primeiras 50 ligações; comparação com o cold caller.

**Pontos em que a análise discorda:**
- **"Construir para baratear" tem teto:** a telefonia Twilio é igual em qualquer caminho, por isso
  construir poupa só ~15–40% por minuto. O minuto fica em R$ 0,50–1,00 — continua a ser um
  **adicional pago** (preço-alvo R$ 1,50–2,00/min), nunca dentro do plano de R$ 147.
- **"Número próprio por cliente" não exige construir** (as plataformas também aceitam). O que pesa
  é que **cada cliente terá de enviar documentos brasileiros** para a Twilio.
- **O termo de responsabilidade é necessário mas não basta** — as regras de segurança ficam no
  código. No beta não é preciso (o operador é o dono); já prever a tabela de aceite (versão, data)
  para o produto.
- **A IA não pode apresentar-se como "Daniel"** — deve dizer na primeira frase que é assistente
  virtual a falar em nome dele/da empresa.

**Custo do beta** (~10 leads/dia ≈ 220/mês, até 3 tentativas ≈ 500 min): **~R$ 300–600/mês**
(minutos R$ 250–500 + número celular + servidor ~R$ 50–100) + cold caller pontual ~R$ 1.000–2.000.
Estimativa **~R$ 10–60 por demo**. Preços de agregadores marcados como tal; confirmar nas páginas
oficiais.

**Nota honesta sobre o volume:** 10 leads/dia uma pessoa liga em ~1 h/dia. Neste volume a IA não
poupa tempo que valha o desenvolvimento — o valor do beta é **validar o produto** (roteiro, funil,
integração, custo real por minuto) antes de o vender aos clientes. Manter o prazo curto (~8 semanas)
para não roubar foco da M1.

**Abertura da ligação no MVP:** "Olá, [nome]! Aqui é a Lara, assistente virtual do Daniel França —
esta ligação é gravada. Você pediu informações sobre…". Remove "Aqui é o Daniel" e "Digital Pro" do
roteiro atual.

**Critério para virar produto:** taxa de demo ≥ ~70% da do cold caller com custo por demo menor;
zero reclamações; 3–5 clientes que aceitem pagar o adicional com o preço na mesa; cadastro de número
testado com 1 cliente real; parecer jurídico (Anatel/LGPD).

### Variante — prospects novos (lista fria, ex.: Google Maps via agent-local)

A recomendação acima vale para **carteira + leads que pediram contacto**. Para prospects novos, sem
pedido de contacto, muda o seguinte:

| Tema | Leads com pedido de contacto | Prospects novos (lista fria) |
|---|---|---|
| Base legal (LGPD) | Consentimento / relação prévia | Só "legítimo interesse": exige registo do teste de balanceamento, dizer na ligação de onde veio o contacto, opt-out imediato. Massoterapeutas autónomos usam telemóvel pessoal → dado pessoal, risco maior |
| Classificação | Defensável como relacionamento | **Telemarketing ativo** claro → Twilio exige número 0303 (ou a confirmar "Chamada Verificada") → na prática **exige CNPJ (ME)**; o celular em pessoa física não serve |
| Número | Risco baixo | Alto risco de ser marcado como "suspeita de spam" nos celulares — atende menos e contamina o número usado para os leads quentes |
| Conversão | 10–25% de demo por conversa (premissa) | Cold call humano ~2–3%; com IA a rejeição tende a ser maior → custo por demo sobe para **R$ 100+** |
| Quem liga | IA sozinha (com regras em código) | **Humano** (cold caller), não a IA sozinha |

**Caminho recomendado para prospects novos — "aquecer primeiro, ligar depois":** o primeiro
contacto é pelo canal que já existe (prospecção WhatsApp/email do agent-local). Quem responder com
interesse ("quero saber mais") passa a ser lead com pedido de contacto, com registo da data e da
origem, e entra na fila da Lara. Assim a IA liga só para quem já demonstrou interesse, o número não
queima e a base legal fica sólida. Ligação fria direta fica com o cold caller humano.

**Variante proposta pelo utilizador (29/09/2026) — cold caller faz o 1.º contacto, a Lara liga
aos interessados:** avaliada como **boa em parte**.
- **Certo:** o consentimento para a ligação da IA é recolhido por uma pessoa → base legal sólida para
  a Lara. O cold caller tem de perguntar explicitamente ("posso pedir à Lara, a nossa assistente
  virtual, que lhe ligue?") e registar no CRM (data, quem recolheu).
- **Ajuste:** se o lead já mostrou interesse ao cold caller, **o cold caller deve marcar a demo na
  hora** — é o momento de maior conversão; uma 2.ª ligação para agendar acrescenta atrito e o lead
  pode não atender. A Lara entra onde a pessoa não tem tempo: quem disse "ligue-me depois" / "mande
  mais informação", confirmação e lembrete da demo, reagendamento e quem faltou (no-show).
- **Continua a valer para a 1.ª ligação (do humano):** legítimo interesse (LGPD), classificação como
  telemarketing (0303/CNPJ) e **número diferente do da Lara**, para o número dela não ser marcado
  como spam.

**Vários públicos (pequenas a grandes empresas):** exige que cada campanha tenha roteiro, perfil de
público e métricas próprias (entidade "campanha" no CRM, não um roteiro único). Cautelas: com ~10
leads/dia, testar muitos públicos em paralelo dá amostras pequenas demais para concluir — testar
**1–2 públicos de cada vez** (~100+ leads cada); empresas maiores têm recepcionista/filtro e decisor
difícil de alcançar (pior para IA) e ciclo de venda longo; o produto (R$ 147/mês) é desenhado para
pequenos negócios — públicos maiores tocam na M5, que só entra depois da M1.

**No produto:** permitir que clientes usem a IA em listas frias aumenta o risco para a plataforma
(bloqueio de números e da conta Twilio, LGPD solidária). Regra em código: a campanha de voz só aceita
leads com origem/consentimento registado; listas frias ficam fora até haver parecer jurídico.

## Pontuação RICE

| R | I | C | E | Score |
|---|---|---|---|---|
| 1 | 2 | 0.8 | 4 | 0.40 |

- **R = 1:** beta para uma conta (a operação do próprio dono).
- **I = 2:** leads quentes e carteira podem gerar demos e clientes (M1); ainda não medido.
- **C = 0.8:** consentimento confirmado e protótipo existente; falta medir conversão e testar a voz ao vivo.
- **E = 4:** reforço do protótipo + integração CRM/executors + gateway + piloto.

## Veredito proposto

**Implementations**, em duas frentes — depois das respostas abaixo:
- **Fora deste repo, já:** cold caller (etapa 0) e reforço do protótipo com ligações de teste
  (etapa 1), no próprio `ai-coldcall-agent-study`.
- **Neste repo:** `feat/ligacoes-voz-beta` (integração CRM + worker `voice` + `voice-gateway`),
  iniciada quando o protótipo passar no critério técnico da etapa 1.

## Perguntas ao utilizador

1. **Qual modelo de comissão propor ao representante?** (ver simulador abaixo)

(Respondidas: marca "Lara, assistente virtual de Daniel França"; volume ~10 leads/dia; sem CNPJ;
**tem comprovante de endereço no Brasil** → número celular Twilio em pessoa física viável.)

**Execução do beta por representante comercial (29/09/2026):** o utilizador quer terceirizar a
operação a uma equipa/representante que invista no projeto, com **20% de comissão recorrente**
sobre a mensalidade dos clientes retidos. A meta do beta passa a ser a do plano progressivo do
representante. Duas páginas (privadas até partilhar):
- Simulador interno de Daniel (24 meses, 3 modelos de comissão, receita da firma):
  https://claude.ai/artifact/5CdUQe5T92GQeiZFaeDXUh
- Proposta para o representante (sem dados de receita da firma; modelo 20% por 24 meses + bônus
  de 1 mensalidade; ferramentas por conta dele — telefonia VoIP ilimitada ex. Api4com R$ 169,90/mês
  e headset ~R$ 200 uma vez — reembolsadas por Daniel nos meses com meta de demos realizadas
  batida; metas 12/22/35 demos realizadas por mês nas fases 1/2/3):
  https://claude.ai/artifact/Ss7QLNGHmWSPWBXLTh2scs

Resultado com as premissas padrão (50→70→100 discagens/dia, preço R$147→197, churn 8%/mês):
- **Só 20% recorrente:** representante ganha < R$ 1.000/mês nos primeiros 6 meses (R$ 964 no
  mês 6, R$ 2.112 no mês 12, R$ 12,6 mil no 1.º ano). Pouco atrativo para quem começa do zero.
- **20% + bônus de ativação (100% da 1.ª mensalidade, pago após a 2.ª):** R$ 2.392 no mês 6,
  R$ 3.539 no mês 12, R$ 24,8 mil no 1.º ano. Custa a Daniel ~R$ 29 mil a menos em 2 anos.
- **Escalonado 20→25→30% por tamanho da carteira:** meio-termo (R$ 16,4 mil no 1.º ano).
- Tensão com a regra anterior em `docs/marketing/comercial/parceria-professor-e-escada-de-preco.md`
  ("nunca comissão recorrente sobre preço travado de entrada"): aqui o representante é vendedor
  ativo, por isso recorrente faz sentido, mas **com prazo** (12 ou 24 meses) e fora do preço Fundador.

## Em aberto

- Preço mensal do número **celular** BR na Twilio e prazo de aprovação dos documentos.
- Se o número aparece corretamente no ecrã de celulares BR (identificador de chamada).
- Regras de documentação por subconta Twilio (fase de produto).
- Preço exato da transcrição e do LLM dentro do ElevenLabs Agents.

## Fontes

- [Twilio Voice Pricing Brazil](https://www.twilio.com/en-us/voice/pricing/br)
- [Twilio — Brazil Regulatory Guidelines](https://www.twilio.com/en-us/guidelines/br/regulatory)
- [Twilio — Brazil Voice Guidelines](https://www.twilio.com/en-us/guidelines/br/voice)
- [Twilio — Regulatory FAQ (prazo de aprovação)](https://www.twilio.com/docs/phone-numbers/regulatory/faq)
- [Api4com — planos](https://www.api4com.com/)
- [Claro — plano Controle](https://www.claro.com.br/celular/controle)
- [Contabilizei — Profissional de TI pode ser MEI?](https://www.contabilizei.com.br/contabilidade-online/profissional-de-ti-pode-ser-mei/)
- [Wetax — Programador pode ser MEI em 2026?](https://wetax.com.br/programador-pode-ser-mei-em-2026)
- [Contabilidade.com — CNAE 8220-2/00 teleatendimento](https://contabilidade.com/blog/cnae-8220200-atividades-de-teleatendimento-simples-nacional-fator-r-e-abertura-de-empresa/)
- [ElevenLabs — Agents pricing](https://elevenlabs.io/pricing/agents)
- [ElevenLabs — corte de preço conversational AI](https://elevenlabs.io/blog/we-cut-our-pricing-for-conversational-ai)
- [UsagePricing — mudança de preço ElevenLabs (05/2026)](https://www.usagepricing.com/blueprint/activity/elevenlabs-2026-05-07-price-change)
- [ElevenLabs — Models](https://elevenlabs.io/docs/overview/models)
- [Puter — ElevenLabs API pricing](https://developer.puter.com/tutorials/elevenlabs-api-pricing/)
- [Deepgram — Nova-3](https://deepgram.com/learn/introducing-nova-3-speech-to-text-api)
- [ConvertAudioToText — Deepgram Nova-3](https://convertaudiototext.com/blog/deepgram-nova-3-explained)
- [Layer3 — OpenAI Realtime pricing](https://www.layer3labs.io/guides/openai-realtime-api-pricing)
- [OpenAI — gpt-realtime](https://developers.openai.com/api/docs/models/gpt-realtime)
- [CloudTalk — Retell pricing](https://www.cloudtalk.io/retell-ai-pricing/)
- [CloudTalk — Vapi pricing](https://www.cloudtalk.io/blog/vapi-ai-pricing/)
- [Estado de Minas — bloqueio de telemarketing abusivo (09/05/2026)](https://www.em.com.br/emfoco/2026/05/09/operadoras-como-vivo-claro-e-tim-passam-a-seguir-novas-regras-da-anatel-para-bloqueio-temporario-de-ligacoes-de-telemarketing-abusivo/)
- [Anatel — prefixo 0303](https://www.gov.br/anatel/pt-br/regulado/numeracao/telemarketing-ativo-prefixo-0303)
- [InfoMoney — 0303 deixa de ser obrigatório](https://www.infomoney.com.br/consumo/chamadas-de-telemarketing-nao-precisam-mais-usar-prefixo-0303-decide-anatel/)
- [MPF — recomenda volta do 0303](https://www.mpf.mp.br/o-mpf/unidades/pr-go/noticias/mpf-recomenda-que-anatel-restabeleca-uso-obrigatorio-do-prefixo-0303-para-telemarketing)
- [2CX — exigências regulatórias para operações ativas 2026](https://2cx.com.br/exigencias-regulatorias-para-operacoes-ativas-2026/)
- [Del Grande — gravação de ligação e LGPD](https://delgrande.com.br/blog/como-adequar-a-gravacao-de-ligacao-a-lgpd/)
- [AI Act — artigo 50](https://artificialintelligenceact.eu/article/50/)
- [Comissão Europeia — FAQ art. 50](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act)
- [MarketsandMarkets — voice AI cold call](https://www.marketsandmarkets.com/AI-sales/voice-ai-can-agents-successfully-cold-call)
