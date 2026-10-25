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

### Fase 2 — Frontend + docs

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts`, `src/services/api.ts` | `response_creativity` |
| `frontend-crm/src/components/agente/CamadaIdentidade.tsx` | card + drawer "Criatividade das respostas" |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | `strict` + caixa "Seguir à risca" + marca no `BlockRow` |
| `frontend-admin/src/pages/AdminAgents.tsx`, `backend-crm/routes/admin_agents.py` | exibir o campo novo |
| `docs/architecture/*.md`, `docs/prompts_llms.md`, `docs/plans/motor-llm-otimizacoes.md` | refletir o estado novo |

---

## Checks de Validação

### Cenário P1 — "Seguir à risca" na Fase 0 (Playground)
- [ ] Na Lara, marcar "Seguir à risca" na orientação da Fase 0
- [ ] Nova conversa no Playground, enviar só "olá"
- [ ] Confirmar: a resposta apresenta a Lara e pergunta Val ou Daniel, sem frases a mais
- [ ] Confirmar no log do executor: chamada da Filha com `temperature=0.2`

### Cenário P2 — Card geral em "Rígida"
- [ ] Camada Identidade → Criatividade das respostas → Rígida → salvar
- [ ] Recarregar a página: valor continua "Rígida"
- [ ] Enviar mensagem no Playground: log mostra `temperature=0.2`

### Cenário P3 — "Padrão" não muda nada
- [ ] Card em "Padrão"
- [ ] Log mostra a chamada da Filha sem `temperature`

### Cenário P4 — Orientação estrita num caminho não escolhido não vale
- [ ] Coberto por teste automatizado (`backend-executors/tests/`)

---

## Ajustes Possíveis Pós-Implementação

- Temperatura baixa fixa para a Mãe (M1) depois de medir o efeito na Filha.
