# Cold Call Script — Lara: Sistema de Vendas 24/7
**Agentes:** hormozi-chief · hormozi-leads · hormozi-closer
**Data:** 2026-06-21 | **Status:** v1.0

---

## 🐝 HORMOZI CHIEF — Diagnóstico e Roteamento

### Onde isso se encaixa

```
Oferta:               8.5/10 ✅  Já construída (grand-slam-offer.md)
Pricing:              ✅          Campanha Fundador R$147/mês ativa
Canal Warm:           ✅          Scripts de voz/texto já existem (plano-tatico)
Canal Cold (texto):   ✅          Scripts de WhatsApp já existem (Script 3, plano-tatico)
Canal Cold (LIGAÇÃO): ❌          NÃO EXISTE — é isso que este documento resolve
```

**Diagnóstico:** este não é um problema de oferta nem de pricing — os dois já estão prontos.
É um problema de **canal**: falta o roteiro para o canal de voz (telefone), que é mais
intrusivo e tem uma física diferente do WhatsApp (você tem ~10 segundos antes de ser
desligado, contra um texto que a pessoa lê quando quiser).

**Importante — isso não substitui o que já existe:**
- O CLOSER script do `plano-tatico-20-clientes-60-dias.md` é para **demo já agendada** (a pessoa já disse sim para conversar).
- Este documento é para a **ligação fria** — a pessoa não sabe que você vai ligar. A abertura muda tudo; o resto do framework (CLOSER) se mantém.
- Isso também é o precursor manual do bloqueador #5 do Plano Tático ("Cold call AI outbound — em desenvolvimento"): rodar esse script manualmente primeiro valida o que funciona antes de qualquer automação.

### Roteamento

| Etapa | Agente | Framework |
|-------|--------|-----------|
| Estratégia, listas, metas de volume | hormozi-leads | Core 4 — Cold Outreach |
| Estrutura da ligação e fechamento | hormozi-closer | CLOSER (adaptado para abertura fria) |

### Regra de sequência (não pular etapas)

> A ligação fria é a **Fase 3** do seu Plano Tático (semana 5–8), depois de esgotar
> warm outreach e referrals. Se você ainda tem professor, ex-clientes ou indicações
> sem contatar, ligue para eles primeiro — é gratuito e converte mais. Cold call é para
> expandir o volume quando o warm não for suficiente para a meta.

---

## 🧲 HORMOZI LEADS — Estratégia de Cold Call (Core 4 aplicado a telefone)

### Por que ligação, e não só texto

```
Texto (WhatsApp):  Fricção baixa para enviar, fricção baixa para ignorar.
                   Você manda 30 e recebe 2 respostas.

Ligação:           Fricção alta para atender, mas se atender, você qualifica
                   ou desqualifica em 90 segundos — sem esperar resposta de texto
                   por 3 dias. Voz constrói confiança mais rápido que texto.

Regra Hormozi Leads: os dois canais não competem — ligação é para quem não
respondeu o texto, ou para listas de maior intenção (ex: imóveis, alto ticket,
onde 1 cliente vale o esforço de discar).
```

### Fontes de lista por avatar

| Avatar (agente) | Segmentos | Onde encontrar a lista | Melhor horário para ligar |
|---|---|---|---|
| **Híbrido Agendador** | Massoterapia, psicólogos, dentistas, terapeutas, clínicas | Google Maps ("massoterapeuta SP", "psicólogo + bairro"), Instagram Business | 9h–11h ou 14h–16h (fora de horário de atendimento) |
| **SDR** | Imóveis, consultoria, coaching, assessoria | Instagram/LinkedIn de corretores e consultores, grupos de nicho, CRECI público | 10h–12h ou 16h–18h |
| **Closer** | Infoprodutos, e-commerce, lojas físicas | Lojas no Instagram/Shopify com anúncio ativo, grupos de empreendedores digitais | 11h–13h ou 19h–21h (fora do expediente "tradicional", público mais digital) |

### Qualificador pré-call (não perder tempo discando errado)

Reaproveitando o qualificador já validado na oferta — **NÃO ligue para quem**:

```
✗ Recebe menos de 20 leads/clientes por mês no WhatsApp
  → O ROI da Lara não fecha com volume baixo. Vai ouvir "não preciso disso".

✗ Não tem WhatsApp Business ativo / atende só por telefone fixo
  → Produto não serve. Desqualificar antes de discar economiza o dia.

✗ Já é claramente grande demais (rede, franquia com call center próprio)
  → Ciclo de decisão muda completamente — não é fit para ligação fria de fundador solo.
```

### Tática de aquecimento pré-call (aumenta taxa de atendimento)

```
1–2 dias antes de ligar, mande uma mensagem curta (texto ou Instagram):
"Oi [Nome], vou te ligar rapidinho [dia] sobre algo que pode reduzir
[falta de pacientes / lead que esfria / carrinho abandonado] no seu negócio.
2 minutos, sem compromisso."

Por que funciona (Hormozi Leads): a pessoa já viu seu nome quando o telefone
toca — você não é mais 100% desconhecido. Taxa de atendimento sobe.
```

### Metas de volume — Sales Math aplicado

```
Regra Hormozi: cold outreach é jogo de volume. Mas ligação tem custo de tempo
maior que texto — defina volume pelo tempo disponível, não por uma meta arbitrária.

Cenário Founder solo (1–2h/dia dedicadas a discar):
  20–25 ligações/dia → 100–125 ligações/semana

Cenário com ajuda (você + 1 pessoa fazendo follow-up de texto):
  40–60 ligações/dia → 200–300 ligações/semana
```

---

## 🤝 HORMOZI CLOSER — O Script Completo de Cold Call

### Princípio: o objetivo da ligação fria NÃO é vender no telefone

```
Regra Hormozi Closer: numa ligação fria você tem 2 saídas boas — nunca force
uma terceira:

  MICRO-CLOSE (padrão, 90% dos casos):
    Agendar a demo de 15 minutos (ao vivo ou no Sandbox/Playground).

  MACRO-CLOSE (quando a pessoa já está convencida na ligação):
    Ativar na hora com a oferta Fundador — só se ELA empurrar pra isso,
    nunca force fechamento de cartão no meio de uma ligação não-agendada.

Por quê: fechar uma venda de R$147–297/mês com alguém que não sabe quem você
é há 90 segundos é raro e, quando forçado, gera reembolso e cancelamento.
Diagnosticar e agendar é o jogo certo no frio. Fechar é o jogo certo no warm.
```

### Estrutura universal (CLOSER comprimido para ligação fria)

```
0. ABERTURA (10–15s) — pattern interrupt + permissão. Se não passar daqui, acabou.
1. RAZÃO DA LIGAÇÃO (15s) — específica ao negócio dela, não genérica.
2. C - CLARIFY (1–2 perguntas, não 5 — tempo é curto no frio)
3. L - LABEL (1 frase — mostra que entendeu)
4. O - OVERVIEW (1 pergunta de custo de inação)
5. S - SELL (a vacation, comprimida — 30 segundos, sem demo completa)
6. E - EXPLAIN (objeções de cold call, ver abaixo)
7. R - REINFORCE/CLOSE (assumptive close pra demo ou ativação)
```

---

### 🅰️ Script A — Híbrido Agendador (serviços com agendamento)
*Massoterapia, psicólogos, dentistas, terapeutas, clínicas, escolas/cursos com matrícula*

```
ABERTURA:
"Oi, [Nome]? Aqui é o [seu nome] — você tem 30 segundos? Ligo rápido e se
não fizer sentido pra você, te deixo em paz."

[espera o "sim"/"pode falar"]

RAZÃO DA LIGAÇÃO:
"Perfeito. Vi seu [consultório/clínica] no [Google Maps/Instagram] — trabalho
com um sistema que ajuda [massoterapeutas/psicólogos/dentistas] a parar de
perder sessão por falta de confirmação, sem precisar de recepcionista.
Posso te fazer uma pergunta rápida sobre isso?"

C — CLARIFY:
"Hoje, quando um paciente não responde a confirmação de sessão,
o que costuma acontecer — ele simplesmente não aparece?"
"Numa semana normal, quantas faltas ou cancelamentos de última hora você tem?"

L — LABEL:
"Então pelo que você me disse, o problema não é só a falta em si —
é que não tem um processo automático cobrando confirmação, então quando
alguém esquece, você só descobre na hora da sessão vazia. Isso é justo?"

O — OVERVIEW:
"Se cada falta é uma sessão de R$[valor] perdida, e você tem [X] faltas
por mês — isso é R$[cálculo] por mês que já era seu. Em 12 meses, isso vira
R$[X×12]. Isso pesa?"

S — SELL (comprimido):
"É exatamente isso que o agente Híbrido Agendador resolve. Ele manda
confirmação automática, faz até 1 follow-up educado, e se a pessoa some,
ele tenta reconectar — tudo no WhatsApp do seu número, 24h por dia.
Uma colega sua reduziu de 20% pra 3% de faltas em 14 dias.
Recepcionista custa R$2.200/mês. Isso custa R$297 e nunca falta."

E — EXPLAIN (ver objeções de cold call abaixo)

R — REINFORCE / CLOSE:
"Olha, em vez de eu te explicar tudo por telefone, deixa eu te mostrar
funcionando — é uma demo de 15 minutos, sem compromisso. Prefere
[amanhã de manhã] ou [quinta à tarde]?"
```

---

### 🅱️ Script B — SDR (alto ticket)
*Imóveis, consultoria, coaching, assessoria*

```
ABERTURA:
"Oi, [Nome]? Aqui é o [seu nome] — tem 30 segundos? Ligo rápido."

RAZÃO DA LIGAÇÃO:
"Vi seu perfil no [Instagram/site] — você trabalha com [imóveis/consultoria].
Ajudo gente como você a não perder lead de alto ticket por demora na resposta.
Posso te perguntar uma coisa rápida?"

C — CLARIFY:
"Hoje, quando entra um lead novo pelo WhatsApp, quem responde primeiro —
você, ou alguém do seu time?"
"E quando o lead demora pra ser respondido, o que costuma acontecer com ele?"

L — LABEL:
"Então o problema não é falta de lead — é que sem resposta rápida e
follow-up, um lead de R$[ticket médio] esfria antes de virar reunião.
Faz sentido?"

O — OVERVIEW:
"Se você recebe [X] leads por mês e perde [Y]% por demora, isso é
[Z] oportunidades de R$[ticket] que você nem sabe que perdeu. Isso te
incomoda?"

S — SELL (comprimido):
"É isso que o agente SDR faz: responde em segundos, qualifica e agenda
reunião só com quem está quente — você só entra pra fechar.
SDR humano custa R$3.500/mês. A Lara SDR custa R$297 e nunca dorme."

E — EXPLAIN (ver objeções de cold call abaixo)

R — REINFORCE / CLOSE:
"Deixa eu te mostrar isso agendando uma reunião sozinho, em tempo real —
15 minutos. [Amanhã 10h] ou [quinta 16h], qual funciona melhor pra você?"
```

---

### 🅲 Script C — Closer (baixo ticket)
*Infoprodutos, e-commerce, lojas físicas*

```
ABERTURA:
"Oi, [Nome]? Aqui é o [seu nome] — 30 segundos, ligo rápido."

RAZÃO DA LIGAÇÃO:
"Vi sua loja/produto no [Instagram]. Trabalho com um sistema que recupera
carrinho abandonado e fecha venda direto no WhatsApp, sem você estar online.
Posso te fazer uma pergunta sobre isso?"

C — CLARIFY:
"Hoje, quando alguém some no meio de uma compra ou some depois de
perguntar o preço, você tem algum processo de recuperação, ou perde o
contato?"
"Quantas dessas conversas 'mortas' você acha que tem, num mês normal?"

L — LABEL:
"Então o que está acontecendo é: o lead até demonstrou interesse, mas sem
follow-up ele esfria e você nunca mais ouve falar dele. Isso bate com a
sua realidade?"

O — OVERVIEW:
"Se 1 em cada [X] desses fechasse com um follow-up automático, a R$[ticket]
cada, isso é R$[cálculo] por mês que está ficando na mesa. Faz sentido
recuperar isso?"

S — SELL (comprimido):
"O agente Closer conversa do 'oi' até o pagamento, manda foto/vídeo do
produto, e faz follow-up de quem parou de responder — tudo automático.
1 venda extra por mês já paga o mês inteiro da Lara."

E — EXPLAIN (ver objeções de cold call abaixo)

R — REINFORCE / CLOSE:
"Posso te mostrar funcionando agora numa demo rápida de 15 minutos —
sem compromisso. Prefere hoje à tarde ou amanhã de manhã?"
```

---

### Objeções específicas de Cold Call

*Diferentes das objeções de demo já agendada (que estão no plano-tatico). Estas são as que aparecem ANTES da pessoa decidir te dar atenção.*

```
"Como você conseguiu meu número?"
→ "Vi no [Google Maps/Instagram do seu negócio] — é o contato que você
   deixa público pra clientes. Não é nada privado, prometo."

"Não tenho tempo agora"
→ "Sem problema. Posso te ligar [em 1h] ou [amanhã nesse horário]?
   Ou, se preferir, te mando uma mensagem com a ideia e você vê quando puder."

"Manda por WhatsApp / e-mail"
→ "Mando, sim! Só me deixa te fazer 1 pergunta rápida pra eu mandar a
   coisa certa pro seu caso, não um texto genérico — [pergunta de Clarify]"

"Já uso outro sistema / já tenho um processo"
→ "Que bom que você já pensa nisso. Posso perguntar — esse processo
   também faz follow-up automático de quem não respondeu, ou é manual?"
   [a resposta geralmente revela o gap — segue pro Label]

"Quanto custa?" (perguntado cedo demais)
→ "Depende do agente que faz sentido pro seu caso — pra te dar um número
   justo eu preciso entender sua situação primeiro. Posso te perguntar
   uma coisa rápida?" [volta pro Clarify]

"Não atendo ligação de vendas / tira meu contato da lista"
→ "Entendido, sem problema nenhum. Não vou mais te ligar. Tenha um bom dia."
   [SEMPRE respeitar imediatamente — sem insistir, sem segunda tentativa
   de convencer. Pressão aqui queima a reputação, não converte.]
```

### Voicemail / caixa postal (curto, sem pitch completo)

```
"Oi [Nome], aqui é o [seu nome]. Te ligo rapidinho sobre uma forma de
[parar de perder sessão por falta / responder lead mais rápido /
recuperar carrinho abandonado] sem contratar mais ninguém.
Vou te mandar uma mensagem no WhatsApp também — qualquer coisa, me chama."

[SEMPRE seguir com o texto de aquecimento na sequência — nunca deixar
só o voicemail sem o toque de texto]
```

### Cadência de follow-up (ligação + texto combinados)

| Tentativa | Ação | Quando |
|-----------|------|--------|
| 1ª | Ligação | Dia 0, horário ideal do avatar |
| Se não atender | Texto curto + voicemail (se caiu) | Imediatamente após |
| 2ª | Ligação em outro horário do dia | Dia 0 ou Dia 1 |
| 3ª | Ligação | Dia 3 |
| Se engajou mas não fechou demo | Lead magnet grátis (script de confirmação/scripts prontos) | Dia 5 |
| Última tentativa | "Estou encerrando a campanha Fundador [data]" | Dia 7 |
| Encerramento | Pedido de indicação, sem pitch | Dia 14 |

> **Regra Hormozi Closer:** 80% das vendas acontecem depois do 5º contato — não desista na 2ª ligação. Reaproveite a sequência D+1/D+3/D+5/D+7/D+14 já validada no Plano Tático.

---

## 📊 Sales Math — Funil e Metas

### Funil estimado (calibrar com dados reais após a 1ª semana)

| Etapa | Taxa estimada | Sobre 100 ligações discadas |
|-------|---------------|------------------------------|
| Atende a ligação | 20–30% | 20–30 contatos |
| Engaja além da abertura (não desliga) | 50–60% | 10–18 conversas |
| Aceita agendar demo | 25–35% | 3–6 demos agendadas |
| Show rate da demo | 70% (meta já validada) | 2–4 demos realizadas |
| Close rate a frio | 10–15% (meta já validada no hormozi-closer) | + os que fecham depois via nutrição D+1→D+14 |

```
Leitura prática: ~100 ligações → 1–2 clientes fechados direto na sequência
de demo, MAIS uma fração adicional que fecha via follow-up (a maioria das
vendas vem do 5º+ contato, não da ligação inicial).
```

### Quanto ligar para bater a meta

```
Meta do Plano Tático — Fase 3 (Semana 5–8): +8–10 clientes via cold + content.

Cenário conservador (founder solo, 20-25 ligações/dia):
  100–125 ligações/semana × 4 semanas = 400–500 ligações
  → ~4–7 clientes diretos da ligação + contribuição da nutrição = dentro da meta.

Cenário acelerado (com apoio para follow-up, 40-60 ligações/dia):
  200–300 ligações/semana × 4 semanas = 800–1.200 ligações
  → margem para bater o cenário agressivo do plano (23 clientes).
```

> **Alavanca real:** não é o volume de ligações — é o **show rate** e o **close
> rate** da demo. +5% no close rate já vale mais que dobrar o volume discado
> (mesma regra do Sales Math no plano-tatico). Grave suas ligações (com aviso)
> e revise toda semana o que fez a pessoa engajar ou desligar.

---

## ✅ Checklist de Execução Diária

```
Antes de começar:
[ ] Lista do dia qualificada (≥20 leads/mês no WhatsApp, segmento certo)
[ ] Mensagem de aquecimento enviada 1–2 dias antes (quando possível)
[ ] Script do avatar certo em mãos (A, B ou C)

Durante:
[ ] Abertura + permissão SEMPRE primeiro — nunca pular pro pitch
[ ] Anotar as palavras exatas que a pessoa usa (vira ammunition pro Label/Sell)
[ ] Meta da ligação = agendar demo, não vender no telefone
[ ] Respeitar imediatamente quem pedir para não ligar de novo

Depois:
[ ] Registrar resultado no CRM (atendeu / engajou / agendou / recusou)
[ ] Disparar o texto de follow-up correspondente no mesmo dia
[ ] Revisar 1x por semana: taxa de atendimento, engajamento, agendamento
```

---

*Produzido por: hormozi-chief (diagnóstico e roteamento) · hormozi-leads (estratégia de canal, listas, metas) · hormozi-closer (scripts CLOSER adaptados para ligação fria, objeções, cadência)*
*Complementa: `plano-tatico-20-clientes-60-dias.md` (Fase 3 — Cold Outreach) e `grand-slam-offer.md` / `pricing-strategy.md` (avatares, âncoras de valor)*
*Arquivo: `C:\crm-auto-digital\docs\marketing\cold-call-script.md`*
