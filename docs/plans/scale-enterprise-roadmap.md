# Planos Scale e Enterprise — Roadmap de Implementação

> **Documento criado:** 02/06/2026
> **Base:** plans-subscriptions.md (plano original) comparado com o estado implementado em junho/2026.

---

## O que já está construído (base para os novos planos)

Antes de planejar o Scale e Enterprise, é importante entender o que a etapa 9 entregou:

| Funcionalidade | Estado |
|---|---|
| Modelo de planos (`Plan` + `PlanLimits` + `Subscription`) | ✅ |
| Planos Start (R$97) e Growth (R$197) no seed | ✅ |
| Feature-gate `follow_up_enabled` por plano | ✅ |
| Feature-gate `playground_monthly_limit` por plano | ✅ |
| `trial_ends_at` na Subscription | ✅ |
| Endpoint admin atribuir plano + UI | ✅ |
| Webhook Kiwify (activação automática de subscriptions) | ✅ |
| Alertas de consumo 80%/100% no frontend-crm | ✅ |
| **`max_instances` (controlo de instâncias WhatsApp por plano)** | ❌ não implementado |
| **Multi-instância WhatsApp (criar N instâncias)** | ❌ não implementado |

A base está sólida. O que falta para os novos planos é essencialmente o **pilar multi-instância**.

---

## Definição dos Planos

### Plano Scale — a definir (era R$397/mês)

> Público: empresas com equipa de vendas, múltiplos WhatsApp activos.

| Recurso | Proposta inicial | Notas |
|---|---|---|
| Instâncias WhatsApp | Até 3 | Depende de multi-instância implementada |
| Conversas IA/mês | 1.500 | 3× o Growth |
| Contatos no CRM | 5.000 | |
| Follow-up | ✅ | |
| Playground | ✅ ilimitado | |
| Instância adicional | +R$99/mês | A confirmar |
| Excedente conversa | R$0,40 | |

> **Preço a confirmar.** "Plano Scale" já existe no Kiwify mas sem código CRM mapeado.

---

### Plano Enterprise — sob orçamento

> Público: grandes empresas, agências, revendedores.

| Recurso | Proposta |
|---|---|
| Instâncias WhatsApp | Até 5 (ou ilimitado) |
| Conversas IA/mês | 5.000+ (ou ilimitado) |
| Contatos no CRM | 15.000+ |
| Follow-up | ✅ |
| Playground | ✅ |
| Suporte prioritário | ✅ |
| Onboarding dedicado | ✅ |
| Preço | Sob orçamento (contacto directo) |

O Enterprise não passa pelo Kiwify — o admin activa manualmente com o plano `crm_enterprise` após negociação.

---

## O que é preciso construir

### Pré-requisito crítico: Multi-instância WhatsApp

O Scale e Enterprise só fazem sentido comercial com múltiplas instâncias WhatsApp. Actualmente cada utilizador tem exatamente 1 instância. Para suportar N instâncias:

1. **`max_instances` em `PlanLimits`** — novo campo (nullable = ilimitado)
2. **Gate de criação de instância** — ao criar nova instância WhatsApp, verificar se o utilizador ainda tem slots disponíveis
3. **UI multi-instância no frontend-crm** — selector de instância activa nas conversas, Kanban por instância ou unificado
4. **Seed** — `crm_scale: max_instances=3`, `crm_enterprise: max_instances=5` (ou null)

### Plano `crm_enterprise` no seed

```python
"crm_enterprise": {
    "max_leads": None,          # ilimitado
    "max_ia_conversas_monthly": 5000,
    "max_whatsapp_send_daily": None,
    "max_instances": None,      # ilimitado ou 5
    "follow_up_enabled": True,
    "playground_monthly_limit": None,
}
```

### Plano `crm_scale`

```python
"crm_scale": {
    "max_leads": 5000,
    "max_ia_conversas_monthly": 1500,
    "max_whatsapp_send_daily": 200,
    "max_instances": 3,
    "follow_up_enabled": True,
    "playground_monthly_limit": None,
}
```

### Fluxo Enterprise (sem Kiwify)

```
Negociação directa → admin abre painel
  → Usuários → "Plano" → selecciona crm_enterprise
  → subscription activa manualmente (já funciona com o modal actual)
```

Não requer desenvolvimento adicional além do seed.

### Kiwify para o Scale

Quando o preço do Scale estiver confirmado, basta:
1. Criar o preço no produto Kiwify ("Plano Scale")
2. Adicionar ao `PLAN_NAME_TO_CODE` em `webhooks_kiwify.py`:
   ```python
   "Plano Scale": "crm_scale",
   ```

---

## Outras funcionalidades mencionadas para Fase 2

O utilizador mencionou dois pré-requisitos antes do lançamento da Fase 2:

1. **Clonagem de voz** — áudio personalizado do agente (já existe infra de áudio no inbound)
2. **Compatibilidade com API oficial Meta** — substituir UazAPI por API oficial; muda o billing (por mensagem) e remove o risco de banimento

Estes dois pontos são independentes dos planos mas influenciam o posicionamento e o preço.

---

## Recomendações por prioridade

### P1 — Agora (sem dependências externas)

**Seed `crm_scale` e `crm_enterprise`**
- Adicionar ao `seed.py` com os limites definidos acima
- O Enterprise já funciona no painel admin sem mais código
- Baixo risco, entrega imediata

### P2 — Próxima sprint

**`max_instances` no modelo de planos**
- Adicionar coluna `max_instances` ao `PlanLimits` via `ensure_plan_limits_columns()`
- Gate de criação de instância: ao `POST /whatsapp/connect`, verificar count de instâncias activas vs limite
- Sem UI nova — a criação de instâncias já existe, só adiciona a verificação

### P3 — Sprint seguinte

**UI multi-instância no frontend-crm**
- Selector de instância no header (dropdown "Activo: +351 9xx xxx xxx")
- Leads filtrados por instância ou unificados (decisão de produto)
- Kanban por instância ou tag visual por instância nos cards

### P4 — Quando o preço do Scale estiver confirmado

**Scale no Kiwify**
- Confirmar o preço
- Mapear "Plano Scale" → `crm_scale` no webhook
- Activa a venda automática

### P5 — Fase 2 completa (mais longo prazo)

**API oficial Meta**
- Substitui UazAPI
- Muda toda a infra de envio e recepção
- Preço por mensagem altera o modelo de cobrança — `max_whatsapp_send_daily` pode deixar de fazer sentido

**Clonagem de voz**
- Feature de diferenciação para Scale/Enterprise
- Não afecta a estrutura de planos, mas pode ser um add-on pago

---

## Resumo: o que fazer primeiro

```
Sprint imediata (1–2 dias):
  → Seed crm_scale + crm_enterprise  [P1]
  → Enterprise já funciona no painel admin

Sprint seguinte (3–5 dias):
  → max_instances no PlanLimits       [P2]
  → Gate de criação de instância      [P2]

Quando preço Scale confirmado (1 dia):
  → Mapear no webhook Kiwify          [P4]

Mais longo prazo:
  → UI multi-instância                [P3]
  → API oficial Meta + voz            [P5]
```
