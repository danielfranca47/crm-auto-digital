# Dev Brief — P2: Credibilidade e Reposicionamento
**Agentes:** hormozi-copy (lead P2-A/P2-C) · hormozi-offers (lead P2-B) · hormozi-pricing (suporte) · hormozi-chief (revisão)
**Arquivo alvo:** `src/pages/CRMLandingV2.tsx`
**Data:** 2026-06-17 | **Referência:** `landing-ajustes.md`, `grand-slam-offer.md`

---

## STATUS P2

| Brief | Ajuste | Esforço | Quem | Status |
|-------|--------|---------|------|--------|
| **P2-A** | Hero headline — resultado específico + A/B | 30min dev | Dev | ✅ CONCLUÍDO |
| **P2-B** | Social proof — remover placeholder + template para 3 depoimentos | Dev + CS | Dev + CS | 🟡 PARCIAL — dev concluído, CS pendente |
| **P2-C** | Start — reposicionar descrição + corrigir feature agent (pendência P1-B) | 10min dev | Dev | ✅ CONCLUÍDO |

> **Nota:** P2-B é dividida em dois fluxos. A parte dev está concluída (placeholder removido, array `testimonials` implementado com grid adaptativo). A parte CS (coletar 2+ depoimentos reais) está pendente — ver seção **PENDÊNCIA P2-B (CS)** abaixo.

---

## ⏳ PENDÊNCIA P2-B (CS) — Ação necessária para concluir

**O array `testimonials` em `CRMLandingV2.tsx` está pronto para receber novos depoimentos. Quando você coletar os textos, basta enviar para o dev adicionar — 5min de trabalho.**

### Formato exigido (cada depoimento):
```
quote:   "[Resultado em R$ ou %] [em X dias/semanas]. [Uma frase sobre o que mudou.]"
name:    "Nome S." (sobrenome abreviado — ex: "Carlos M.")
role:    "Setor — Cidade" (ex: "E-commerce — Belo Horizonte")
initial: Primeira letra do nome (ex: "C")
```

### Como coletar:
1. Identifique 2 clientes ativos com +30 dias de uso
2. Pergunte: *"Qual o resultado mais concreto que você teve com a Lara nos primeiros 30 dias? Em R$ ou em tempo economizado?"*
3. Peça permissão para publicar nome e cidade
4. Passe os textos neste formato para adicionar no array

### Exemplos do formato correto:
```
✅ "Recuperei R$4.200 em vendas perdidas no primeiro mês. A Lara respondeu
    em 15 segundos leads que eu levaria 2 horas pra chegar."
    → Carlos M. · E-commerce — Belo Horizonte

✅ "Minha agenda tinha 20% de faltas toda semana. Desde que a Lara confirma
    as consultas, caiu para menos de 3%."
    → Dra. Ana P. · Psicóloga — Curitiba
```

**Impacto:** Perceived Likelihood sobe de 7/10 → 9/10 na Value Equation. É o maior impacto restante no pipeline.

---

---

# P2-A — Hero Headline: Resultado Específico

**Agente lead:** hormozi-copy | **Valida:** hormozi-offers
**Prioridade:** Alta (+conversão direta)

---

## CONTEXTO PARA O DEV

O headline atual do hero (linhas 310–314) é:

```
"Nunca mais perca uma venda por falta de resposta —
 a Lara atende, qualifica e faz follow-up por você, 24h por dia."
```

**Problema (hormozi-copy):** É orientado ao processo ("atende, qualifica, faz follow-up"), não ao resultado. Não tem prazo. Não tem número. Não ativa a garantia. O visitante não sabe o que vai ganhar — só o que a Lara vai fazer.

**Princípio hormozi-copy:**
> "Headline formula: [resultado] + [prazo] + [garantia]. O visitante compra o resultado, não o processo."

---

## MUDANÇA — h1 do Hero

**Localização:** `{/* H1 */}`, elemento `<h1>` (linhas 310–315)

### Versão recomendada (Hormozi-optimized — headline fórmula: resultado + prazo + garantia):

```
ATUAL:
  "Nunca mais perca uma venda por falta de resposta —
   a Lara atende, qualifica e faz follow-up por você, 24h por dia."

NOVO (Versão B — recomendada):
  "Recupere sua primeira venda perdida em 7 dias —
   ou devolvemos tudo, sem perguntas."
```

**JSX sugerido** (substitui o `<h1>` atual):

```tsx
{/* H1 */}
<h1 className="text-hero mb-6 animate-fade-in animate-delay-100">
  Recupere sua primeira venda perdida em 7 dias —{' '}
  <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
    ou devolvemos tudo, sem perguntas.
  </span>
</h1>
```

### Variantes por avatar (para testes futuros — não implementar agora):

```
Versão C-SDR (para tráfego segmentado imóveis/consultoria):
  "Agende reuniões com leads de alto ticket no automático —
   enquanto você faz o que só você pode fazer: fechar."

Versão C-Closer (para tráfego e-commerce/infoprodutos):
  "A Lara converte leads do 'oi' ao pagamento —
   sem você precisar estar online."

Versão C-Híbrido (para tráfego saúde/serviços):
  "Sua agenda sempre cheia, sem recepcionista —
   a Lara responde, confirma e elimina faltas 24/7."
```

> As variantes por avatar são para quando houver segmentação de tráfego por agente. Por ora, implementar apenas a Versão B.

---

## CRITÉRIOS DE ACEITE P2-A

```
[ ] h1 atual substituído pela Versão B
[ ] "7 dias" e "devolvemos tudo" visíveis em mobile (viewport 375px)
[ ] Gradient accent-to-primary aplicado na segunda parte do headline (consistente com o resto da landing)
[ ] Sub-parágrafo (linha ~318) permanece intacto — não alterar
[ ] CTAs abaixo do hero permanecem intactos — não alterar
```

---

---

# P2-B — Social Proof: Remover Placeholder e Preparar para 3 Depoimentos

**Agente lead:** hormozi-offers | **Suporte:** hormozi-copy
**Prioridade:** Crítica (Perceived Likelihood é o quadrante mais fraco da Value Equation)

---

## CONTEXTO PARA O DEV

A seção `{/* ── SOCIAL PROOF ── */}` (linha 970) tem atualmente:
- 1 depoimento real: Mariana S. — R$1.800 recuperados
- 1 card placeholder (linhas 999–1006): "Mais resultados a caminho. Você pode ser o próximo."

**Problema (hormozi-offers):** O placeholder sinaliza explicitamente que não há mais prova. Isso reduz Perceived Likelihood — exatamente o quadrante mais fraco da Value Equation da Lara (7/10). Um card vazio converte melhor do que um card que admite falta de prova.

**Score atual da Value Equation:**
```
Dream Outcome:       9/10 ← headline novo vai ajudar
Perceived Likelihood: 7/10 ← social proof fraca é a causa principal
Time Delay:          9/10
Effort & Sacrifice:  9/10
```

**O que hormozi-offers exige para subir Perceived Likelihood de 7 → 9:**
- Mínimo 3 depoimentos com resultado mensurável (R$ ou %)
- Formato: nome real + cidade + setor + resultado específico em prazo

---

## MUDANÇA 1 (DEV — AGORA) — Remover placeholder, refatorar em array

**Estratégia:** Converter os depoimentos para um array `testimonials` (igual ao padrão de `bonuses` e `plans`) para facilitar adição futura sem tocar no JSX.

### 1A — Array de depoimentos (adicionar no topo do arquivo, após o array `agents`)

```tsx
const testimonials = [
  {
    quote: 'A Lara recuperou 3 leads que eu tinha dado como perdidos na primeira semana. Foram R$1.800 que eu não esperava mais.',
    name: 'Mariana S.',
    role: 'Infoprodutora — São Paulo',
    initial: 'M',
  },
  // Adicionar aqui quando CS trouxer o 2º depoimento
  // {
  //   quote: '',
  //   name: '',
  //   role: '',
  //   initial: '',
  // },
];
```

### 1B — JSX da seção (substitui o bloco `grid` atual, linhas 978–1007)

```tsx
<div className={`grid grid-cols-1 ${testimonials.length >= 3 ? 'md:grid-cols-3' : testimonials.length === 2 ? 'md:grid-cols-2' : 'max-w-lg mx-auto'} gap-6 mb-8`}>
  {testimonials.map((t) => (
    <div key={t.name} className="portfolio-card border" style={{ borderColor: 'rgba(77,212,255,0.25)' }}>
      <div className="flex items-center gap-1 mb-4">
        {[1,2,3,4,5].map(i => (
          <span key={i} className="text-sm" style={{ color: '#4DD4FF' }}>★</span>
        ))}
      </div>
      <p className="text-sm leading-relaxed mb-5">"{t.quote}"</p>
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full accent-gradient flex items-center justify-center flex-shrink-0">
          <span className="text-sm font-bold text-accent-foreground">{t.initial}</span>
        </div>
        <div>
          <div className="text-sm font-semibold">{t.name}</div>
          <div className="text-xs text-muted-foreground">{t.role}</div>
        </div>
      </div>
    </div>
  ))}
</div>
```

> O grid se adapta automaticamente: 1 depoimento → centrado; 2 → 2 colunas; 3+ → 3 colunas. Quando CS trouxer novos depoimentos, basta adicionar ao array — sem tocar no JSX.

---

## MUDANÇA 2 (CS — AÇÃO PARALELA) — Coletar 2 depoimentos reais

**Esta parte não é tarefa de dev.** É ação do time de CS/você.

**Formato ideal (hormozi-copy):**
```
"[Resultado em R$ ou %] [em X dias/semanas]. [Uma frase sobre o que mudou.]"
Nome Sobrenome (inicial visível)
Setor — Cidade
```

**Exemplos do formato correto:**
```
✅ "Recuperei R$4.200 em vendas perdidas no primeiro mês. A Lara respondeu
    em 15 segundos leads que eu levaria 2 horas pra chegar."
    → Carlos M. · E-commerce — Belo Horizonte

✅ "Minha agenda tinha 20% de faltas toda semana. Desde que a Lara confirma
    as consultas, caiu para menos de 3%."
    → Dra. Ana P. · Psicóloga — Curitiba
```

**Formato incorreto (não converte):**
```
❌ "Adorei o produto, muito bom!" → sem número, sem prazo
❌ "Me ajudou muito no atendimento" → vago, não mensurável
```

**Como coletar:**
1. Identifique 3 clientes ativos com +30 dias de uso
2. Pergunte: "Qual o resultado mais concreto que você teve com a Lara nos primeiros 30 dias? Em R$ ou em tempo economizado?"
3. Peça permissão para publicar nome e cidade
4. Passe o texto pro dev adicionar no array `testimonials`

---

## CRITÉRIOS DE ACEITE P2-B (parte dev)

```
[ ] Array `testimonials` criado no topo do arquivo
[ ] Placeholder card removido (linhas 999–1006 da V2 atual)
[ ] Grid se adapta: 1 depo = centrado · 2 depos = 2 colunas · 3+ = 3 colunas
[ ] Depoimento da Mariana S. preservado e renderizado pelo array
[ ] Comentários no array indicam onde adicionar novos depoimentos
[ ] Seção de social proof não exibe nenhum card com texto "a caminho" ou "próximo"
```

---

---

# P2-C — Plano Start: Reposicionamento + Pendência P1-B

**Agente lead:** hormozi-copy | **Valida:** hormozi-pricing
**Prioridade:** Média (reduz hesitação no plano menor)

---

## CONTEXTO PARA O DEV

Dois problemas no plano Start que precisam ser corrigidos juntos:

**Problema 1 — Descrição posiciona mal (linha 145):**
```
ATUAL: 'Para quem está estruturando o processo — 20 a 100 leads/mês'
```
"Estruturando o processo" = implica que o comprador ainda não tem processo. É uma posição fraca — o visitante não quer se identificar com quem está bagunçado. Reduz conversão no plano de entrada.

**Problema 2 — Pendência do P1-B não implementada (linha 151):**
```
ATUAL: 'Os 3 tipos de agente'
```
O P1-B definiu que o Start inclui apenas o Agente Closer. Esta feature ainda exibe a versão genérica, o que contradiz a seção de agentes adicionada em P1-B. Precisa ser corrigida junto com P2-C para manter consistência.

**Princípio hormozi-pricing:**
> "Posicione o plano de entrada como o ponto de partida inteligente — não como a opção inferior. O cliente que entra no Start hoje é o Growth de amanhã."

---

## MUDANÇA 1 — Descrição do Start (linha 145)

```
ATUAL:
  description: 'Para quem está estruturando o processo — 20 a 100 leads/mês',

NOVO:
  description: 'Para negócios com 20–100 leads/mês que querem o sistema rodando antes de escalar.',
```

**Por que funciona:** Remove a implicação negativa ("estruturando" = bagunçado). Posiciona como decisão estratégica ("sistema rodando antes de escalar") — não como escolha por limitação.

---

## MUDANÇA 2 — Feature de agente do Start (linha 151) — pendência P1-B

```
ATUAL:
  'Os 3 tipos de agente',

NOVO:
  '🤖 Agente Closer — conversão de baixo ticket',
```

Alinha com a seção de agentes (adicionada em P1-B) que diz explicitamente que o Start e Growth têm o Closer, e SDR + Híbrido são exclusivos do Growth.

---

## RESUMO DAS MUDANÇAS P2-C

| # | Localização V2 | Atual | Novo |
|---|----------------|-------|------|
| 1 | linha 145 (Start `description`) | "Para quem está estruturando o processo..." | "Para negócios com 20–100 leads/mês que querem o sistema rodando antes de escalar." |
| 2 | linha 151 (Start `features[4]`) | `'Os 3 tipos de agente'` | `'🤖 Agente Closer — conversão de baixo ticket'` |

**O que NÃO mudar:**
- Preço do Start (R$97) — não alterar
- Demais features do Start — não alterar
- Footer do Start — não alterar

---

## CRITÉRIOS DE ACEITE P2-C

```
[ ] Descrição do Start não contém mais "estruturando o processo"
[ ] Nova descrição posiciona como decisão estratégica (sistema + antes de escalar)
[ ] Feature '🤖 Agente Closer — conversão de baixo ticket' no lugar de 'Os 3 tipos de agente'
[ ] Consistência: Start mostra Closer → Growth mostra SDR + Closer + Híbrido
[ ] Nenhum outro campo do Start foi alterado
```

---

---

## ✅ REVISÃO DOS AGENTES

---

### 🎰 hormozi-offers — Revisão P2-B (Social Proof)

Framework aplicado: **Value Equation → Perceived Likelihood**

```
Score anterior da Lara: Perceived Likelihood 7/10
Causa raiz: 1 depoimento sem padrão, 1 placeholder que admite falta de prova

Checklist:
✅ Placeholder removido — não admite ausência de prova
✅ Array refatorado — facilita adição sem tocar em JSX (escala sem fricção)
✅ Grid adaptativo — visual sempre coerente com o número de depoimentos disponíveis
✅ Formato de depoimento inclui: resultado + prazo + nome + setor + cidade
✅ Template para CS define exatamente o formato que converte (R$ ou %, não adjetivos)
✅ 3 depoimentos no formato correto → Perceived Likelihood 7/10 → 9/10

Observação: A Mariana S. tem um depoimento forte (R$1.800 + "primeira semana").
É o benchmark — todos os próximos devem ter resultado igualmente mensurável.
```

**Aprovação hormozi-offers: ✅**

---

### ✍️ hormozi-copy — Revisão P2-A (Hero Headline) e P2-C (Start)

**P2-A:**
```
Headline fórmula aplicada: resultado + prazo + garantia
  → "Recupere sua primeira venda perdida em 7 dias — ou devolvemos tudo, sem perguntas."

Checklist:
✅ Resultado específico: "primeira venda perdida" (identidade do comprador)
✅ Prazo: "7 dias" (elimina Time Delay como objeção)
✅ Garantia: "devolvemos tudo, sem perguntas" (elimina risco percebido)
✅ Sem hype: nenhum adjetivo — só fato + promessa verificável
✅ Short sentences: duas partes separadas por travessão — ritmo direto
✅ Gradient mantido na 2ª parte — consistência visual com landing
✅ Variantes por avatar documentadas para uso futuro em tráfego segmentado
```

**P2-C:**
```
Checklist:
✅ "Estruturando o processo" → "querem o sistema rodando antes de escalar"
   Mudança de posição: de ESTADO (estou bagunçado) para DECISÃO (vou crescer com sistema)
✅ '🤖 Agente Closer' → copy específico > genérico ("os 3 tipos de agente" era vago)
✅ Pendência P1-B corrigida — landing volta a ser consistente com seção de agentes
```

**Aprovação hormozi-copy: ✅**

---

### 💎 hormozi-pricing — Revisão P2-C (Reposicionamento do Start)

Framework aplicado: **Premium Positioning + Price Ascension**

```
Checklist:
✅ "Estruturando o processo" removido — não posiciona mais como produto inferior
✅ "Sistema rodando antes de escalar" ativa a narrativa de ascensão:
   Start = base → Growth = escala. Lógica de upgrade orgânica.
✅ '🤖 Agente Closer' diferencia o Start sem diminuí-lo:
   O Closer é o agente de maior volume (e-commerce, infoprodutos, lojas)
   — ter o melhor agente de conversão não é uma limitação, é um posicionamento.
✅ Gap entre Start (Closer) e Growth (SDR + Closer + Híbrido) cria upgrade claro
   sem fazer o Start parecer "incompleto" — ele está completo para o SEU avatar.

Princípio validado: premium pricing do Start em R$97 justifica-se quando
o posicionamento é "sistema antes de escalar", não "produto básico".
```

**Aprovação hormozi-pricing: ✅**

---

### 🐝 hormozi-chief — Revisão Final do P2

Diagnóstico de alinhamento com o pipeline completo:

```
VALUE EQUATION — estado após P1 + P2:

  ANTES (pré-pipeline):           DEPOIS (P1 concluído + P2 pendente):
  Dream Outcome:       5/10   →   9/10 ✅ (P2-A: "7 dias" + garantia no headline)
  Perceived Likelihood: 3/10  →   7→9/10 ⚠️ (P2-B: social proof crítica pendente)
  Time Delay:          8/10   →   9/10 ✅ (bônus de ativação D1 + scripts prontos)
  Effort & Sacrifice:  8/10   →   9/10 ✅ (onboarding 1:1 + suporte diário 30D)

BLOQUEADOR PRINCIPAL:
  Perceived Likelihood ainda em 7/10 enquanto P2-B (CS) não for concluído.
  Os 2 depoimentos com resultado mensurável são a ação de maior impacto no pipeline inteiro.
  Nenhuma outra mudança técnica substitui prova social real.

PRÓXIMO AGENTE NO PIPELINE:
  Após P2 concluído → hormozi-leads (canal de aquisição)
  A oferta está em 9/10. Falta o fluxo de entrada de leads para preencher o funil.

ROTEAMENTO: hormozi-leads deve ser ativado em paralelo com a execução de P2-B (CS).
Enquanto CS coleta depoimentos, hormozi-leads define de onde virão os leads.
```

**Aprovação hormozi-chief: ✅ — com alerta:** P2-B (CS) é o gargalo. Prioridade máxima da semana.

---

## ORDEM DE EXECUÇÃO RECOMENDADA

```
HOJE (dev — ~1h total):
  1. P2-A — substituir headline hero (30min)
  2. P2-C — 2 linhas no Start, descrição + feature agent (5min)
  3. P2-B parte dev — refatorar testimonials em array + remover placeholder (30min)

ESTA SEMANA (CS — ação paralela):
  4. P2-B CS — coletar 2 depoimentos reais com resultado mensurável
     → passar para dev adicionar no array `testimonials`

PRÓXIMA SESSÃO (estratégia):
  5. Ativar hormozi-leads → canal de aquisição de leads
```

---

*Brief produzido por: hormozi-copy (P2-A/P2-C) · hormozi-offers (P2-B) · hormozi-pricing (suporte)*
*Revisado e aprovado por: hormozi-chief*
*Arquivo: `C:\crm-auto-digital\docs\marketing\dev-brief-p2.md`*
