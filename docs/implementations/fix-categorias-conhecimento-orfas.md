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
continuam de fora, de propósito: vão para o Fluxo de Venda na Fase 3.
**Para validar:** Cenários P1, P2 e P4, abaixo.

### Fase 2 — Consolidar (remover a ambiguidade)

**Objetivo:** as categorias de Referência já lidas passam para o mesmo bloco único;
saem as instruções "usar APENAS quando…" por categoria (`decision_engine.py`,
apresentação e follow-up), mantendo as notas de mídia e as narrativas. Qualificação e
fecho passam a ter FAQs e preços. Medir o tamanho do prompt antes/depois.

### Fase 3 — Limpar a Camada 4

**Objetivo:** retirar as categorias Roteiro e Duplicado das listas por template;
itens existentes nelas aparecem numa secção "Para mover" (destino indicado, texto para
copiar), fora do prompt e fora do conteúdo extra.

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

### Cenário P3 — Preço perguntado na qualificação (Fase 2)
- [ ] (definido na Fase 2)

### Cenário P5 — Camada 4 limpa (Fase 3)
- [ ] (definido na Fase 3)

---

## Ajustes Possíveis Pós-Implementação

- **Fontes duplicadas que são ambas lidas:** garantia (Camada 4 `guarantee_policy` +
  Camada 6 `guarantee_text`) e prova social no híbrido (Camada 4 `social_proof` +
  Camada 1 `warming_social_proof`). Candidato a investigação na discovery.
- **Conversão assistida de roteiros para blocos do Fluxo de Venda:** o sistema não sabe
  a fase nem o gatilho de cada roteiro; hoje quem decide é o utilizador ao mover.
