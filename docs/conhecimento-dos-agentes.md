# Conhecimento dos Agentes — Análise e Plano de Implementação

> **Criado em:** 2026-03-27
> **Escopo:** Camada 4 (Conhecimento) do `AgenteConfiguracao.tsx`
> **Objetivo:** Definir quais informações cada arquétipo de agente precisa, por quê, e como o usuário deve preenchê-las de forma orientativa.

---

## 1. Por que o conhecimento importa em cada agente

O LLM que roda o agente não tem memória de negócio — ele só sabe o que você fornece. O conteúdo da Camada 4 é o único "treinamento específico" que o agente recebe sobre o seu produto, seus clientes e suas regras. Sem ele, o agente responde de forma genérica e perde conversões.

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

#### Categorias de conhecimento necessárias

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 1 | **Perfil da Empresa** | `company_profile` | Crítico | O agente precisa responder "quem vocês são?" com precisão durante F1/F2. Sem isso, improvisa e perde credibilidade. |
| 2 | **Prova Social** | `social_proof` | Crítico | Usada no F3 e no aquecimento. Clientes B2B de alto ticket precisam ver que outros como eles já confiaram. Reduz resistência antes da reunião. |
| 3 | **Objeções e Respostas** | `objections_faq` | Crítico | Objeções pré-reunião ("está caro", "não é o momento", "preciso consultar meu sócio") são barreiras que impedem o agendamento. O bot precisa de respostas prontas. |
| 4 | **Critérios de Qualificação** | `qualification_criteria` | Recomendado | Define o que é aprovado ou descartado no F1 e F3. Sem isso, o bot usa critérios genéricos e avança leads errados. |
| 5 | **FAQ Pré-Reunião** | `pre_meeting_faq` | Recomendado | Reduz atrito antes do agendamento: duração, formato, o que esperar. Aumenta taxa de comparecimento. |
| 6 | **Política de Preço** | `price_policy` | Recomendado | Define o que o bot pode ou não dizer sobre preço antes da reunião. Sem instrução, o bot improvisa e pode citar valores que atrapalham a negociação do humano. |
| 7 | **Script de Dossiê** *(novo)* | `handoff_briefing_template` | Recomendado | Define quais campos o bot deve incluir no resumo enviado ao vendedor antes da reunião. Sem isso o dossiê é genérico e o vendedor não se prepara. |
| 8 | **Diferenciação Competitiva** *(novo)* | `competitive_differentials` | Opcional | Respostas para "já usamos X" ou "estou avaliando também Y". Em mercados com concorrentes diretos é essencial; em nicho único, opcional. |
| 9 | **Mensagens de Nurture** *(novo)* | `nurture_content` | Opcional | Conteúdo para leads que não qualificaram agora mas têm potencial futuro. Sem isso, o bot arquiva sem cultivar relacionamento. |

**Lacuna atual vs. já implementado:**
Categorias 1–6 já estão em `KNOWLEDGE_CATEGORIES_BY_TEMPLATE.sdr_padrao`. As categorias 7, 8 e 9 não existem ainda — são novas propostas.

---

### 2.2 Agente 02 — Vendedor Autônomo / Low Ticket (`closer_agressivo`)

**Missão:** Pipeline 100% automatizado. Qualificação mínima (1–2 perguntas) → Pitch completo → Link de pagamento → Recuperação de carrinho → Upsell pós-compra. Sem intervenção humana.

**Cenários cobertos:**
- Inbound: lead clicou no anúncio, dor implícita no clique
- Outbound: lista fria (seguidores, base de e-mail, retargeting)

#### Categorias de conhecimento necessárias

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 1 | **Script de Pitch** | `pitch_script` | Crítico | É o coração do agente. Estrutura: Dor → Solução → Benefícios → Prova Social → Oferta → Urgência. Sem isso o agente improvisa e não converte. |
| 2 | **FAQ de Objeções** | `objections_faq` | Crítico | Em low ticket a janela de decisão é de minutos. O bot precisa de respostas instantâneas para "está caro", "vou pensar", "já tentei antes". |
| 3 | **Depoimentos e Provas Sociais** | `social_proof` | Crítico | Depoimentos específicos (resultado + tempo + perfil) reduzem o risco percebido na hora do pagamento. |
| 4 | **Detalhes do Produto** | `product_details` | Recomendado | O que está incluído na compra: módulos, bônus, formato de entrega. O lead pergunta "o que vem junto?" durante o pitch. |
| 5 | **Política de Garantia** | `guarantee_policy` | Recomendado | Remove o último obstáculo antes do pagamento. "Garantia de X dias sem risco" é um argumento de fechamento clássico. |
| 6 | **Condição Atual da Oferta** | `urgency_offer` | Recomendado | Urgência real (prazo, vagas, desconto) — única forma ética de criar senso de urgência. Deve ser atualizado conforme a campanha muda. |
| 7 | **Conteúdo de Upsell** | `upsell_content` | Opcional | Produto a apresentar imediatamente pós-compra. Momento de maior abertura do cliente — oportunidade de aumentar LTV. |
| 8 | **Script de Recuperação de Carrinho** *(novo)* | `cart_recovery_scripts` | Recomendado | As 3 mensagens de follow-up (2h, 24h, 48h) com ângulos diferentes. Sem isso, o bot usa mensagem genérica de lembrete. |
| 9 | **Perguntas de Fit** *(novo)* | `fit_questions` | Recomendado | As 1–2 perguntas de qualificação mínima antes do pitch. Sem elas, o bot faz o pitch para qualquer pessoa — inclusive quem não tem a dor. |
| 10 | **Onboarding Pós-Compra** *(novo)* | `post_purchase_onboarding` | Opcional | Mensagem de boas-vindas + próximos passos enviados automaticamente após pagamento confirmado. Reduz chargeback e aumenta satisfação. |

**Lacuna atual vs. já implementado:**
Categorias 1–7 já estão em `KNOWLEDGE_CATEGORIES_BY_TEMPLATE.closer_agressivo`. As categorias 8, 9 e 10 são novas propostas.

---

### 2.3 Agente 03 — Assistente Comercial Híbrido (`hybrid_scheduler`)

**Missão:** Assistente comercial que responde dúvidas de forma natural e persuasiva para gerar agendamentos. Pode apresentar planos e preços durante a conversa, mas o pagamento **sempre ocorre presencialmente** na marcação — nunca via link de pagamento digital. O agente agenda; o dinheiro passa na mão.

**Cenários cobertos:**
- Inbound: lead demonstrou interesse ativo (mensagem, formulário, link de agendamento)
- Outbound: prospecção com tom pessoal ("o [Profissional] me pediu para entrar em contato")

**Exemplo de nicho:** massagista que atende por sessão avulsa ou pacotes mensais. O agente responde sobre tipos de massagem, duração, preços, disponibilidade — e fecha o agendamento com ou sem compromisso de pacote.

#### Dois sub-modos de operação

O Agente 3 opera em dois sub-modos distintos conforme a configuração do usuário. As categorias de conhecimento necessárias diferem entre eles.

| Sub-modo | Objetivo do agendamento | O agente apresenta preço? | Pagamento |
|---|---|---|---|
| **Compromisso comercial** | Lead agenda já comprometido com um plano/pacote/serviço | Sim — apresenta tabela e fecha escolha antes de agendar | Presencial na marcação |
| **Sem compromisso** | Lead agenda uma sessão de diagnóstico/exploração sem pressão de compra | Não obrigatório — responde se perguntado, mas não conduz | Presencial (se houver) |

---

#### Categorias de conhecimento — Base comum (ambos os sub-modos)

Estas categorias são necessárias independentemente do sub-modo:

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 1 | **Bio do Profissional** | `professional_bio` | Crítico | Primeira coisa que o lead quer saber: quem é? Por que confiar? O agente usa para se apresentar em nome do profissional. |
| 2 | **Histórias de Transformação** | `social_proof` | Crítico | Usada no aquecimento (AQ). O lead se identifica com um caso parecido — aumenta confiança e motivação para agendar. |
| 3 | **Preview da Sessão / Serviço** | `session_preview` | Crítico | Descreve o que acontece na marcação: duração, formato, o que o lead pode esperar. Reduz ansiedade e aumenta comparecimento. |
| 4 | **Política de Agendamento** | `scheduling_policy` | Recomendado | Regras de cancelamento, reagendamento e no-show. O lead pergunta antes de confirmar — sem resposta clara, desiste. |
| 5 | **Script de Aquecimento** | `warming_script` | Recomendado | Texto que conecta a dor ou necessidade do lead com o que o profissional resolve. Usado antes de propor o agendamento. |
| 6 | **Follow-up Pós-Sessão** | `post_session_followup` | Opcional | Mensagens para quem veio mas não retornou: reconectar, propor nova marcação, citar resultado que ficou pendente. |
| 7 | **Script de Indicação** | `referral_script` | Opcional | Pedido de indicação para clientes satisfeitos. Momento ideal: após confirmar que a sessão foi bem. |

---

#### Categorias de conhecimento — Compromisso comercial

Adicionadas ao base comum quando o objetivo é fechar um plano ou pacote antes de agendar:

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 8 | **Tabela de Serviços e Preços** *(novo)* | `service_pricing_table` | Crítico | O agente precisa apresentar planos, pacotes e valores com precisão. Ex.: "Massagem relaxante 60 min — R$ 120 / Pacote 4 sessões — R$ 420". Sem isso improvisa preços ou diz "não sei informar". |
| 9 | **Objeções Comerciais** *(novo)* | `commercial_objections` | Crítico | Objeções típicas antes de fechar um pacote: "está caro", "vou pensar", "deixa eu ver minha agenda". O agente precisa de respostas persuasivas prontas — sem elas perde o compromisso antes de agendar. |
| 10 | **Diferenciais do Serviço** *(novo)* | `service_differentials` | Recomendado | Por que escolher este profissional vs. outro? Técnica, formação, ambiente, localização, materiais usados. Usado quando o lead compara com alternativas. |
| 11 | **Condição Especial Vigente** *(novo)* | `active_promotion` | Recomendado | Desconto, bônus ou condição limitada atual. Mantido separado da tabela de preços porque muda com frequência. O agente cita apenas se for verdade — não inventa urgência. |
| 12 | **Política de Pagamento Presencial** *(novo)* | `payment_policy` | Recomendado | Formas aceitas na hora: Pix, dinheiro, cartão. Valor de entrada ou sinal para reservar vaga (se houver). Sem isso o lead chega sem saber como pagar. |
| 13 | **FAQ Pré-Compromisso** *(novo)* | `pre_commitment_faq` | Recomendado | Perguntas frequentes antes de fechar o pacote: "posso pausar?", "as sessões vencem?", "consigo transferir para outra pessoa?". Reduz dúvidas que travam o sim. |

---

#### Categorias de conhecimento — Sem compromisso

Adicionadas ao base comum quando o objetivo é apenas gerar uma marcação exploratória:

| # | Categoria | Chave | Importância | Por que é necessária |
|---|---|---|---|---|
| 8 | **Roteiro de Perguntas de Contexto** | `pain_questions` | Recomendado | Perguntas abertas para entender o que o lead busca. As respostas viram o briefing enviado ao profissional antes da sessão — ele chega preparado. |
| 9 | **FAQ do Serviço (sem preço obrigatório)** | `service_faq` | Recomendado | Dúvidas gerais sobre o serviço: duração, formato, localização. O agente responde se perguntado sobre preço, mas não conduz a conversa para lá. |
| 10 | **Material Pré-Sessão** | `pre_session_material` | Opcional | Instrução ou formulário enviado 24h antes para o lead chegar preparado. |

---

#### Implicação para a UX da Camada 4

O sub-modo deve ser determinado por um campo de configuração na Camada 1 ou Camada 3 (ainda não existente): algo como `appointment_mode: 'commercial' | 'exploratory'`. Com base nesse valor, a Camada 4 exibe conjuntos de categorias diferentes — a base comum sempre aparece; o bloco comercial ou o bloco exploratório aparece condicionalmente.

**Lacuna atual vs. já implementado:**
O `hybrid_scheduler` em `KNOWLEDGE_CATEGORIES_BY_TEMPLATE` cobre parcialmente o sub-modo "sem compromisso" (categorias 1–3 do base + `pain_questions`, `scheduling_policy`, `service_faq`, `pre_session_material`). O sub-modo "compromisso comercial" (categorias 8–13) não existe ainda — são novas propostas. O campo `appointment_mode` também não existe.

---

## 3. UX de preenchimento orientativo

### 3.1 Problema atual

O componente `CamadaConhecimento.tsx` já tem a estrutura correta (seções guiadas por template + conteúdo extra livre). O problema é que o usuário vê uma lista de cards com apenas um botão "Preencher →" — não há **orientação progressiva** nem **personalização pelos dados que ele já preencheu** nas Camadas 1 e 2.

**Lacunas de UX identificadas:**
1. O usuário não sabe por onde começar (crítico vs. opcional não é suficiente)
2. Os exemplos nos `placeholder` são genéricos — não usam o nicho/oferta que o usuário preencheu na Camada 2
3. Não há indicação de "como fica bom vs. ruim"
4. Usuário que acabou de configurar o agente chega numa tela de lista fria — sem contexto de por que precisa preencher
5. Não há feedback visual de "o agente está pronto para usar"

### 3.2 Proposta de UX: Preenchimento Guiado em 3 Modos

#### Modo 1 — Onboarding Wizard (Primeira vez)
Quando o usuário não tem nenhum item preenchido, substituir a lista de cards por um **wizard passo a passo**:

```
[Passo 1/3] → Identidade do Agente
  "Antes de preencher, quero confirmar 2 coisas rápidas
   sobre o negócio — já temos esses dados, só confirme:"
  ✓ Nicho: [valor da Camada 2 — editável]
  ✓ Oferta: [valor da Camada 2 — editável]
  ✓ Público-alvo: [valor da Camada 2 — editável]

[Passo 2/3] → Seções Críticas
  Apresenta apenas as 3 seções de importância "critical",
  uma de cada vez, com exemplos PRÉ-PREENCHIDOS usando o
  nicho e oferta confirmados no passo 1.

[Passo 3/3] → Seções Recomendadas
  Apresenta as seções "recommended" com opção de pular.
```

#### Modo 2 — Edição contextual (Retorno)
Após primeira configuração, mantém a lista atual de cards mas com:
- **Barra de progresso visual** de completude (ex: "5 de 6 seções críticas preenchidas")
- **Destaque da seção mais urgente** com CTA claro ("O agente precisa disso para funcionar bem")
- **Tooltip de impacto** em cada card: qual estágio do fluxo usa aquela informação

#### Modo 3 — Revisão periódica
Para categorias com dados temporais (`urgency_offer`, `cart_recovery_scripts`):
- **Badge de "Atualização necessária"** quando a oferta tem mais de 30 dias sem edição
- Sugestão de revisão ao abrir a aba

### 3.3 Personalização dos exemplos pelos dados da Camada 2

O maior ganho de UX é usar o que o usuário **já preencheu** para pré-personalizar os placeholders e hints. Exemplo:

**Caso genérico (atual):**
```
hint: "Descreva: nome oficial, segmento, o que entrega, para quem..."
placeholder: "Nome: [Empresa]\nSegmento: [Ex: Software B2B]..."
```

**Caso personalizado (proposta):**
```
// Se config.niche = "clínica estética" e config.target_audience = "mulheres 30-50 anos"
hint: "Descreva quem é sua clínica e o que ela entrega para mulheres que querem tratamentos estéticos"
placeholder: "Nome: [Clínica]\nSegmento: Estética e beleza\nO que entrega: tratamentos para mulheres de 30 a 50 anos..."
```

**Implementação:** O componente `CamadaConhecimento` já recebe `templateKey` como prop. Adicionar `agentConfig: Partial<AgentConfig>` como segunda prop e usar os campos `niche`, `target_audience`, `offer_description` para gerar hints/placeholders dinâmicos via função pura.

### 3.4 Indicador de "Agente Pronto"

Em vez de apenas contar críticos, mostrar um **score de prontidão** dividido em 3 níveis:

| Nível | Critério | Mensagem |
|---|---|---|
| 🔴 Não funcional | Menos de 2 seções críticas preenchidas | "O agente não tem informações suficientes para responder bem." |
| 🟡 Funcional básico | Todas as seções críticas preenchidas | "O agente consegue operar, mas sem diferenciação." |
| 🟢 Otimizado | Todas críticas + pelo menos 2 recomendadas | "O agente está pronto para operar com alta performance." |

---

## 4. Plano de implementação

### Fase 1 — Novas categorias de conhecimento (sem nova UI)

**Objetivo:** Adicionar as categorias que faltam em `agente.ts` para os 3 templates.
**Complexidade:** Baixa — apenas dados, sem lógica nova.
**Arquivo:** `frontend-crm/src/types/agente.ts`

| Template | Categoria nova | Chave | Importância |
|---|---|---|---|
| `sdr_padrao` + `consultor_especialista` | Script de Dossiê | `handoff_briefing_template` | Recomendado |
| `sdr_padrao` + `consultor_especialista` | Diferenciação Competitiva | `competitive_differentials` | Opcional |
| `sdr_padrao` + `consultor_especialista` | Mensagens de Nurture | `nurture_content` | Opcional |
| `closer_agressivo` | Script de Recuperação de Carrinho | `cart_recovery_scripts` | Recomendado |
| `closer_agressivo` | Perguntas de Fit | `fit_questions` | Recomendado |
| `closer_agressivo` | Onboarding Pós-Compra | `post_purchase_onboarding` | Opcional |
| `hybrid_scheduler` | Script de Aquecimento | `warming_script` | Recomendado |
| `hybrid_scheduler` | Follow-up Pós-Sessão | `post_session_followup` | Opcional |
| `hybrid_scheduler` | Script de Indicação | `referral_script` | Opcional |

**Cada nova categoria precisa de:**
- `key`, `label`, `description` — identificação
- `hint` — instrução clara de o que escrever (1–4 linhas)
- `placeholder` — exemplo estruturado de conteúdo de qualidade
- `importance` — `critical` / `recommended` / `optional`

---

### Fase 2 — Score de prontidão do agente

**Objetivo:** Substituir o contador "X/Y críticas preenchidas" por um indicador visual com 3 níveis (Não funcional / Básico / Otimizado).
**Complexidade:** Baixa — cálculo simples + CSS.
**Arquivo:** `frontend-crm/src/components/agente/CamadaConhecimento.tsx`

Lógica:
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

### Fase 3 — Personalização dos hints por contexto da Camada 2

**Objetivo:** Gerar hints e placeholders dinamicamente usando os dados de negócio já preenchidos.
**Complexidade:** Média — requer refactor da assinatura do componente + função de geração.
**Arquivos:** `CamadaConhecimento.tsx`, `AgenteConfiguracao.tsx`

**Passo 3a:** Passar `agentConfig` como prop para `CamadaConhecimento`:
```tsx
// AgenteConfiguracao.tsx
<CamadaConhecimento templateKey={config.template_key} agentConfig={config} />
```

**Passo 3b:** Criar função `getPersonalizedCategory(cat, config)` que retorna versão modificada de `hint` e `placeholder` substituindo tokens como `[NICHO]`, `[OFERTA]`, `[PÚBLICO]` pelos valores reais:
```typescript
function getPersonalizedCategory(
  cat: KnowledgeCategory,
  config: Partial<AgentConfig>
): KnowledgeCategory {
  const niche = config.niche || '[nicho do negócio]';
  const audience = config.target_audience || '[público-alvo]';
  const offer = config.offer_description || '[descrição da oferta]';
  return {
    ...cat,
    hint: cat.hint
      .replace('[NICHO]', niche)
      .replace('[PÚBLICO]', audience)
      .replace('[OFERTA]', offer),
    placeholder: cat.placeholder
      .replace('[NICHO]', niche)
      .replace('[PÚBLICO]', audience)
      .replace('[OFERTA]', offer),
  };
}
```

**Passo 3c:** Atualizar as definições de categorias em `agente.ts` para incluir os tokens substituíveis nos campos `hint` e `placeholder`.

---

### Fase 4 — Wizard de onboarding (primeira configuração)

**Objetivo:** Guiar o usuário passo a passo quando a base de conhecimento está vazia.
**Complexidade:** Alta — novo componente de wizard com estado próprio.
**Arquivo:** Novo `CamadaConhecimentoWizard.tsx` + modificação em `CamadaConhecimento.tsx`

**Lógica de ativação:**
```typescript
// Em CamadaConhecimento.tsx
const isFirstTime = items.length === 0 && guidedCategories.length > 0;
if (isFirstTime) return <CamadaConhecimentoWizard ... />;
```

**Estrutura do wizard:**
1. **Passo de contexto** — confirmar nicho, oferta e público (pré-preenchidos da Camada 2, editáveis)
2. **Seções críticas** — uma de cada vez, com hint personalizado + preview do placeholder preenchido
3. **Seções recomendadas** — com opção "Pular por agora" + indicador de impacto
4. **Conclusão** — score de prontidão + atalho para adicionar conteúdo extra

---

### Fase 5 — Badge de atualização temporal (para closer_agressivo)

**Objetivo:** Alertar quando `urgency_offer` e `cart_recovery_scripts` estão desatualizados (> 30 dias).
**Complexidade:** Baixa — verificar `updated_at` no card.
**Arquivo:** `CamadaConhecimento.tsx`

```typescript
function isStale(item: KnowledgeItem, days = 30): boolean {
  const updated = new Date(item.updated_at);
  const now = new Date();
  return (now.getTime() - updated.getTime()) / (1000 * 60 * 60 * 24) > days;
}
```

Mostrar badge "Atualizar" em vermelho no card quando `isStale(item)` for `true` para as chaves `urgency_offer` e `cart_recovery_scripts`.

---

## 5. Ordem de prioridade de implementação

| Fase | Impacto | Complexidade | Recomendação |
|---|---|---|---|
| **Fase 1** — Novas categorias | Alto | Baixa | Implementar primeiro — adiciona valor imediato sem risco |
| **Fase 2** — Score de prontidão | Médio | Baixa | Implementar junto com Fase 1 |
| **Fase 5** — Badge temporal | Médio | Baixa | Implementar junto com Fase 1+2 |
| **Fase 3** — Hints personalizados | Alto | Média | Implementar após Fase 1 |
| **Fase 4** — Wizard de onboarding | Alto | Alta | Implementar por último — maior ganho, maior risco |

---

## 6. Referências no código

| Arquivo | Relevância |
|---|---|
| [frontend-crm/src/types/agente.ts](../frontend-crm/src/types/agente.ts) | `KnowledgeCategory`, `KNOWLEDGE_CATEGORIES_BY_TEMPLATE` |
| [frontend-crm/src/components/agente/CamadaConhecimento.tsx](../frontend-crm/src/components/agente/CamadaConhecimento.tsx) | Componente principal da aba Camada 4 |
| [frontend-crm/src/pages/AgenteConfiguracao.tsx](../frontend-crm/src/pages/AgenteConfiguracao.tsx) | Orquestrador — passa `templateKey` para `CamadaConhecimento` |
| [frontend-crm/src/pages/TiposAgentes.tsx](../frontend-crm/src/pages/TiposAgentes.tsx) | Fonte dos fluxos de cada agente (`AGENTS` array) |
| [backend-crm/routes/knowledge.py](../backend-crm/routes/knowledge.py) | API CRUD de itens de conhecimento |
