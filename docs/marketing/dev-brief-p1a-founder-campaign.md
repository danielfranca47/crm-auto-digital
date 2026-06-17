# Dev Brief — P1-A: Apresentação de Preço Durante Campanha Fundador
**Agentes:** hormozi-pricing (lead) + hormozi-copy
**Tarefa:** Eliminar confusão de preço sem encerrar a campanha
**Arquivo alvo:** `src/pages/CRMLanding.tsx` — SOMENTE LEITURA pelo dev, sem alteração de lógica de negócio
**Data:** 2026-06-15 | **Prioridade:** CRÍTICA

---

## CONTEXTO PARA O DEV

A landing atual mostra **dois preços diferentes para o mesmo produto** em lugares distintos:

```
Seção de Planos (linha ~832):       Growth = R$297/mês  ← preço regular
Seção Launch Access (linha ~677):   Growth = R$147/mês  ← preço de campanha
```

O visitante lê as duas seções e não sabe qual é o preço real. Isso mata a conversão.

**A campanha Fundador está ativa.** Não removemos o preço de fundador — apresentamos ele corretamente.

**Princípio (Hormozi Pricing):**
> "Mostre o preço maior primeiro como âncora. Revele o preço real como a consequência lógica de agir agora."

---

## ESTRATÉGIA: "Fundador como Preço Ativo"

Transformar o Growth card para mostrar **um único preço com contexto completo**:
- R$297 aparece apenas como preço tachado (âncora "o que você não vai pagar")
- R$147 é o preço ativo e visível
- R$197 aparece apenas como "o que vira depois" — nunca como segundo preço

A seção Launch Access é **eliminada como seção de preço** e transformada em seção de escassez/contexto.

---

## MUDANÇAS — COMPONENTE A COMPONENTE

---

### MUDANÇA 1 — Card de Plano Growth
**Arquivo:** `CRMLanding.tsx`
**Localização:** Array `plans`, objeto com `name: 'Growth'` (linha ~125)
**Tipo:** Modificação de dados + lógica de renderização do card

#### 1.1 — Badge do card

```
ATUAL:    badge: 'RECOMENDADO'
NOVO:     badge: 'CAMPANHA FUNDADOR'
```

Cor do badge não muda (mantém fundo `#4DD4FF`, texto `#0D0A17`).
Adicionar embaixo do badge um segundo micro-badge:

```jsx
// Abaixo do badge principal, dentro do card (após o título do plano):
<span className="text-xs px-2 py-0.5 rounded-full font-medium"
  style={{ background: 'rgba(77,212,255,0.15)', color: '#4DD4FF' }}>
  5 vagas restantes
</span>
```

#### 1.2 — Bloco de preço

```
ATUAL:
  R$297/mês

NOVO:
  [R$297] tachado + pequeno (âncora)
  R$147  principal (preço ativo)
  /mês pelos primeiros 12 meses
```

**JSX sugerido** (substitui o bloco `<div className="flex items-baseline gap-1">` atual):

```jsx
<div className="mb-1">
  <span
    className="text-sm line-through text-muted-foreground opacity-60 mr-1"
    aria-label="Preço regular">
    R$297
  </span>
  <span className="text-xs text-muted-foreground opacity-60">/mês</span>
</div>
<div className="flex items-baseline gap-1">
  <span className="text-4xl font-extrabold text-accent">R$147</span>
  <span className="text-muted-foreground text-sm">/mês</span>
</div>
<p className="text-xs text-muted-foreground mt-1">
  pelos primeiros 12 meses
</p>
```

#### 1.3 — Nota de rodapé do card (footer)

```
ATUAL:  'Excedente: R$0,50/conversa'

NOVO (duas linhas):
  linha 1: 'Depois: R$197/mês para sempre — preço travado'
  linha 2: 'Novos clientes pagarão R$297/mês · Excedente: R$0,50/conversa'
```

**JSX sugerido** (substitui o `<p>` do footer atual):

```jsx
<div className="text-xs text-muted-foreground mt-1 space-y-0.5">
  <p style={{ color: '#4DD4FF' }} className="font-medium">
    Depois: R$197/mês para sempre — preço travado
  </p>
  <p>
    Novos clientes pagarão R$297/mês · Excedente: R$0,50/conversa
  </p>
</div>
```

#### 1.4 — Primeira feature do Growth (lista de features)

```
ATUAL:  '✦ Ativação 1:1 + 15 Scripts + 30 dias ao vivo (R$641 em bônus)'

NOVO (manter, adicionar antes dela):
  '🔒 Preço de Fundador — travado para sempre'
```

Inserir como primeiro item da array `features` do Growth:

```js
'🔒 Preço de Fundador — travado para sempre',
```

---

### MUDANÇA 2 — Seção Launch Access
**Localização:** Seção `{/* ── LAUNCH ACCESS ── */}` (linha ~677)
**Tipo:** Substituição completa de conteúdo — a seção vira "Por que ser Fundador?"

A seção deixa de mostrar preço e vira uma **seção de contexto de campanha** que explica o que significa ser Fundador. Nenhum número de preço nesta seção — o preço já foi apresentado no card acima.

**Título novo:**
```
ATUAL:  'R$147/mês pelos 12 primeiros meses — depois R$197'
NOVO:   'O que significa entrar como Fundador?'
```

**Parágrafo novo:**
```
ATUAL:
  "Os primeiros parceiros da Lara entram como Fundadores: R$147/mês pelos 12 primeiros
  meses. Depois, o preço trava em R$197/mês para sempre — enquanto o Growth para novos
  clientes sobe para R$297/mês."

NOVO:
  "Fundadores são os primeiros parceiros da Lara. Você entra antes do lançamento público,
  com preço menor, e esse preço fica travado para sempre — mesmo quando o Growth subir
  para R$297/mês para novos clientes.

  Você nunca paga mais do que R$197/mês. Para sempre.
  E os primeiros 12 meses saem por ainda menos."
```

**Card interno — atualizar textos:**

```
ATUAL (h3):    'Vaga de Fundador — 5 vagas apenas'
NOVO (h3):     '5 vagas disponíveis esta semana'

ATUAL (p1):    'O Onboarding ao Vivo acontece toda semana às terças — 10 vagas por sessão.
               Cada Fundador recebe sessão 1:1 prioritária para sair ativo no dia 1.'
NOVO (p1):     'O onboarding ao vivo acontece toda terça — 10 vagas por sessão.
               Fundadores têm sessão 1:1 prioritária: saem ativos no dia 1, não em semanas.'

ATUAL (p2 — preço):  'Após os 12 meses: R$197/mês para sempre. Novos clientes pagarão R$297/mês.'
NOVO (p2):     'Depois dos primeiros 12 meses, seu preço trava em R$197/mês — para sempre.
               Novos clientes que entrarem depois da campanha pagarão R$297/mês.'

ATUAL (badge ✦):   'Preço de Fundador — 5 vagas apenas'
NOVO (badge ✦):    'Ativo agora — campanha encerra quando as vagas acabarem'
```

---

### MUDANÇA 3 — Seção de Bônus (value stack)
**Localização:** Seção `{/* ── BONUS STACK ── */}` (linha ~616)
**Tipo:** Atualização de copy no card de resumo

**Card de resumo no final (o card com a conta "17%"):**

```
ATUAL:
  "Você paga R$297/mês — apenas 17% do valor real."
  "Valor total: R$1.735/mês → Seu investimento: R$297/mês"

NOVO:
  "Campanha Fundador: você investe R$147/mês pelos primeiros 12 meses."
  "Depois R$197/mês para sempre. Novos clientes pagam R$297/mês."
  "Valor entregue: equivalente a R$3.500+/mês de SDR humano ou recepcionista."
```

**JSX sugerido** (substitui o bloco central do card):

```jsx
<div className="text-center space-y-2">
  <div className="text-sm text-muted-foreground">
    Campanha Fundador: você investe{' '}
    <span className="font-bold text-accent text-lg">R$147/mês</span>
    {' '}pelos primeiros 12 meses
  </div>
  <div className="text-xs text-muted-foreground">
    Depois:{' '}
    <strong style={{ color: '#4DD4FF' }}>R$197/mês para sempre</strong>
    {' '}— enquanto novos clientes pagarão{' '}
    <span className="line-through opacity-50">R$297/mês</span>
  </div>
  <div className="text-xs text-muted-foreground mt-2">
    Equivalente a contratar: SDR humano (R$3.500/mês) ou recepcionista (R$2.200/mês).
    A Lara faz os dois por menos.
  </div>
  <div className="text-xs text-muted-foreground mt-2 opacity-70">
    Garantia incondicional de 30 dias — você entra, usa, e decide. O risco é nosso.
  </div>
</div>
```

---

### MUDANÇA 4 — Badge de campanha na Navbar / Hero (opcional, alta conversão)
**Tipo:** Novo componente — banner de campanha acima do navbar ou dentro do Hero
**Prioridade:** Recomendado, não bloqueante

Adicionar uma barra fina acima do `<header>` fixo com a campanha ativa:

```jsx
{/* CAMPAIGN BAR — adicionar ANTES do <header> */}
<div className="fixed top-0 inset-x-0 z-[60] py-1.5 px-4 text-center text-xs font-semibold"
  style={{ background: '#4DD4FF', color: '#0D0A17' }}>
  🔒 Campanha Fundador ativa — 5 vagas a R$147/mês.{' '}
  <a href="#planos" className="underline font-bold">Garantir minha vaga →</a>
</div>
```

Se adicionado, ajustar o `top-0` do `<header>` para `top-8` ou equivalente para não sobrepor.

---

## RESUMO DAS MUDANÇAS

| # | Componente | O que muda | Impacto |
|---|-----------|-----------|---------|
| 1A | Growth card — badge | `RECOMENDADO` → `CAMPANHA FUNDADOR` | Identifica o plano como campanha |
| 1B | Growth card — preço | `R$297` → `~~R$297~~ → R$147/mês pelos 12 primeiros meses` | Elimina ambiguidade de preço |
| 1C | Growth card — footer | Adiciona explicação R$197 pós-campanha | Contexto sem confusão |
| 1D | Growth card — features | Adiciona `🔒 Preço de Fundador — travado` como 1ª feature | Reforça benefício de entrar agora |
| 2 | Launch Access section | Remove referência de preço — vira seção "O que é Fundador?" | Elimina o segundo preço da página |
| 3 | Bonus stack card | Atualiza R$297 para R$147 com contexto de campanha | Consistência em toda a página |
| 4 | Campaign bar (novo) | Barra fixa no topo com campanha ativa | Visibilidade imediata |

---

## PRINCÍPIO UTILIZADO (para o dev entender o porquê)

```
ANTES (confuso):
  Seção A: "Growth = R$297/mês" → RECOMENDADO
  Seção B: "Fundador = R$147/mês" → seção separada

  Resultado: visitante não sabe qual é o preço real.
  Pior: parece que R$147 e R$297 são coisas diferentes.

DEPOIS (correto — ancoragem Hormozi):
  Growth = ~~R$297~~ → R$147/mês (campanha)
  "Depois R$197/mês para sempre"
  "Novos clientes pagarão R$297/mês"

  Resultado: visitante entende:
  1. O preço normal seria R$297
  2. Agora está em R$147 por ser Fundador
  3. Vai travar em R$197 para sempre
  4. Quem entrar depois vai pagar mais

  Uma história. Um preço. Zero confusão.
```

---

## CRITÉRIOS DE ACEITE

```
[ ] Página inteira tem apenas UM preço numérico ativo: R$147/mês
[ ] R$297 aparece apenas tachado, como âncora — nunca como preço de compra
[ ] R$197 aparece apenas como "preço pós-campanha travado" — nunca como opção de compra
[ ] A seção Launch Access não exibe nenhum número de preço isolado
[ ] O card de bônus não menciona R$297 como preço de compra
[ ] Todos os CTAs levam para o Growth com R$147 ativo
[ ] Mobile: o preço tachado + preço ativo são legíveis em viewport 375px
```

---

## O QUE NÃO MUDAR

```
[ ] Lógica de checkout / pagamento — não alterar
[ ] Planos Start, Scale, Enterprise — não alterar
[ ] Qualquer integração de API ou backend
[ ] Estrutura geral da página (ordem das seções)
[ ] A garantia dupla — não alterar
[ ] O array de features do Growth (apenas adicionar o item 🔒 no topo)
```

---

*Brief produzido por: hormozi-pricing (lógica de ancoragem) + hormozi-copy (copy)*
*Revisado por: hormozi-chief*
*Arquivo: `C:\crm-auto-digital\docs\marketing\dev-brief-p1a-founder-campaign.md`*
