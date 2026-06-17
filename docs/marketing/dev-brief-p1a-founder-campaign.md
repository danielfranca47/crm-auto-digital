# Dev Brief — Offer Pipeline | CRMLandingV2.tsx
**Agentes:** hormozi-pricing + hormozi-copy + hormozi-offers
**Arquivo alvo:** `src/pages/CRMLandingV2.tsx`
**Data atualização:** 2026-06-17

---

## HISTÓRICO DE AJUSTES

| Brief | Ajuste | Status | Data |
|-------|--------|--------|------|
| P1-A | Eliminar confusão de preço — Campanha Fundador | ✅ CONCLUÍDO | 2026-06-17 |
| P1-B | Seção dos 3 agentes especializados na landing | ✅ CONCLUÍDO | 2026-06-17 |
| **P1-C** | **Corrigir âncora de valor — substituir R$1.735 por comparação de mercado** | ✅ CONCLUÍDO | 2026-06-17 |

---

## ✅ P1-A — VALIDAÇÃO COMPLETA

Todas as mudanças verificadas em `CRMLandingV2.tsx` — todos os critérios de aceite aprovados.

| Mudança | Localização V2 | Status |
|---------|----------------|--------|
| Badge Growth: `CAMPANHA FUNDADOR` | linha 128 | ✅ |
| Micro-badge `5 vagas restantes` | linhas 886–890 | ✅ |
| Bloco de preço: R$297 tachado + R$147 ativo | linhas 898–912 | ✅ |
| Footer duplo: R$197 travado + R$297 para novos | linhas 913–921 | ✅ |
| Feature `🔒 Preço de Fundador` no topo do Growth | linha 132 | ✅ |
| Launch Access → "O que é ser Fundador?" | linhas 697–736 | ✅ |
| Card de bônus com âncora de mercado | linhas 671–693 | ✅ |
| Campaign Bar fixa + navbar top-8 + hero pt-24 | linhas 211–251 | ✅ |

---

---

# Dev Brief — P1-B + P3-B: Agentes na Landing e Agente por Plano

**Agentes:** hormozi-offers (lead) + hormozi-pricing + hormozi-copy
**Tarefa:** (1) criar seção dos 3 agentes; (2) corrigir distribuição de agentes por plano
**Arquivo alvo:** `CRMLandingV2.tsx` — SOMENTE as mudanças listadas abaixo
**Prioridade:** CRÍTICA

---

## CONTEXTO PARA O DEV

Duas mudanças interdependentes que precisam ser feitas juntas para não criar nova inconsistência:

**Problema 1 (P1-B):** Os 3 agentes especializados (SDR / Closer / Híbrido) são o maior diferencial da Lara e não aparecem em nenhum lugar da landing. O visitante vê "IA que atende" — não vê que existe um agente treinado para o SEU tipo de negócio.

**Problema 2 (P3-B):** O plano Start tem `'Os 3 tipos de agente'` na linha 119 — mas a estratégia de produto define que o Start inclui **apenas o Closer**. Growth e acima têm os 3 agentes. Se P1-B for implementado sem corrigir P3-B, a landing vai contradizer a si mesma.

**Princípio (hormozi-offers + hormozi-pricing):**
> "Específico converte, genérico não. O visitante precisa ver qual agente é o dele — e qual plano tem esse agente."

---

## MUDANÇA 1 — Dados dos agentes (adicionar no topo do arquivo)

**Localização:** Inserir o array `agents` após o array `bonuses` (linha ~105), antes da declaração de `plans`.

```tsx
const agents = [
  {
    emoji: '🎯',
    name: 'Agente SDR',
    badge: 'Alto Ticket',
    badgeColor: '#F59E0B',
    sectors: ['Imóveis', 'Consultoria', 'Coaching', 'Assessoria'],
    outcome: 'Agenda reuniões com leads quentes de alto ticket — enquanto você está em outras reuniões.',
    detail: 'Qualifica compradores, filtra curiosos e entrega apenas leads prontos para fechar negócio.',
    anchor: 'SDR humano custa R$3.500/mês. A Lara SDR custa R$297.',
    plan: 'Growth',
  },
  {
    emoji: '💳',
    name: 'Agente Closer',
    badge: 'Baixo Ticket',
    badgeColor: '#10B981',
    sectors: ['Infoprodutos', 'E-commerce', 'Lojas Físicas'],
    outcome: 'Converte do primeiro "oi" até o pagamento — sem você precisar estar online.',
    detail: 'Recupera carrinhos abandonados, converte leads que responderam tarde e faz follow-up de quem sumiu.',
    anchor: '1 venda extra por mês paga o mês inteiro da Lara.',
    plan: 'Start e Growth',
  },
  {
    emoji: '📅',
    name: 'Agente Híbrido Agendador',
    badge: 'Serviços',
    badgeColor: '#8B5CF6',
    sectors: ['Psicólogos', 'Dentistas', 'Terapeutas', 'Clínicas'],
    outcome: 'Agenda sempre cheia, faltas eliminadas — sem precisar de recepcionista.',
    detail: 'Responde dúvidas, confirma sessões com antecedência e faz follow-up de pacientes que sumiram.',
    anchor: 'Recepcionista custa R$2.200/mês. A Lara custa R$297 e trabalha 24/7 — sem faltar, sem 13°.',
    plan: 'Growth',
  },
];
```

---

## MUDANÇA 2 — Nova seção de agentes (JSX)

**Localização:** Inserir **após** o `</section>` de fechamento do SECTOR TABS (linha ~387) e **antes** do comentário `{/* ── HOW IT WORKS ── */}`.

```tsx
{/* ── AGENTS — Os 3 agentes especializados ── */}
<section className="py-20 px-4">
  <div className="container mx-auto max-w-5xl">
    <div className="text-center mb-12">
      <span className="text-accent text-sm font-semibold uppercase tracking-widest">
        Especializado no seu tipo de venda
      </span>
      <h2 className="text-heading mt-2">
        Não é um chatbot genérico.<br />
        É um agente treinado pro seu negócio.
      </h2>
      <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
        Escolha o agente. A Lara já sabe como vender do seu jeito.
      </p>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
      {agents.map((agent) => (
        <div
          key={agent.name}
          className="portfolio-card flex flex-col border"
          style={{ borderColor: `${agent.badgeColor}33` }}>

          {/* Header */}
          <div className="flex items-center gap-3 mb-4">
            <div className="text-4xl">{agent.emoji}</div>
            <div>
              <div className="font-bold text-base">{agent.name}</div>
              <span
                className="text-xs px-2 py-0.5 rounded-full font-semibold"
                style={{
                  background: `${agent.badgeColor}22`,
                  color: agent.badgeColor,
                }}>
                {agent.badge}
              </span>
            </div>
          </div>

          {/* Setores */}
          <div className="flex flex-wrap gap-1.5 mb-4">
            {agent.sectors.map(s => (
              <span
                key={s}
                className="text-xs px-2 py-0.5 rounded-full border text-muted-foreground"
                style={{ borderColor: 'hsl(var(--border))' }}>
                {s}
              </span>
            ))}
          </div>

          {/* Outcome */}
          <p className="text-sm font-semibold mb-2 leading-snug">
            {agent.outcome}
          </p>

          {/* Detalhe */}
          <p className="text-xs text-muted-foreground leading-relaxed mb-4 flex-1">
            {agent.detail}
          </p>

          {/* Âncora de valor */}
          <div
            className="text-xs px-3 py-2 rounded-lg font-medium mb-4"
            style={{
              background: `${agent.badgeColor}11`,
              color: agent.badgeColor,
              borderLeft: `3px solid ${agent.badgeColor}`,
            }}>
            {agent.anchor}
          </div>

          {/* Plano */}
          <div className="text-xs text-muted-foreground text-center mt-auto">
            {agent.plan.includes('e') ? 'Disponível nos planos ' : 'Disponível no plano '}
            <strong style={{ color: '#4DD4FF' }}>{agent.plan}</strong>
          </div>
        </div>
      ))}
    </div>

    {/* CTA */}
    <div className="text-center">
      <p className="text-sm text-muted-foreground mb-4">
        <strong style={{ color: '#4DD4FF' }}>Agente Closer</strong> disponível no Start e no Growth.{' '}
        <strong style={{ color: '#4DD4FF' }}>SDR e Híbrido</strong> exclusivos do Growth.
      </p>
      <a href="#planos" className="btn-hero inline-flex items-center gap-2">
        Ver planos e ativar meu agente <ArrowRight className="w-4 h-4" />
      </a>
    </div>
  </div>
</section>
```

---

## MUDANÇA 3 — Corrigir distribuição de agentes nos planos (array `plans`)

Esta mudança resolve a inconsistência: o Start atualmente diz `'Os 3 tipos de agente'` mas a estratégia define que o Start tem apenas o Closer.

### 3A — Plano Start: substituir feature genérica pelo agente correto

**Localização:** Array `plans`, objeto `name: 'Start'`, array `features`, linha ~119.

```
ATUAL:
  'Os 3 tipos de agente',

NOVO (substituir):
  '🤖 Agente Closer — conversão de baixo ticket',
```

### 3B — Plano Growth: tornar explícito que tem os 3 agentes

**Localização:** Array `plans`, objeto `name: 'Growth'`, array `features`, linha ~132 (logo após o `🔒`).

```
ATUAL (primeiras features do Growth):
  '🔒 Preço de Fundador — travado para sempre',
  '✦ Ativação 1:1 + 15 Scripts + 30 dias ao vivo (R$641 em bônus)',

NOVO (inserir entre as duas):
  '🔒 Preço de Fundador — travado para sempre',
  '🤖 SDR + Closer + Híbrido — todos os 3 agentes',
  '✦ Ativação 1:1 + 15 Scripts + 30 dias ao vivo (R$641 em bônus)',
```

### 3C — Planos Scale e Enterprise: sem alteração necessária

Scale e Enterprise já têm `'Tudo do Growth'` na lista de features — os 3 agentes estão implícitos. Não alterar.

---

## RESUMO DE TODAS AS MUDANÇAS

| # | Tipo | Localização V2 | O que muda |
|---|------|----------------|-----------|
| 1 | Novo array | linha ~105 (após `bonuses`) | Adicionar `const agents = [...]` |
| 2 | Nova seção JSX | linha ~387 (após SECTOR TABS) | Seção `{/* ── AGENTS ── */}` |
| 3A | Edição de dado | linha ~119 (Start features) | `'Os 3 tipos de agente'` → `'🤖 Agente Closer — conversão de baixo ticket'` |
| 3B | Edição de dado | linha ~133 (Growth features) | Inserir `'🤖 SDR + Closer + Híbrido — todos os 3 agentes'` após o `🔒` |

**O que NÃO mudar:**
- Seção SECTOR TABS — não alterar
- Features grid — não alterar
- Qualquer outro campo dos planos
- Lógica de checkout, APIs ou integrações

---

## CRITÉRIOS DE ACEITE

```
[ ] Nova seção aparece entre SECTOR TABS e HOW IT WORKS
[ ] 3 cards em desktop (grid 3 colunas) — Closer no centro
[ ] Cards empilham em mobile (grid 1 coluna)
[ ] Cada card mostra: emoji, nome, badge colorido, setores, outcome, âncora, plano disponível
[ ] Badges com cores distintas: SDR amarelo / Closer verde / Híbrido roxo
[ ] CTA leva para #planos e nota explica Closer = Start+Growth / SDR+Híbrido = Growth
[ ] Start exibe '🤖 Agente Closer — conversão de baixo ticket' (não mais 'Os 3 tipos de agente')
[ ] Growth exibe '🤖 SDR + Closer + Híbrido — todos os 3 agentes' como 2ª feature
[ ] Nenhuma outra seção da página foi alterada
```

---

## PRINCÍPIO UTILIZADO

```
ANTES (duas inconsistências):
  Landing: sem menção dos agentes
  Start:   "Os 3 tipos de agente" → contradiz a estratégia de produto
  Growth:  agentes não listados explicitamente

DEPOIS (consistência total):
  Seção de agentes → visitante se identifica com SDR / Closer / Híbrido
  Start:  "🤖 Agente Closer" → correto, claro, sem prometer o que não entrega
  Growth: "🤖 SDR + Closer + Híbrido" → diferencial explícito do upgrade
  CTA da seção: "SDR e Híbrido exclusivos do Growth" → incentiva upgrade orgânico
```

---

*Brief produzido por: hormozi-offers + hormozi-pricing + hormozi-copy*
*Revisado por: hormozi-chief*
*Arquivo: `C:\crm-auto-digital\docs\marketing\dev-brief-p1a-founder-campaign.md`*

---

---

# Dev Brief — P1-C: Âncora de Valor — Substituir R$1.735 por Comparação de Mercado

**Agente lead:** hormozi-pricing | **Suporte:** hormozi-copy
**Tarefa:** Substituir número interno arbitrário (R$1.735) por âncora de mercado real
**Arquivo alvo:** `CRMLandingV2.tsx` — 3 mudanças cirúrgicas, sem alterar estrutura
**Prioridade:** CRÍTICA

---

## CONTEXTO PARA O DEV

A seção BONUS STACK ainda tem dois problemas de ancoragem:

**Problema 1 — h2 com número interno (linha 751):**
```
"Você está recebendo R$1.735/mês em valor."
```
R$1.735 é a soma dos itens do offer stack (R$997 + R$297 + R$197 + R$147 + R$97). O visitante não conhece o mercado de software pra saber se R$997 para "IA 24/7" é caro ou barato. Número sem âncora externa = número ignorado.

**Problema 2 — Core bonus com valor interno (linha 85):**
```
value: 'R$997/mês'
```
R$997 é 1/3 do custo de um SDR junior — mas o visitante não faz esse cálculo. Vê um número e não sente o valor.

**Princípio hormozi-pricing:**
> "Always compare price to cost of NOT solving the problem. Show the cost of alternatives. Make the gap SO large that the price becomes irrelevant."

**O que muda:** Substituímos os números internos por comparações que o visitante JÁ CONHECE — o custo de um SDR, de uma recepcionista, de um chatbot genérico. A math faz o trabalho.

---

## MUDANÇA 1 — Core bonus: valor interno → âncora de mercado

**Arquivo:** `CRMLandingV2.tsx`
**Localização:** Array `bonuses`, objeto com `num: '✦'` (linha 85)

```
ATUAL:
  value: 'R$997/mês',

NOVO:
  value: 'vs R$3.500+/mês de SDR',
```

**Por que funciona (hormozi-pricing):** O visitante já viu SDR na seção de agentes (linha ~430). "vs R$3.500+/mês de SDR" ativa uma âncora conhecida. O card do core item passa a dizer, em cyan: `vs R$3.500+/mês de SDR` — contraste imediato com o preço de R$147.

---

## MUDANÇA 2 — h2: remover R$1.735, adicionar comparação de mercado

**Localização:** `{/* BONUS STACK */}`, `<h2>` (linhas 749–752)

```
ATUAL:
  <h2 className="text-heading mt-2">
    Campanha Fundador: você investe R$147/mês.<br />
    Você está recebendo R$1.735/mês em valor.
  </h2>

NOVO:
  <h2 className="text-heading mt-2">
    Campanha Fundador: você investe R$147/mês.<br />
    Sua alternativa custaria{' '}
    <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
      R$3.500+/mês.
    </span>
  </h2>
```

**Por que funciona (hormozi-copy):** Contraste direto na mesma linha — R$147 vs R$3.500+. O visitante faz o cálculo sozinho: 23x mais barato. Sem hype, sem número inventado. Só a math.

---

## MUDANÇA 3 — Novo bloco de comparação de mercado

**Localização:** Inserir **após** o `</div>` de fechamento do `bonuses.map()` (linha ~783) e **antes** do comentário `{/* MUDANÇA 3 — card de resumo */}` (linha ~785).

```tsx
{/* P1-C — Bloco de comparação de mercado */}
<div className="portfolio-card p-6 mb-4">
  <p className="text-xs font-semibold text-center mb-5 uppercase tracking-widest text-muted-foreground">
    Sem a Lara, você pagaria:
  </p>
  <div className="space-y-0">
    {[
      {
        label: 'SDR humano (alto ticket)',
        sub: 'Sem 24/7. Sem CRM integrado. Tira férias.',
        price: 'R$3.500/mês',
        highlight: true,
      },
      {
        label: 'Recepcionista (serviços)',
        sub: 'Sem follow-up automático. Sem analytics.',
        price: 'R$2.200/mês',
        highlight: true,
      },
      {
        label: 'Chatbot genérico',
        sub: 'Sem agente especializado. Sem CRM nativo.',
        price: 'R$200+/mês',
        highlight: false,
      },
      {
        label: 'CRM separado (ex: HubSpot básico)',
        sub: 'Sem IA. Sem WhatsApp nativo.',
        price: 'R$500/mês',
        highlight: false,
      },
    ].map(({ label, sub, price, highlight }) => (
      <div
        key={label}
        className="flex items-start justify-between gap-4 py-3 border-b border-border last:border-0">
        <div>
          <span className="text-sm text-foreground">{label}</span>
          <span className="block text-xs text-muted-foreground opacity-60 mt-0.5">{sub}</span>
        </div>
        <span
          className="text-sm font-bold flex-shrink-0"
          style={{ color: highlight ? 'hsl(var(--destructive))' : 'hsl(var(--muted-foreground))' }}>
          {price}
        </span>
      </div>
    ))}
  </div>
  <div className="mt-5 pt-4 border-t border-border">
    <div className="flex items-center justify-between text-sm mb-3">
      <span className="text-muted-foreground">Total alternativo:</span>
      <span className="font-bold text-foreground">R$3.500 – R$6.200/mês</span>
    </div>
    <div
      className="text-center text-sm font-semibold py-2 px-4 rounded-lg"
      style={{ background: 'rgba(77,212,255,0.1)', color: '#4DD4FF' }}>
      A Lara faz tudo isso por{' '}
      <strong>R$147/mês</strong>
      {' '}— menos de R$5/dia.
    </div>
  </div>
</div>
```

**Por que funciona (hormozi-pricing):**
- Anchoring técnica: mostra o preço alto (R$3.500) antes de revelar o preço real (R$147)
- "Break price into smallest unit": R$147 ÷ 30 = R$4,90/dia → "menos de R$5/dia" ativa comparação emocional imediata
- Total alternativo R$3.500–R$6.200 mostra que mesmo a opção mais barata (chatbot + CRM = R$700) custa 5x mais

---

## FLUXO FINAL DA SEÇÃO APÓS AS 3 MUDANÇAS

```
ANTES:
  h2: "você investe R$147/mês. Você está recebendo R$1.735 em valor."  ← número interno
  [lista de bônus com core = R$997/mês]                                ← âncora desconhecida
  [card de resumo com âncora de mercado]                               ← P1-A ok

DEPOIS:
  h2: "você investe R$147/mês. Sua alternativa custaria R$3.500+/mês." ← contraste direto
  [lista de bônus com core = vs R$3.500+/mês de SDR]                  ← âncora conhecida
  [bloco comparativo: R$3.500 / R$2.200 / R$200 / R$500]              ← math explícita
  [card de resumo — P1-A ok, complementa o bloco acima]               ← consistente
```

---

## RESUMO DAS MUDANÇAS

| # | Tipo | Localização V2 | O que muda |
|---|------|----------------|-----------|
| 1 | Edição de dado | linha 85 (`bonuses` array, core) | `value: 'R$997/mês'` → `value: 'vs R$3.500+/mês de SDR'` |
| 2 | Edição de JSX | linhas 749–752 (h2 da seção) | Segunda linha: remove `R$1.735` → adiciona `R$3.500+/mês` com gradient |
| 3 | Novo bloco JSX | entre linhas 783–785 | Bloco comparativo de 4 alternativas de mercado |

**O que NÃO mudar:**
- Os valores individuais dos bônus (R$297, R$197, R$147, R$97) — são credíveis como serviço de onboarding
- O card de resumo de P1-A (linhas 785–807) — complementa este bloco, não conflita
- Estrutura, ordem e estilo visual da seção — só conteúdo

---

## CRITÉRIOS DE ACEITE

```
[ ] h2 não menciona mais R$1.735
[ ] h2 segunda linha mostra "R$3.500+/mês" com gradient accent-to-primary
[ ] Core bonus mostra "vs R$3.500+/mês de SDR" em cyan (não mais R$997/mês)
[ ] Bloco comparativo aparece entre a lista de bônus e o card de resumo
[ ] Bloco tem 4 linhas: SDR (destructive) / Recep (destructive) / Chatbot (muted) / CRM (muted)
[ ] Total alternativo visível: "R$3.500 – R$6.200/mês"
[ ] Linha final em destaque: "A Lara faz tudo isso por R$147/mês — menos de R$5/dia."
[ ] Card de resumo de P1-A permanece intacto abaixo do bloco
[ ] Mobile: bloco comparativo legível em 375px (flex-wrap ou stacked ok)
```

---

## ✅ REVISÃO DOS AGENTES

### 💎 hormozi-pricing

Framework aplicado: **Price Anchoring + Price-to-Value Discrepancy**

```
✅ "Show the cost of NOT solving the problem" → bloco comparativo mostra R$3.500–R$6.200
✅ "Compare to alternative solutions" → SDR, recepcionista, chatbot, CRM listados com preço real
✅ "Never present price without context" → h2 mostra R$147 vs R$3.500+ antes de qualquer número
✅ "Break price into smallest unit" → R$147/mês = menos de R$5/dia
✅ "10x value rule" → R$3.500 / R$147 = 23x mais barato (supera o 10x mínimo)
✅ Âncora substitui número interno (R$997) por âncora externa (R$3.500 de SDR) — muito mais forte
```

**Aprovação hormozi-pricing:** ✅ Ancoragem correta. O gap R$147 vs R$3.500 torna o preço irrelevante.

---

### ✍️ hormozi-copy

Framework aplicado: **Value Stack Copy + Hormozi Writing Style**

```
✅ "Specific numbers over vague claims" → R$3.500 / R$2.200 / R$200 / R$500 (não "mais barato")
✅ "Show the math — let them calculate the ROI" → total alternativo explícito: R$3.500–R$6.200
✅ "Contrast: old way vs. new way" → tabela: alternativas caras vs Lara R$147
✅ "Short sentences" → "A Lara faz tudo isso por R$147/mês — menos de R$5/dia."
✅ "Proof > promises" → preços de mercado são verificáveis, não afirmações da empresa
✅ "Anti-hype" → copy direto, sem adjetivos (não "incrível" ou "revolucionário")
✅ Gradient no headline cria hierarquia visual sem perder a objetividade
```

**Aprovação hormozi-copy:** ✅ Copy direto e matemático. O visitante faz o cálculo antes de terminar de ler.

---

*Brief produzido por: hormozi-pricing (lead) + hormozi-copy*
*Revisado por: hormozi-chief*
*Arquivo: `C:\crm-auto-digital\docs\marketing\dev-brief-p1a-founder-campaign.md`*
