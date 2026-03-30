# [Nome do Cenário] — Input

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
| `tone_of_voice` | _(ex: profissional, próximo, directo)_ |
| `niche` | _(ex: Imobiliário de luxo)_ |
| `target_audience` | _(ex: Investidores com capital > 500k)_ |
| `offer_description` | _(descrição da oferta principal)_ |
| `goals` | _(ex: Qualificar e agendar visita ao imóvel)_ |
| `custom_instructions` | _(instruções adicionais ao agente — opcional)_ |

---

## 2. Conversa a Simular

Mensagens do cliente em sequência. O agente responde após cada uma.

| # | Mensagem do Cliente |
|---|---|
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |

> Adicionar ou remover linhas conforme necessário.

---

## 3. O que Avaliar

- [ ] O agente qualifica os campos correctos para o `agent_mode`?
- [ ] A progressão de categoria (qualification → closing) acontece quando esperado?
- [ ] O tom e a linguagem estão alinhados com o `tone_of_voice` configurado?
- [ ] A oferta é apresentada no momento adequado?
- [ ] Outros: ___

---

## 4. Notas do Operador

_(contexto adicional, hipóteses a testar, comportamentos esperados)_
