# Dev Brief — Offer Pipeline | CRMLandingV2.tsx
**Agentes:** hormozi-pricing + hormozi-copy + hormozi-offers
**Arquivo alvo:** `src/pages/CRMLandingV2.tsx`
**Data atualização:** 2026-06-17

---

## HISTÓRICO DE AJUSTES

| Brief | Ajuste | Status | Critérios | Data |
|-------|--------|--------|-----------|------|
| P1-A | Eliminar confusão de preço — Campanha Fundador | ✅ CONCLUÍDO | Todos aprovados | 2026-06-17 |
| **P1-B** | **Adicionar os 3 agentes especializados na landing** | 🔴 PENDENTE | — | — |

---

## ✅ P1-A — VALIDAÇÃO COMPLETA

Todas as mudanças do brief anterior foram verificadas em `CRMLandingV2.tsx`:

| Mudança | Implementado | Localização V2 | Status |
|---------|-------------|----------------|--------|
| 1A — Badge Growth: `CAMPANHA FUNDADOR` | Sim | linha 128 | ✅ |
| 1B — Micro-badge `5 vagas restantes` | Sim | linhas 886–890 | ✅ |
| 1B — Bloco de preço: R$297 tachado + R$147 ativo | Sim | linhas 898–912 | ✅ |
| 1C — Footer duplo: R$197 travado + R$297 para novos | Sim | linhas 913–921 | ✅ |
| 1D — Feature `🔒 Preço de Fundador` no topo | Sim | linha 132 | ✅ |
| 2 — Launch Access vira "O que é Fundador?" | Sim | linhas 697–736 | ✅ |
| 3 — Card de resumo com R$147 + âncora mercado | Sim | linhas 671–693 | ✅ |
| 4 — Campaign Bar fixa no topo | Sim | linhas 211–217 | ✅ |
| 4 — Navbar ajustado para `top-8` | Sim | linha 220 | ✅ |
| 4 — Hero com `pt-24` para compensar | Sim | linha 251 | ✅ |

**Critérios de aceite P1-A — todos verificados:**
- [x] Página tem apenas UM preço ativo: R$147/mês
- [x] R$297 aparece apenas tachado, como âncora
- [x] R$197 aparece apenas como "preço pós-campanha travado"
- [x] Launch Access não exibe número de preço isolado
- [x] Card de bônus não menciona R$297 como preço de compra
- [x] Campaign Bar visível no topo com CTA para `#planos`

---

---

# Dev Brief — P1-B: Adicionar os 3 Agentes Especializados na Landing

**Agentes:** hormozi-offers (lead) + hormozi-copy
**Tarefa:** Criar seção dos 3 agentes especializados
**Arquivo alvo:** `CRMLandingV2.tsx` — SOMENTE adicionar nova seção, sem alterar as existentes
**Prioridade:** CRÍTICA

---

## CONTEXTO PARA O DEV

A Lara tem 3 agentes IA especializados que são o maior diferencial competitivo do produto:

```
SDR          → imóveis, consultoria, assessoria, coaching (alto ticket)
Closer       → infoprodutos, e-commerce, lojas físicas (baixo ticket)
Híbrido      → psicólogos, dentistas, terapeutas (serviços presenciais)
```

**Problema:** Esses 3 agentes não aparecem em nenhum lugar da landing V2 atual. O visitante vê "IA que atende" — não vê que existe um agente treinado especificamente para o SEU tipo de negócio. Isso elimina o principal argumento de conversão.

**Princípio (Hormozi Offers):**
> "O visitante só paga quando acredita que a solução foi feita para ele. Genérico não converte. Específico converte."

A seção dos agentes transforma "chatbot genérico" em "agente especializado no meu negócio" — aumenta Perceived Likelihood na Value Equation.

---

## ESTRATÉGIA: "Qual é o seu agente?"

A nova seção deve funcionar como um **seletor de identidade**: o visitante lê os 3 agentes e um deles é obviamente ele. Quando o visitante pensa "esse aqui é pra mim", a conversão acontece.

Estrutura visual: 3 cards horizontais lado a lado, cada um com:
- Emoji + nome do agente
- Badge com tipo (Alto Ticket / Baixo Ticket / Serviços)
- Para quem é (setores, em destaque)
- O que faz (outcome específico, 1 frase)
- Comparação de mercado (âncora de valor)

---

## MUDANÇA — NOVA SEÇÃO DE AGENTES

**Arquivo:** `CRMLandingV2.tsx`
**Localização:** Inserir a nova seção **APÓS** o bloco `{/* ── SECTOR TABS ── */}` (linha ~387) e **ANTES** de `{/* ── HOW IT WORKS ── */}` (linha ~390).

Ou seja, adicionar entre o fechamento `</section>` dos SECTOR TABS e o `{/* ── HOW IT WORKS ── */}`.

---

### 1 — Dados da seção (adicionar junto aos outros arrays no topo, perto da linha 83)

```tsx
const agents = [
  {
    emoji: '🎯',
    name: 'Agente SDR',
    badge: 'Alto Ticket',
    badgeColor: '#F59E0B',
    sectors: ['Imóveis', 'Consultoria', 'Coaching', 'Assessoria'],
    outcome: 'Agenda reuniões com leads quentes de alto ticket — enquanto você está em outras reuniões.',
    anchor: 'SDR humano custa R$3.500/mês. A Lara SDR custa R$297.',
    detail: 'Qualifica compradores, filtra curiosos e entrega apenas leads prontos para conversar negócio.',
  },
  {
    emoji: '💳',
    name: 'Agente Closer',
    badge: 'Baixo Ticket',
    badgeColor: '#10B981',
    sectors: ['Infoprodutos', 'E-commerce', 'Lojas Físicas'],
    outcome: 'Converte do primeiro "oi" até o pagamento — sem você precisar estar online.',
    anchor: '1 venda extra por mês paga o mês inteiro da Lara.',
    detail: 'Recupera carrinhos abandonados, converte leads que responderam tarde e faz follow-up de quem sumiu.',
  },
  {
    emoji: '📅',
    name: 'Agente Híbrido',
    badge: 'Serviços',
    badgeColor: '#8B5CF6',
    sectors: ['Psicólogos', 'Dentistas', 'Terapeutas', 'Clínicas'],
    outcome: 'Agenda sempre cheia, faltas eliminadas — sem precisar de recepcionista.',
    anchor: 'Recepcionista custa R$2.200/mês. A Lara Híbrido custa R$297 e trabalha 24/7.',
    detail: 'Responde dúvidas, confirma sessões com antecedência e faz follow-up de pacientes que sumiram.',
  },
];
```

---

### 2 — JSX da seção (inserir no return, após o `</section>` do SECTOR TABS)

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
        Qual é o seu? Escolha o agente e a Lara já sabe como vender do seu jeito.
      </p>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {agents.map((agent) => (
        <div key={agent.name}
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

          {/* Para quem */}
          <div className="flex flex-wrap gap-1.5 mb-4">
            {agent.sectors.map(s => (
              <span key={s}
                className="text-xs px-2 py-0.5 rounded-full border text-muted-foreground"
                style={{ borderColor: 'hsl(var(--border))' }}>
                {s}
              </span>
            ))}
          </div>

          {/* Outcome */}
          <p className="text-sm font-semibold mb-2 leading-snug flex-1">
            {agent.outcome}
          </p>

          {/* Detalhe */}
          <p className="text-xs text-muted-foreground leading-relaxed mb-4">
            {agent.detail}
          </p>

          {/* Âncora de valor */}
          <div
            className="text-xs px-3 py-2 rounded-lg font-medium mt-auto"
            style={{
              background: `${agent.badgeColor}11`,
              color: agent.badgeColor,
              borderLeft: `3px solid ${agent.badgeColor}`,
            }}>
            {agent.anchor}
          </div>
        </div>
      ))}
    </div>

    {/* CTA */}
    <div className="text-center mt-10">
      <p className="text-sm text-muted-foreground mb-4">
        Todos os 3 agentes estão incluídos no plano{' '}
        <strong style={{ color: '#4DD4FF' }}>Growth</strong>.
        O Start inclui o Agente Closer.
      </p>
      <a href="#planos" className="btn-hero inline-flex items-center gap-2">
        Ver planos e escolher meu agente <ArrowRight className="w-4 h-4" />
      </a>
    </div>
  </div>
</section>
```

---

## RESUMO DAS MUDANÇAS

| # | Onde | O que muda | Impacto |
|---|------|-----------|---------|
| 1 | Topo do arquivo, linha ~83 | Adicionar array `agents` com 3 objetos | Dados dos 3 agentes |
| 2 | Return, após SECTOR TABS (~linha 387) | Inserir `<section>` dos agentes | Nova seção visual |

**O que NÃO mudar:**
- Seção SECTOR TABS — não alterar
- Features grid — não alterar
- Plans array — não alterar
- Qualquer outra seção existente

---

## CRITÉRIOS DE ACEITE

```
[ ] Seção visível entre SECTOR TABS e HOW IT WORKS
[ ] 3 cards aparecem corretamente em desktop (grid 3 colunas)
[ ] 3 cards empilham em mobile (grid 1 coluna)
[ ] Cada card mostra: emoji, nome, badge colorido, setores, outcome, âncora
[ ] Cores dos badges são distintas (amarelo/verde/roxo)
[ ] CTA "Ver planos e escolher meu agente" leva para #planos
[ ] Nota "Todos os 3 agentes incluídos no Growth" visível
[ ] Não quebra nenhuma seção existente da página
```

---

## PRINCÍPIO UTILIZADO (para o dev entender o porquê)

```
ANTES (genérico):
  "A Lara atende, qualifica e faz follow-up"
  → O visitante pensa: "é mais um chatbot"

DEPOIS (específico):
  "Agente SDR — para imóveis, consultoria, coaching"
  "Agenda reuniões com leads de alto ticket — enquanto você está em outras reuniões"
  "SDR humano custa R$3.500. A Lara custa R$297."
  → O visitante pensa: "esse aqui foi feito pra mim"

Resultado: Perceived Likelihood sobe de 7/10 → 9/10 na Value Equation.
Visitante para de comparar com chatbot genérico.
Passa a comparar com SDR humano / recepcionista.
```

---

*Brief produzido por: hormozi-offers (posicionamento dos agentes) + hormozi-copy (copy)*
*Revisado por: hormozi-chief*
*Arquivo: `C:\crm-auto-digital\docs\marketing\dev-brief-p1a-founder-campaign.md`*
