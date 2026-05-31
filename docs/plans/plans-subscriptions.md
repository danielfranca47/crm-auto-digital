# Planos e Modelo de Negócio — AutoDigital

> **Status: PARCIALMENTE IMPLEMENTADO**
> Sistema de planos e limites de consumo existe com arquitetura própria (via `PlanLimits`). O gate de funcionalidades por plano (`follow_up_enabled`, `playground_enabled`, `max_instances`) **não foi implementado**.
> **Pendências sujeitas a reavaliação** — decidir se o bloqueio de features por plano ainda é prioridade.

## Modelo de cobrança

**Híbrido (plano + consumo):** cada plano inclui uma franquia fixa de conversas IA por mês. Conversas além da franquia são cobradas individualmente.

**Infraestrutura WhatsApp:** Uazapi (API não oficial) — ~R$79/mês por instância. Sem taxa por mensagem da Meta.

**Custo médio estimado por conversa IA:** ~R$0,06 (modelo Sonnet). Esses números podem ser diferentes.

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

## Estado atual da implementação

### O que existe ✅

O backend-core tem um sistema de planos via `Plan` + `PlanLimits` + `Subscription`. O endpoint `GET /me/entitlements` retorna `UserLimits` com:
- `max_ia_conversas_monthly` — franquia de conversas IA
- `max_leads` — limite de contatos
- `max_whatsapp_send_daily` — limite de envios diários
- `max_prospec_monthly` — limite de prospecções

O backend-crm consome esses limites para controle de consumo de conversas e leads.

### O que não existe ❌ (pendente e sujeito a reavaliação)

O modelo `Subscription` não possui campos de feature-gate. Os seguintes bloqueios **não estão implementados**:

| Feature | Status |
|---|---|
| `follow_up_enabled` por plano | ❌ Qualquer usuário pode usar follow-up independente do plano |
| `playground_enabled` por plano | ❌ Qualquer usuário pode usar o playground |
| `max_instances` (multi-instância) | ❌ Não existe controle de número de instâncias por plano |
| Middleware de verificação de feature por plano | ❌ Não existe |

---

## Definições técnicas para implementação futura

### O que contaria como "conversa IA"
- Agente gera e envia pelo menos 1 resposta
- Janela de sessão sugerida: 24h (novo contato após 24h de inatividade = nova conversa)

### Comportamento ao atingir limites (proposto)
- **Contatos:** alerta em 80% → ao atingir 100%, novas mensagens de números desconhecidos não criam contato novo
- **Conversas:** processadas normalmente ao ultrapassar, mas registradas como excedente para cobrança no fim do ciclo

### Prioridades de implementação (quando retomar)
1. Adicionar campos de feature-gate ao modelo de `PlanLimits` (`follow_up_enabled`, `playground_enabled`, `max_instances`)
2. Middleware de verificação nos endpoints: `POST /api/leads/start-followup`, `POST /api/playground/chat`, criação de instâncias WhatsApp
3. Dashboard de uso: conversas usadas vs franquia, contatos usados vs limite, alertas em 80%, CTAs de upgrade
