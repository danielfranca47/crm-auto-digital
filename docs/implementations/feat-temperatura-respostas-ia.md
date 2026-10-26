# Criatividade das respostas (temperatura) + orientação "seguir à risca"

---

**Branch:** `worktree-feat+temperatura-respostas-ia` (nome pedido: `feat/temperatura-respostas-ia`; o `EnterWorktree` sanitiza o nome)
**Status:** Em andamento
**Autonomia:** manual

---

## Motivação

No teste da Lara (Sensi Vitae, 25/10/2026) no Playground, a orientação da Fase 0 foi
seguida, mas a IA acrescentou frases que não estavam nela ("Que bom receber sua
mensagem!") e inventou dados ("a Val atende de segunda a sábado"; a disponibilidade
configurada é todos os dias). O utilizador quer poder deixar o agente mais rígido e
fiel ao texto que escreve no Fluxo de Venda.

Causa raiz: nenhuma chamada de LLM envia `temperature` (`_build_payload()` em
`backend-executors/app/services/llm_service.py`), então vale o padrão do provedor (alto,
~1.0 no OpenRouter/Llama 3.3). Também não existe forma de dizer "este texto é para usar
assim", e o rótulo de uma orientação normal ("INSTRUÇÃO DE FLUXO DE VENDA") deixa a Filha
livre para enfeitar.

---

## Problemas Identificados (estado anterior)

1. **Sem temperatura (`llm_service.py:_build_payload`)** — payload sem `temperature` nos
   dois provedores (OpenAI Responses e OpenRouter Chat Completions).
2. **Sem controlo no AI Profile** — o utilizador não tem como pedir respostas mais
   previsíveis.
3. **Orientação sem modo literal (`decision_engine.py:_evaluate_sales_flow_phases`)** — toda
   orientação vira uma instrução aberta; não há como marcar "diga isto, sem acrescentar".

---

## Abordagem

Dois níveis, decididos no Plan Mode (25/10/2026). "Por fase" foi descartado: grosso
demais (a fase inteira ficaria rígida mesmo quando só uma frase importa) e o mesmo efeito
se consegue marcando "seguir à risca" nas orientações da fase.

```
Chamada da Filha (decide())
  temperatura = 0.2 se alguma orientação "seguir à risca" está ativa neste turno
              senão mapa de ai_profile.response_creativity
                   creative → 0.9 · balanced → 0.5 · strict → 0.2
              senão (vazio = "Padrão") → não envia temperatura (comportamento atual)
```

- **Geral:** campo `response_creativity` no AI Profile; card "Criatividade das respostas"
  na Camada Identidade, ao lado de "Provedor de IA".
- **Por ação:** campo `strict` no bloco `orientacao`; caixa "Seguir à risca". No turno em
  que entra no prompt, troca o rótulo por uma instrução literal e força temperatura 0.2.
- Fora de escopo: temperatura da Mãe (roteamento) — continua em M1 de
  `docs/plans/motor-llm-otimizacoes.md`, porque mudaria todos os agentes.

---

## Plano de Implementação

### Fase 1 — Backend: campo, temperatura no payload, orientação estrita

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | coluna `response_creativity` |
| `backend-core/app/db.py` | coluna no dicionário do `ensure_*` |
| `backend-core/app/api/ai_profiles.py` | enum `ResponseCreativity` + campo em `AIProfileBase`/`AIProfileUpdate` |
| `backend-executors/app/services/llm_service.py` | `temperature` em `_build_payload`; `resolve_child_temperature()`; `generate_child_result(..., temperature_override=)` |
| `backend-executors/app/services/decision_engine.py` | rótulo literal + `strict_active` em `_evaluate_sales_flow_phases`; `decide()` passa `temperature_override=0.2` |
| `backend-executors/tests/` | testes de payload, mapa e orientação estrita |

Decisões:
- A orientação estrita só vale no turno em que dispara. A reinjeção permanente de
  orientações críticas (segunda passagem) mantém o rótulo normal, senão a Filha repetiria
  a mesma frase literal em todo turno da fase.
- `decide()` reavalia a fase (função pura, mesmo padrão de `compose_decision_output`) só
  nas rotas cujo builder injeta o Fluxo de Venda (`_SALES_FLOW_INJECTING_CHILD_ROUTES`):
  pré-agendamento e agendamento não injetam blocos, então não baixam a temperatura.
- O kwarg `temperature_override` só é passado quando há orientação estrita. Assim os
  mocks antigos de `generate_child_result` nos testes continuam válidos.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `1907285` | campo `response_creativity`, temperatura no payload, orientação estrita + testes |

Testes: `backend-executors/tests` com 332 passados. `backend-core/tests` com 82 passados e
8 falhas que já existem iguais em `main` (`test_ai_profile_agent_mode.py`,
`test_ai_profile_timezone_persistence.py`), sem relação com esta mudança.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** a IA respondia sempre no "nível de criatividade" padrão do modelo, que é
alto. Não havia como pedir que seguisse um texto à risca.
**Agora:** o servidor já sabe guardar o nível "Criativa / Equilibrada / Rígida" de cada
agente e já sabe tratar uma orientação marcada "seguir à risca". Nesse caso a IA recebe a
ordem de usar só o que está escrito, com o nível mais rígido, naquela resposta. Agentes
que não mexerem em nada continuam exatamente como estavam.
**Para validar:** os Cenários P1 a P3 dependem da tela (Fase 2). O Cenário P4 já está
coberto pelos testes automáticos.

### Fase 2 — Frontend + docs

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts`, `src/services/api.ts` | `response_creativity` |
| `frontend-crm/src/components/agente/CamadaIdentidade.tsx` | card + drawer "Criatividade das respostas" |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `strict` + caixa "Seguir à risca" + marca no `BlockRow` |
| `frontend-admin/src/pages/AdminAgents.tsx`, `backend-crm/routes/admin_agents.py` | exibir o campo novo |
| `docs/architecture/*.md`, `docs/prompts_llms.md`, `docs/plans/motor-llm-otimizacoes.md` | refletir o estado novo |

Decisões:
- Card como modal (`ModalCriatividade`, mesmo padrão do "Provedor de IA" com `OptCard`), na
  grelha de identidade, logo a seguir ao card do provedor.
- "Padrão" grava `null`. O `PATCH` com `exclude_unset` limpa o campo, e o executor não envia
  temperatura.
- A exportação/importação de agente (`AgentExportImportPanel.tsx`) exporta tudo menos uma
  lista de exclusões, então leva `response_creativity` e `strict` sem mudança.
- Typecheck: `frontend-crm` com os mesmos 66 erros que já existem em `main` e nenhum novo.
  `frontend-admin` com 0 erros.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `99c5590` | card + modal, caixa "Seguir à risca" + etiqueta, painel admin, docs de arquitetura |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** não havia nenhum botão para controlar o quanto a IA inventa ou enfeita.
**Agora:** em "Configurar Agente → Identidade" há um card "Criatividade das respostas"
com Padrão, Criativa, Equilibrada e Rígida. Em cada Orientação do Fluxo de Venda há a caixa
"Seguir à risca", e o bloco marcado mostra a etiqueta "à risca". O painel admin mostra o
nível quando não está em "Padrão".
**Para validar:** Cenários P1, P2 e P3, abaixo.

---

## Checks de Validação

Setup usado (25/10/2026): conta de teste local (user 15, perfil 5, OpenAI gpt-4o-mini),
com cópias de `core.db`/`crm.db` dentro da worktree e os blocos da Fase 0 da Lara copiados
para o perfil de teste. O backend-core arrancou com SMTP vazio no processo.

### Cenário P1 — "Seguir à risca" na Fase 0 (Playground)
- [x] Marcar "Seguir à risca" na orientação da Fase 0 (caixa aparece, etiqueta "à risca" no bloco, `strict: true` gravado)
- [x] Nova conversa no Playground, enviar só "olá"
- [x] Confirmar: a resposta apresenta a Lara e pergunta Val ou Daniel, sem frases a mais
- [x] Confirmar no log do executor: chamada da Filha com `temperature=0.2`
- **Revalidado em:** 26/10/2026, depois da Fase 3, via API do Playground (3 execuções): as 3
  respostas foram "Oi! Sou a Lara, atendente do Sensi Vitae. Qual terapeuta você tem
  interesse: Val ou Daniel?", com `temperature=0.2`. Antes disso, o perfil de teste foi
  alinhado com o de produção na cópia local do `core.db` (`name=Lara`,
  `brand_name=Sensi Vitae Massages`, `identity_mode=human_agent`). Com o nome "Daniel", a
  identidade ("Você é Daniel") brigava com "Apresente-se como Lara", e a resposta perguntava
  Val ou Daniel sem se apresentar.
- **Validado em:** 25/10/2026 (parcial). Com o card em "Padrão", a Recepção saiu com
  `temperature=0.2`, vinda da orientação estrita. **Falhou no conteúdo:** a resposta foi
  "Seja bem-vindo(a)! / Agradeço pelo contato. / Me conta o que você está buscando.",
  sem apresentar a Lara nem perguntar Val ou Daniel. Igual sem "seguir à risca". A Fase 0
  disparou (`phases_triggered=["p0"]`), então a orientação entrou no prompt. Ver Fase 3.

### Cenário P2 — Card geral em "Rígida"
- [x] Camada Identidade → Criatividade das respostas → Rígida → "Salvar Camada 1"
- [x] Recarregar a página: valor continua "Rígida"
- [x] Enviar mensagem no Playground: log mostra `temperature=0.2`
- **Validado em:** 25/10/2026: `response_creativity=strict` no banco e card "Rígida" depois
  de recarregar; log `event=llm_child_temperature route=recepcao temperature=0.2`. O valor
  só grava no servidor com "Salvar Camada 1", como os outros campos da camada.

### Cenário P3 — "Padrão" não muda nada
- [x] Card em "Padrão" (grava `null`)
- [x] Log mostra a chamada da Filha sem `temperature`
- **Validado em:** 25/10/2026: turno "quanto custa a massagem relaxante?" (rota
  apresentação, sem orientação estrita ativa) não gerou nenhum `llm_child_temperature`

### Cenário P4 — Orientação estrita num caminho não escolhido não vale
- [x] Coberto por teste automatizado (`test_strict_orientation_in_unchosen_branch_not_active`)
- **Validado em:** 25/10/2026: teste passa, junto com os da entrada da fase e da reinjeção crítica

---

## Fase 3 — Diagnóstico + Correção: Recepção ignorava a orientação da Fase 0 (25/10/2026)

### Problema identificado

No Cenário P1, com a orientação da Lara na Fase 0 (com e sem "seguir à risca"), a Recepção
respondia só "Seja bem-vindo(a)! / Agradeço pelo contato. / Me conta o que você está
buscando.". A orientação entrava no prompt (`phases_triggered=["p0"]`), mas perdia para o
texto fixo de `_build_child_prompt_recepcao()`:
- "Não faz perguntas de qualificação neste turno";
- exemplos ✅ só de cumprimento;
- `"message_text": "<cumprimento caloroso — máximo 2-3 linhas>"`;
- o bloco do Fluxo de Venda era colado no fim, depois do formato JSON.

Baixar a temperatura até reforçava isto, porque o modelo obedece mais ao que está escrito
com mais força.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_recepcao`: avalia o Fluxo de Venda antes de montar o texto. Com blocos, insere "INSTRUÇÕES DO DONO DO NEGÓCIO PARA ESTE TURNO" no meio do prompt (com motivo e exemplo ✅/❌), acrescenta o item 4 em "O QUE VOCÊ FAZ" e troca a regra de pergunta e o modelo de `message_text`. Sem blocos, o prompt fica igual |
| `backend-executors/tests/test_recepcao_sales_flow_orientation.py` | 4 testes: sem orientação, com orientação, orientação estrita, fora da entrada da fase |
| `docs/architecture/llm-architecture.md`, `docs/architecture/sales-flow.md`, `docs/prompts_llms.md` | variante da Recepção |

Decisão: vale para qualquer orientação da Fase 0, não só as estritas. Uma orientação da Fase
0 ser ignorada é defeito por si só; o "seguir à risca" só acrescenta o modo literal e a
temperatura baixa.

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `105414d` | Recepção obedece às instruções da Fase 0 |

Testes: `backend-executors/tests` com 336 passados.

### Relatório da Fase 3 — o que mudou na prática

**Antes:** na primeira resposta, o agente ignorava o que estava escrito na Fase 0 do Fluxo
de Venda e mandava sempre um cumprimento genérico, com ou sem "seguir à risca".
**Agora:** quando a Fase 0 tem orientações, elas passam a mandar na primeira resposta. O
agente cumprimenta e faz o que está escrito (apresentar-se como Lara, perguntar Val ou
Daniel). Com "seguir à risca", fica o mais perto possível das palavras escritas. Sem
orientações na Fase 0, a primeira resposta continua igual.
**Para validar:** Cenário P1 (repetir) e Cenário P5, abaixo.

### Cenário P5 — Saudação composta com a orientação da Fase 0
- [x] Nova conversa no Playground: "ola, gostaria de saber mais sobre as massagens da val"
- [x] Confirmar: a Recepção apresenta a Lara sem perguntar de novo "Val ou Daniel?"
- **Validado em:** 26/10/2026, depois da Fase 4, via API do Playground, com o perfil de
  teste alinhado à produção (Llama 3.3 70B na OpenRouter, `custom_instructions` da Lara).
  "massagens da val": 3 de 3 "Olá! Sou a Lara, Atendente do Sensi Vitae." "quero marcar com a
  Val": 3 de 3 iguais. Controlo "quanto custa a massagem?": 3 de 3 mantêm "Val ou Daniel?".
  Mais 8 de 8 de cada no banco de ensaio. Antes da Fase 4 falhava 3 de 3, com e sem
  "seguir à risca".

---

## Fase 4 — Recepção repetia a pergunta já respondida (26/10/2026)

### Problema identificado

No P5, a Recepção voltava a perguntar "Val ou Daniel?" a quem já tinha escrito "massagens da
val". Várias instruções do prompt empurram para terminar em pergunta: a orientação estrita
("termine nessa pergunta"), o bloco de tom de voz ("sempre feche com UMA pergunta") e a
regra da Recepção de não tocar no pedido comercial. Só texto no prompt não resolveu: com uma
regra e um exemplo a mais, falhou 3 de 3 no gpt-4o-mini e 5 de 5 no Llama 3.3. Pedir ao modelo
"já respondeu? sim/não" também não, porque respondeu "não" até para "quero marcar com a Val".
Pedir a **opção citada** funcionou: o modelo devolve "Val" 8 de 8, mas mesmo assim escreve a
pergunta em cerca de metade das vezes.

### Correção

| Arquivo | Mudança |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_recepcao`: com instruções da Fase 0, exemplo ✅/❌ de pergunta já respondida e campo `lead_already_answered` no início do JSON. `compose_decision_output()`: na Recepção, com o campo preenchido, `_drop_trailing_question()` tira a frase final terminada em "?". `_strict_orientation_injection`: exceção "a menos que a mensagem do lead já a responda" |
| `backend-executors/app/services/orchestrator_models.py` | `ChildResult.lead_already_answered` |
| `backend-executors/tests/test_recepcao_sales_flow_orientation.py`, `test_requeue_pending_message_routing.py` | prompt com e sem instruções, corte da pergunta, pergunta mantida sem o campo, `_drop_trailing_question` |
| `docs/architecture/llm-architecture.md`, `docs/prompts_llms.md` | campo novo e corte |

Decisão: o corte fica em código (princípio 1 de `prompt-engineering-principles.md`). O
modelo só aponta a opção, que é o que ele faz bem, e o código garante o resultado. Sem o
campo, nada muda.

### Commits Fase 4

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `639590a` | campo `lead_already_answered`, corte da pergunta repetida, exceção no "seguir à risca" |

Testes: `backend-executors/tests` com 342 passados.

### Relatório da Fase 4 — o que mudou na prática

**Antes:** se o cliente escrevia logo "queria saber das massagens da Val", a Lara
apresentava-se e perguntava a seguir "Val ou Daniel?", como se não tivesse lido.
**Agora:** a Lara apresenta-se e não repete a pergunta. O pedido do cliente segue para a
resposta seguinte, que trata das massagens da Val. Se o cliente não escolheu (ex.: "quanto
custa?"), a pergunta continua a ser feita.
**Para validar:** P5 acima (já validado via API).

### Observação de configuração (não é código)

Com o Llama 3.3, a orientação da Lara tal como está ("…Pergunte qual terapeuta ele tem
interesse. ⏎⏎ Terapeuta Val ou Daniel") gerou em 3 de 8 vezes "Qual terapeuta você tem
interesse?", sem nomear os dois. Escrita numa só frase ("Apresente-se como Lara, Atendente
do Sensi Vitae, e pergunte com qual terapeuta ele tem interesse: Val ou Daniel."), saiu 8 de
8 com os nomes. A mudança é no Fluxo de Venda da conta, feita pelo utilizador.

---

## Ajustes Possíveis Pós-Implementação

- Temperatura baixa fixa para a Mãe (M1) depois de medir o efeito na Filha.
- As outras Filhas também colam o bloco do Fluxo de Venda no fim do prompt, depois do JSON.
  Os prompts delas não proíbem perguntas como o da Recepção, mas vale observar se alguma
  orientação de outra fase também é ignorada.
