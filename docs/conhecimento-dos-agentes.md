# Conhecimento dos Agentes — Referência Oficial

> **Atualizado em:** 2026-03-28 (sub-modo comercial Agente 03 implementado)
> **Escopo:** Camada 4 (Conhecimento) do `AiProfile.tsx`
> **Status:** Estrutura implementada e em produção

---

## 1. Por que o conhecimento importa em cada agente

O LLM que roda o agente não tem memória de negócio — ele só sabe o que você fornece. O conteúdo da Camada 4 é o único "treinamento específico" que o agente recebe sobre o produto, os clientes e as regras do usuário. Sem ele, o agente responde de forma genérica e perde conversões.

Cada arquétipo tem um **papel estratégico diferente** na jornada de vendas, o que determina quais informações são insubstituíveis:

| Arquétipo | Papel na jornada | Risco sem conhecimento |
|---|---|---|
| Agente 01 · SDR Alto Ticket | Qualificar e agendar reunião | Avança lead errado para o humano / Perde lead certo por resposta vaga |
| Agente 02 · Vendedor Autônomo | Qualificar + Pitch + Fechar | Não convence → taxa de conversão baixa / Perde objeções por falta de resposta |
| Agente 03 · Assistente Comercial | Acolher, aquecer e agendar | Lead chega frio para a sessão / Profissional sem contexto desperdiça a consulta |

---

## 2. Mapeamento de conhecimento por agente

### 2.1 Agente 01 — SDR de Alto Ticket (`sdr_padrao` / `consultor_especialista`)

**Missão:** Qualificar profundamente (Filtros 1–3), filtrar leads com fit real e entregar ao humano um dossiê completo de contexto. O bot nunca vende — ele prepara o terreno.

**Cenários cobertos:**
- Inbound: lead chegou com dor declarada (formulário, anúncio, link direto)
- Outbound: lead selecionado por perfil, dor precisa ser despertada

#### Categorias de conhecimento

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 1 | **Perfil da Empresa** | `company_profile` | Crítico | O agente precisa responder "quem vocês são?" com precisão durante F1/F2. Sem isso, improvisa e perde credibilidade. |
| 2 | **Prova Social** | `social_proof` | Crítico | Usada no F3 e no aquecimento. Clientes B2B de alto ticket precisam ver que outros como eles já confiaram. Reduz resistência antes da reunião. |
| 3 | **Objeções e Respostas** | `objections_faq` | Crítico | Objeções pré-reunião ("está caro", "não é o momento", "preciso consultar meu sócio") são barreiras que impedem o agendamento. O bot precisa de respostas prontas. |
| 4 | **Critérios de Qualificação** | `qualification_criteria` | Recomendado | Define o que é aprovado ou descartado no F1 e F3. Sem isso, o bot usa critérios genéricos e avança leads errados. |
| 5 | **FAQ Pré-Reunião** | `pre_meeting_faq` | Recomendado | Reduz atrito antes do agendamento: duração, formato, o que esperar. Aumenta taxa de comparecimento. |
| 6 | **Política de Preço** | `price_policy` | Recomendado | Define o que o bot pode ou não dizer sobre preço antes da reunião. Sem instrução, o bot improvisa e pode citar valores que atrapalham a negociação do humano. |
| 7 | **Script de Dossiê** | `handoff_briefing_template` | Recomendado | Define quais campos o bot deve incluir no resumo enviado ao vendedor antes da reunião. Sem isso o dossiê é genérico e o vendedor não se prepara. |
| 8 | **Diferenciação Competitiva** | `competitive_differentials` | Opcional | Respostas para "já usamos X" ou "estou avaliando também Y". Em mercados com concorrentes diretos é essencial; em nicho único, opcional. |
| 9 | **Mensagens de Nurture** | `nurture_content` | Opcional | Conteúdo para leads que não qualificaram agora mas têm potencial futuro. Sem isso, o bot arquiva sem cultivar relacionamento. |

---

### 2.2 Agente 02 — Vendedor Autônomo / Low Ticket (`closer_agressivo`)

**Missão:** Pipeline 100% automatizado. Qualificação mínima (1–2 perguntas) → Pitch completo → Link de pagamento → Recuperação de carrinho → Upsell pós-compra. Sem intervenção humana.

**Cenários cobertos:**
- Inbound: lead clicou no anúncio, dor implícita no clique
- Outbound: lista fria (seguidores, base de e-mail, retargeting)

#### Categorias de conhecimento

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 1 | **Script de Pitch** | `pitch_script` | Crítico | É o coração do agente. Estrutura: Dor → Solução → Benefícios → Prova Social → Oferta → Urgência. Sem isso o agente improvisa e não converte. |
| 2 | **FAQ de Objeções** | `objections_faq` | Crítico | Em low ticket a janela de decisão é de minutos. O bot precisa de respostas instantâneas para "está caro", "vou pensar", "já tentei antes". |
| 3 | **Depoimentos e Provas Sociais** | `social_proof` | Crítico | Depoimentos específicos (resultado + tempo + perfil) reduzem o risco percebido na hora do pagamento. |
| 4 | **Perguntas de Fit** | `fit_questions` | Recomendado | As 1–2 perguntas de qualificação mínima antes do pitch. Sem elas, o bot faz o pitch para qualquer pessoa — inclusive quem não tem a dor. |
| 5 | **Detalhes do Produto** | `product_details` | Recomendado | O que está incluído na compra: módulos, bônus, formato de entrega. O lead pergunta "o que vem junto?" durante o pitch. |
| 6 | **Política de Garantia** | `guarantee_policy` | Recomendado | Remove o último obstáculo antes do pagamento. "Garantia de X dias sem risco" é um argumento de fechamento clássico. |
| 7 | **Condição Atual da Oferta** | `urgency_offer` | Recomendado | Urgência real (prazo, vagas, desconto) — única forma ética de criar senso de urgência. Deve ser atualizado conforme a campanha muda. ⚠️ Badge de atualização ativado após 30 dias sem edição. |
| 8 | **Script de Recuperação de Carrinho** | `cart_recovery_scripts` | Recomendado | As 3 mensagens de follow-up (2h, 24h, 48h) com ângulos diferentes. Sem isso, o bot usa mensagem genérica de lembrete. ⚠️ Badge de atualização ativado após 30 dias sem edição. |
| 9 | **Conteúdo de Upsell** | `upsell_content` | Opcional | Produto a apresentar imediatamente pós-compra. Momento de maior abertura do cliente — oportunidade de aumentar LTV. |
| 10 | **Onboarding Pós-Compra** | `post_purchase_onboarding` | Opcional | Mensagem de boas-vindas + próximos passos enviados automaticamente após pagamento confirmado. Reduz chargeback e aumenta satisfação. |

---

### 2.3 Agente 03 — Assistente Comercial Híbrido (`hybrid_scheduler`)

**Missão:** Assistente comercial que responde dúvidas de forma natural e persuasiva para gerar agendamentos. O agente agenda; o pagamento ocorre presencialmente na marcação — nunca via link digital.

**Cenários cobertos:**
- Inbound: lead demonstrou interesse ativo (mensagem, formulário, link de agendamento)
- Outbound: prospecção com tom pessoal ("o [Profissional] me pediu para entrar em contato")

**Exemplo de nicho:** massagista que atende por sessão avulsa ou pacotes mensais. O agente responde sobre tipos de massagem, duração, preços, disponibilidade — e fecha o agendamento.

#### Categorias de conhecimento

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 1 | **Bio do Profissional** | `professional_bio` | Crítico | Primeira coisa que o lead quer saber: quem é? Por que confiar? O agente usa para se apresentar em nome do profissional. |
| 2 | **Histórias de Transformação** | `social_proof` | Crítico | Usada no aquecimento. O lead se identifica com um caso parecido — aumenta confiança e motivação para agendar. |
| 3 | **Preview da Sessão / Serviço** | `session_preview` | Crítico | Descreve o que acontece na marcação: duração, formato, o que o lead pode esperar. Reduz ansiedade e aumenta comparecimento. |
| 4 | **Script de Aquecimento** | `warming_script` | Recomendado | Texto que conecta a dor ou necessidade do lead com o que o profissional resolve. Usado antes de propor o agendamento. |
| 5 | **Roteiro de Perguntas de Contexto** | `pain_questions` | Recomendado | Perguntas abertas para entender o que o lead busca. As respostas viram o briefing enviado ao profissional antes da sessão — ele chega preparado. |
| 6 | **Política de Agendamento** | `scheduling_policy` | Recomendado | Regras de cancelamento, reagendamento e no-show. O lead pergunta antes de confirmar — sem resposta clara, desiste. |
| 7 | **FAQ do Serviço** | `service_faq` | Recomendado | Dúvidas gerais sobre o serviço: duração, formato, localização, preços. |
| 8 | **Follow-up Pós-Sessão** | `post_session_followup` | Opcional | Mensagens para quem veio mas não retornou: reconectar, propor nova marcação, citar resultado que ficou pendente. |
| 9 | **Material Pré-Sessão** | `pre_session_material` | Opcional | Instrução ou formulário enviado 24h antes para o lead chegar preparado. |
| 10 | **Script de Indicação** | `referral_script` | Opcional | Pedido de indicação para clientes satisfeitos. Momento ideal: após confirmar que a sessão foi bem. |

---

## 3. Sistema de prontidão do agente

O componente `CamadaConhecimento.tsx` exibe um **score de prontidão** em 3 níveis calculado em tempo real:

| Nível | Critério | Mensagem ao usuário |
|---|---|---|
| Não funcional | Menos de 2 seções críticas preenchidas | "O agente não tem informações suficientes para responder bem." |
| Funcional básico | Todas as seções críticas preenchidas | "O agente consegue operar, mas sem diferenciação." |
| Otimizado | Todas críticas + pelo menos 2 recomendadas preenchidas | "O agente está pronto para operar com alta performance." |

**Lógica implementada em** [CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx):

```typescript
function getReadinessLevel(
  guidedCategories: KnowledgeCategory[],
  itemByCategory: Map<string, KnowledgeItem>
): 'none' | 'basic' | 'optimized' {
  const critical = guidedCategories.filter(c => c.importance === 'critical');
  const recommended = guidedCategories.filter(c => c.importance === 'recommended');
  const criticalFilled = critical.filter(c => itemByCategory.has(c.key)).length;
  const recommendedFilled = recommended.filter(c => itemByCategory.has(c.key)).length;

  if (criticalFilled < 2) return 'none';
  if (criticalFilled < critical.length) return 'basic';
  if (recommendedFilled >= 2) return 'optimized';
  return 'basic';
}
```

---

## 4. Badge de atualização temporal

Categorias com conteúdo de curta validade exibem um badge de alerta quando não foram editadas há mais de 30 dias. Aplicado às chaves `urgency_offer` e `cart_recovery_scripts` do `closer_agressivo`.

**Lógica implementada em** [CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx):

```typescript
function isStale(item: KnowledgeItem, days = 30): boolean {
  const updated = new Date(item.updated_at);
  const now = new Date();
  return (now.getTime() - updated.getTime()) / (1000 * 60 * 60 * 24) > days;
}
```

---

## 5. Personalização de hints pela Camada 2

O componente `CamadaConhecimento` recebe `agentConfig` como prop opcional. Quando presente, os campos `hint` e `placeholder` de cada categoria têm os tokens `[NICHO]`, `[PÚBLICO]` e `[OFERTA]` substituídos pelos valores reais preenchidos nas camadas anteriores.

**Prop adicionada:**
```tsx
// AiProfile.tsx
<CamadaConhecimento templateKey={config.template_key} agentConfig={config} />
```

**Função de personalização em** [CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx):

```typescript
function getPersonalizedCategory(
  cat: KnowledgeCategory,
  config: Partial<AgentConfig>
): KnowledgeCategory {
  const niche    = config.niche             || '[nicho do negócio]';
  const audience = config.target_audience   || '[público-alvo]';
  const offer    = config.offer_description || '[descrição da oferta]';
  return {
    ...cat,
    hint: cat.hint
      .replace(/\[NICHO\]/g, niche)
      .replace(/\[PÚBLICO\]/g, audience)
      .replace(/\[OFERTA\]/g, offer),
    placeholder: cat.placeholder
      .replace(/\[NICHO\]/g, niche)
      .replace(/\[PÚBLICO\]/g, audience)
      .replace(/\[OFERTA\]/g, offer),
  };
}
```

---

## 6. Wizard de onboarding (primeira configuração)

Quando o usuário não tem nenhum item de conhecimento preenchido, `CamadaConhecimento` renderiza `CamadaConhecimentoWizard` em vez da lista de cards.

**Lógica de ativação:**
```typescript
const isFirstTime = items.length === 0 && guidedCategories.length > 0;
if (isFirstTime) return <CamadaConhecimentoWizard ... />;
```

**Estrutura do wizard (3 passos):**

1. **Contexto** — confirmar nicho, oferta e público (pré-preenchidos da Camada 2, editáveis). Os valores confirmados personalizam os hints dos passos seguintes.
2. **Seções críticas** — exibidas uma de cada vez, com hint personalizado e placeholder contextualizado.
3. **Seções recomendadas** — exibidas com opção "Pular por agora" e indicador de impacto.

O wizard também exibe o score de prontidão ao final, com atalho para adicionar conteúdo extra livre.

**Arquivo:** [CamadaConhecimentoWizard.tsx](../frontend-crm/src/components/agente/CamadaConhecimentoWizard.tsx)

---

## 7. Sub-modo comercial do Agente 03

O `hybrid_scheduler` suporta dois modos de operação, selecionável na **Camada 5 (Apresentação)**:

| Modo | Chave | Comportamento |
|---|---|---|
| **Agendamento Exploratório** | `exploratory` (padrão) | Aquece com prova social e preview da sessão → propõe agendamento sem compromisso de compra |
| **Compromisso Comercial** | `commercial` | Apresenta serviços e preços → trata objeções → fecha escolha de pacote → ENTÃO agenda. Pagamento sempre presencial. |

### Campo de configuração

O campo `appointment_mode: 'commercial' | 'exploratory'` fica em `AgentConfig` (Camada 1) e é persistido em `ai_profiles.appointment_mode` no backend-core.

### Categorias de conhecimento exclusivas do modo comercial

Quando `appointment_mode === 'commercial'`, a Camada 4 exibe 6 categorias adicionais com divisor visual:

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 1 | **Tabela de Serviços e Preços** | `service_pricing_table` | Crítico | O agente apresenta os serviços disponíveis e valores. Sem isso, pergunta o interesse antes de citar valores. |
| 2 | **Objeções Comerciais e Respostas** | `commercial_objections` | Crítico | Respostas configuradas para "está caro", "vou pensar", "não preciso agora". Sem isso, o agente usa empatia genérica. |
| 3 | **Diferenciais do Serviço** | `service_differentials` | Recomendado | Argumentos de diferenciação frente à concorrência ou ao "fazer por conta própria". |
| 4 | **Condição Especial Vigente** | `active_promotion` | Recomendado | Promoção, bônus ou desconto ativo — cria urgência real. Deve ser atualizado quando a condição mudar. |
| 5 | **Política de Pagamento Presencial** | `payment_policy` | Recomendado | Formas aceitas, parcelamento, política de entrada. O agente nunca envia link de checkout. |
| 6 | **FAQ Pré-Compromisso** | `pre_commitment_faq` | Recomendado | Dúvidas frequentes antes de confirmar o pacote: cancelamento, validade, reagendamento. |

### Fluxo executado pelo agente (modo comercial)

```
1. Qualificação concluída pelo lead
2. Aquecimento com prova social (campo social_proof ou warming_social_proof)
3. Apresentação dos serviços/pacotes com preços
4. Tratamento de objeções conforme respostas configuradas
5. Confirmação verbal/escrita da escolha de serviço
6. Proposta de agendamento
7. Pagamento ocorre presencialmente — nenhum link de checkout é enviado
```

### Injeção no prompt (backend)

O `decision_engine` detecta `appointment_mode == 'commercial'` e injeta o bloco `MODO COMERCIAL` no prompt de apresentação. Os `knowledge_items` são lidos de `backend-crm` via `executor.py` e incluídos no contexto de execução antes de chegar ao `decision_engine`.

**Arquivos relevantes:**
- [backend-core/app/db.py](../backend-core/app/db.py) — migração da coluna `appointment_mode`
- [backend-core/app/api/ai_profiles.py](../backend-core/app/api/ai_profiles.py) — schemas Pydantic
- [backend-crm/routes/executor.py](../backend-crm/routes/executor.py) — injeção de `knowledge_items` no contexto
- [backend-executors/app/services/decision_engine.py](../backend-executors/app/services/decision_engine.py) — lógica de `commercial_injection`
- [frontend-crm/src/types/agente.ts](../frontend-crm/src/types/agente.ts) — `KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL`
- [frontend-crm/src/components/agente/CamadaApresentacao.tsx](../frontend-crm/src/components/agente/CamadaApresentacao.tsx) — seletor `ModalAppointmentMode`
- [frontend-crm/src/components/agente/CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx) — seção comercial condicional

---

## 8. Referências no código

| Arquivo | Relevância |
|---|---|
| [frontend-crm/src/types/agente.ts](../frontend-crm/src/types/agente.ts) | `KnowledgeCategory`, `KNOWLEDGE_CATEGORIES_BY_TEMPLATE` — fonte de verdade das categorias por template |
| [frontend-crm/src/components/agente/CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx) | Componente principal da Camada 4: score de prontidão, badge temporal, personalização de hints |
| [frontend-crm/src/components/agente/CamadaConhecimentoWizard.tsx](../frontend-crm/src/components/agente/CamadaConhecimentoWizard.tsx) | Wizard de onboarding para primeira configuração |
| [frontend-crm/src/pages/AiProfile.tsx](../frontend-crm/src/pages/AiProfile.tsx) | Orquestrador — passa `templateKey` e `agentConfig` para `CamadaConhecimento` |
| [frontend-crm/src/pages/TiposAgentes.tsx](../frontend-crm/src/pages/TiposAgentes.tsx) | Definição dos arquétipos de agente (`AGENTS` array) |
| [backend-crm/routes/knowledge.py](../backend-crm/routes/knowledge.py) | API CRUD de itens de conhecimento |
| [backend-crm/routes/executor.py](../backend-crm/routes/executor.py) | Inclui `knowledge_items` no contexto de execução enviado ao `decision_engine` |
| [backend-executors/app/services/decision_engine.py](../backend-executors/app/services/decision_engine.py) | `_build_child_prompt_apresentation()` — lógica de `commercial_injection` vs `warming_injection` |
| [frontend-crm/src/components/agente/CamadaApresentacao.tsx](../frontend-crm/src/components/agente/CamadaApresentacao.tsx) | Seletor `ModalAppointmentMode` (exploratory / commercial) |
