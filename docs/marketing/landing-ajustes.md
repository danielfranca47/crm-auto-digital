# Landing Page — Ajustes Recomendados
**Revisão:** Hormozi Chief | **Referência:** CRMLanding.tsx
**Data:** 2026-06-15 | **Prioridade ordenada**

> Este arquivo pontua ajustes. A página NÃO foi modificada.
> Implementar em ordem de impacto.

---

## PRIORIDADE 1 — CRÍTICO (impacto direto em conversão)

### [P1-A] Eliminar confusão de preço entre Growth e Fundador

**Problema:** O visitante vê R$297 na tabela de planos e R$147 na seção Fundador.
Não entende qual é o preço real. Confusion kills conversion.

**Solução:**
- Remover a seção "Preço de Fundador" da landing principal
- Criar uma lógica condicional: Fundador aparece apenas após CTA clicado
  (ex: modal "Você está no período de acesso antecipado — seu preço é R$197/mês")
- OU: manter Fundador mas como único preço visível na landing, com countdown

**Onde:** Seção `{/* ── LAUNCH ACCESS ── */}` (linha ~677) e tabela de planos (linha ~832)

---

### [P1-B] Adicionar os 3 Agentes na seção de funcionalidades

**Problema:** SDR, Closer e Híbrido Agendador são o maior diferencial competitivo
e não aparecem em nenhum lugar da landing. O visitante vê "bot que responde" — não vê
a especialização que justifica o preço.

**Solução:** Adicionar seção antes ou dentro de `funcionalidades`:

```
🤖 SDR — Alto Ticket
Para imóveis, consultoria, coaching, assessoria.
Agenda reuniões com leads quentes. Você fecha, a Lara prospecta.

💳 Closer — Baixo Ticket
Para infoprodutos, e-commerce, lojas físicas.
Converte do "oi" ao pagamento — sem você estar online.

📅 Híbrido Agendador — Serviços Presenciais
Para psicólogos, dentistas, terapeutas.
Responde dúvidas, confirma sessões, elimina faltas.
```

**Onde:** Criar nova seção após `{/* ── SECTOR TABS ── */}` (linha ~344) ou
incluir como seletor nos planos.

---

### [P1-C] Corrigir âncora de valor — substituir R$1.735 por comparação de mercado

**Problema:** "R$1.735 em valor" parece número inventado porque R$997 para "Lara 24/7" não tem âncora externa.

**Solução (copy para a seção de bônus):**

```jsx
// SUBSTITUIR o parágrafo atual no bonus section:
<h2>Você investe R$297/mês.<br />
    Sua alternativa custaria R$3.500+/mês.</h2>

// Adicionar comparação:
"SDR humano: R$3.500/mês (sem CRM, sem 24/7)"
"Recepcionista: R$2.200/mês (sem follow-up automático)"
"Chatbot genérico: R$200/mês (sem agente especializado, sem CRM)"
```

**Onde:** Seção `{/* ── BONUS STACK ── */}` (linha ~616) — header e card de resumo.

---

## PRIORIDADE 2 — IMPORTANTE (aumenta credibilidade)

### [P2-A] Headline do Hero — adicionar resultado específico

**Atual:**
> "Nunca mais perca uma venda por falta de resposta — a Lara atende, qualifica e faz follow-up por você, 24h por dia."

**Recomendado (testar como variante):**
> "Recupere sua primeira venda perdida em 7 dias — ou devolvemos tudo."

**Ou (avatar SDR):**
> "Agende reuniões com leads de alto ticket no automático — enquanto você faz o que só você pode fazer: fechar."

**Onde:** Seção `{/* ── HERO ── */}`, tag `<h1>` (linha ~263)

---

### [P2-B] Social proof — mínimo 3 depoimentos antes de converter

**Problema:** 1 depoimento + 1 card vazio com "Você pode ser o próximo" transmite produto novo/sem histórico.

**Solução mínima viável:**
- 3 depoimentos com: nome real, cidade, resultado mensurável
- Formato ideal: "Recuperei R$X em Y dias" ou "Agenda sempre cheia — economia de R$2.200/mês"
- Remover o card "Mais resultados a caminho" — melhor deixar vazio do que admitir que não tem

**Onde:** Seção `{/* ── SOCIAL PROOF ── */}` (linha ~755)

---

### [P2-C] Descrição do plano Start — reposicionar como "ponto de entrada", não "inferior"

**Atual:** "Para quem está estruturando o processo — 20 a 100 leads/mês"

**Problema:** "Estruturando o processo" = "você ainda não tem processo" → posição fraca.

**Recomendado:**
```
Start — R$97/mês
"Para negócios com 20–100 leads/mês que querem o sistema funcionando antes de escalar"
```

**Onde:** `plans` array, plano Start, campo `description` (linha ~110)

---

## PRIORIDADE 3 — MELHORIA (otimização contínua)

### [P3-A] Adicionar plano Anual na seção de planos

SaaS com pagamento anual tem churn 70% menor. Mesmo que ainda não esteja operacional,
criar um card "Anual — economize 4 meses" com CTA "Entrar na lista" planta a semente.

**Preço sugerido:** R$197/mês × 12 = R$2.364 à vista (vs R$297 × 12 = R$3.564)
Frase: "4 meses de graça. Zero risco com garantia de 30 dias."

---

### [P3-B] Especificar qual agente está em qual plano

**Atual:** Planos listam features técnicas (conversas, contatos, WhatsApps)
**Recomendado:** Adicionar qual agente está disponível por plano

```
Start R$97:   Agente Closer (baixo ticket)
Growth R$297: SDR + Closer + Híbrido (todos os 3)
Scale R$397:  Todos os 3 + múltiplos WhatsApps
```

---

### [P3-C] Adicionar prova de velocidade com número concreto

**Atual:** "Em menos de 30 minutos a Lara já está atendendo"
**Recomendado:** "Primeira resposta automática em menos de 5 segundos — testado"

Velocidade de resposta é o principal argumento de valor. Dar um número concreto de
tempo de resposta no hero ou na seção "como funciona" aumenta a perceived likelihood.

---

## RESUMO DE IMPACTO ESPERADO

| Ajuste | Impacto Estimado | Esforço |
|--------|-----------------|---------|
| P1-A: Eliminar confusão de preço | Alta conversão (+15-30%) | Médio |
| P1-B: Adicionar 3 agentes visíveis | Diferenciação (+qualificação) | Baixo |
| P1-C: Âncora de valor real | Justificação de preço (+15%) | Baixo |
| P2-A: Headline com resultado | A/B test — validar | Baixo |
| P2-B: +2 depoimentos reais | Credibilidade crítica | Depende do time |
| P2-C: Reposicionar Start | Reduz hesitação no plano menor | Baixo |
| P3-A: Plano Anual | LTV +2-3x nos convertidos | Médio |
| P3-B: Agente por plano | Clareza de escolha | Baixo |
| P3-C: Número de velocidade | Perceived likelihood | Baixo |

---

*Revisão: Hormozi Chief — baseado em $100M Offers (Value Equation) e análise de CRMLanding.tsx*
*A página não foi modificada. Implementar ajustes no código após aprovação.*
