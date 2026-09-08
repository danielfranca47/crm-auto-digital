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

## Fase 3 — Achados de pesquisa além do que o usuário indicou

**Objetivo:** ao revisar a Fase 2, o usuário pediu explicitamente algo
diferente do que fez até aqui — não só formalizar o que ele mesmo indicou,
mas pesquisar e trazer valor novo, achados de mercado que ele não mencionou
e que se apliquem concretamente ao sistema.

Para isso, foi lido o cliente de LLM real do sistema
(`backend-executors/app/services/llm_service.py`), não só os prompts, e
cruzado com pesquisa de mercado (OpenAI Structured Outputs, OWASP GenAI
prompt injection, configuração de temperature, prompt caching automático da
OpenAI). Revelou 4 achados código-a-código inéditos nesta implementação:
(1) nenhuma chamada define `temperature` — decisões estruturadas (rota da
Mãe, extração de campo) rodam com o default alto do provider; (2)
`json_object` solto em vez de Structured Outputs (`json_schema`+`strict`)
da Responses API — concretiza o gap já citado no princípio 5 com o mecanismo
exato disponível hoje; (3) a mensagem do lead entra no prompt sem nenhum
delimitador que a marque como dado (não instrução) — superfície de prompt
injection não tratada num sistema multi-tenant que recebe texto arbitrário
de qualquer lead; (4) o bloco de campos faltantes (`missing_fields`), que
muda a cada turno, aparece cedo demais no prompt da Filha, invalidando o
prefixo que a OpenAI cachearia automaticamente (até 90% de desconto, 80%
menos latência) — relevante porque o sistema chama a LLM a cada mensagem de
WhatsApp.

| Arquivo | O que muda |
|---|---|
| `docs/architecture/prompt-engineering-principles.md` | Nova seção "9. Achados de pesquisa aplicados ao nosso motor de LLM" com os 4 achados (cada um com arquivo/linha real, fonte de mercado, marcado como gap conhecido) + 1 item novo na checklist final |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `c9f1b62` | Seção 9 (4 achados de pesquisa) + item de checklist |

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o documento cobria só o que já era prática conhecida no time
(princípios 1-7) e o esqueleto de prompt que o próprio usuário descreveu
(princípio 8) — nada vinha de uma investigação nova no motor de LLM real.
**Agora:** existe uma seção 9 com 4 achados que ninguém tinha levantado
ainda nesta implementação — configuração de `temperature`, uso de
Structured Outputs da OpenAI, isolamento da mensagem do lead como defesa
contra prompt injection, e reordenação do prompt para aproveitar o cache
automático da OpenAI — cada um citando o código real e uma fonte de
mercado, registrados como gaps conhecidos (candidatos a implementação
futura de código, fora do escopo desta tarefa documental).
**Para validar:** Cenário P3, abaixo — mesma natureza do P1/P2 (revisão de
conteúdo, sem mudança de comportamento em runtime).

## Fase 4 — Correção de escopo: mover achados de pesquisa para docs/plans

**Objetivo:** ao revisar a Fase 3, o usuário esclareceu o propósito do
documento — `prompt-engineering-principles.md` é conhecimento acionável
para escrever um prompt **com o que já existe hoje**, não um lugar para
registrar otimizações futuras ainda não implementadas (isso já tem lugar
próprio em `docs/plans/`) nem para espelhar a estrutura real do sistema
(isso é `prompts_llms.md`/`docs/architecture/`). A seção 9 (os 4 achados de
pesquisa) violava essa regra — descrevia gaps de código para implementação
futura, não critério de escrita de prompt.

**O que mudou:**
- `docs/architecture/prompt-engineering-principles.md`: seção 9 removida
  por completo (revertida), junto do item de checklist que a referenciava.
  O documento volta a ter só os 8 princípios/esqueleto já validados pelo
  usuário.
- `docs/plans/motor-llm-otimizacoes.md`: passa a ser a **única** fonte dos 4
  achados (já continha o mesmo conteúdo, criado na resposta anterior a
  pedido do usuário) — contexto do arquivo atualizado para não referenciar
  mais a seção 9 removida. Itens M3 (isolar mensagem do lead) e M4
  (reordenar prompt para cache) ganharam uma nota "Ao implementar": quando
  esses itens virarem código de verdade, a própria implementação deve
  voltar a `prompt-engineering-principles.md` e adicionar a instrução
  concreta resultante — só nesse momento esse conhecimento passa a ser
  "prática já aplicada", que é o que o documento existe para registrar.
- Cenário P3 removido dos Checks de Validação (não há mais conteúdo na
  seção 9 do documento de arquitetura para validar).

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `<pendente>` | Reversão da seção 9 + atualização do plano em docs/plans |

---

## Checks de Validação

Tarefa documental — sem cenário de Playground/WhatsApp aplicável. O check é
revisão de conteúdo:

### Cenário P1 — Revisão do conteúdo pelo usuário
- [ ] Usuário lê `docs/architecture/prompt-engineering-principles.md` e
      confirma que os 7 princípios e os exemplos/gaps citados fazem sentido
- [x] (2026-09-08) Confirmar que as referências a arquivo/função citadas
      (ex. `decision_engine.py:1837`, `sales-flow.md`) ainda batem com o
      código real no momento da leitura — verificado por Claude

### Cenário P2 — Revisão do conteúdo da seção 8 (esqueleto) pelo usuário
- [ ] Usuário lê a seção "8. Esqueleto de um prompt de Filha" e confirma que
      o esqueleto e a distinção fixo/dinâmico fazem sentido
- [x] (2026-09-08) Confirmar que as referências citadas
      (`decision_engine.py:2569`, `decision_engine.py:3993`,
      `decision_engine.py:1211`) ainda batem com o código real no momento
      da leitura — verificado por Claude

---

## Ajustes Possíveis Pós-Implementação

- Os gaps documentados (PROIBIÇÕES em negativo, falta de validação de código
  para VALIDAÇÃO/`checkout_sent`+URL, ausência de schema reforçado na Mãe)
  não são corrigidos nesta implementação — ficam registrados no documento
  como candidatos a uma implementação futura própria
  (`docs/plans/*-melhorias-futuras.md`, se o usuário quiser abrir), com seus
  próprios testes P/C.
