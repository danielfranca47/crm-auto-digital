# Dev Brief — Offer Pipeline | CRMLandingV2.tsx
**Agentes:** hormozi-pricing + hormozi-copy + hormozi-offers
**Arquivo alvo:** `src/pages/CRMLandingV2.tsx`
**Data atualização:** 2026-06-17

---

## HISTÓRICO DE AJUSTES

| Brief | Ajuste | Status | Data |
|-------|--------|--------|------|
| P1-A | Eliminar confusão de preço — Campanha Fundador | ✅ CONCLUÍDO | 2026-06-17 |
| **P1-B** | **Seção dos 3 agentes especializados na landing** | ✅ CONCLUÍDO | 2026-06-17 |

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
