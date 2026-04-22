# Planos e Modelo de Negócio — AutoDigital

## Modelo de cobrança

**Híbrido (plano + consumo):** cada plano inclui uma franquia fixa de conversas IA por mês. Conversas além da franquia são cobradas individualmente.

**Infraestrutura WhatsApp:** Uazapi (API não oficial) — ~R$79/mês por instância. Sem taxa por mensagem da Meta.

**Custo médio estimado por conversa IA:** ~R$0,06 (modelo Sonnet). Esses numeros podem ser diferente  

**Agentes disponíveis em todos os planos** — SDR, Closer, Hybrid. Não é limitação de plano, é escolha estratégica.

---

## Fase 1 — Lançamento imediato (1 instância por cliente)

### Plano Start — R$97/mês
Público: profissionais solo, micro-negócios, validação.

| Recurso | Limite |
|---|---|
| Instâncias WhatsApp | 1 |
| Conversas IA/mês | 250 |
| Contatos no CRM | 500 |
| Follow-up automatizado | ❌ |
| Playground de testes | ❌ |
| Analytics avançados | ❌ |
| Excedente por conversa | R$0,60 |

> Follow-up excluído intencionalmente para criar alavanca de upgrade.

### Plano Growth — R$197/mês (Recomendado)
Público: negócios que validaram e querem a experiência completa.

| Recurso | Limite |
|---|---|
| Instâncias WhatsApp | 1 |
| Conversas IA/mês | 500 |
| Contatos no CRM | 1.500 |
| Follow-up automatizado | ✅ |
| Playground de testes | ✅ |
| Analytics avançados | ✅ |
| Excedente por conversa | R$0,50 |

---

## Fase 2 — Após implementar multi-instância

### Plano Scale — R$397/mês
| Recurso | Limite |
|---|---|
| Instâncias WhatsApp | Até 3 |
| Conversas IA/mês | 1.500 |
| Contatos no CRM | 5.000 |
| Instância adicional | R$99/mês cada |
| Excedente por conversa | R$0,40 |

### Plano Enterprise — R$697/mês
| Recurso | Limite |
|---|---|
| Instâncias WhatsApp | Até 5 |
| Conversas IA/mês | 5.000 |
| Contatos no CRM | 15.000 |
| Instância adicional | R$89/mês cada |
| Excedente por conversa | R$0,30 |

---

## Definições técnicas para implementação

### O que conta como "conversa IA"
- Agente gera e envia pelo menos 1 resposta
- Janela de sessão sugerida: 24h (novo contato após 24h de inatividade = nova conversa)

### Modelo de dados sugerido (`subscription`/`user_plan`)
```
- user_id (FK)
- plan_slug: "start" | "growth" | "scale" | "enterprise"
- status: "active" | "past_due" | "cancelled" | "trialing"
- max_conversations_month: 250 | 500 | 1500 | 5000
- max_contacts: 500 | 1500 | 5000 | 15000
- max_instances: 1 | 1 | 3 | 5
- follow_up_enabled: false | true | true | true
- playground_enabled: false | true | true | true
- advanced_analytics: false | true | true | true
- overage_price_per_conversation: 0.60 | 0.50 | 0.40 | 0.30
- current_month_conversations: int
- current_contacts_count: int
- billing_cycle_start: date
```

### Controle de funcionalidades por plano

| Funcionalidade | Start | Growth | Scale | Enterprise |
|---|---|---|---|---|
| Conversa IA | ✅ | ✅ | ✅ | ✅ |
| Qualificação F1/F2/F3 | ✅ | ✅ | ✅ | ✅ |
| Follow-up automatizado | ❌ | ✅ | ✅ | ✅ |
| Playground | ❌ | ✅ | ✅ | ✅ |
| Dashboard completo + analytics | ❌ | ✅ | ✅ | ✅ |
| Multi-instância | ❌ | ❌ | ✅ | ✅ |

### Comportamento ao atingir limites
- **Contatos:** alerta em 80% → ao atingir 100%, novas mensagens de números desconhecidos não criam contato novo
- **Conversas:** processadas normalmente ao ultrapassar, mas registradas como excedente para cobrança no fim do ciclo

---

## Prioridades de implementação

1. Criar tabela `subscription` com os campos acima
2. Middleware de verificação de limites em: agente (conversas), criação de contato, follow-up, playground
3. Dashboard de uso: conversas usadas vs franquia, contatos usados vs limite, alertas em 80%, CTAs de upgrade
