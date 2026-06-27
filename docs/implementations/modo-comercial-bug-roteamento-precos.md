# Modo Comercial não apresenta tabela de preços (bug de persistência + bug de roteamento)

**Branch:** `main`
**Status:** Todos os cenários validados (Fase 1 e Fase 2 corrigidas e confirmadas)

---

## Motivação

O utilizador perguntou se o agente híbrido agendador (no modo `agenda`/`scheduler`/
`exploratory`) consegue responder perguntas genéricas de preço/serviços fora do
fluxo de agendamento (ex.: *"Gostaria de saber a questão de massagens disponíveis
valores etc"*).

Investigação (research agent) confirmou: no modo `exploratory` (modo da conta de
teste na altura), `service_pricing_table` só é lido pela filha de **agendamento**
(para resolver duração), nunca pela filha de **apresentação** — a apresentação só
injeta a tabela de preços quando `appointment_mode == "commercial"`
(`backend-executors/app/services/decision_engine.py:2442`).

O utilizador pediu para eu activar o modo "Compromisso Comercial" via UI e testar.
Ao fazê-lo, descobri **dois bugs distintos**, em camadas diferentes:

1. **Bug de persistência (Fase 1 — corrigido e validado nesta sessão)**: a UI
   gravava `appointment_mode` no lugar errado; o valor real nunca mudava.
2. **Bug de roteamento (Fase 2 — identificado, NÃO corrigido)**: mesmo com
   `appointment_mode` correctamente persistido como `"commercial"`, o bloco de
   prompt que apresenta a tabela de preços continua a não disparar, porque a
   condição que o protege compara contra um valor que a Mãe (decision engine) não
   está a emitir na prática.

---

## Problemas Identificados

### 1. `appointment_mode` não persistia na coluna lida pelo decision engine (CORRIGIDO)

- **Onde:** `frontend-crm/src/services/api.ts`
  - `saveConfig()` (linha ~1428, antes da correcção): gravava
    `appointment_mode: config.appointment_mode` dentro do objecto `offer_pack`
    (JSON nested), nunca como campo de topo do payload `PUT /ai-profiles/me`.
  - `getConfig()` (linha ~1344-1348, antes da correcção): tentava adivinhar o
    valor a partir de `presentation_variant` em vez de ler a coluna real.
- **Por que importa:** `backend-executors/app/services/decision_engine.py:2430`
  lê `ai_profile.get("appointment_mode")` directamente como campo de topo —
  nunca olha para dentro de `offer_pack`. Confirmado por um agente de pesquisa
  dedicado: não existe, em lugar nenhum do `backend-crm` ou `backend-executors`,
  nenhum código que faça flatten/merge de `offer_pack` para o nível de topo do
  dict `ai_profile`. O mesmo padrão de bug já estava documentado para outros
  campos em `docs/ai-profile-fields.md` (`qualification_score_threshold`,
  `buying_signal_keywords`, e também `calendar_integration` — este último inofensivo
  porque nunca é lido por ninguém).
- **Sintoma observado:** ao seleccionar "Compromisso Comercial" na UI
  (Configurar Agente → Apresentação → Modo de Operação) e salvar, a UI passava a
  *mostrar* "Compromisso Comercial" (porque `presentation_variant` mudava
  correctamente para `"sales"`), mas `GET /ai-profiles/me` confirmava
  `appointment_mode: "exploratory"` — inalterado. O toggle era um no-op silencioso
  para o decision engine.

### 2. Bloco "MODO COMERCIAL" não dispara mesmo com `appointment_mode="commercial"` (CORRIGIDO — Fase 2)

- **Onde:** `backend-executors/app/services/decision_engine.py:2437-2441`
  ```python
  if (
      template_key_for_warming == "hybrid_scheduler"
      and mother_decision.route_to == "qualification"
      and not mode_contract.get("missing_fields")
  ):
      if appointment_mode == "commercial":
          # injeta prova social + TABELA DE SERVIÇOS/PREÇOS + objeções + ...
  ```
  Este bloco (linhas 2437-2514, dentro de `_build_child_prompt_apresentation`)
  só é construído quando `mother_decision.route_to == "qualification"` **literalmente**.
- **Sintoma observado (evidência bruta, capturada via DevTools Network):**
  testei (Playground, `ai_profile_id=5`, já com `appointment_mode="commercial"`
  confirmado via API) a mensagem:
  > "Oi, meu nome é Carla, quero fazer uma massagem relaxante para aliviar o
  > estresse do trabalho, faço sempre que posso. Gostaria de saber quais opções
  > de massagem vocês têm e os valores"

  Resposta da API (`POST /api/playground/chat`, lead_id=309) — campos relevantes:
  ```json
  {
    "mother_decision": {
      "route_to": "recepcao",
      "reason": "route:recepcao|effective_route:apresentation|lead interessada em opções de massagem e preços.|greeting_first_enforced"
    },
    "lead_state": { "category": "apresentation", "qualification_state": { "missing_fields": [] } },
    "decision_trace": { "agent_mode": "agenda", "presentation_variant": "sales", "mother_route": "recepcao", "effective_route": "apresentation" },
    "message_to_send": "Oi, Carla! ... Podemos explorar as opções que melhor se adequam a você. O que você gostaria de saber mais?\n\nOi, Carla! ... Vamos marcar um horário? Quais dias e horários você prefere..."
  }
  ```
  `mother_decision.route_to` é `"recepcao"`, **não** `"qualification"` — apesar de
  `missing_fields` estar vazio (qualificação completa) e `effective_route` ser
  `"apresentation"`. A condição do bloco comercial (que compara contra a string
  literal `"qualification"`) nunca fica verdadeira nesta passagem, então a tabela
  de preços nunca é injetada — o bot ignora o pedido de preço e empurra para
  agendamento.
- **Causa raiz confirmada (via leitura do código, sem alterações às cegas):**
  Confirmada a hipótese (a) do levantamento original. Sequência exacta:
  1. `compose_decision_output()` (linha ~4792) já chama
     `effective_route_override=route_for_child` — ou seja, `effective_route`/
     `decision_trace` **já estava correcto** (mostrava `"apresentation"`).
  2. `route_for_child` (linha ~4407) começa como `mother_decision.route_to`, mas
     pode ser promovido por três caminhos distintos antes do dispatch do prompt
     da filha (linha ~4671): (i) `mother_decision.route_to=="qualification"` +
     `missing_fields` vazio → promovido via Rule 3 anti-loop (linha 4471); (ii)
     `mother_decision.route_to=="recepcao"` + `compound_follow_through` ou
     `perceived_category` divergente → "saudação composta" (linhas 4411-4457);
     (iii) a Mãe já devolve `"apresentation"` directamente.
  3. O dispatch (linha 4671, `elif route_for_child == "apresentation":`) chama
     `_build_child_prompt_apresentation(context, message_text, mother_decision)` —
     **sem** receber `route_for_child`. A função só tem acesso ao
     `mother_decision.route_to` **original** (pré-promoção).
  4. Dentro dela, o gate do bloco MODO COMERCIAL (`_auto_promoted_from_qual`,
     linha ~2355) só reconhecia o caminho (i) (`route_to=="qualification"`).
     No teste com "Carla" (1ª mensagem do lead, rica: nome + interesse + pedido de
     preço), o `_enforce_greeting_first` (linha 3785) força
     `mother_decision.route_to="recepcao"` porque `outbound_count==0` (bot nunca
     respondeu) — isto é o caminho (ii). `route_for_child` é correctamente
     promovido para `"apresentation"`, mas o gate antigo nunca via isso, porque
     só olhava para o `route_to` literal, não para o resultado da promoção.
  5. `_build_mode_contract_context()` (usada para calcular `missing_fields`) não
     depende de `mother_decision.route_to` — por isso é seguro alargar o gate sem
     recalcular nada.
- **Correcção aplicada:** `_auto_promoted_from_qual` passou a aceitar
  `mother_decision.route_to in ("qualification", "recepcao")` (mantendo a
  exigência de `missing_fields` vazio). O gate do bloco MODO COMERCIAL
  (linha ~2442) foi simplificado para reutilizar `_auto_promoted_from_qual`
  directamente, eliminando a duplicação da mesma condição em dois sítios.
  Efeito colateral positivo (mesma causa raiz, sem mudança de escopo): o ramo
  `elif presentation_variant == "scheduler"` / `else` (modo exploratório) do
  mesmo bloco de aquecimento também passa a disparar nesse cenário de saudação
  composta — antes também ficava preso pelo mesmo gate, em qualquer modo.
- **Por que isto era mais profundo que o bug da Fase 1:** a Fase 1 era um problema
  de "o valor certo não chega ao sítio certo" (mecânico, 1 condição de leitura/escrita
  trocada). Este era um problema de "a condição de negócio compara contra o valor
  errado quando há mais de um caminho de promoção de rota" — confirmado por leitura
  completa do fluxo `mother_decision.route_to` → `route_for_child` →
  `effective_route_to` antes de tocar no código, em vez de mudar a string de
  comparação às cegas.

---

## Plano de Implementação

### Fase 1 — Corrigir persistência de `appointment_mode`

**Objetivo:** fazer o toggle "Modo de Operação" (Compromisso Comercial ↔
Agendamento Exploratório) escrever e ler o campo real que o decision engine
consulta.

| Arquivo | O que mudou |
|---|---|
| `frontend-crm/src/services/api.ts` | `saveConfig()`: `appointment_mode` removido de dentro de `offer_pack`; enviado como campo de topo no payload do `PUT /ai-profiles/me` (ao lado de `presentation_variant`). `getConfig()`: lê `appointment_mode` directamente da coluna de topo (`(profile as any)?.appointment_mode`), com fallback em `offer_pack` só para perfis antigos salvos antes desta correcção; removida a lógica que adivinhava o valor a partir de `presentation_variant` |
| `docs/ai-profile-fields.md` | Removida a linha da tabela de discrepâncias que descrevia o bug como comportamento intencional ("derivado de presentation_variant"); tabela da Camada 5 actualizada para "Coluna direta" com nota da correcção |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1100fb5` | `fix(ai-profile): appointment_mode nao persistia na coluna lida pelo decision engine` |

**Detalhes do commit `1100fb5`:**
- `frontend-crm/src/services/api.ts` — ver tabela acima
- `docs/ai-profile-fields.md` — discrepância documentada removida (já corrigida)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** seleccionar "Compromisso Comercial" na UI e salvar não tinha **nenhum**
efeito no comportamento real da IA — `appointment_mode` ficava sempre
`"exploratory"` no banco, porque a UI gravava o valor dentro de `offer_pack`
(nunca lido pelo decision engine) em vez da coluna de topo.

**Agora:** o valor seleccionado na UI é gravado e lido correctamente na coluna de
topo. Confirmado via API directa (`GET /ai-profiles/me`) antes e depois da
correcção — ver Cenário C1 abaixo.

**Para validar:** Cenário C1 abaixo (já validado).

---

### Fase 2 — Corrigir o gate do bloco MODO COMERCIAL (aceitar `route_to=="recepcao"`)

**Objetivo:** fazer o bloco de aquecimento/MODO COMERCIAL disparar também quando a
qualificação foi concluída na própria 1ª mensagem do lead (saudação composta), não
só quando a Mãe devolve `route_to=="qualification"` literalmente.

| Arquivo | O que mudou |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_apresentation()`: `_auto_promoted_from_qual` (linha ~2355) passou a aceitar `mother_decision.route_to in ("qualification", "recepcao")` em vez de só `"qualification"`; gate do bloco MODO COMERCIAL (linha ~2442) simplificado para reutilizar `_auto_promoted_from_qual` em vez de repetir a condição |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `dc5aa4b` | `fix(decision-engine): bloco MODO COMERCIAL nao disparava na saudacao composta da 1a mensagem` |

**Detalhes do commit `dc5aa4b`:**
- `backend-executors/app/services/decision_engine.py` — ver tabela acima

### Relatório da Fase 2 — o que mudou na prática

**Antes:** quando a 1ª mensagem do lead já vinha completa (nome, interesse e pedido
de preço, tudo numa mensagem só), o `_enforce_greeting_first` forçava a rota interna
para `"recepcao"` (regra de "sempre saudar primeiro"). A filha de apresentação ainda
respondia (a promoção para `"apresentation"` continuava a funcionar), mas o bloco que
injeta a tabela de serviços/preços no prompt nunca via essa promoção — só reconhecia
o caminho em que a Mãe devolve `"qualification"` directamente. Resultado: o bot
ignorava o pedido de preço e empurrava direto para agendamento, mesmo com "Compromisso
Comercial" activo.

**Agora:** o mesmo gate reconhece os dois caminhos que levam à apresentação com
qualificação completa — `"qualification"` (caminho já existente) e `"recepcao"`
forçado por saudação composta (caminho novo). Confirmado via API directa
(`POST /api/playground/chat`) repetindo a mensagem exacta de "Carla" que falhava
antes — ver Cenário C2 abaixo.

**Para validar:** Cenário C2 abaixo (já validado).

---

## Checks de Validação

### Cenário C1 — `appointment_mode` persiste correctamente após a correcção
- [x] Antes da correcção: seleccionar "Compromisso Comercial" na UI → salvar →
  `GET /ai-profiles/me` mostra `appointment_mode: "exploratory"` (bug confirmado)
- [x] Aplicar a correcção (commit `1100fb5`) → repetir o mesmo fluxo na UI
- [x] `GET /ai-profiles/me` mostra `appointment_mode: "commercial"`,
  `presentation_variant: "sales"` — valor real persistido
- **Validado em:** 27/06/2026 — conta de teste (`autodigital157@gmail.com`,
  AI Profile id=5). Sequência exacta: (1) antes da correção, UI mostrava
  "Compromisso Comercial" salvo mas API confirmava `appointment_mode=exploratory`
  — bug confirmado e reproduzido; (2) aplicada a correção no código; (3) reload da
  página (Vite HMR), repetido o fluxo "Modo de Operação" → "Compromisso Comercial"
  → "SALVAR ALTERAÇÕES" → "SALVAR APRESENTAÇÃO"; (4) `GET /ai-profiles/me` confirmou
  `appointment_mode: "commercial"`, `presentation_variant: "sales"` — corrigido.

### Cenário C2 — Bot apresenta a tabela de preços quando perguntado genericamente (Fase 2 — PASSOU)
- [x] Com `appointment_mode="commercial"` activo, perguntar genericamente sobre
  serviços/preços (sem pedir agendamento) → bot deve citar a tabela de preços
  cadastrada
- **Falhou em:** 27/06/2026 — múltiplas tentativas no Playground (leads #308, #309),
  incluindo uma mensagem rica com nome + interesse + pedido explícito de preço
  ("Oi, meu nome é Carla, quero fazer uma massagem relaxante... Gostaria de saber
  quais opções de massagem vocês têm e os valores"). Em todas as tentativas, o bot
  respondeu de forma genérica ("temos opções incríveis", "podemos explorar as
  opções") e pivotou para pedir data/horário de agendamento, **sem nunca citar
  nome de serviço ou valor da tabela**. Resposta bruta da API capturada na secção
  "Problemas Identificados" item 2 acima — confirma `mother_decision.route_to:
  "recepcao"` em vez de `"qualification"`, impedindo o bloco comercial de disparar.
- **Validado em:** 27/06/2026 — após aplicar a correcção (commit `dc5aa4b`) e
  reiniciar `backend-executors` (não usa `--reload`), repeti via API
  (`POST /api/playground/chat`, lead novo #310) a **mensagem exacta** de "Carla"
  que falhava antes. Resposta: `mother_decision.route_to` continua `"recepcao"`
  (comportamento correcto — saudação ainda é forçada no 1º contacto) e
  `decision_trace.effective_route` continua `"apresentation"`, mas agora
  `message_to_send` cita a tabela real: *"Oferecemos a sessão avulsa de 30min por
  R$120 e a sessão estendida de 90min por R$220."* — valores exactos do item de
  conhecimento legado (id=21) cadastrado na feature de múltiplas tabelas. O bot
  identificou correctamente que "massagem relaxante" mapeia para essa tabela (e não
  para a tabela "Ana — Hipnoterapia", também cadastrada na conta) e citou nome do
  serviço + duração + preço antes de propor agendamento — confirma o bug corrigido.

---

## Estado actual do ambiente (para retomar)

- Conta de teste (`autodigital157@gmail.com`, AI Profile id=5,
  `template_key=hybrid_scheduler`, `agent_mode=agenda`) está **actualmente** com
  `appointment_mode="commercial"` / `presentation_variant="sales"` (deixada assim
  de propósito, após o teste da Fase 1). Se for repetir testes do modo
  exploratório por algum motivo, lembrar de trocar de volta via UI.
- Servidores locais (backend-core:8001, backend-crm:8000, backend-executors:8002,
  frontend-crm:8080) estavam todos em execução no fim desta sessão.
  `backend-executors` foi reiniciado manualmente durante a Fase 2 (não usa
  `--reload`) para carregar a correcção do commit `dc5aa4b`.
- Leads de sandbox criados durante os testes: #308/#309 (Fase 2, falha original),
  #310 (Fase 2, validação pós-correcção, via API) — nenhum agendamento real foi
  confirmado em nenhum destes leads (apenas perguntas/respostas de preço).

## Ajustes Possíveis Pós-Implementação

- Considerar se a UI deveria avisar/confirmar visualmente quando uma alteração de
  "Modo de Operação" é salva (hoje não há nenhuma confirmação de sucesso visível
  além do banner genérico "Editando..." desaparecer) — fora de escopo aqui, mas
  facilitaria detectar bugs de persistência como o da Fase 1 mais rápido no futuro.
