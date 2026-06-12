# Advisor Agent — Avaliação e Plano de Expansão

**Data:** Junho 2026  
**Contexto:** Análise do advisor-agent actual e roadmap de evolução para um colaborador técnico de alto valor para um fundador solo a construir um SaaS de CRM com automação de vendas via WhatsApp.

---

## 1. O que o advisor faz hoje

### Papel actual: Observador Retrospectivo

O advisor na sua forma actual desempenha o papel de um **jornalista técnico** — lê o que aconteceu, organiza numa narrativa e entrega um relatório diário.

| Capacidade | Implementada |
|---|---|
| Ler histórico de sessões Claude Code | Sim |
| Identificar ficheiros modificados por área | Sim |
| Ler contexto do projecto (CLAUDE.md + docs) | Sim |
| Ler git log | Sim |
| Gerar avaliação técnica | Sim |
| Identificar pontos fortes | Sim |
| Identificar melhorias com prioridade | Sim |
| Sugerir próximas prioridades | Sim |
| Análise diária automática | Sim |
| Dashboard web | Sim |

### Limitações actuais

1. **Sem memória transversal** — cada análise começa do zero, não aprende com análises anteriores
2. **Só olha para trás** — não monitoriza o código em tempo real
3. **Passivo** — espera ser chamado, não avisa sobre problemas
4. **Sem contexto de produto** — não sabe o que é uma funcionalidade "valiosa" para os clientes vs. trabalho interno
5. **Sem acesso ao código** — analisa o que o dev fez, não o resultado (o código em si)
6. **Sem métricas objectivas** — só avaliação qualitativa

---

## 2. O que seria um bom profissional neste papel

### Analogia: o Director Técnico Fractional

No mercado, um CTO fractional para uma startup em fase de construção tipicamente entrega:

1. **Revisão de arquitectura** — valida decisões antes de serem implementadas
2. **Radar de riscos** — identifica o que pode explodir antes de explodir
3. **Acelerador de decisões** — responde a "como faço X?" com contexto do sistema
4. **Memória do projecto** — lembra o porquê de cada decisão tomada
5. **Coach de qualidade** — padrões de excelência técnica aplicados ao contexto específico
6. **Tradutor produto ↔ código** — alinha o que o produto precisa com o que o código deve fazer

O advisor actual cobre parcialmente o ponto 5. Os restantes 5 pontos são oportunidades de expansão.

---

## 3. O que a investigação diz sobre AI advisors em 2026

Com base em pesquisa actualizada:

### Tendências confirmadas

- **Revisão especializada por agentes** — ferramentas como Augment Code e Qodo identificam 42-48% de bugs reais em revisão automática, muito acima dos 20% de analisadores estáticos tradicionais. A abordagem que funciona é ter agentes especializados (segurança, performance, correctness) em vez de um agente genérico.

- **Detecção de dívida técnica activa** — plataformas modernas analisam arquitectura, acoplamento entre módulos e padrões de defeitos para dar uma "pontuação de remediação" por módulo. Isso permite priorizar o que corrigir antes que se torne um bloqueio.

- **Contexto como base de dados** — os fundadores solo mais produtivos de 2025-2026 tratam o contexto do AI como uma base de dados estruturada: decisões de produto, histórico técnico, padrões de cliente. Isto é exactamente o que o advisor pode gerir.

- **De monólogo a painel** — a evolução dos revisores de código vai de um relatório único para um painel de especialistas: cada agente foca numa dimensão diferente (segurança, débito, coerência com arquitectura).

- **De retrospectivo a proactivo** — a geração actual de ferramentas notifica o dev antes do problema se instalar, não depois de ele já ter feito o commit.

### O gap que existe para um fundador solo

Os estudos de 2025 mostram que **84% dos devs usam AI**, mas a maioria usa para geração de código — não para análise estratégica. Para um fundador solo, o maior risco não é escrever código lento, é tomar decisões de arquitectura que criam dívida técnica silenciosa, ou trabalhar nas áreas erradas sem perceber.

---

## 4. Ideias de expansão — ordenadas por valor

### Nível 1 — Alta prioridade, implementação simples

#### 1.1 Memória transversal de análises
**O que é:** Guardar todas as análises num histórico. A análise do dia compara com as análises das últimas semanas.  
**Valor:** O advisor passa a dizer "este é o terceiro sprint que a área de follow-up tem prioridade HIGH sem ser resolvida" — contexto impossível de ter sem memória.  
**Implementação:** Persistir análises históricas em `data/history/`. Incluir as últimas 3-5 análises no contexto ao gerar uma nova.

#### 1.2 Alerta de padrões negativos
**O que é:** Detectar padrões problemáticos nos commits e sessões — ex.: muitas sessões curtas no mesmo ficheiro (sinal de instabilidade), ausência de commits há N dias, trabalho numa única área.  
**Valor:** Aviso proactivo antes do problema virar dívida.  
**Implementação:** `services/pattern_detector.py` com regras simples. Alerta visível no topo do dashboard.

#### 1.3 Métricas objectivas de sessão
**O que é:** Adicionar ao dashboard: número de ficheiros modificados por área, sessões por semana, ratio documentação/código.  
**Valor:** Dados concretos sobre onde o tempo vai. Difícil de perceber sem métricas.  
**Implementação:** `services/metrics.py` — agrega dados dos JSONL sem precisar chamar o Claude.

---

### Nível 2 — Alto valor, implementação moderada

#### 2.1 Revisão de código por área
**O que é:** O advisor lê os diffs do git (`git diff main`) e analisa o código real, não apenas o que o dev pediu ao Claude.  
**Valor:** Detecta problemas que o dev não percebeu que existiam — código duplicado, violações de convenção, ausência de filtro por `user_id`, etc.  
**Implementação:** `readers/code_reader.py` — usa `git diff` para obter os diffs dos últimos N commits. Passa ao Claude com um prompt de revisão especializado.

#### 2.2 Rastreador de decisões de arquitectura
**O que é:** Um registo persistente das decisões técnicas importantes tomadas no projecto — porquê se usou SQLite raw em vez de ORM, porquê os backends estão separados, etc.  
**Valor:** Quando o advisor detecta uma sessão que contradiz uma decisão anterior, avisa. Evita regressões de arquitectura.  
**Implementação:** `data/decisions.json` editável. O analyzer verifica consistência das sessões recentes com as decisões registadas.

#### 2.3 Modo "Pré-sessão"
**O que é:** Um endpoint `/briefing` que, ao ser chamado, gera um briefing de 5 linhas: "o que ficou pendente ontem, o que está em HIGH priority, o que deves focar hoje".  
**Valor:** Em vez de abrir o dashboard para ver análise retroactiva, abres para saber o que fazer agora.  
**Implementação:** Novo endpoint em `main.py`. Prompt diferente focado em contexto de arranque de dia.

---

### Nível 3 — Transformador, implementação mais complexa

#### 3.1 Agentes especializados por dimensão
**O que é:** Em vez de um único prompt que avalia tudo, dividir em agentes especializados:
- **Agente de Segurança** — verifica se há dados de utilizador sem filtro por `user_id`, endpoints sem auth, etc.
- **Agente de Consistência** — verifica se o que foi implementado é consistente com o CLAUDE.md e os docs de arquitectura
- **Agente de Produto** — avalia se o trabalho feito está alinhado com o que os 3 tipos de agente de venda precisam

**Valor:** Análises muito mais precisas e accionáveis. A abordagem de painel em vez de monólogo é o estado da arte em 2026.  
**Implementação:** `services/specialist_agents.py` — corre 3 chamadas `claude --print` em paralelo com prompts especializados, depois um agente de síntese que agrega.

#### 3.2 Integração com roadmap e objectivos
**O que é:** Um ficheiro `data/goals.json` onde defines objectivos do projecto (ex.: "lançar agente 2 funcional até agosto 2026"). O advisor mede a progressão e avisa se o ritmo actual não chega ao objectivo.  
**Valor:** Liga o trabalho técnico diário aos objectivos de negócio. Converte o advisor de "avaliador técnico" para "parceiro de negócio".  
**Implementação:** Interface simples no dashboard para gerir objectivos. O analyzer inclui os objectivos no contexto.

#### 3.3 Revisão proactiva de PRs / branches
**O que é:** Monitorizar quando uma nova branch é criada ou quando commits são feitos, e gerar automaticamente uma revisão da branch antes de ela ser merged ou de se começar a trabalhar nela.  
**Valor:** Evita mergear problemas. Detecta quando uma branch está a ficar grande demais ou a acumular conflitos.  
**Implementação:** `services/branch_watcher.py` com polling do git. Trigger automático ao detectar nova branch.

---

## 5. Roadmap sugerido

### Fase A — Esta semana (30 min de implementação)
- [ ] 1.1 Memória transversal de análises
- [ ] 1.3 Métricas objectivas de sessão

### Fase B — Próximo sprint
- [ ] 1.2 Alerta de padrões negativos
- [ ] 2.3 Modo "Pré-sessão" (`/briefing`)

### Fase C — Após lançamento do produto base
- [ ] 2.1 Revisão de código por área (git diff)
- [ ] 2.2 Rastreador de decisões de arquitectura

### Fase D — Versão madura
- [ ] 3.1 Agentes especializados por dimensão
- [ ] 3.2 Integração com roadmap e objectivos
- [ ] 3.3 Revisão proactiva de branches

---

## 6. Visão final: o que o advisor pode ser

Com as expansões da Fase D, o advisor deixa de ser um "observador" e passa a ser um **CTO fractional autónomo** que:

- Conhece o historial completo de decisões do projecto
- Avisa antes de problemas se instalarem
- Mede a progressão em relação aos objectivos de produto
- Revê código real, não apenas pedidos ao Claude
- Tem especialistas por dimensão (segurança, produto, arquitectura)
- Gera o briefing do dia ao arrancar o computador
- Actua como memória viva do projecto

Para um fundador solo a construir um SaaS com 3 tipos de agentes de venda, este nível de suporte é o equivalente a ter um sócio técnico disponível 24/7 — sem custo fixo de equipa.

---

## Fontes de pesquisa

- [AI Code Review Automation: Complete Guide 2025 — Digital Applied](https://www.digitalapplied.com/blog/ai-code-review-automation-guide-2025)
- [Best AI Coding Agents for 2026 — Faros AI](https://www.faros.ai/blog/best-ai-coding-agents-2026)
- [2026 Agentic Coding Trends Report — Anthropic](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
- [5 AI Code Review Pattern Predictions in 2026 — Qodo](https://www.qodo.ai/blog/5-ai-code-review-pattern-predictions-in-2026/)
- [AI-Driven Technical Debt Analysis — Milestone](https://mstone.ai/blog/ai-driven-technical-debt-analysis/)
- [Using Agentic AI to Eliminate Technical Debt — Ubix Labs](https://www.ubixlabs.com/blog/using-agentic-ai-to-eliminate-technical-debt)
- [AI as Solo Founder Productivity Multiplier — SoftwareSeni](https://www.softwareseni.com/ai-as-solo-founder-productivity-multiplier-tools-workflows-and-real-roi/)
- [The One-Person Unicorn: How Solo Founders Use AI — NxCode](https://www.nxcode.io/resources/news/one-person-unicorn-context-engineering-solo-founder-guide-2026)
- [AI in Software Development: Productivity at the Cost of Code Quality — DevOps.com](https://devops.com/ai-in-software-development-productivity-at-the-cost-of-code-quality-2/)
- [Stack Overflow Developer Survey 2025 — AI section](https://survey.stackoverflow.co/2025/ai)
