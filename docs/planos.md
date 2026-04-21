# Planos e Limites — AutoDigital

> Documento de referência para implementação dos planos de assinatura no sistema.
> Última atualização: Abril 2026

---

## 1. Visão geral do modelo de negócio

### Modelo de cobrança
**Híbrido (plano + consumo)**: cada plano inclui uma franquia fixa de conversas IA por mês. Conversas além da franquia são cobradas individualmente como excedente.

### Infraestrutura base
- **API WhatsApp**: Uazapi (API não oficial) — custo por instância ~R$79/mês
- **Sem taxa por mensagem da Meta** — diferente de plataformas que usam API oficial (WATI, TailorTalk etc.)
- **Custo variável**: tokens de IA (LLM) consumidos por conversa do agente
- **Custo médio estimado por conversa IA**: R$0,06 (modelo Sonnet) — pode ser otimizado com modelos mais baratos para fases iniciais da conversa

### Agentes
Os 3 tipos de agente (SDR, Closer, Hybrid) estão **disponíveis em todos os planos**. O cliente escolhe 1 tipo de agente por instância com base no modelo de vendas dele. Não é uma limitação de plano — é uma escolha estratégica de negócio.

---

## 2. Estrutura de planos

### Fase 1 — Lançamento imediato (sistema atual)

Estes 2 planos funcionam com 1 instância por cliente (limitação técnica atual).

#### Plano Start — R$97/mês

**Público**: profissionais solo, micro-negócios, quem quer validar a automação.

| Recurso | Limite |
|---------|--------|
| Instâncias WhatsApp | 1 |
| Conversas IA/mês | 250 |
| Contatos armazenados no CRM | 500 |
| Tipos de agente | 3 (SDR, Closer, Hybrid) |
| Qualificação F1/F2/F3 | ✅ Sim |
| Follow-up automatizado | ❌ Não incluído |
| CRM integrado | ✅ Sim |
| AI Profile (configuração do agente) | ✅ Sim |
| Dashboard | Básico |
| Playground de testes | ❌ Não incluído |
| Analytics avançados | ❌ Não incluído |
| Excedente por conversa | R$0,60 |

**Nota sobre follow-up**: o follow-up automatizado é propositalmente excluído do Start para criar uma alavanca natural de upgrade. O cliente vai perceber que está a perder leads por falta de reengajamento e terá incentivo para subir de plano.

---

#### Plano Growth — R$197/mês (Recomendado)

**Público**: negócios que já validaram e querem a experiência completa.

| Recurso | Limite |
|---------|--------|
| Instâncias WhatsApp | 1 |
| Conversas IA/mês | 500 |
| Contatos armazenados no CRM | 1.500 |
| Tipos de agente | 3 (SDR, Closer, Hybrid) |
| Qualificação F1/F2/F3 | ✅ Sim |
| Follow-up automatizado | ✅ Sim |
| CRM integrado | ✅ Sim |
| AI Profile (configuração do agente) | ✅ Sim |
| Dashboard | Completo |
| Playground de testes | ✅ Sim |
| Analytics avançados | ✅ Sim |
| Excedente por conversa | R$0,50 |

---

### Fase 2 — Após implementar multi-instância

Estes planos requerem que o sistema suporte múltiplas instâncias Uazapi por cliente.

#### Plano Scale — R$397/mês

**Público**: negócios em crescimento com volume de leads via anúncios.

| Recurso | Limite |
|---------|--------|
| Instâncias WhatsApp | Até 3 |
| Conversas IA/mês | 1.500 |
| Contatos armazenados no CRM | 5.000 |
| Tudo do Growth | ✅ Sim |
| Suporte prioritário | ✅ Sim |
| Excedente por conversa | R$0,40 |
| Instância adicional (além das 3) | R$99/mês cada |

---

#### Plano Enterprise — R$697/mês

**Público**: empresas com alto volume que precisam de operação distribuída entre números.

| Recurso | Limite |
|---------|--------|
| Instâncias WhatsApp | Até 5 |
| Conversas IA/mês | 5.000 |
| Contatos armazenados no CRM | 15.000 |
| Tudo do Scale | ✅ Sim |
| Onboarding dedicado | ✅ Sim |
| Excedente por conversa | R$0,30 |
| Instância adicional (além das 5) | R$89/mês cada |

**Motivo para multi-instância**: como usamos API não oficial, volumes altos de conversa num único número aumentam o risco de bloqueio pela Meta. Distribuir conversas entre múltiplos números reduz esse risco significativamente.

---

## 3. Definições técnicas para implementação

### 3.1 O que conta como "conversa IA"

Uma **conversa IA** é um ciclo de interação entre o agente de IA e um lead/contato. Deve ser contabilizada quando:
- O agente de IA gera e envia pelo menos 1 resposta a um contato
- Cada sessão de conversa (conjunto de mensagens trocadas com um mesmo contato num período contínuo) conta como 1 conversa

**Sugestão de implementação**: definir uma janela de sessão (ex: 24h desde a última mensagem). Se o mesmo contato voltar a falar após 24h de inatividade, conta como nova conversa.

### 3.2 O que conta como "contato armazenado"

Um **contato armazenado** é qualquer registo no CRM vinculado à instância do cliente, independentemente do estado na pipeline (novo, qualificado, arquivado etc.).

**Comportamento ao atingir limite**:
- O sistema deve alertar o cliente quando atingir 80% do limite
- Ao atingir 100%, o sistema pode continuar a receber mensagens mas não cria novos contatos — apenas interage com contatos existentes
- O cliente pode liberar espaço arquivando/excluindo contatos antigos ou fazendo upgrade

### 3.3 Controle de follow-up por plano

O follow-up automatizado deve ser **desativado no plano Start**. Isto significa:
- O sistema de follow-up (reengajamento automático após inatividade do lead) não é executado
- A configuração de follow-up pode estar visível na interface (para o cliente ver o que ganha ao fazer upgrade) mas inativa
- O agente ainda responde normalmente quando o lead envia mensagem — o que não acontece é o envio proativo de follow-up

### 3.4 Controle de funcionalidades por plano

| Funcionalidade | Start | Growth | Scale | Enterprise |
|---------------|-------|--------|-------|------------|
| Endpoint do agente (conversa IA) | ✅ | ✅ | ✅ | ✅ |
| Qualificação F1/F2/F3 | ✅ | ✅ | ✅ | ✅ |
| Follow-up automatizado | ❌ | ✅ | ✅ | ✅ |
| Playground (endpoint de teste) | ❌ | ✅ | ✅ | ✅ |
| Dashboard básico | ✅ | ✅ | ✅ | ✅ |
| Dashboard completo + analytics | ❌ | ✅ | ✅ | ✅ |
| Multi-instância | ❌ | ❌ | ✅ | ✅ |

### 3.5 Modelo de dados sugerido

O sistema precisa de uma entidade/tabela para gerir os planos e limites de cada utilizador:

```
subscription / user_plan:
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
  - current_month_conversations: int (contador resetado mensalmente)
  - current_contacts_count: int (atualizado em tempo real)
  - billing_cycle_start: date
  - created_at: timestamp
  - updated_at: timestamp
```

### 3.6 Lógica de contagem e excedente

```
Ao receber mensagem de um contato:
  1. Verificar se é nova sessão (>24h desde última interação)
  2. Se sim → incrementar current_month_conversations
  3. Verificar se current_month_conversations > max_conversations_month
     - Se sim → conversa é processada normalmente, mas registar como excedente
     - Calcular cobrança: (current - max) × overage_price_per_conversation
  4. No final do ciclo de billing → gerar cobrança de excedente se houver
  5. Resetar current_month_conversations para 0
```

### 3.7 Lógica de contatos

```
Ao criar novo contato:
  1. Verificar current_contacts_count vs max_contacts
  2. Se current_contacts_count >= max_contacts × 0.80
     - Enviar alerta ao cliente (notificação no dashboard ou WhatsApp)
  3. Se current_contacts_count >= max_contacts
     - Bloquear criação de novos contatos
     - Mensagens de números desconhecidos são recebidas mas não geram registo novo
     - Sugerir upgrade ou limpeza de base
```

---

## 4. Margem e custos por plano

### Custos fixos por cliente

| Componente | Custo |
|-----------|-------|
| Instância Uazapi | ~R$79/mês por instância |
| Hosting/servidor | Rateado entre clientes |
| Tokens IA (estimativa 250 conversas) | ~R$15/mês |
| Tokens IA (estimativa 500 conversas) | ~R$30/mês |
| Tokens IA (estimativa 1500 conversas) | ~R$90/mês |
| Tokens IA (estimativa 5000 conversas) | ~R$300/mês |

### Margem bruta estimada

| Plano | Receita | Custo estimado | Margem bruta |
|-------|---------|---------------|-------------|
| Start (R$97) | R$97 | ~R$94 (1×Uazapi + tokens) | ~3% |
| Growth (R$197) | R$197 | ~R$109 (1×Uazapi + tokens) | ~45% |
| Scale (R$397) | R$397 | ~R$327 (3×Uazapi + tokens) | ~18% |
| Enterprise (R$697) | R$697 | ~R$695 (5×Uazapi + tokens) | ~0.3% |

> **NOTA IMPORTANTE**: as margens acima consideram o custo da Uazapi por instância incluindo TODAS as instâncias do plano. Na prática, nem todo cliente do Scale vai usar as 3 instâncias desde o início — muitos começam com 1-2. A margem real tende a ser melhor do que o cenário pessimista acima.
>
> O plano Start tem margem apertada por design — é um plano de **aquisição**, não de lucro. O objetivo é converter o cliente para Growth em 1-2 meses.
>
> O excedente de conversas é receita adicional com margem alta (o custo real por conversa excedente é ~R$0,06, cobrado a R$0,30-0,60).

---

## 5. Estratégia de lançamento

### Fase 1 (imediata)
- Lançar apenas **Start** e **Growth**
- Growth é o plano "recomendado" na página de preços
- Sistema suporta 1 instância por cliente

### Fase 2 (após multi-instância)
- Lançar **Scale** e **Enterprise**
- Na página de preços, mostrar como "em breve" até estarem prontos
- Implementar gestão de múltiplas instâncias por cliente no backend

### Considerações sobre a API não oficial
- Os planos Scale e Enterprise existem justamente para mitigar o risco de bloqueio distribuindo conversas entre múltiplos números
- Incluir na documentação/onboarding boas práticas para evitar bloqueio: warm-up de número novo, ritmo gradual de mensagens, não enviar spam

---

## 6. Resumo rápido para implementação

**Prioridade 1 — Criar tabela/modelo de subscription com campos listados em 3.5**

**Prioridade 2 — Middleware de verificação de limites:**
- Verificar franquia de conversas antes de processar resposta do agente
- Verificar limite de contatos antes de criar novo registo no CRM
- Verificar se follow-up está habilitado antes de executar jobs de follow-up
- Verificar se playground está habilitado antes de permitir acesso ao endpoint de teste

**Prioridade 3 — Dashboard de uso:**
- Mostrar ao cliente: conversas usadas vs franquia, contatos usados vs limite
- Alertas quando se aproxima dos limites (80%)
- Indicação clara de funcionalidades bloqueadas no plano atual com CTA de upgrade
