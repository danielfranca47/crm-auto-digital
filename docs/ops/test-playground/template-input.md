
> Copiar este ficheiro, renomear para `<nome-cenario>-input.md` e preencher.

---

## 1. Configuração do Bot

| Campo | Valor |
|---|---|
| `name` | _(nome interno do perfil, ex: "Consultor Imobiliário")_ |
| `brand_name` | _(nome da marca/empresa)_ |
| `agent_name` | _(nome do agente, ex: "Sofia")_ |
| `agent_mode` | _(consultivo / agenda / direto)_ |
| `template_key` | _(sdr_padrao / consultor_especialista / closer_agressivo / hybrid_scheduler)_ |
| `response_style` | _(active \| passive — `passive`: agente responde perguntas directas antes de qualificar; `active` padrão: qualifica primeiro)_ |
| `qualification_required_fields` | _(lista JSON de campos obrigatórios, ex: `["service_interest","availability_window"]`; `null` = usa defaults do modo; `[]` = sem qualificação obrigatória)_ |
| `tone_of_voice` | _(ex: profissional, próximo, directo)_ |
| `niche` | _(ex: Imobiliário de luxo)_ |
| `target_audience` | _(ex: Investidores com capital > 500k)_ |
| `offer_description` | _(descrição da oferta principal — incluir tabela de preços se aplicável)_ |
| `goals` | _(ex: Qualificar e agendar visita ao imóvel)_ |
| `custom_instructions` | _(instruções adicionais ao agente — numeradas, uma por linha)_ |

> **Notas de configuração:**
> - `response_style=passive` é recomendado para negócios B2C onde o cliente chega com perguntas (serviços, preços, localização). O agente responde primeiro e qualifica depois de forma natural.
> - `qualification_required_fields` permite remover campos inadequados para o nicho (ex: `price_acceptance` para negócios com preço fixo, `location_preference` para gabinetes físicos).
> - Se `qualification_required_fields=[]`, o agente não bloqueia progressão por qualificação — útil para negócios de alta confiança onde a qualificação é implícita.

---

## 2. Cenários de Teste

> Definir 1 a 3 cenários. Cada cenário é uma conversa independente com um lead sandbox.

### Cenário A — _(nome descritivo, ex: "Cliente normal pergunta e agenda")_

_(Descrição breve do perfil do cliente e da situação)_

| # | Mensagem do Cliente |
|---|---|
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |

**Comportamento esperado:**
- Turno 1:
- Turno 2:
- Turno 3:
- Turno 4:
- Turno 5:

---

### Cenário B — _(opcional)_

| # | Mensagem do Cliente |
|---|---|
| 1 | |
| 2 | |
| 3 | |

**Comportamento esperado:**
- Turno 1:
- Turno 2:
- Turno 3:

---

### Cenário C — _(opcional)_

| # | Mensagem do Cliente |
|---|---|
| 1 | |
| 2 | |
| 3 | |

**Comportamento esperado:**
- Turno 1:
- Turno 2:
- Turno 3:

---

## 3. O que Avaliar

### Validação de fixes específicos (preencher conforme fixes activos)
- [ ] **response_style=passive:** agente responde perguntas directas antes de qualificar?
- [ ] **qualification_required_fields:** nenhuma pergunta sobre campos removidos da lista?
- [ ] **Sinais de fecho:** quando cliente confirma ("fica combinado", "pode ser"), agente avança para agendamento?

### Qualidade geral
- [ ] O agente qualifica os campos correctos para o `agent_mode`?
- [ ] A progressão de categoria (qualification → apresentation/closing) acontece quando esperado?
- [ ] O tom e a linguagem estão alinhados com o `tone_of_voice` configurado?
- [ ] A oferta é apresentada no momento adequado?
- [ ] `custom_instructions` são respeitadas (especialmente instruções críticas)?
- [ ] O agente envia confirmação estruturada de reserva/agendamento?
- [ ] Outros: ___

---

## 4. Notas do Operador

_(contexto adicional, hipóteses a testar, comportamentos esperados, critérios de aprovação)_

**Critério de aprovação:** ≥ _/_ turnos correctos.
