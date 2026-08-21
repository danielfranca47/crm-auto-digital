# Arquitetura Multi-Provedor de LLM (OpenAI + OpenRouter)

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Todo o texto gerado por IA (decisão de rota "Mãe", resposta "Filha", extração de campos
de qualificação, mensagens de conflito/lembrete/título de reunião) passa hoje
exclusivamente pela OpenAI (`backend-executors/app/services/llm_service.py`, Responses
API, modelo `gpt-4o-mini` em produção). Não existe fallback: uma oscilação ou outage da
OpenAI derruba a geração de mensagens para todos os usuários.

O utilizador quer manter a OpenAI como provedor padrão (sem mudança de comportamento
para quem não mexer em nada), mas dar a cada usuário a opção de escolher, no próprio AI
Profile, um provedor alternativo — OpenRouter — reduzindo a dependência de uma única
infraestrutura.

**Decisões tomadas em Plan Mode:**
- Chave OpenRouter é única, do sistema (env var em `backend-executors`), não BYOK por usuário.
- O modelo OpenRouter é uma lista curada (dropdown fechado), não texto livre.
- Modelos pesquisados e escolhidos (família Llama):
  - Padrão: `meta-llama/llama-3.3-70b-instruct` — melhor equilíbrio entre confiabilidade
    de JSON estruturado, qualidade em PT-BR, custo e contexto (131k), servido por ~12
    provedores diferentes no próprio OpenRouter (redundância adicional).
  - Alternativa "maior qualidade": `nousresearch/hermes-3-llama-3.1-405b` (variante paga,
    não `:free`, que tem rate limit agressivo e não serve como fallback de produção).
  - Rejeitado: `meta-llama/llama-3.1-8b-instruct` — taxa de falha maior em manter JSON
    estrito sob as validações Pydantic deste sistema (`MotherDecision`/`ChildResult`).

---

## Problemas Identificados (estado anterior)

1. **Provedor único sem fallback:** `llm_service.py` fala só com a OpenAI — qualquer
   instabilidade dela impacta 100% da geração de mensagens.
2. **Sem opção de escolha por usuário:** `ai_profiles` (backend-core) não tem nenhum
   campo relacionado a provedor/modelo de LLM.

---

## Abordagem

```
AI Profile (backend-core) ganha 2 campos novos:
  llm_provider         enum "openai" (default) | "openrouter"
  llm_provider_model   enum null | "meta-llama/llama-3.3-70b-instruct" | "nousresearch/hermes-3-llama-3.1-405b"

ai_profile já flui inteiro e sem filtro até backend-executors (confirmado — nenhuma
mudança em enrich_context_bundle() é necessária, ver docs/architecture/playground-parity.md).

decision_engine.py / field_extractor.py / meeting_scheduler.py já têm `ai_profile`
disponível em cada um dos 7 pontos de chamada ao llm_service — só precisam repassá-lo.

llm_service.py ganha resolução de provedor por chamada:
  ai_profile.llm_provider == "openrouter" e OPENROUTER_API_KEY configurada
    → payload formato Chat Completions (messages/response_format), parse choices[0].message.content
  caso contrário (openai, ou openrouter sem chave configurada no servidor)
    → payload formato Responses API atual (input/text.format), parse output_text (comportamento inalterado)
```

---

## Plano de Implementação

### Fase 1 — backend-core: schema do AI Profile

**Objetivo:** adicionar `llm_provider`/`llm_provider_model` ao AI Profile, sem nenhum efeito em backend-executors ainda.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | 2 colunas novas |
| `backend-core/app/db.py` (`ensure_ai_profile_columns()`) | 2 entradas no dict de migração idempotente |
| `backend-core/app/api/ai_profiles.py` | Enums `LlmProvider`/`LlmProviderModel`; campos em `AIProfileBase`/`AIProfileUpdate`; subset admin |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b4350c1` | schema completo: coluna + migração idempotente + enums/schemas Pydantic + subset admin |

**Detalhes do commit `b4350c1`:**
- `backend-core/app/models/ai_profile.py` — colunas `llm_provider` (default `"openai"`) e `llm_provider_model`
- `backend-core/app/db.py` — 2 entradas em `ensure_ai_profile_columns()` para migração idempotente (sqlite + postgres)
- `backend-core/app/api/ai_profiles.py` — enums `LlmProvider` (`openai`/`openrouter`) e `LlmProviderModel` (as 2 opções curadas); campos em `AIProfileBase`/`AIProfileUpdate` (`AIProfileOut` herda automaticamente); inclusão no dict do endpoint `GET /ai-profiles/admin/all`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o AI Profile não tinha nenhum campo relacionado a provedor de IA — todo mundo usava a OpenAI sem opção de escolha.
**Agora:** o AI Profile de cada usuário tem 2 campos novos (`llm_provider`, `llm_provider_model`), ainda sem efeito nenhum na geração de mensagens — é só a "gaveta" onde a escolha vai ficar guardada. Todo perfil existente já nasce com `llm_provider="openai"` automaticamente (backfill via `server_default`), então nada muda para ninguém ainda. Tentar salvar um modelo OpenRouter fora da lista curada (ex.: `"gpt-4o"`) já é rejeitado pela API com erro 422 — validado com um teste direto no schema Pydantic.
**Para validar:** Cenário P... nenhum ainda é visível na UI/Playground — essa fase é só schema de banco de dados. O primeiro cenário testável de ponta a ponta (P1) só existe a partir da Fase 3, quando `llm_service.py` já souber ler esse campo.

### Fase 2 — backend-executors: abstração de provedor em `llm_service.py`

**Objetivo:** ramificar payload/parsing por provedor, 100% backward-compatible (nenhum caller passa `ai_profile` real ainda).

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/core/config.py` | `openrouter_api_base`/`openrouter_api_key` |
| `backend-executors/.env.example` | Bloco novo de exemplo |
| `backend-executors/app/services/llm_service.py` | `_resolve_provider_config`, `_build_payload`/`_extract_text` por provedor, `_post_with_retry` recebendo `api_base`/`api_key` |
| `backend-executors/tests/test_llm_service_retry.py` | Ajusta chamadas existentes + novos casos de resolução de provedor |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `21ff3c2` | abstração completa de provedor em `llm_service.py` + settings + 15 testes novos |

**Detalhes do commit `21ff3c2`:**
- `backend-executors/app/core/config.py` — `openrouter_api_base`/`openrouter_api_key`
- `backend-executors/.env.example` — bloco de exemplo para as novas variáveis
- `backend-executors/app/services/llm_service.py` — `_resolve_provider_config()` decide OpenAI vs OpenRouter a partir de `ai_profile.llm_provider`, com fallback para OpenAI se a chave OpenRouter não estiver configurada no servidor; `_build_payload()`/`_extract_output_text()` ramificam entre Responses API (OpenAI) e Chat Completions (OpenRouter); `_post_with_retry()` passa a aceitar `api_base`/`api_key` por parâmetro, com default = config da OpenAI (100% compatível com chamadas existentes sem esses argumentos); as 7 funções públicas ganham `ai_profile` opcional
- `backend-executors/tests/test_llm_service_retry.py` — 15 testes novos (resolução de provedor, clamp de modelo desconhecido para o padrão curado, fallback por chave ausente, parsing OpenRouter, payload shape, roteamento ponta a ponta); os 11 testes originais continuam passando sem nenhuma alteração de assinatura

**Nota de verificação:** a suíte completa (`pytest`) tem 66 testes falhando neste repositório antes mesmo desta fase — causados por uma mudança já em andamento e não commitada em `decision_engine.py` (fase de recepção/p0 do Fluxo de Venda, alheia a esta feature). Confirmei via `git stash` que o conjunto de falhas é idêntico com e sem as mudanças desta fase — nenhuma regressão nova introduzida.

### Relatório da Fase 2 — o que mudou na prática

**Antes:** `llm_service.py` só sabia falar com a OpenAI — não existia nenhum código capaz de montar uma requisição para outro provedor.
**Agora:** o serviço sabe montar e interpretar chamadas tanto para a OpenAI quanto para o OpenRouter, mas essa capacidade ainda está "desligada" — nenhuma parte do sistema está passando a escolha do usuário para dentro dessa função ainda (isso é a Fase 3). Se a OpenRouter for escolhida mas a chave não estiver configurada no servidor, o sistema volta sozinho para a OpenAI em vez de travar a conversa.
**Para validar:** ainda nenhum cenário de ponta a ponta (Playground/WhatsApp) — a validação desta fase é só o `pytest` (26/26 testes passando em `test_llm_service_retry.py`). Os cenários P1-P3/C1-C2 do checklist abaixo só ficam testáveis a partir da Fase 3.

### Fase 3 — backend-executors: repassar `ai_profile` nos 7 pontos de chamada

**Objetivo:** ligar de fato o comportamento — a escolha do usuário passa a ter efeito.

| Arquivo | O que muda |
|---|---|
| `decision_engine.py` | `_decide_post_meeting_management()` e `decide()` passam `ai_profile=ai_profile` nas 3 chamadas ao llm_service |
| `field_extractor.py` | `extract_fields_llm()` passa `ai_profile=ai_profile` (já extraído localmente) |
| `meeting_scheduler.py` | 3 wrappers passam `ai_profile=ai_profile` (já é parâmetro de cada um) |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1bcf4fa` | os 7 pontos de chamada passam a repassar `ai_profile`; 25 arquivos de teste corrigidos |

**Detalhes do commit `1bcf4fa`:**
- `backend-executors/app/services/decision_engine.py` — hoist de `ai_profile = context.get("ai_profile") or {}` em `_decide_post_meeting_management()` e `decide()`; as 3 chamadas ao `llm_service` passam `ai_profile=ai_profile`. **Nota técnica:** este arquivo já tinha uma mudança não commitada e alheia a esta feature (WIP de uma fase p0/recepção do Fluxo de Venda). Separei os dois conjuntos de mudança usando um patch isolado (`git apply --cached`) para que o commit contenha só as 4 alterações relacionadas a `ai_profile` — o WIP alheio continua intocado e não commitado, exatamente como estava antes desta tarefa
- `backend-executors/app/services/field_extractor.py` — `extract_fields_llm()` passa `ai_profile` (já extraído localmente) para `generate_decision_text()`
- `backend-executors/app/services/meeting_scheduler.py` — os 3 wrappers passam `ai_profile=ai_profile`
- 25 arquivos de teste (`scripts/` e `tests/`) — as funções fake que faziam monkeypatch de `llm_service.generate_mother_route`/`generate_child_result`/`generate_decision_text`/`generate_conflict_message` tinham assinatura fixa (`lambda _prompt: ...`) e quebravam com o novo argumento nomeado `ai_profile`; todas passaram a aceitar `**kwargs`

**Nota de verificação:** suíte completa rodada antes e depois — mesmo conjunto de 66 falhas pré-existentes (idênticas, confirmado por `diff`), nenhuma regressão nova introduzida por esta fase.

### Relatório da Fase 3 — o que mudou na prática

**Antes:** a escolha de provedor no AI Profile (Fases 1-2) existia no banco de dados e no código de `llm_service.py`, mas nada no sistema real passava essa escolha para dentro da função — todo mundo continuava, na prática, usando a OpenAI.
**Agora:** a escolha do usuário tem efeito real. Se o AI Profile de um lead tiver `llm_provider="openrouter"`, as 7 chamadas de IA desse turno (decisão de rota, resposta ao lead, extração de qualificação, mensagens de conflito/lembrete/título de reunião) usam o OpenRouter — com fallback automático para a OpenAI se a chave do OpenRouter não estiver configurada no servidor.
**Para validar:** Cenários P1, P2, P3 (Playground) e C1, C2 (WhatsApp real) do checklist abaixo — todos ficam testáveis a partir de agora. Falta só a Fase 4 (UI) para o usuário poder fazer essa escolha sem precisar editar o banco/API diretamente — até lá, dá para testar via PATCH direto em `/ai-profiles/me`.

### Fase 4 — frontend-crm: UI no AI Profile

**Objetivo:** usuário escolhe provedor/modelo na tela de configuração do agente.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | Campos novos em `AgentConfig`/`DEFAULT_AGENT_CONFIG` |
| `frontend-crm/src/components/agente/CamadaIdentidade.tsx` | Novo card + modal `ModalLlmProvider` |
| `frontend-crm/src/services/api.ts` | Passthrough em `getConfig`/`saveConfig` |

### Fase 5 — docs e visibilidade admin

**Objetivo:** manter `docs/architecture/` como espelho do sistema e dar visibilidade ao operador.

| Arquivo | O que muda |
|---|---|
| `docs/architecture/admin-agents-contract.md` | Nova linha de contrato |
| `backend-crm/routes/admin_agents.py` | Campos novos nos 2 subsets manuais |
| `frontend-admin/src/pages/AdminAgents.tsx` + `api.ts` | Badge somente leitura |
| `docs/architecture/llm-architecture.md` | Atualiza tabela de arquivos críticos e seção de retry |

---

## Checks de Validação

### Cenário P1 — Perfil OpenAI (padrão) sem regressão
- [ ] Playground, perfil com `llm_provider="openai"` (ou sem o campo, backfill automático)
- [ ] Enviar mensagem e confirmar resposta normal da IA
- [ ] Confirmar: comportamento idêntico ao anterior à mudança

### Cenário P2 — Perfil OpenRouter com chave configurada
- [ ] Playground, perfil com `llm_provider="openrouter"` + modelo padrão, `OPENROUTER_API_KEY` setada no `.env` do backend-executors
- [ ] Enviar mensagem e confirmar que mãe + filha respondem normalmente

### Cenário P3 — Perfil OpenRouter sem chave configurada no servidor
- [ ] Mesmo perfil do P2, mas `OPENROUTER_API_KEY` ausente
- [ ] Confirmar: conversa completa normalmente (fallback para OpenAI), sem erro 500
- [ ] Confirmar no log: `event=llm_provider_fallback`

### Cenário P4 — UI de seleção de provedor
- [ ] Abrir AI Profile → card "Provedor de IA" mostra OpenAI por padrão
- [ ] Trocar para OpenRouter, escolher modelo, salvar, recarregar página
- [ ] Confirmar: seleção persiste

### Cenário P5 — Reverter para OpenAI limpa o modelo
- [ ] Com perfil em OpenRouter + modelo selecionado, voltar para OpenAI e salvar
- [ ] Confirmar: `llm_provider_model` fica nulo no backend

### Cenário C1 — WhatsApp real, wrappers de meeting_scheduler
- [ ] Lead real em perfil OpenRouter atinge um gatilho de conflito de agenda ou lembrete
- [ ] Confirmar: mensagem gerada no tom certo do agente (não a string fixa de fallback)

### Cenário C2 — WhatsApp real, extração de qualificação
- [ ] Turno de qualificação em perfil OpenRouter
- [ ] Confirmar: `extract_fields_llm` não quebra o turno

---

## Ajustes Possíveis Pós-Implementação

- Sem alerta automático para `event=llm_provider_fallback` — depende de observação manual do log nesta iteração.
- Custo/uso do OpenRouter não aparece em nenhum dashboard de custo já existente para a OpenAI.
- `metadata.route` (observabilidade) não é enviado no payload OpenRouter — sem impacto funcional, nada no código lê esse campo de volta.
