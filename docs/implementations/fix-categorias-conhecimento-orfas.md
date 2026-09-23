# Fix: categorias de conhecimento que a IA nunca lê

**Status:** Aguardando Plan Mode
**Origem:** `docs/discovery/levantamentos/2026-09-23-busca-vetorial-gemini.txt` — triagem da discovery (bug confirmado, veio direto para implementations por decisão do utilizador)

---

## Motivação

O ecrã de conhecimento do agente (Camada 4 do AI Profile) oferece categorias que o
utilizador preenche, mas cujo texto **nunca chega ao prompt** do LLM. O cliente acha
que ensinou o agente e o agente não sabe responder, ou improvisa. É uma causa provável
do relato "às vezes pergunto uma informação e ele não responde".

Dois problemas confirmados na triagem:

1. **Categorias órfãs.** As chaves definidas em `frontend-crm/src/types/agente.ts`
   (ex.: `CAT_PRE_MEETING_FAQ`, ~linha 684) sem nenhuma referência em
   `backend-executors/app/services/decision_engine.py` nem em
   `backend-crm/services/ai_orchestrator/`: `company_profile`, `pre_meeting_faq`,
   `scheduling_policy`, `price_policy`, `competitive_differentials`,
   `professional_bio`, `urgency_offer`, `referral_script`, `fit_questions`,
   `pain_questions`, `handoff_briefing_template`, `nurture_content`,
   `post_purchase_onboarding`, `post_session_followup`, `pre_session_material`,
   `session_preview`, `upsell_content`, `warming_script`, `cart_recovery_scripts`.
   `docs/conhecimento-dos-agentes.md:37` classifica `company_profile` como
   **Crítico** ("o agente precisa responder 'quem vocês são?'"). A mídia dessas
   categorias ainda pode ser usada por blocos do Fluxo de Venda
   (`decision_engine.py:5375`); o **texto** não. (`qualification_criteria` não é
   órfã — é lida em `backend-crm/routes/qualification.py:110`.)
2. **Só o item mais recente por categoria.** `_load_knowledge_items`
   (`backend-crm/services/ai_orchestrator/orchestrator.py:503-528`) guarda só a
   primeira linha de cada categoria (ordenado por `updated_at DESC`); os outros itens
   ativos da mesma categoria são ignorados em silêncio. A única exceção é
   `service_pricing_table` (`_MULTI_ITEM_CATEGORIES`, linha 465). No banco local,
   `company_profile` já tem 2 itens ativos.

Comportamento desejado: todo o conteúdo que o utilizador pode cadastrar chega ao
agente na fase em que faz sentido, ou a categoria deixa de ser oferecida no ecrã.

---

## Área do sistema

backend-executors (montagem dos prompts por fase no `decision_engine`), backend-crm
(carregamento do conhecimento no orchestrator — paridade playground ↔ WhatsApp via
`enrich_context_bundle`), frontend-crm (lista de categorias por agente). Docs:
`docs/conhecimento-dos-agentes.md`, `docs/prompts_llms.md`.

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida (decidir, por categoria, em que fase entra ou se
sai do ecrã; ler antes `docs/architecture/prompt-engineering-principles.md`), responder
as 3 perguntas do Passo 0, e só depois de aprovado seguir para a criação de branch +
worktree (Passo 1).
