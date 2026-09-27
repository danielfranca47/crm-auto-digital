# Fix: conhecimento que a IA nunca lê (e consolidação das camadas)

**Branch:** `fix/categorias-conhecimento-orfas` (na sessão: `worktree-fix+categorias-conhecimento-orfas`)
**Status:** Em andamento
**Origem:** `docs/discovery/levantamentos/2026-09-23-busca-vetorial-gemini.txt` — triagem da discovery (bug confirmado, veio direto para implementations por decisão do utilizador)

---

## Motivação

O ecrã de conhecimento do agente (Camada 4 do AI Profile) oferece categorias que o
utilizador preenche, mas cujo texto **nunca chega ao prompt** do LLM. O cliente acha
que ensinou o agente e o agente não sabe responder, ou improvisa — causa provável do
relato "às vezes pergunto uma informação e ele não responde".

**Impacto medido em produção (23/09/2026, consulta só de leitura):** 16 dos 25 itens
de conhecimento ativos (~58% do texto) estão em categorias órfãs, nos 3 clientes
(cliente 3: 6 de 8 itens, ~83% do texto).

**Pedido do utilizador no Plan Mode:** antes de "ligar os fios", avaliar se cada
categoria faz falta face ao **Fluxo de Venda (Camada 7)** e às outras camadas —
evitar **ambiguidade**, retrabalho e tokens gastos em poluição, mantendo a direção
**semântica** (a IA decide o que é relevante), sem regredir para regras
determinísticas por palavra/categoria.

---

## Problemas Identificados (estado anterior)

1. **Categorias órfãs:** 19 chaves de `frontend-crm/src/types/agente.ts` sem nenhuma
   leitura em `backend-executors/app/services/decision_engine.py` nem no orchestrator
   (ex.: `company_profile`, marcada como **Crítico** em
   `docs/conhecimento-dos-agentes.md:37`).
2. **Conteúdo extra (texto livre / upload) também nunca chegava:** o
   `createKnowledgeManual` e o upload gravam sem categoria; o orchestrator convertia
   em `"uncategorized"` (`orchestrator.py:519`) e nada lia essa chave.
3. **Só o item mais recente por categoria:** `_load_knowledge_items`
   (`orchestrator.py:503`) descarta os restantes itens activos da mesma categoria
   (exceto `service_pricing_table`). Não ocorre hoje em produção.
4. **Qualificação e fecho sem FAQs:** só recebem `business_info`
   (`decision_engine.py`, prompts de qualificação e fecho) — hipótese da investigação
   `docs/discovery/conhecimento-fora-fase-apresentacao.md`.
5. **Categorias que duplicam outras camadas ou o Fluxo de Venda:** ver a classificação
   abaixo.

### Classificação das categorias da Camada 4

| Tipo | Categorias | Destino |
|---|---|---|
| **Referência** — o que o agente *sabe* | `company_profile`★, `professional_bio`★, `pre_meeting_faq`★, `scheduling_policy`★, `price_policy`★, `competitive_differentials`★, conteúdo extra★ · já lidas: `objections_faq`, `service_faq`, `guarantee_policy`, `service_pricing_table`, `commercial_objections`, `service_differentials`, `active_promotion`, `payment_policy`, `pre_commitment_faq` | Bloco único "Base de conhecimento" em todas as fases de conversa |
| **Narrativa proativa** — contar 1x | `social_proof`, `pitch_script`, `product_details` | Ficam (dedup 1x por lead) |
| **Roteiro com momento** — o que o agente *faz* e *quando* | `warming_script`★, `cart_recovery_scripts`★, `nurture_content`★, `post_session_followup`★, `referral_script`★, `pre_session_material`★, `urgency_offer`★ | Fluxo de Venda — saem da Camada 4 |
| **Duplicado de outra camada** | `session_preview`★ (Camada 1), `upsell_content`★ (Camada 6), `fit_questions`★ / `pain_questions`★ (Camada 2), `handoff_briefing_template`★ (dossiê gerado por código) | Saem da Camada 4 |
| Uso próprio | `qualification_criteria` | Fica |

★ = nunca chegava à IA.

---

## Abordagem

```
Camada 4 (Referência + Narrativa + qualification_criteria)
  → orchestrator: knowledge_reference = itens de Referência sem bloco próprio
    (todos os itens activos) + conteúdo extra — ContextBundle via enrich_context_bundle
  → decision_engine: _build_knowledge_reference_block() ao lado de business_info,
    em qualificação, apresentação, follow-up, fecho, pré-agendamento e agendamento
    → UMA instrução semântica ("consulte quando o lead perguntar algo coberto…")
Roteiros → Fluxo de Venda (Camada 7) · Duplicados → camada de origem
```

Porquê um bloco único e não ligar cada categoria à sua fase: ligar uma a uma
acrescentaria ~13 regras "usar APENAS quando…" (determinísticas, ambíguas, caras de
manter). Com bases de ~650 tokens em produção, a recomendação registada na discovery
(Anthropic: abaixo de ~200 mil tokens, a base inteira no prompt) é dar tudo à IA com
uma instrução. Teto de 40 mil caracteres = gatilho da investigação de RAG em stand-by.

---

## Plano de Implementação

### Fase 1 — Levar à IA o que hoje se perde

**Objetivo:** as 6 categorias de referência órfãs + o conteúdo extra chegam à IA em
todas as fases de conversa, sem mexer no que já funciona.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_REFERENCE_ONLY_CATEGORIES`, `_KNOWLEDGE_REFERENCE_MAX_CHARS`, `_load_knowledge_reference()`; campo `knowledge_reference` no `ContextBundle`; passo B2b em `enrich_context_bundle()` |
| `backend-crm/routes/executor.py` | Copia `knowledge_reference` para o contexto do WhatsApp real |
| `backend-executors/app/services/decision_engine.py` | `_build_knowledge_reference_block()` injectado nos 6 prompts de fase, ao lado de `_build_business_info_block()` |
| `backend-executors/tests/test_knowledge_reference_block.py` | Novo — bloco (render, vazio, heading) + presença nas 6 fases |
| `backend-crm/tests/test_knowledge_reference.py` | Novo — seleção de categorias, extras, todos os itens, exclusões, teto, enrich |
| `backend-crm/tests/test_calendar_busy_slots.py` | Esquema de teste ganha a tabela `knowledge_items` (o enrich passou a consultá-la) |
| `docs/architecture/knowledge-base.md`, `playground-parity.md`, `docs/prompts_llms.md` | Bloco novo, campo B2b, mapa de prompts |

**Testes:** 12 novos no backend-executors e 7 no backend-crm, todos a passar. Na suíte
completa do backend-executors, as mesmas 73 falhas que já existiam antes (nenhuma
nova). O backend-crm tem erros de recolha antigos quando corre inteiro (testes que
substituem o `fastapi` e um erro do pydantic em `InboundWebhookPayload`), sem
relação com esta fase; os testes do orchestrator passam quando corridos isolados.

#### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `224d23e` | `knowledge_reference` (orchestrator + executor + decision_engine), testes, docs |

#### Relatório da Fase 1 — o que mudou na prática

**Antes:** o perfil da empresa, a bio do profissional, a FAQ pré-reunião, as
políticas de agendamento e de preço, a diferenciação competitiva e tudo o que era
adicionado como "conteúdo extra" (texto livre ou upload) ficavam guardados, mas a IA
nunca os via. Perguntas sobre isso ficavam sem resposta ou eram improvisadas.
**Agora:** esse conteúdo chega à IA em todas as fases da conversa, num bloco único,
com a instrução de o usar quando o lead pergunta algo que ele cobre e depois retomar
o objetivo da fase. Os roteiros (recuperação de carrinho, aquecimento, etc.)
continuam de fora, de propósito: vão para o Fluxo de Venda na Fase 4.
**Para validar:** Cenários P1, P2 e P4, abaixo.

### Fase 2 — Consolidar (remover a ambiguidade)

**Objetivo:** as categorias de Referência já lidas passam para o mesmo bloco único;
saem as instruções "usar APENAS quando…" por categoria (`decision_engine.py`,
apresentação e follow-up), mantendo as notas de mídia e as narrativas. Qualificação e
fecho passam a ter as FAQs; o preço na qualificação fica como estava (ver decisão abaixo).
Medir o tamanho do prompt antes/depois.

**Decisão no Plan Mode (24/09/2026):** a qualificação retém preço e oferta desde
22/04/2026 (commit `6a05d31`: "preços são exclusivos da fase de apresentação"). O
utilizador decidiu que isto **não é uma regra fixa**: depende do processo de venda de
cada cliente. A Fase 2 mantém o comportamento atual e a Fase 3 transforma-o numa opção.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `_REFERENCE_CATEGORIES` com as 9 categorias já lidas; itens com `category`; tabela estruturada renderizada |
| `backend-executors/app/services/decision_engine.py` | `_build_knowledge_reference_block(exclude_categories)`; saem os blocos "usar APENAS" (apresentação, modo comercial sob pedido, follow-up); exclusões por fase (`_QUALIFICATION_WITHHELD_CATEGORIES`, mídia na apresentação, `_COMMERCIAL_INJECTION_CATEGORIES`, tabela no agendamento); notas de mídia genéricas; regra de pagamento presencial do modo comercial; qualificação responde com "custom_instructions e a base de conhecimento"; instrução geral cobre objeções |
| `backend-executors/tests/test_knowledge_reference_block.py` | Exclusões, qualificação (FAQ sim, preço não), fases seguintes sem "usar APENAS", agendamento sem tabela duplicada, follow-up sem promessa de mídia |
| `backend-executors/tests/test_apresentation_ondemand_commercial_knowledge.py` | Reescrito: tabela pelo bloco único em qualquer template, 1 só vez no turno comercial, nota de mídia |
| `backend-executors/tests/test_narrative_knowledge_dedup.py` | FAQs passam a vir por `knowledge_reference` |
| `backend-crm/tests/test_knowledge_reference.py` | Categorias novas, `category`, tabela renderizada |
| `docs/architecture/knowledge-base.md`, `pipeline-phases.md`, `docs/prompts_llms.md` | Tabela de exclusões por fase, mapa de blocos |

**Tamanho do prompt (conta de teste, antes → depois, em caracteres):**

| Fase | Antes | Depois | "usar APENAS" | FAQ do Serviço | Tabela de preços |
|---|---|---|---|---|---|
| Qualificação | 13 083 | 13 857 | 0 → 0 | não → **sim** | não → não (retida) |
| Apresentação | 17 025 | 16 773 | 3 → 0 | sim | sim |
| Follow-up | 11 911 | 12 203 | 1 → 0 | sim | não → **sim** |
| Fecho | 10 730 | 11 592 | 0 | não → **sim** | não → **sim** |
| Pré-agendamento | 10 939 | 11 801 | 0 | não → **sim** | não → **sim** |
| Agendamento | 12 018 | 12 714 | 0 | não → **sim** | sim (1 vez) |

**Testes:** 22 no bloco, 7 no comercial sob pedido e 10 no orchestrator, todos a passar.
A suíte completa do backend-executors tem 72 falhas antes e depois, a mesma lista (as 73
referidas na Fase 1 eram 72 nesta máquina). No backend-crm, `test_inbound_orchestrator_flag`
falha igual no commit da Fase 1 (erro antigo do pydantic em `InboundWebhookPayload`).

#### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a1ad9ad` | Bloco único com todas as categorias de referência, exclusões por fase, testes, docs |

#### Relatório da Fase 2 — o que mudou na prática

**Antes:** a IA recebia o conhecimento de duas formas diferentes. Uma parte vinha num
bloco único e outra vinha em pedaços, cada um com a sua regra ("usar APENAS se o lead
pedir o preço", "usar APENAS quando levantar uma objeção"…). Essas regras só existiam na
apresentação e no follow-up. A qualificação, o fecho e o agendamento não viam as FAQs,
a garantia nem as objeções. Com mídia configurada, o follow-up dizia à IA que ia enviar
um ficheiro que nunca era enviado.
**Agora:** todo o conhecimento vem num só bloco, com uma só instrução, em todas as
fases. Cada fase só deixa de fora o que já recebe por outro caminho: a tabela no
agendamento, porque já lá está para calcular a duração; o que tem imagem ou ficheiro na
apresentação, porque o ficheiro é a resposta. Os preços continuam retidos na qualificação,
como hoje, até à Fase 3. O prompt da apresentação ficou um pouco mais pequeno. As outras
fases cresceram entre 300 e 900 caracteres, que é o conhecimento que lhes faltava.
**Para validar:** Cenário P3, abaixo.

### Fase 3 — "Preço na qualificação" passa a ser escolha do utilizador

**Objetivo:** na Camada 2, cada utilizador escolhe o que o agente faz quando o lead
pergunta o preço durante a qualificação: "responder quando perguntado" ou "deixar para
a apresentação" (predefinido, igual ao comportamento atual). Novo campo
`qualification_price_disclosure` (`on_request` / `after_qualification`) no AI profile
(backend-core), lido pelo prompt de qualificação; seletor na Camada 2 e no resumo; campo
no painel admin (`admin-agents-contract.md`). A mídia continua só na apresentação.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py`, `app/db.py`, `app/api/ai_profiles.py` | Coluna `qualification_price_disclosure` (padrão `after_qualification`), migração idempotente, enum `QualificationPriceDisclosure` nos schemas |
| `backend-executors/app/services/decision_engine.py` | `_qualification_price_disclosure()`; exclusão das categorias de preço só com `after_qualification`; `_price_line` única nos modos ativo e passivo (substitui "exclusivas da fase de apresentação" e "serão apresentadas em breve"; o modo ativo não tinha regra) |
| `backend-crm/routes/admin_agents.py` | Campo no diff (`_SYSTEM_DEFAULTS`) e nas respostas por utilizador |
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | Seletor `TogglePriceDisclosure` abaixo de "Como o agente coleta informações" |
| `frontend-crm/src/pages/AiProfile.tsx` | Linha "Preço na qualificação" no resumo |
| `frontend-crm/src/types/agente.ts`, `src/services/api.ts` | Campo, valor predefinido, leitura e gravação |
| `backend-core/tests/test_ai_profile_price_disclosure.py` | Novo: padrão e persistência de `on_request` |
| `backend-executors/tests/test_knowledge_reference_block.py` | Qualificação nos dois valores × modos ativo/passivo, valor ausente/desconhecido |
| `docs/architecture/agents.md`, `admin-agents-contract.md`, `knowledge-base.md`, `docs/prompts_llms.md` | Campo novo, tabela de exclusões, `_price_line` |

**Testes:** 2 novos no backend-core e 8 novos no backend-executors, todos a passar. Os
testes antigos do AI profile no backend-core (`test_ai_profile_agent_mode.py` e afins)
já falhavam antes: chamam `create_or_replace_ai_profile` sem `background_tasks`. Na suíte
do backend-executors ficam as mesmas 72 falhas antigas. Há ainda 1 falha de ambiente:
`test_optional_custom_field_is_captured…` tenta ligar ao backend-crm local e falha quando
ele não está a correr; passa sozinho e no seu ficheiro. Não há erros de tipos nos
ficheiros do frontend alterados: os 66 erros do `tsc` são todos noutros ficheiros e já
existiam. A pasta de trabalho passou a ter um `node_modules` ligado ao da pasta principal
(junction, ignorado pelo git).

#### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ce52fcf` | Campo no AI profile, prompt de qualificação, seletor na Camada 2, admin, testes, docs |

#### Relatório da Fase 3 — o que mudou na prática

**Antes:** quando o lead perguntava o preço durante a qualificação, o agente nunca dava
valores. Era uma regra fixa para todos os clientes, decidida em abril. No modo "conduz a
conversa" nem sequer havia instrução sobre o que dizer, e as respostas saíam vagas ("os
preços variam…"), às vezes com uma proposta de marcação.
**Agora:** na Camada 2 há uma escolha nova, "Se o lead perguntar o preço durante a
qualificação", com duas opções:
- **"Deixar para a apresentação" (predefinida):** o agente diz que os valores vêm logo a seguir e continua a qualificar.
- **"Responder com a tabela":** o agente dá o valor da tabela de preços e depois continua a qualificar.

Os clientes atuais ficam na opção predefinida, por isso nada muda para eles até alguém
mudar a escolha. Imagens e ficheiros da tabela continuam a ser enviados só na
apresentação. A escolha aparece no resumo do agente e no painel admin, quando é diferente
da predefinida.
**Para validar:** Cenário P6, abaixo.

### Fase 4 — Limpar a Camada 4

**Objetivo:** retirar as categorias Roteiro e Duplicado das listas por template;
itens existentes nelas aparecem numa secção "Para mover" (destino indicado, texto para
copiar), fora do prompt e fora do conteúdo extra.

**Correção à classificação (Plan Mode, 27/09/2026):**
- `urgency_offer` ("Condição Atual da Oferta", closer) passa de roteiro a **referência**. Os prompts do closer diziam "só mencione urgência se `urgency_offer` estiver preenchido", mas esse texto nunca chegava à IA.
- `post_purchase_onboarding`, que faltava na classificação, entra como roteiro.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | 12 categorias saem de `KNOWLEDGE_CATEGORIES_BY_TEMPLATE`; novo `KNOWLEDGE_CATEGORIES_TO_MOVE` (rótulo + destino) |
| `frontend-crm/src/components/agente/CamadaConhecimento.tsx` | Secção "Para mover" (destino, início do texto, Copiar texto, Ver, Remover); esses itens saem de "Conteúdo adicional" |
| `backend-crm/services/ai_orchestrator/orchestrator.py` | `urgency_offer` em `_REFERENCE_CATEGORIES` |
| `backend-executors/app/services/decision_engine.py` | `urgency_offer` em `_REFERENCE_CATEGORY_LABELS` e `_QUALIFICATION_WITHHELD_CATEGORIES`; a regra de urgência (5 sítios) aponta para a base de conhecimento em vez da chave interna |
| `backend-*/tests/…knowledge_reference*` | `urgency_offer` como referência, fora da qualificação por padrão, regra sem a chave interna |
| `docs/architecture/knowledge-base.md`, `docs/conhecimento-dos-agentes.md` | Classificação final; categorias retiradas com o destino |

**Testes:** 56 no backend-executors e 11 no orchestrator, todos a passar. O `tsc` mantém os
mesmos 66 erros antigos: o de `CamadaConhecimento.tsx` (`title` em `KnowledgeCategory`)
já existia, só mudou de linha.

#### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `fd888bc` | Camada 4 sem roteiros/duplicados, secção "Para mover", `urgency_offer` como referência, testes, docs |

#### Relatório da Fase 4 — o que mudou na prática

**Antes:** a Camada 4 pedia 12 secções que a IA nunca lia. Umas eram roteiros (aquecimento,
recuperação de carrinho, follow-up pós-sessão, indicação…) e outras repetiam o que já existe
noutra camada (preview da sessão, perguntas de dor, upsell…). O cliente preenchia, contava
como "crítico preenchido" e o agente não via nada. A "Condição Atual da Oferta" dos closers
também nunca chegava à IA, e a regra de urgência dependia dela.
**Agora:** a Camada 4 só pede o que o agente consulta. O que alguém já tinha escrito nessas
secções aparece em "Para mover", com o sítio certo para onde levar o texto (Fluxo de Venda,
Identidade, Oferta ou Qualificação) e um botão para copiar. Nada é apagado automaticamente.
A "Condição Atual da Oferta" passa a chegar à IA (fora da qualificação, como os preços).
**Para validar:** Cenário P5, abaixo.

---

## Checks de Validação

### Cenário P1 — "Quem são vocês?" na qualificação (Fase 1)
- [x] Conta de teste local: preencher "Perfil da Empresa" na Camada 4
- [x] Playground, lead novo em qualificação: perguntar "quem são vocês?"
- [x] Confirmar: responde com o perfil cadastrado e retoma a pergunta de qualificação
- **Validado em:** 24/09/2026 — teste automatizado via browser (playground local, lead #512). O perfil foi reescrito com factos únicos (Pinheiros, 2019, 1.200 clientes). A pergunta "onde fica o estúdio e há quanto tempo existem?" teve como resposta "localizado no bairro de Pinheiros… desde 2019… mais de 1.200 atendimentos", e o agente retomou a oferta da tabela de preços. A conta de teste não tem campos de qualificação, por isso a Mãe encaminhou para a apresentação; a fase de qualificação ficou coberta pelo P2. Observação: "quem são vocês?" genérico foi respondido na conversa ao vivo só com a identidade da Camada 1 ("Sou Daniel… da Sensi Vitae"); em 3 execuções repetidas fora do browser, 2 usaram o perfil. É aceitável porque a pergunta é coberta pelas duas fontes.

### Cenário P2 — Conteúdo extra (texto livre) (Fase 1)
- [x] Camada 4 → "Adicionar conteúdo extra" → texto livre com um facto único (ex.: "atendemos ao domicílio na zona sul, taxa R$ 30")
- [x] Playground: perguntar sobre esse facto
- [x] Confirmar: responde com o facto; no `decision_trace`, o bloco "BASE DE CONHECIMENTO DO NEGÓCIO" aparece no prompt
- **Validado em:** 24/09/2026 — "Vocês atendem em casa? Moro no Campo Belo" (fase **qualificação**) teve como resposta "atendimentos ao domicílio na zona sul de São Paulo, com uma taxa de deslocamento fixa de R$ 30" + "pelo menos 48 horas de antecedência", e o agente retomou a oferta da tabela. O `decision_trace` não transporta o texto do prompt. A presença do bloco foi confirmada ao reconstruir o prompt do lead #512 com o mesmo código (`build_context_bundle_for_playground` → `decision_engine.decide`, capturando o prompt da Filha): o bloco está presente nas 3 execuções, com o perfil e o conteúdo extra.

### Cenário P4 — Roteiros não vazam (Fase 1)
- [x] Preencher um roteiro (ex.: "Script de Recuperação de Carrinho")
- [x] Confirmar: o texto não aparece no prompt nem nas respostas
- **Validado em:** 24/09/2026 — o template `hybrid_scheduler` não oferece "Recuperação de Carrinho"; usei o "Script de Aquecimento" (`warming_script`) com a frase-marcador "férias em Fernando de Noronha". Resultados: `knowledge_reference` do lead com 2 itens (perfil + conteúdo extra, sem o roteiro); a marca não aparece em nenhum dos 3 prompts capturados nem nas respostas do playground; nenhum código do backend lê `warming_script`.

### Cenário P3 — Conhecimento consolidado em todas as fases (Fase 2)
- [x] Camada 4 → "FAQ do Serviço" com um facto único (conta de teste: "cada sessão dura 50 minutos, mais 10 de conversa inicial")
- [x] Playground, lead em qualificação: perguntar "quanto tempo dura a sessão?" → responde com os 50 minutos e continua o objetivo da fase
- [x] Playground, apresentação: perguntar o preço → responde com a tabela cadastrada
- [x] Playground, qualificação: perguntar o preço → comportamento de hoje (não dá valores; ficam para a apresentação)
- [x] Prompt reconstruído (mesmo método da Fase 1): nenhum "usar APENAS" nos blocos de conhecimento; a FAQ e a tabela aparecem uma só vez
- **Validado em:** 27/09/2026 — serviços locais reiniciados com o código da Fase 2 (`a1ad9ad`), testes no browser (leads #513 e #514).
  - **FAQ ao vivo:** "quanto tempo dura cada sessão?" → "Cada sessão dura 50 minutos, com mais 10 minutos para uma conversa inicial"; "grávida de 5 meses, posso fazer massagem?" → "a partir do segundo trimestre… massagens pré-natais adaptadas". A Mãe mandou as duas para a apresentação: a conta de teste não tem campos de qualificação e raramente cai na qualificação.
  - **Qualificação:** a fase foi validada ao enviar à IA real o prompt de qualificação do lead #514 (dados reais, código da Fase 2). "O que preciso levar?" → "não precisa trazer nada… toalhas e roupão… roupa confortável" e volta a qualificar.
  - **Preço na qualificação:** não dá valores (3 de 3 execuções), igual ao código da Fase 1. As respostas são vagas e às vezes falam em marcar ("posso agendar uma conversa"). O código da Fase 1 fez o mesmo ("Que dias você tem em mente?"): não é regressão, é o efeito da regra fixa que a Fase 3 torna configurável.
  - **Preço na apresentação ao vivo:** "Quanto custa uma sessão?" → "a partir de R$150, com desconto de 10% para pacotes de 5 sessões pagas à vista" (tabela cadastrada).
  - **Prompt reconstruído nas 6 fases:** 0 regras "usar APENAS"; a FAQ e a tabela aparecem 1 vez cada (a tabela não aparece na qualificação); tamanhos na tabela da Fase 2.

### Cenário P6 — Preço na qualificação configurável (Fase 3)
- [x] Reiniciar backend-core, backend-crm e backend-executors com o código da Fase 3 (a coluna nova é criada no arranque do backend-core); frontend a correr a partir da pasta da correção
- [x] Camada 2: o seletor "Se o lead perguntar o preço durante a qualificação" aparece em "Deixar para a apresentação"; o resumo mostra "Fica para a apresentação"
- [x] Com "Deixar para a apresentação": pergunta de preço com o prompt de qualificação do lead (mesmo método do P3) → diz que os valores vêm a seguir e continua a qualificar, sem citar valores nem propor marcação
- [x] Mudar para "Responder com a tabela", gravar e recarregar a página → a escolha mantém-se e o resumo mostra "Responde com a tabela"
- [x] Repetir a pergunta de preço → responde com o valor da tabela (conta de teste: R$150) e continua a qualificar
- **Validado em:** 27/09/2026 — teste automatizado via browser + IA real, conta de teste local (modo passivo).
  - **Arranque:** o backend-core da pasta da correção arrancou sobre a base local da pasta principal (cópia de segurança antes) e criou a coluna; a conta ficou em `after_qualification`.
  - **Camada 2 e resumo:** o seletor aparece por baixo de "Como o agente coleta informações", já em "Deixar para a apresentação", e o resumo mostra "Fica para a apresentação".
  - **"Deixar para a apresentação"** (lead #513, 3 execuções): a tabela não entra no prompt. Respostas: "Os valores são apresentados logo a seguir, conforme entendermos melhor o que você procura… Que tipo de massagem você está considerando?". Nenhuma cita valores nem propõe marcação, o que corrige as respostas vagas e as propostas de marcação vistas no P3.
  - **Mudança da opção:** passar a "Responder com a tabela" e "SALVAR CAMADA 2" grava `on_request` na base; depois de recarregar, o resumo mostra "Responde com a tabela".
  - **"Responder com a tabela"** (3 execuções): a tabela entra no prompt. Respostas: "Uma sessão de massagem custa a partir de R$150. Para pacotes de 5 sessões pagas à vista, oferecemos um desconto de 10%… Você já tem em mente um tipo específico de massagem?".
  - **Nota de método:** o primeiro ensaio usou o lead #514, que já tinha "R$150" no histórico (resposta da apresentação no P3). Esse ensaio foi descartado e repetido com o #513, sem preço no histórico.
  - **Estado final:** a conta de teste ficou em "Responder com a tabela".

### Cenário P5 — Camada 4 limpa (Fase 4)
- [ ] Serviços com o código da Fase 4 (frontend a partir da pasta da correção)
- [ ] Camada 4 (conta de teste `hybrid_scheduler`): já não lista "Script de Aquecimento", "Preview da Sessão", "Roteiro de Perguntas de Dor", "Follow-up Pós-Sessão", "Material Pré-Sessão" nem "Script de Indicação"
- [ ] O "Script de Aquecimento" já preenchido aparece em "Para mover", com o destino "Fluxo de Venda → fase Apresentação", e não em "Conteúdo adicional"
- [ ] "Copiar texto" copia o conteúdo (ou abre o texto, se o browser bloquear a área de transferência)
- [ ] O contador de secções críticas deixa de contar as secções retiradas
- [ ] Prompt reconstruído: o roteiro continua fora (como no P4)

---

## Ajustes Possíveis Pós-Implementação

- **Fontes duplicadas que são ambas lidas:** garantia (Camada 4 `guarantee_policy` +
  Camada 6 `guarantee_text`) e prova social no híbrido (Camada 4 `social_proof` +
  Camada 1 `warming_social_proof`). Candidato a investigação na discovery.
- **Conversão assistida de roteiros para blocos do Fluxo de Venda:** o sistema não sabe
  a fase nem o gatilho de cada roteiro; hoje quem decide é o utilizador ao mover.
