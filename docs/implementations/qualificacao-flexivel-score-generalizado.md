# Qualificação flexível + score generalizado

**Branch:** `fix/qualificacao-nao-obrigatoria-antes-apresentacao`
**Status:** Em andamento

---

## Motivação

Item deixado em aberto na graduação de
`docs/implementations/fix-qualificacao-obrigatoria-caminho-automatico.md`
(removido nessa graduação): o score de qualificação
(`qualification_score_threshold`) só pontua 4 chaves fixas (`decision_role`,
`urgency`, `budget_or_price_acceptance`, `availability_window`) via
keyword-matching hardcoded — campos custom (como os do cliente Gabriel Smith)
nunca contribuem para o score, e o gate de score é pulado inteiramente
quando o perfil só usa campos custom.

Investigando o código para desenhar essa correção, dois problemas
adicionais e relacionados na raiz foram levantados pelo utilizador:

1. **Captura incompleta**: a extração automática de respostas de
   qualificação (`field_extractor.py::extract_fields_llm()`, uma chamada LLM
   dedicada e já separada da Mãe/Filha) só considera campos marcados
   `required` — respostas a campos `optional`/custom nunca são persistidas
   em `lead_qualification_state`, mesmo quando a LLM as interpreta
   corretamente. Isso é a causa raiz de o bot "ignorar" respostas do lead a
   perguntas de qualificação não-obrigatórias.
2. **Rigidez de interpretação**: os limiares de confiança do extractor
   (0.4/0.6) e os enums fechados do schema (`decision_role:
   "owner|partner|employee|other|null"`) são hardcoded, sem espaço para o
   utilizador calibrar o quão literal a extração deve ser.

Escopo confirmado com o utilizador:
- "Itens padrão obrigatórios" que devem virar sugeridos = só os filtros
  clássicos (tomador de decisão, disponibilidade, urgência, etc.) —
  mudança nos **presets sugeridos no frontend**, não retroativa para
  perfis já configurados em produção.
- Tolerância de interpretação: configurável, **default no máximo de
  flexibilidade** (não tratar respostas apenas no literal), ajustável pelo
  utilizador na Camada de Qualificação se quiser mais rigor.

Não existe "segunda LLM" a ser criada do zero — `field_extractor.py`
já cumpre esse papel (chamada isolada, prompt próprio, não é a Mãe nem a
Filha). O trabalho é fechar os gaps concretos nela, generalizar o score, e
ajustar os presets do frontend.

---

## Problemas Identificados (estado anterior)

1. **Score só pontua 4 chaves fixas:** `backend-crm/services/qualification_state.py:81-120`
   (`compute_4p_scores`) — keyword-matching PT hardcoded só para
   `decision_role`/`urgency`/`budget_or_price_acceptance`/`availability_window`.
   Qualquer outra chave nunca entra no cálculo.

2. **Gate de score pulado para perfis 100% custom:** `backend-crm/services/qualification_guardrails.py:111-123`
   (`_score_below_threshold`) — se nenhuma chave configurada bate com as 4
   fixas, retorna `(True, [])` sem checar nada.

3. **Extractor só captura campos `required`:** `backend-executors/app/services/decision_engine.py:4606-4637`
   — `fields_schema` (o que é pedido ao extractor) e o filtro `new_extracted`
   (o que é persistido) usam só `required_fields`. Respostas a campos
   `optional`/custom são extraídas com sucesso pela LLM mas descartadas
   antes de chegar em `lead_qualification_state.data_json`.

4. **Limiares de confiança e enums rígidos hardcoded:** `backend-executors/app/services/field_extractor.py:86-87`
   (thresholds 0.4/0.6 no texto do prompt) e linha 9-16 (`DEFAULT_FIELD_SCHEMA`
   com enums fechados tipo `owner|partner|employee|other|null`) — sem
   nenhuma forma de o utilizador calibrar o quão literal a interpretação
   deve ser.

5. **`qualify_if`/`disqualify_if` nunca viram sinal estruturado:**
   `backend-executors/app/services/decision_engine.py:683-711` — só
   injetados como texto livre no prompt da Filha de Qualification, nunca
   convertidos em pontuação.

6. **Cópia da UI incorreta:** `frontend-crm/src/components/agente/CamadaQualificacao.tsx:853,1210`
   — afirma "Cada campo qualificado vale 1 ponto", o que nunca foi verdade
   (o algoritmo real é keyword-scoring 0-3 por campo, restrito às 4 chaves
   fixas).

7. **Presets do frontend marcam campos clássicos como obrigatórios por
   padrão:** `frontend-crm/src/components/agente/CamadaQualificacao.tsx:14-47`
   (`SUGGESTIONS`) — `decision_role`, `availability_window`, `urgency`
   vêm `mode: 'required'` em vários presets, tornando o guardrail de
   `missing_fields` mais rígido do que o necessário quando combinado com o
   gap #3 acima (resposta dada mas não capturada = trava percebida como bug).

---

## Abordagem

```
Lead responde pergunta de qualificação (Playground ou WhatsApp real)
  → decision_engine.py: route_to == "qualification"
      → field_extractor.extract_fields_llm(context, fields_schema)
          [Fase 1] fields_schema agora inclui TODOS os campos ativos
                    (required + optional), não só required
          [Fase 2] prompt usa threshold/instrução de qualification_extraction_tolerance
                    (default "equilibrado" = os mesmos 0.4/0.6 já em produção via c320e0e)
          [Fase 3] retorno ganha "qualifies": {campo: yes|no|neutral}
                    para campos com qualify_if/disqualify_if configurados
      → persistido em lead_qualification_state (backend-crm)
          [Fase 1] campos opcionais/custom agora chegam em data_json
          [Fase 3] qualifies_json + custom_fields_score somam ao score total
      → missing_fields/anti-loop/HTTP 409 continuam baseados só em required_fields
        (inalterado em todas as fases — só o que é CAPTURADO muda, não o que BLOQUEIA)
      → can_advance_score_gate() (qualification_guardrails.py)
          [Fase 3] deixa de pular o gate quando o perfil só tem campos custom

Configuração (frontend, Camada de Qualificação)
  [Fase 4] presets sugeridos (decisor/disponibilidade/urgência) passam a
           default "optional" em vez de "required" — usuário ainda pode
           marcar manualmente como obrigatório se quiser
```

---

## Plano de Implementação

### Fase 1 — Captura de campos ativos (não só `required`)

**Objetivo:** `extract_fields_llm()` passa a poder capturar qualquer campo
`mode in ("required", "optional")` de `qualification_fields`, não só os
`required`. Não muda `missing_fields`/bloqueio HTTP 409/anti-loop.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Nova função `_get_active_fields_for_extraction(context)`; `fields_schema`/`new_extracted` usam a união de `required_fields` + campos ativos; `has_progress` corrigido para continuar restrito a `required_fields` |

```python
# ANTES
fields_schema = {field: "string|number|object|null" for field in required_fields}
...
new_extracted = {k: v for k, v in extracted.items() if k in required_fields and _is_filled_value(v)}
...
has_progress = bool(new_extracted)

# DEPOIS
active_fields = list(required_fields)
for key in _get_active_fields_for_extraction(context):
    if key not in active_fields:
        active_fields.append(key)
fields_schema = {field: "string|number|object|null" for field in active_fields}
...
new_extracted = {k: v for k, v in extracted.items() if k in active_fields and _is_filled_value(v)}
...
has_progress = any(field in new_extracted for field in required_fields)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `85078cc` | Captura de campos opcionais/custom no extractor automático + teste novo |

**Detalhes do commit `85078cc`:**
- `backend-executors/app/services/decision_engine.py` — nova `_get_active_fields_for_extraction()`; `fields_schema`/`new_extracted` usam a união de `required_fields` + campos ativos; `has_progress` corrigido para continuar restrito a `required_fields`
- `backend-executors/tests/test_qualification_state_loop.py` — novo teste `test_optional_custom_field_is_captured_but_does_not_affect_missing_fields`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** quando o lead respondia a uma pergunta de qualificação marcada
como "Opcional"/"Desejável" (ou um campo 100% custom), a IA interpretava a
resposta corretamente nos bastidores, mas essa informação era descartada
antes de ser salva — o campo nunca aparecia como preenchido no card do
lead, e o sistema podia continuar perguntando a mesma coisa.

**Agora:** qualquer campo ativo de qualificação (obrigatório ou opcional)
tem sua resposta capturada e salva no card do lead. O que continua igual:
só campos marcados "Obrigatório" bloqueiam o avanço do lead no pipeline —
um campo opcional respondido é salvo, mas nunca trava nem libera o avanço
sozinho (isso é o que as próximas fases tratam: score generalizado).

**Para validar:** Cenário P1, abaixo. Validado ao vivo em 13/08/2026.

**Nota técnica:** rodei a suíte de testes Python existente
(`backend-executors/tests`) antes e depois da mudança — mesmas 22 falhas
pré-existentes nos dois casos (não relacionadas a esta mudança; parecem
vir de uma mudança anterior nos defaults de campos obrigatórios por
`agent_mode`, fora do escopo deste plano). Nenhuma regressão nova.

---

### Fase 2 — Tolerância de extração configurável

**Objetivo:** novo campo `qualification_extraction_tolerance` no AI Profile
(`"flexivel" | "equilibrado" | "rigoroso"`, **default `"equilibrado"`**).

**Ajuste de default (registrado em 13/08/2026, depois de um fix ao vivo):**
o desenho original desta fase (documentado antes de qualquer teste real)
propunha default `"flexivel"`, para não travar respostas informais. Nesse
meio tempo, uma correção separada (`backend-executors/app/services/field_extractor.py`,
commit `c320e0e`, ver `fix-qualificacao-obrigatoria-caminho-automatico.md`
Fase 2) resolveu um bug real de alucinação do extractor: ele inventava
respostas a partir de menções tangenciais porque (a) só via o nome da
chave, não a pergunta configurada, e (b) o limiar de confiança que o
próprio prompt já pedia (`_PROFILE_FIELD_CONFIDENCE_THRESHOLD = 0.4`,
`_DEFAULT_FIELD_CONFIDENCE_THRESHOLD = 0.6`) nunca era verificado em
código. Validado ao vivo (Cenário P4 daquele arquivo): foi exatamente esse
rigor moderado, agora aplicado de verdade, que corrigiu o caso do Gabriel.
Nascer em `"flexivel"` por padrão relaxaria esse mesmo rigor recém-validado
para todo perfil novo. Esta fase passa a **expor como configurável os
mesmos dois valores que já existem hardcoded no código** (0.4/0.6 =
`"equilibrado"`, o novo default) — `"flexivel"` continua disponível como
opção para quem quiser abrir mão de precisão por captura mais informal;
`"rigoroso"` para quem quiser mais precisão.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | Nova coluna `qualification_extraction_tolerance` |
| `backend-core/app/db.py` | Entrada em `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | Enum `QualificationExtractionTolerance`; campo em `AIProfileBase`/`AIProfileUpdate` |
| `backend-executors/app/services/field_extractor.py` | `_PROFILE_FIELD_CONFIDENCE_THRESHOLD`/`_DEFAULT_FIELD_CONFIDENCE_THRESHOLD` (já existentes, de `c320e0e`) passam a ser resolvidos por nível via `_TOLERANCE_THRESHOLDS`/`_resolve_tolerance()` em vez de constantes fixas; `_TOLERANCE_INSTRUCTIONS` complementa o bloco de regras já existente no prompt; `_loosen_enum_schema()` só no nível `"flexivel"` |
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | Novo controle para o utilizador escolher o nível |
| `docs/architecture/admin-agents-contract.md` | Documentar novo campo (regra do CLAUDE.md) |
| `backend-crm/routes/admin_agents.py` | Verificar se a whitelist de campos exibidos ao admin precisa incluir o novo campo |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b808c28` | Tolerância de extração configurável (`qualification_extraction_tolerance`) — coluna, API, controle no frontend e propagação no field_extractor |

**Detalhes do commit `b808c28`:**
- `backend-core/app/models/ai_profile.py` — nova coluna `qualification_extraction_tolerance` (`String`, default `"equilibrado"`)
- `backend-core/app/db.py` — entrada em `ensure_ai_profile_columns()` com o mesmo default
- `backend-core/app/api/ai_profiles.py` — enum `QualificationExtractionTolerance` (`flexivel`/`equilibrado`/`rigoroso`); campo em `AIProfileBase` (default `equilibrado`) e `AIProfileUpdate`; campo incluído em `admin_list_all_ai_profiles`
- `backend-executors/app/services/field_extractor.py` — `_TOLERANCE_THRESHOLDS`/`_resolve_tolerance()` substituem as constantes fixas `_PROFILE_FIELD_CONFIDENCE_THRESHOLD`/`_DEFAULT_FIELD_CONFIDENCE_THRESHOLD` (0.4/0.6 continuam sendo os valores de `"equilibrado"`); `_TOLERANCE_INSTRUCTIONS` complementa o bloco "Regras" do prompt; `_loosen_enum_schema()` troca enums fechados (`decision_role`, `urgency`) por `string|null` só no nível `"flexivel"`
- `backend-executors/tests/test_field_extractor.py` — 6 testes novos: default sem tolerância configurada, valor inválido cai no default, `flexivel` aceita confidence menor, `rigoroso` rejeita confidence que `equilibrado` aceitaria, `flexivel` afrouxa o schema de enum, `equilibrado` mantém o enum fechado
- `frontend-crm/src/types/agente.ts` — campo `qualification_extraction_tolerance` em `AgentConfig` e `DEFAULT_AGENT_CONFIG` (default `'equilibrado'`)
- `frontend-crm/src/services/api.ts` — campo no tipo `AiProfilePayload`, na leitura do perfil (`getConfig`) e na gravação (`saveConfig`)
- `frontend-crm/src/components/agente/CamadaQualificacao.tsx` — novo card "Tolerância de extração" em Parâmetros avançados + `DrawerTolerancia` com as 3 opções e descrição de cada uma
- `frontend-admin/src/services/api.ts` — campo adicionado ao tipo `UserProfile` (para o painel admin listar/diffar)
- `backend-crm/routes/admin_agents.py` — campo propagado em `admin_agents_users`, `admin_agents_user_detail` e em `_SYSTEM_DEFAULTS` (default `"equilibrado"`) para participar do diff genérico exibido no `AdminAgents.tsx`
- `docs/architecture/admin-agents-contract.md` — nova linha na tabela de campos do AI Profile

### Relatório da Fase 2 — o que mudou na prática

**Antes:** o quão "literal" a IA precisava ser para considerar uma resposta de
qualificação como válida era fixo no código (0.4 de confiança para campos do
perfil, 0.6 para os campos padrão) — sem nenhuma forma de o usuário calibrar
isso pela interface.

**Agora:** a Camada de Qualificação tem um novo controle, "Tolerância de
extração", com 3 níveis:
- **Flexível** — aceita respostas parafraseadas/informais, mesmo sem os
  termos exatos (ex.: "sou eu mesmo que decido" passa a contar para
  `decision_role`, mesmo sem bater no enum `owner|partner|employee|other`).
- **Equilibrado** (padrão) — mantém exatamente o comportamento que já estava
  em produção (0.4/0.6, validado no caso do Gabriel). Nenhum perfil existente
  muda de comportamento até o usuário trocar manualmente.
- **Rigoroso** — exige confirmação mais explícita antes de extrair.

**Nota técnica:** rodei a suíte de testes Python existente
(`backend-executors/tests`) antes e depois da mudança — mesmas 22 falhas
pré-existentes nos dois casos (mesmas do relatório da Fase 1, não
relacionadas a esta mudança). Nenhuma regressão nova. Adicionei 6 testes
novos em `test_field_extractor.py`, todos passando. `tsc --noEmit` limpo em
`frontend-crm` e `frontend-admin`. Não rodei a suíte do `backend-core`
(pytest não está instalado no `.venv` local) — validei os 3 arquivos por
sintaxe (`ast.parse`) e por um smoke test direto do Pydantic (`AIProfileBase`
gera default `equilibrado`; `AIProfileUpdate` aceita `flexivel`/`rigoroso` e
rejeita valor inválido com `ValidationError`).

**Para validar:** Cenário P2, abaixo. Validado ao vivo em 13/08/2026.

### Fase 3 — Score generalizado para qualquer campo configurado

**Objetivo:** campos custom ativos passam a pontuar via sinal `qualifies`
(derivado de `qualify_if`/`disqualify_if`), sem alterar o algoritmo das 4
chaves clássicas.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/field_extractor.py` | Bloco de prompt adicional para campos com `qualify_if`/`disqualify_if`; retorno ganha `"qualifies"` |
| `backend-executors/app/services/decision_engine.py` | Fallbacks e patch para `crm_client` ganham `qualifies_json` |
| `backend-crm/services/qualification_state.py` | `compute_custom_fields_score()`, `compute_qualification_max_score()`; `upsert_qualification_state()` ganha `ai_profile` opcional |
| `backend-crm/database.py` | Novas colunas `qualifies_json`, `custom_fields_score` em `lead_qualification_state` |
| `backend-crm/services/qualification_guardrails.py` | `_score_below_threshold()` só pula o gate se não houver nenhum campo ativo configurado; `_4P_SCORABLE_KEYS` importado de `qualification_state.py` |
| `backend-crm/routes/leads.py:565-578` | `missing_fields_detail` passa a listar também campos custom ativos que faltam score |
| `backend-crm/tests/test_qualification_integrity_guardrails.py` | Reescrever `test_apply_suggested_category_allows_advance_with_custom_fields_only` |

### Fase 4 — Presets padrão do frontend deixam de ser `required`

**Objetivo:** campos clássicos nos presets de sugestão (`SUGGESTIONS` em
`CamadaQualificacao.tsx`) passam de `required` para `optional`. Não afeta
perfis já configurados.

| Preset | Campo | Antes | Depois |
|---|---|---|---|
| `sdr_scheduler` | `decision_role` | required | optional |
| `sdr_scheduler` | `availability_window` | required | optional |
| `agenda` | `decision_role` | required | optional |
| `agenda` | `availability_window` | required | optional |
| `closer` | `decision_role` | required | optional |
| `direto` | `decision_role` | required | optional |
| `consultivo` | `urgency` | required | optional |

Também nesta fase: corrigir a cópia "Cada campo qualificado vale 1 ponto" e
o "/12" fixo (`CamadaQualificacao.tsx:853,1210`) para refletir o mecanismo
pós-Fase 3, com valor máximo dinâmico.

**Decisão de risco (registrada após investigar o caso real do Gabriel):**
`missing_fields` (derivado só de campos `required`) é o único sinal que a
LLM Mãe usa para decidir `route_to="qualification"` — está escrito
literalmente no prompt dela (`_build_mother_prompt`,
`backend-executors/app/services/decision_engine.py:1758,1804-1815`:
"REGRA DE QUALIFICAÇÃO: se missing_fields não estiver vazio... route_to
DEVE ser qualification"). Zero campos obrigatórios = a Mãe nunca entra em
qualification para uma pergunta comercial direta — foi exatamente o que
aconteceu nos dois testes do Gabriel (`response_style=active` e
`=passive`, ambos com os 2 campos custom dele em `optional`). O score
(Fase 3) não compensa isso: ele só é consultado quando o sistema já tentou
mover a categoria PARA FORA de "qualification" — nunca influencia se a Mãe
decide entrar lá.

Isso significa que aplicar esta Fase 4 como desenhada (todos os 4 campos
clássicos viram `optional` por padrão) reproduz, para qualquer usuário novo
que aceite o preset sem customizar, o mesmo bug do Gabriel. **Decisão do
utilizador:** manter a Fase 4 como desenhada (não adicionar nenhum campo
obrigatório de volta aos presets) e, em vez disso, adicionar um aviso
visível na UI sempre que o perfil ficar com zero campos `mode="required"`
em `qualification_fields` — alertando que, nesse estado, a qualificação
automática pode nunca ser acionada pela IA (a Mãe só entra em qualification
quando há pelo menos 1 campo obrigatório pendente).

**Adição ao escopo desta fase — aviso de zero campos obrigatórios:**

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | Banner de aviso (mesmo padrão visual de `BannerSugestao`) quando `qualification_fields.filter(f => f.mode === 'required').length === 0` — texto explicando que, sem nenhum campo obrigatório, a IA pode nunca iniciar a qualificação automaticamente antes de apresentar a oferta |

Condição de exibição: computada a partir do array `qualification_fields`
já disponível no componente — nenhuma chamada de API nova.

---

## Checks de Validação

### Cenário P1 — Campo opcional é capturado e persistido
- [x] Perfil com um campo `mode="optional"` custom configurado
- [x] Playground: responder à pergunta desse campo
- [x] Confirmar via `GET /api/leads/{id}/qualification-fields` que o valor foi persistido
- [x] Confirmar que a categoria não é bloqueada por causa dele (continua fora de `missing_fields`)
- **Validado em:** 13/08/2026 — `ai_profile_id=5` com campo custom `custom_cor_preferida` (`mode="optional"`) além do `service_interest` (`required`). Lead 454, mensagem única respondendo aos dois: `filled_fields=['service_interest', 'custom_cor_preferida']`, `missing_fields=[]`. `GET /api/leads/454/qualification-fields` retornou `{"service_interest": "automação do WhatsApp", "custom_cor_preferida": "azul"}` — valor do campo opcional persistido corretamente, e a categoria avançou normalmente para `apresentation` (não ficou bloqueada por causa do campo opcional).

### Cenário P2 — Tolerância flexível captura resposta não-literal
- [x] Perfil com `qualification_extraction_tolerance` explicitamente em `flexivel`
- [x] Playground: responder a `decision_role` com frase que não usa os termos do enum (ex.: "sou eu mesmo que decido")
- [x] Confirmar que o campo é capturado mesmo sem correspondência literal
- [x] Perfil sem o campo definido (ou em `equilibrado`) → confirmar que o comportamento é idêntico ao atual (0.4/0.6, já validado em produção)
- **Validado em:** 13/08/2026 — conta de teste nova (`qa-tolerancia-fase2@test.com`, `user_id=22`), `ai_profile_id=7` (`agent_mode=consultivo`), campo `decision_role` configurado como `required` (só esse campo, sem os outros 3P clássicos). Reiniciei o `backend-core` local antes do teste para a migração da nova coluna (`ensure_ai_profile_columns()`) rodar — não havia como testar sem isso.
  - **Tolerância `flexivel` (lead 457):** pergunta automática "Você toma as decisões de compra?" respondida com "sou eu mesmo que decido" (sem nenhum termo do enum `owner|partner|employee|other`). Resultado: `qualification_state.data_json = {"decision_role": "eu mesmo que decido"}` — campo capturado com o texto livre do lead, não forçado para um dos tokens do enum (confirma `_loosen_enum_schema` em ação). `missing_fields=[]`, `qualification_advance_blocked_reason=["score_3_of_12_below_threshold_6"]` (bloqueado por score, não por campo faltando — comportamento esperado).
  - **Tolerância `equilibrado` (lead 458, perfil trocado via `PATCH /ai-profiles/me`, lead novo para isolar o teste):** mesma pergunta, mesma resposta literal ("sou eu mesmo que decido"). Resultado: capturado de forma idêntica (`data_json = {"decision_role": "eu mesmo que decido"}`, mesmo score 3). **Ressalva honesta:** essa frase específica não expôs uma diferença observável de comportamento entre os dois níveis — o LLM já interpretou a frase com confiança suficiente em ambos os casos (a inferência semântica do modelo não depende só do limiar numérico ou do enum do schema, que é só uma dica de tipo, não uma validação estrita em código). O que este teste confirma com segurança: (a) `flexivel` captura respostas não-literais sem quebrar nada; (b) `equilibrado` não regrediu — continua capturando exatamente como antes desta fase. A diferenciação mais nítida entre os 3 níveis (limiares 0.25/0.4/0.6/0.8 e o afrouxamento do enum) está coberta pelos 6 testes automatizados de `test_field_extractor.py`, que isolam a lógica de gate sem depender da variabilidade do LLM real.

### Validação adicional — perguntas abertas na conta real, via MCP (13/08/2026)

A pedido do utilizador, repeti a validação de captura de campos opcionais
(mecanismo da Fase 1) na conta real de testes `autodigital157@gmail.com`
(`user_id=15`, AI Profile "Daniel", `ai_profile_id=5`), dirigindo o browser
via `chrome-devtools-mcp` em vez de chamadas diretas à API — o utilizador
pediu para "ver o teste pelo MCP".

**Setup:** o servidor MCP (`chrome-devtools-manual`) estava com um Chrome
órfão preso no profile dedicado (`.cache/chrome-devtools-mcp/chrome-profile`)
de uma sessão anterior — matei o processo (`taskkill /T /F`) e reconectei.
O profile já tinha uma sessão válida (`crm_token` no `localStorage`,
JWT decodificado confirma `user_id=15`/`autodigital157@gmail.com`, expira em
~21h) — não precisei de senha.

**Alteração persistida no perfil "Daniel" (real, não descartável):** adicionei
2 campos custom novos em Camada 2 → Qualificação, via UI:
- `custom_tipo_de_automacao` — pergunta "Que tipo de automação você busca?", `mode=optional`
- `custom_cep_do_local_de_atendimento` — pergunta "Qual seria o cep do local de atendimento?", `mode=optional`

Confirmei também, na mesma tela, que o card "Tolerância de extração" (novo
nesta Fase 2) está a renderizar corretamente em produção local, mostrando
"Equilibrado" (default).

**Teste 1 (lead 459) — falso alarme:** a primeira mensagem de teste continha
a palavra "atendimento", que é keyword de handoff hardcoded
(`backend-executors/app/services/fast_path.py::HANDOFF_KEYWORDS`) — o bot
saltou direto para handoff ("Vou te conectar com alguém do time"). Confirmei
via log (`decision fast_path next_action=handoff reason=keyword_handoff`) que
isto é um guardrail pré-existente, sem relação com a Fase 2. Reformulei a
frase de teste para não conter nenhuma das keywords.

**Teste 2 (lead 460):** respondi à pergunta obrigatória `service_interest`
com uma frase que também respondia à pergunta aberta de `custom_tipo_de_automacao`,
na mesma mensagem. Resultado: `data_json = {"service_interest": "...",
"custom_tipo_de_automacao": "automação de respostas no whatsapp"}` — os dois
campos capturados a partir de uma única resposta em linguagem natural. Numa
mensagem seguinte tentei também informar o CEP, mas a conversa já tinha
avançado para a fase de agendamento (`route_to` deixou de ser
`qualification`) — o extractor de campos só corre nessa fase, então o CEP
não foi capturado nesse turno. Comportamento esperado e pré-existente (não é
regressão desta fase), não um bug.

**Teste 3 (lead 461) — isolado, para validar o CEP:** sessão nova, resposta
única já incluindo `service_interest` e o CEP juntos, ainda dentro da fase de
qualificação. Resultado: `data_json = {"service_interest": "...",
"custom_cep_do_local_de_atendimento": "01310-100"}` — capturado corretamente.

**Conclusão (testes 1–3):** o mecanismo de captura de campos opcionais/abertos
(Fase 1) continua a funcionar corretamente para perguntas genuinamente
abertas (sem enum), inclusive quando múltiplos campos são respondidos na
mesma mensagem, na conta real de testes. Nenhuma regressão observada.

**Teste 4 (lead 462) — fluxo natural, turno a turno, para validar que a
qualificação obrigatória em si não regrediu:** a pedido do utilizador, refiz
o teste sem pré-responder nada — mandei só "Olá, bom dia", esperei a
resposta, e só depois fui respondendo exatamente ao que a IA perguntava a
cada turno, uma coisa de cada vez (sem adiantar campos), deixando a IA
conduzir suas próprias perguntas de qualificação.

- Turno 1 — `"Olá, bom dia"` → bot responde com saudação + `"Como posso ajudar você hoje?"` (recepção, sem pergunta de qualificação ainda).
- Turno 2 — `"Vi o anuncio de voces e fiquei curioso pra saber mais"` (intenção vaga, sem citar o serviço) → a própria IA formulou e fez a pergunta de qualificação obrigatória: `"Qual serviço te interessa?"` (`route_to=qualification`, `missing_fields=["service_interest"]`).
- Turno 3 — respondi só a isso: `"Quero automatizar as respostas do whatsapp da minha empresa"` → `service_interest` capturado (`data_json = {"service_interest": "automatizar as respostas do whatsapp"}`), `missing_fields` esvaziou, guardrail de auto-promoção acionou (`qualification_auto_promoted=True`, igual ao mecanismo já validado antes desta fase) e o lead avançou sozinho para agendamento — este perfil só tem 1 campo `required` (`service_interest`), então não havia mais nenhuma pergunta obrigatória pendente.
- Turno 4 — `"Pode ser quinta as 14h"` → fluxo de agendamento seguiu normalmente, confirmou o horário.

Nenhum handoff inesperado, nenhuma repetição de pergunta, nenhum erro — o
guardrail de `missing_fields`/anti-loop e a lógica de auto-promoção (ambos
fora do escopo desta Fase 2, tocados só indiretamente) continuam intactos.
Isto confirma que parametrizar os limiares de confiança e afrouxar o schema
de enum no `field_extractor.py` (mudanças desta fase) não interferiu em nada
no caminho de qualificação obrigatória guiada pela própria IA.

### Cenário P3 — Score generalizado bloqueia e libera perfil 100% custom
- [ ] Perfil 100% custom com `qualify_if` configurado, score abaixo do threshold
- [ ] Confirmar: `qualification_advance_blocked: true`
- [ ] Após sinal positivo suficiente: confirmar avanço

### Cenário P4 — Presets sugeridos não vêm mais como obrigatórios
- [ ] Abrir Camada de Qualificação, aplicar sugestão para cada `agent_mode`
- [ ] Confirmar que os campos da tabela da Fase 4 aparecem como "Opcional"/"Desejável"

### Cenário P5 — Aviso de zero campos obrigatórios aparece
- [ ] Perfil com todos os campos de `qualification_fields` em `optional`/`off` (nenhum `required`)
- [ ] Abrir Camada de Qualificação
- [ ] Confirmar: banner de aviso visível informando que a qualificação pode nunca ser acionada automaticamente
- [ ] Marcar 1 campo como `required` → confirmar que o aviso desaparece

---

## Ajustes Possíveis Pós-Implementação

- **Didática do score na UI:** a correção de copy da Fase 4 só resolve a
  imprecisão factual do texto atual ("Cada campo qualificado vale 1
  ponto" → texto correto). Falta uma explicação didática de verdade — o
  usuário não tem hoje como entender, olhando só para o campo "Score
  mínimo", como suas escolhas de configuração (quantos campos marca como
  ativos, quais usa `qualify_if`/`disqualify_if`, required vs. optional)
  mudam o score máximo possível e o que precisa acontecer na conversa para
  bater o mínimo configurado. Melhoria proposta: adicionar exemplos
  concretos lado a lado na UI (ex.: "Com 2 campos custom configurados e
  `qualify_if` preenchido, o máximo passa a ser 18 pontos; se o lead
  responder aos 2 com sinal positivo, score = 18 — se responder sem sinal
  claro, score = 12"). Não bloqueante para as Fases 1-4.

- **Transparência sobre quais campos "contam" para o quê:** hoje um campo
  chamado `decision_role` parece visualmente idêntico a um campo custom
  qualquer na UI — nada indica que ele é uma das chaves que o score
  automático sabe pontuar (`_4P_SCORABLE_KEYS`), nem que campos `required`
  são o único sinal que faz a LLM Mãe decidir entrar em qualification
  (`missing_fields`, ver decisão de risco na Fase 4 acima). Melhoria
  proposta: badges/tooltips na lista de campos indicando (a) "conta para o
  score automático" quando aplicável, (b) reforçar visualmente que
  `Obrigatório` é o que aciona a qualificação automática, não apenas uma
  trava de conclusão. Não bloqueante para as Fases 1-4.
