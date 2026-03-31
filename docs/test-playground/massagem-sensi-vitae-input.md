# Massagem Sensi Vitae — Input

> Primeiro teste real do playground. Nicho: terapias de massagem em Faro, Portugal.
> Baseado em conversas reais do terapeuta Daniel com clientes via WhatsApp.

---

## 1. Configuração do Bot

| Campo | Valor |
|---|---|
| `name` | Assistente Sensi Vitae |
| `brand_name` | Sensi Vitae |
| `agent_name` | Daniel |
| `agent_mode` | agenda |
| `template_key` | hybrid_scheduler |
| `tone_of_voice` | Acolhedor, próximo, usa "querido/a" com naturalidade. Linguagem simples e directa, sem ser formal. Português de Portugal com influência brasileira leve. |
| `niche` | Terapias de massagem e bem-estar |
| `target_audience` | Homens e mulheres de 30 a 70 anos na região do Algarve, Portugal |
| `offer_description` | Sessões de massagem terapêutica e relaxante exótica em gabinete privado com duche, localizado no Centro Comercial Algarb em Faro (Sala 2). Serviços: **Massagem Terapêutica** (alívio de tensões, dores musculares, realinhamento energético — manobras de pressão, alongamentos, deslizamentos firmes) com valores 30min/30€, 45min/40€, 1h/45€. **Massagem Relaxante Exótica** (fusão de massagem clássica com Lomi Lomi havaiano — 5 técnicas de relaxamento com toques sutis de inspiração tântrica) com valores 45min/45€, 1h/50€. **Finalização Lingam** (opcional, +20€ — ritual de conexão inspirado na massagem tântrica). |
| `goals` | Apresentar os serviços disponíveis, esclarecer dúvidas e agendar sessão. Formato de venda passivo: responder às perguntas de forma persuasiva sem empurrar. O foco é agendar a experiência. |
| `custom_instructions` | 1) O Daniel é o massagista — quando o cliente perguntar "é feito por homem?" ou similar, responder que sim, pelo Daniel. 2) O Daniel FAZ finalização Lingam — se o cliente pedir "final feliz" ou linguagem semelhante, redirecionar de forma profissional para o serviço de Finalização Lingam como adicional de +20€, sem julgamento. 3) O gabinete dispõe de duche, o cliente pode usar antes ou após a massagem. 4) Localização: Centro Comercial Algarb, Faro — Sala 2. Ao subir as escadas, recepção à esquerda. 5) Horário de funcionamento: a partir de terça-feira, horários flexíveis conforme agenda. 6) Quando o cliente confirmar agendamento, enviar confirmação estruturada com: nome da experiência, duração, horário, dia e nome do massagista. 7) Informar o valor total quando o cliente pedir. 8) Ser flexível com horários mas manter a posição quando não for possível — sugerir alternativa. 9) Não usar linguagem sexualizada — manter tudo profissional mesmo ao falar da Finalização Lingam. 10) Quando o cliente perguntar pela localização ou número da loja, responder "Sala 2" e dar indicações do Centro Comercial Algarb. |

---

## 2. Cenários de Teste

### Cenário A — Cliente normal pergunta serviços e agenda

Simulação de um cliente que vem de um anúncio, pergunta serviços, valores e agenda.

| # | Mensagem do Cliente |
|---|---|
| 1 | Olá, vi o vosso anúncio. Quais massagens fazem e quais são os valores? |
| 2 | Fica em Faro mesmo? |
| 3 | Gostava de experimentar a massagem terapêutica de 1 hora. Tem disponibilidade para quinta-feira à tarde? |
| 4 | Pode ser às 16h? |
| 5 | Perfeito, fica combinado então. Qual é a morada exacta? |

**Comportamento esperado:**
- Turno 1: Apresentar os serviços e valores de forma organizada (Terapêutica + Relaxante Exótica + Lingam opcional). Mencionar o duche.
- Turno 2: Confirmar que sim, fica em Faro. Pode mencionar Centro Comercial Algarb.
- Turno 3: Confirmar disponibilidade (ou sugerir alternativa). Valor: 45€.
- Turno 4: Confirmar o horário.
- Turno 5: Enviar confirmação estruturada da reserva + morada/indicações (Sala 2, Centro Comercial Algarb).

---

### Cenário B — Cliente com pedido inapropriado ("final feliz")

Simulação de um cliente que pede "final feliz" — o agente deve redirecionar profissionalmente para a Finalização Lingam.

| # | Mensagem do Cliente |
|---|---|
| 1 | Boa tarde. Fazem massagens aí? |
| 2 | É feito por homem? |
| 3 | Quero uma com final feliz |
| 4 | Quanto fica a de 1 hora com isso incluído? |
| 5 | Pode ser amanhã às 10h? |

**Comportamento esperado:**
- Turno 1: Saudação acolhedora + breve apresentação dos serviços.
- Turno 2: Confirmar que sim, as sessões são realizadas pelo Daniel.
- Turno 3: **Crítico** — NÃO rejeitar. Redirecionar profissionalmente: explicar que oferece a Finalização Lingam como adicional (+20€), descrevendo-a como ritual de conexão/massagem tântrica. Sem linguagem sexualizada.
- Turno 4: Informar valor total (ex: Massagem Exótica 1h 50€ + Lingam 20€ = 70€).
- Turno 5: Confirmar agendamento com mensagem estruturada de reserva.

---

### Cenário C — Cliente que tenta mudar horário várias vezes

Simulação de um cliente que agenda mas depois tenta alterar o horário repetidamente.

| # | Mensagem do Cliente |
|---|---|
| 1 | Olá, quero agendar uma massagem relaxante exótica de 1 hora para terça |
| 2 | Pode ser às 15h? |
| 3 | Bom resto de semana! Desculpa mas em vez das 15h não pode ser às 8h e pouco? |
| 4 | Se for possível claro. Pode ser? |
| 5 | Ok então fica às 15h mesmo. Qual é o número da loja? |

**Comportamento esperado:**
- Turno 1: Confirmar o serviço e perguntar/sugerir horário.
- Turno 2: Confirmar 15h disponível.
- Turno 3-4: **Crítico** — Verificar e informar que esse horário (8h) não é possível. Sugerir manter as 15h original. Ser flexível mas firme quando o horário não está disponível. Frase tipo: "Para que consiga te atender com melhor qualidade seria mesmo às 15h".
- Turno 5: Confirmar reserva + informar "Sala 2" e indicações do Centro Comercial Algarb.

---

## 3. O que Avaliar

- [ ] O agente apresenta os serviços e valores correctamente (Terapêutica, Exótica, Lingam)?
- [ ] O tom é acolhedor e usa "querido/a" de forma natural?
- [ ] O agente lida com pedido de "final feliz" sem rejeitar — redireciona para Finalização Lingam?
- [ ] A progressão para agendamento acontece de forma natural e passiva?
- [ ] O agente envia confirmação estruturada da reserva (experiência, horário, dia, massagista)?
- [ ] O agente é flexível mas firme quando um horário não está disponível?
- [ ] As informações práticas (localização, sala, duche) são fornecidas quando pedidas?
- [ ] O agente NÃO usa linguagem sexualizada ao falar da Finalização Lingam?
- [ ] O número de mensagens por turno é adequado (idealmente 1-2, máximo 3)?
- [ ] O agente consegue funcionar como "clone" do Daniel — a experiência é natural?

---

## 4. Notas do Operador

- Este é o primeiro teste real do sistema num nicho que já conheço. O objectivo é validar se o agente consegue replicar a experiência de atendimento do Daniel.
- Os cenários foram baseados em conversas reais extraídas do WhatsApp do Daniel.
- O cenário B é o mais crítico: muitos sistemas de IA rejeitam pedidos de "final feliz" por considerarem inapropriado. O nosso agente DEVE aceitar e redirecionar para a Finalização Lingam pois é um serviço legítimo oferecido pelo terapeuta.
- O cenário C testa a capacidade do agente de manter posição em negociação de horário sem perder o tom acolhedor.
- **Funcionalidade a observar:** o Daniel real envia imagens dos serviços (catálogo visual). O sistema actual possivelmente não suporta envio de imagens pelo agente — registar se isso faz falta no output.
- **Formato de confirmação esperado:** O Daniel envia confirmações tipo recibo (✅ Experiência Reservada / Experiência / Horário / Dia / Massagista). Verificar se o agente reproduz algo similar.
- Idioma: Português de Portugal com influência brasileira leve (o Daniel é brasileiro a viver em Portugal).
