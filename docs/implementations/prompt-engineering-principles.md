# Documentação de Princípios de Engenharia de Prompt

**Branch:** `feat/prompt-engineering-principles`
**Status:** Em andamento

---

## Motivação

O usuário quis verificar se existia uma base de conhecimento documentada
sobre boas práticas de prompt no projeto, antes de continuar otimizando
prompts das LLMs Mãe/Filhas. Ele lembrou que uma recomendação já aplicada em
uma implementação anterior (fluxo de vendas / Camada 7) foi usar guardrails
como gatilho em código em vez de colocar tudo em texto de prompt (risco de
alucinação da IA) — mas suspeitava que isso não estava generalizado como
princípio documentado, o que explicaria divergência de estilo entre prompts
otimizados recentemente e outros que ficaram para trás.

A verificação confirmou que não existia esse documento. Os dois arquivos
mais próximos (`docs/prompts_llms.md` e
`docs/ops/simulacao-prompts-llm-autodigital157.md`) são, respectivamente, um
mapa técnico do estado atual dos prompts e uma fotografia pontual de
auditoria — nenhum captura critérios prescritivos para orientar a escrita ou
revisão de um prompt novo.

Pesquisa de mercado feita nesta sessão (guia de prompt engineering da
Claude/Anthropic + práticas de guardrails de agentes de IA) foi cruzada com
o código real do sistema para produzir um diagnóstico de "o que já
aplicamos vs. gaps conhecidos" — esse diagnóstico virou o conteúdo do novo
documento.

---

## Problemas Identificados (estado anterior)

1. **Ausência de documento de princípios:** nenhum arquivo em `docs/`
   funcionava como referência de critérios para escrever/revisar prompt —
   confirmado por busca textual em `docs/`, `docs/plans/` e
   `docs/architecture/` por "boas práticas", "best practices", "princípios",
   "meta-prompter".
2. **`docs/prompts_llms.md` órfão do workflow:** já existia e é relevante
   para a mesma área (mapa técnico de cada prompt real), mas não estava
   listado na tabela "Documentação de Arquitetura" do `CLAUDE.md` — nenhuma
   instrução conectava sua leitura ao trabalho de editar prompt de Mãe/Filha.
3. **Divergência de estilo entre prompts:** algumas Filhas foram otimizadas
   ad-hoc (blocos "REGRA ANTI-REPETIÇÃO", "TOM DE VOZ — REGRAS WHATSAPP",
   "VALIDAÇÃO — VERIFICAR ANTES DE RETORNAR" na Qualification/Apresentação),
   enquanto outras (Filha Closing genérica, blocos hardcoded da Recepção)
   não passaram pela mesma revisão — sintoma direto do problema 1.

---

## Abordagem

Documentação pura, sem mudança de comportamento em runtime:

```
Pesquisa de mercado (prompt engineering) + leitura do código real
  → diagnóstico "já aplicamos / gap conhecido" por princípio
  → docs/architecture/prompt-engineering-principles.md (7 princípios + checklist)
  → CLAUDE.md: tabela de arquitetura + instrução de leitura obrigatória
    antes de mexer em prompt de Mãe/Filha ou Camada 7
```

Os gaps identificados durante a pesquisa (ex.: falta de validação de código
para `checkout_sent`+URL, PROIBIÇÕES em formato negativo, ausência de schema
reforçado na chamada da Mãe) são **documentados como conhecidos**, não
corrigidos nesta implementação — ficam registrados no próprio documento como
candidatos a uma implementação futura própria, com seus próprios testes.

---

## Plano de Implementação

### Fase 1 — Criar o documento de princípios e conectar ao workflow

**Objetivo:** registrar os princípios de prompt engineering aplicáveis ao
sistema e garantir que futuras sessões os leiam antes de mexer em prompt de
Mãe/Filha.

| Arquivo | O que muda |
|---|---|
| `docs/architecture/prompt-engineering-principles.md` | Novo arquivo — 7 princípios (guardrail de código vs. prompt, positivo vs. negativo, few-shot, contexto/motivo, JSON estruturado, permissão para incerteza, minimalismo), cada um com regra, motivo, onde já aplicamos (arquivo/função real) e gap conhecido — fechando com checklist rápida |
| `CLAUDE.md` | Nota de leitura obrigatória logo após "Pipeline de IA (fluxo inbound)"; duas novas linhas na tabela "Documentação de Arquitetura" (o novo arquivo + `docs/prompts_llms.md`, que estava ausente da tabela) |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `936ae33` | Documento de princípios + conexão ao workflow (CLAUDE.md) |

**Detalhes do commit `936ae33`:**
- `docs/architecture/prompt-engineering-principles.md` — 7 princípios com regra, motivo, onde já aplicamos e gap conhecido, fechando com checklist
- `CLAUDE.md` — nota de leitura obrigatória + 2 linhas novas na tabela de Documentação de Arquitetura
- `docs/implementations/prompt-engineering-principles.md` — registro desta implementação

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não havia nenhum documento no projeto com critérios para escrever
ou revisar um prompt de Mãe/Filha — só um mapa técnico do que já existe
(`docs/prompts_llms.md`) e uma fotografia pontual de auditoria, nenhum dos
dois prescritivo.
**Agora:** existe `docs/architecture/prompt-engineering-principles.md` com 7
princípios (guardrail de código vs. prompt, positivo vs. negativo, few-shot,
contexto/motivo, JSON estruturado, permissão para incerteza, minimalismo),
cada um citando onde o sistema já segue a prática e onde há gap conhecido —
e o `CLAUDE.md` agora instrui a ler esse documento (+ `docs/prompts_llms.md`)
antes de mexer em qualquer prompt de Mãe/Filha ou configurar a Camada 7.
**Para validar:** Cenário P1, abaixo — é revisão de conteúdo, não teste de
sistema (tarefa é documentação pura, sem mudança de comportamento em
runtime).

---

## Fase 2 — Esqueleto de um prompt de Filha (anatomia)

**Objetivo:** durante a revisão do Cenário P1, o usuário lembrou de um
padrão de mercado para estruturar um prompt ("o que ela é, o que faz, o que
não faz, exemplos do que fazer e do que não fazer") e pediu para: confirmar
que esse padrão já está aplicado nas Filhas otimizadas recentemente
(Recepção, Closing), pesquisar como o mercado documenta essa estrutura, e
acrescentar isso ao documento — com cuidado de distinguir estrutura fixa
(igual para todo usuário) de conteúdo que precisa ser variável por negócio
(multi-tenant).

Investigação: `_build_child_prompt_recepcao()` (`decision_engine.py:2569`)
já segue o esqueleto completo 100% fixo (exemplos são de comportamento,
válidos para qualquer nicho). `_build_child_prompt_closing()`
(`decision_engine.py:3993`) segue o mesmo esqueleto com nomes de seção
próprios, mas delega os exemplos a `_build_training_examples_block()`
(`decision_engine.py:1211`) — classificações reais do operador no
Playground, dinâmicas por negócio. Pesquisa de mercado (blog oficial da
Anthropic, "Prompt engineering best practices for 2026") confirmou a mesma
ordem de blocos e o critério fixo-vs-dinâmico para exemplos.

| Arquivo | O que muda |
|---|---|
| `docs/architecture/prompt-engineering-principles.md` | Nova seção "8. Esqueleto de um prompt de Filha" (esqueleto, onde já aplicamos, regra multi-tenant fixo vs. dinâmico, gap conhecido, fonte) + 1 item novo na checklist final |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `7af4d94` | Seção 8 (esqueleto de prompt) + item de checklist |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** o documento tinha 7 princípios individuais, mas nenhum descrevia
a estrutura/ordem completa de um prompt de Filha — cada princípio cobria uma
prática isolada (guardrail, positivo vs. negativo, exemplos, etc.), sem
juntar tudo num esqueleto único.
**Agora:** existe uma seção 8 mostrando o esqueleto completo (identidade →
faz → não faz → exemplos → formato de saída), citando a Recepção como
exemplo 100% fixo e a Closing como exemplo do mesmo esqueleto com exemplos
dinâmicos por negócio — e a checklist final ganhou 1 pergunta nova para
conferir isso em prompts futuros.
**Para validar:** Cenário P2, abaixo — mesma natureza do P1 (revisão de
conteúdo, sem mudança de comportamento em runtime).

---

## Checks de Validação

Tarefa documental — sem cenário de Playground/WhatsApp aplicável. O check é
revisão de conteúdo:

### Cenário P1 — Revisão do conteúdo pelo usuário
- [ ] Usuário lê `docs/architecture/prompt-engineering-principles.md` e
      confirma que os 7 princípios e os exemplos/gaps citados fazem sentido
- [ ] Confirmar que as referências a arquivo/função citadas (ex.
      `decision_engine.py:1837`, `sales-flow.md`) ainda batem com o código
      real no momento da leitura

### Cenário P2 — Revisão do conteúdo da seção 8 (esqueleto) pelo usuário
- [ ] Usuário lê a seção "8. Esqueleto de um prompt de Filha" e confirma que
      o esqueleto e a distinção fixo/dinâmico fazem sentido
- [ ] Confirmar que as referências citadas (`decision_engine.py:2569`,
      `decision_engine.py:3993`, `decision_engine.py:1211`) ainda batem com
      o código real no momento da leitura

---

## Ajustes Possíveis Pós-Implementação

- Os gaps documentados (PROIBIÇÕES em negativo, falta de validação de código
  para VALIDAÇÃO/`checkout_sent`+URL, ausência de schema reforçado na Mãe)
  não são corrigidos nesta implementação — ficam registrados no documento
  como candidatos a uma implementação futura própria
  (`docs/plans/*-melhorias-futuras.md`, se o usuário quiser abrir), com seus
  próprios testes P/C.
