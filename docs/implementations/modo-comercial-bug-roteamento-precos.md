# Modo Comercial não apresenta tabela de preços (bug de persistência + bug de roteamento)

**Branch:** `main`
**Status:** Em andamento — Fase 1 concluída e validada; Fase 2 identificada, NÃO investigada/corrigida ainda

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

### 2. Bloco "MODO COMERCIAL" não dispara mesmo com `appointment_mode="commercial"` (NÃO CORRIGIDO — Fase 2)

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
- **Hipóteses a investigar (não confirmadas ainda):**
  a. `"recepcao"` pode ser o rótulo que a Mãe emite quando decide a rota mas o
     guardrail de "Rule 3" (anti-loop, mencionado por um research agent anterior
     em `decision_engine.py:4471-4479`) já promoveu o `route_for_child` para
     `"apresentation"` sem alterar o `mother_decision.route_to` original — ou seja,
     talvez a condição devesse comparar `effective_route`/`route_for_child` em vez
     de `mother_decision.route_to`.
  b. Pode ser que, para este `agent_mode`/playbook, a Mãe **nunca** emite
     literalmente `"qualification"` como `route_to` — sempre usa `"recepcao"` como
     sinónimo/rótulo — e o código de `decision_engine.py:2439` ficou desalinhado
     com uma renomeação anterior (precisa de `git log -p` / `git blame` nessa
     linha e em torno de `route_to` para confirmar quando/se isso mudou).
  c. Pode haver mais de um valor possível para `route_to` nesta fase (`"recepcao"`,
     `"qualification"`, talvez outros) e a condição precisa de cobrir todos, não só
     um literal.
- **Por que isto é mais profundo que o bug da Fase 1:** a Fase 1 era um problema
  de "o valor certo não chega ao sítio certo" (mecânico, 1 condição de leitura/escrita
  trocada). Este é um problema de "a condição de negócio está a comparar contra o
  valor errado" — requer entender o full fluxo de `mother_decision.route_to` vs.
  `effective_route`/`route_for_child` em `decision_engine.py` antes de decidir a
  correcção certa (e confirmar que não há mais nenhum sítio que dependa do
  comportamento actual antes de mudar a condição).

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

### Cenário C2 — Bot apresenta a tabela de preços quando perguntado genericamente (Fase 2 — NÃO PASSOU)
- [ ] Com `appointment_mode="commercial"` activo, perguntar genericamente sobre
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
- **Pendente:** diagnosticar e corrigir o bug de roteamento (ver hipóteses na
  secção "Problemas Identificados" item 2). Requer leitura de
  `decision_engine.py` em torno de onde `mother_decision.route_to` é definido
  (provavelmente perto da função que decide `route_for_child`/Rule 3 anti-loop,
  mencionada por research anterior em `decision_engine.py:4471-4479` e
  `4599-4611`) antes de propor a correcção certa. **Não tentar corrigir às cegas
  só mudando a string de comparação** — primeiro confirmar todos os valores
  possíveis de `route_to` que a Mãe pode emitir nesta fase, e se `effective_route`
  já existe como alternativa mais correcta para esta condição.

---

## Estado actual do ambiente (para retomar)

- Conta de teste (`autodigital157@gmail.com`, AI Profile id=5,
  `template_key=hybrid_scheduler`, `agent_mode=agenda`) está **actualmente** com
  `appointment_mode="commercial"` / `presentation_variant="sales"` (deixada assim
  de propósito, após o teste da Fase 1). Se for repetir testes do modo
  exploratório por algum motivo, lembrar de trocar de volta via UI.
- Servidores locais (backend-core:8001, backend-crm:8000, backend-executors:8002,
  frontend-crm:8080) estavam todos em execução no fim desta sessão.
- Leads de sandbox criados durante os testes desta fase: #308 (mensagem simples),
  #309 ("Carla", mensagem rica) — nenhum agendamento real foi confirmado nestes
  leads (o bot só chegou a perguntar data/horário, sem o lead responder).

## Ajustes Possíveis Pós-Implementação

- Considerar se a UI deveria avisar/confirmar visualmente quando uma alteração de
  "Modo de Operação" é salva (hoje não há nenhuma confirmação de sucesso visível
  além do banner genérico "Editando..." desaparecer) — fora de escopo aqui, mas
  facilitaria detectar bugs de persistência como o da Fase 1 mais rápido no futuro.
