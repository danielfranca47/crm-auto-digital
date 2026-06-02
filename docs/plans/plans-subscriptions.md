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

---

## Definições Pendentes — Perguntas para o Fundador

> Responde directamente abaixo de cada pergunta. Quando estiver completo, usamos estas respostas para actualizar o seed de planos e implementar os feature-gates.

---

### A — Estrutura de planos

**A1.** Quais planos vais lançar na Fase 1? Mantens os nomes Start e Growth, ou preferes outros?
> _Resposta:_sim, os scale e enterprise ficaram disponíveis em breve.

**A2.** Os preços R$97 (Start) e R$197 (Growth) estão confirmados, ou vão mudar?
> _Resposta:_ confirmados

**A3.** Vais oferecer cobrança anual com desconto? Se sim, qual percentagem?
> _Resposta:_ sim  

Desconto normal para assinatura anual: equivalente a 50 % de desconto nos 2 primeiros meses. na prática no final do período de 12 meses, 1 mes sairá gratis.

Preços das campanhas especiais anuais será: R$ 997 no starter e R$ 1997 no Growth 



**A4.** Existe período de teste gratuito (trial)? Se sim, quantos dias e com que limites?
> _Resposta:_

sim, existirá de 7 dias, mas esse benefício eu só irei liberar para leads selecionados que fizerem a call comigo.

---

### B — Limites por plano

**B1.** Quantos leads (contatos no CRM) cada plano suporta?
> Start: _500__ / Growth: _1500__


**B2.** Quantas conversas IA por mês cada plano inclui na franquia?
> Start: _250__ / Growth: __500_

**B3.** O plano Start inclui follow-up automatizado? (Actualmente proposto: ❌ Start, ✅ Growth)
> _Resposta:_nao

**B4.** O plano Start inclui acesso ao Playground de testes? (Actualmente proposto: ❌ Start, ✅ Growth)
> _Resposta:_apenas 5 por mês
+ R$ 1,99 para cada teste extra

**B5.** Quantas instâncias WhatsApp cada plano permite? (Actualmente proposto: 1 em ambos)
> Start: _uma__ / Growth: _uma__

---

### C — Excedentes e bloqueios

**C1.** Quando o utilizador ultrapassa o limite de conversas IA, o que acontece?
- [ ] Bloqueia até renovar o ciclo
- [] Cobra excedente automaticamente (R$___ por conversa)
- [x] Envia alerta e aguarda decisão do utilizador
> _Resposta:_sistema precisa dar o aviso e oferecer link do checkout para comprar mais conversas.

**C2.** Quando o utilizador atinge o limite de leads, o que acontece?
- [x] Bloqueia criação de novos leads
- [ ] Bloqueia só a IA em novos leads (leads existentes continuam)
- [ ] Apenas alerta, não bloqueia
> _Resposta:_precisa ter um aviso tambem de limites de leads atingido, pedir para ele remover leads ou atualizar seu plano.

**C3.** Queres cobrar excedente automaticamente (requer integração de pagamento) ou prefereres gerir manualmente por agora?
> _Resposta:_quero cobrar automático. Estou cogitando utilizar um gateway de pagamento externo como kiwify por enquanto e posteriormente desenvolver algo mais robusto.

---

### D — Gestão de assinaturas

**D1.** Como vais atribuir planos aos utilizadores agora (antes de ter checkout automático)?
- [ ] Tu atribuis manualmente pelo painel admin
- [ ] O utilizador paga e tu activas manualmente
- [x] Integração com Stripe/Kirvano/Hotmart (qual?)
> _Resposta:_

**D2.** Queres um endpoint/botão no painel admin para atribuir/mudar plano de um utilizador com um clique?
> _Resposta:_sim

**D3.** Os teus utilizadores de teste internos (tua conta, contas de demo) devem ter um plano especial sem limites?
> _Resposta:_sim

---

### E — Fase 2 (multi-instância)

**E1.** A Fase 2 (planos Scale e Enterprise com múltiplas instâncias) é uma prioridade próxima ou pode aguardar?
> _Resposta:_pode aguardar. Primeiro vou ter de desenvolver o recurso de clonagem de voz e compatibilidade com api oficial da meta.

**E2.** Os preços R$397 (Scale) e R$697 (Enterprise) estão confirmados?
> _Resposta:_sim
