# Massagem Sensi Vitae — Input

> Teste real do playground. Nicho: terapias de massagem em Faro, Portugal.
> Baseado em conversas reais do terapeuta Daniel com clientes via WhatsApp.
> **Teste 3 — 2026-04-01:** configuração actualizada com Fix #4 (`qualification_required_fields`) + Fix #5 (passive mode corrigido) + Fix #6 (sinais de fecho).
> **Teste 4 — 2026-04-01:** configuração actualizada com Fix #9 (`presentation_variant=scheduler` para eliminar tom SDR/B2B).

---

## 1. Configuração do Bot

| Campo | Valor |
|---|---|
| `name` | Assistente Sensi Vitae |
| `brand_name` | Sensi Vitae |
| `agent_name` | Daniel |
| `agent_mode` | `agenda` |
| `template_key` | `hybrid_scheduler` |
| `response_style` | `passive` ← **Fix #5: modo passivo corrigido** |
| `presentation_variant` | `scheduler` ← **Fix #9: reserva de sessão presencial — sem linguagem SDR/B2B** |
| `qualification_required_fields` | `["service_interest", "availability_window"]` ← **Fix #4: remove price_acceptance** |
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

## 3. O que Avaliar — Teste 3

### Validação dos novos fixes (critérios obrigatórios)
- [ ] **Fix #5 (passive mode):** T1 apresenta serviços e valores sem pedir disponibilidade primeiro?
- [ ] **Fix #5 (passive mode):** T2 responde "Sim, fica em Faro" antes de perguntar qualquer coisa?
- [ ] **Fix #4 (qualification_required_fields):** Nenhuma pergunta sobre "que valor pretende investir"?
- [ ] **Fix #6 (sinais de fecho):** T5 "Perfeito, fica combinado" → agente envia confirmação (não pede mais campos)?
- [ ] **Fix #9 (presentation_variant=scheduler):** Tom acolhedor de spa — sem "mapear situação", "plano de ação", "cliente com o teu perfil" ou linguagem SDR/B2B?

### Qualidade geral
- [ ] O agente apresenta os serviços e valores correctamente (Terapêutica, Exótica, Lingam)?
- [ ] O tom é acolhedor e usa "querido/a" de forma natural?
- [ ] O agente lida com pedido de "final feliz" sem rejeitar — redireciona para Finalização Lingam?
- [ ] O agente envia confirmação estruturada da reserva (experiência, horário, dia, massagista)?
- [ ] O agente é flexível mas firme quando um horário não está disponível (Cenário C)?
- [ ] As informações práticas (localização, Sala 2, duche) são fornecidas quando pedidas?


---

## 4. Notas do Operador

- **Teste 3** — foco em validar Fix #4, Fix #5 e Fix #6. Cenários A, B e C são os mesmos dos testes anteriores para permitir comparação directa.
- Os cenários foram baseados em conversas reais do WhatsApp do Daniel.
- **Configuração obrigatória antes do teste:**
  1. Confirmar `response_style=passive` no ai_profile (campo adicionado no Fix #3)
  2. Definir `qualification_required_fields=["service_interest","availability_window"]` (campo adicionado no Fix #4)
  3. Definir `presentation_variant=scheduler` no ai_profile — via UI (Camada 5 → Objetivo do agendamento → Agendamento Exploratório) ou directamente na BD
  4. Após definir `presentation_variant`, limpar `generated_prompt_parts=null` no ai_profile e aguardar re-geração automática pelo meta-prompter (ou forçar via POST `/meta-prompter/regenerate`)
  5. Reiniciar backend-executors para carregar o código dos fixes
- O cenário B é o mais crítico para `custom_instructions`: "final feliz" → Finalização Lingam sem linguagem sexualizada.
- O cenário C testa firmeza de horário sem perder o tom acolhedor.
- **Critério de aprovação do Teste 3:** ≥ 7/10 turnos correctos + todos os critérios obrigatórios da checklist do `otimizacao.md`.
- **Funcionalidade a observar:** confirmação estruturada tipo recibo (✅ Experiência Reservada / Experiência / Horário / Dia / Massagista) — confirmar se acontece após Fix #6.
- Idioma: Português de Portugal com influência brasileira leve (o Daniel é brasileiro a viver em Portugal).
