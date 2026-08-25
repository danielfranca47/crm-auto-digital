# Execução em runtime do bloco `espera` (Smart Delay) — pausa do Fluxo de Venda

**Branch:** `feat/sales-flow-espera-pausa`
**Status:** Em andamento — P1 e P2 validados no Playground (25/08/2026), pendente: Cenário C1 (WhatsApp real)

---

## Motivação

Este item nasceu como "Ajuste possível" na graduação de `fix-intent-trigger-fase-entrada.md`, registrado em
`docs/implementations/sales-flow-webhook-condicao-espera-runtime.md` (arquivo-mãe, cobria `webhook` e `espera`
juntos). Diagnóstico em Plan Mode concluiu que as duas features não têm dependência entre si e devem ser
implementações separadas — esta cobre só `espera`; `webhook` fica para uma implementação seguinte
(`feat/sales-flow-webhook-execucao`).

O builder visual (`CamadaFluxoVenda.tsx`) já permite configurar um bloco `espera` (⏳ Smart Delay) com
`wait_value`/`wait_unit`, e `decision_engine.py` já **emite** um `system_action` quando ele dispara
(`{"type": "delay", ...}`, `decision_engine.py:832-839`) — mas nada no lado de consumo
(`backend-crm/routes/executor.py::_dispatch_system_actions()`, espelho em `playground.py`) trata esse tipo de
ação. Ela é descartada silenciosamente. O bloco é configurável na UI mas não tem nenhum efeito real na
conversa.

**Comportamento desejado, esclarecido pelo usuário durante o diagnóstico:** enquanto o tempo configurado não
passa, o fluxo fica pausado — os gatilhos/ações que vêm **depois** do bloco `espera` na mesma fase não
disparam. Um checkbox novo no bloco decide o que acontece se o lead escrever durante a pausa: marcado → a IA
continua respondendo normalmente (só as ações automáticas do Fluxo de Venda ficam paradas); desmarcado → pausa
total, o bot não responde nada enquanto o tempo estiver correndo.

---

## Problemas Identificados (estado anterior)

1. **`espera` sem execução real:** `decision_engine.py` emite `{"type": "delay", "wait_value", "wait_unit"}`
   quando o bloco dispara, mas `_dispatch_system_actions()` (`backend-crm/routes/executor.py:276-395`) não tem
   nenhum branch para `"delay"` — a ação é ignorada, nenhum estado é persistido, nada pausa. Mesma lacuna em
   `playground.py`.
2. **Sem campo para controlar resposta da LLM durante a pausa:** o schema do bloco (`SalesFlowBlock`,
   `frontend-crm/src/types/agente.ts`) não tem nenhum campo equivalente ao checkbox descrito acima — precisa
   ser criado do zero, junto com o form correspondente em `CamadaFluxoVenda.tsx`.

---

## Abordagem

```
Bloco `espera` dispara (last_trigger_active=True na posição dele)
  → decision_engine calcula wait_until = agora + wait_value/wait_unit
  → emite system_action "sales_flow_pause_set" {until, block_id, phase_id, suppress_llm}
  → interrompe a avaliação do restante da fase neste turno (nada abaixo dele roda)
  → executor.py / playground.py persistem em leads.sales_flow_wait (JSON)

Turnos seguintes, enquanto wait_until > agora:
  → decision_engine lê leads.sales_flow_wait
  → se suppress_llm=True → força suppress_llm_response (reaproveita mecanismo já existente)
  → ao alcançar o block_id da pausa na avaliação da fase → interrompe (nada abaixo dele roda)

Quando wait_until <= agora:
  → decision_engine emite "sales_flow_pause_clear" → executor.py limpa a coluna
  → fase volta a avaliar normalmente, incluindo o próprio bloco `espera` (pode disparar de novo)
```

---

## Plano de Implementação

### Fase 1 — Schema, motor de decisão, dispatch e checkbox no builder

**Objetivo:** bloco `espera` pausa de fato o restante da fase, com a opção de a LLM continuar ou não
respondendo durante a pausa, funcionando tanto no Playground quanto no WhatsApp real.

| Arquivo | O que muda |
|---|---|
| `backend-crm/database.py` | Nova coluna `leads.sales_flow_wait TEXT NULL` via `ensure_column()` — JSON `{"until", "block_id", "phase_id", "suppress_llm"}` |
| `backend-executors/app/services/decision_engine.py` | Novo helper `_load_sales_flow_wait(context)`; gate no topo/loop de `_evaluate_sales_flow_phases()`; emissão de `sales_flow_pause_set`/`sales_flow_pause_clear` no lugar de `"delay"` |
| `backend-crm/routes/executor.py` | Novo branch em `_dispatch_system_actions()` para `sales_flow_pause_set`/`sales_flow_pause_clear` |
| `backend-crm/routes/playground.py` | Mesmo branch espelhado (mutação de estado pura — roda de verdade no Playground) |
| `frontend-crm/src/types/agente.ts` | Novo campo no bloco `espera`: `suppress_llm_during_wait?: boolean` |
| `frontend-crm/src/components/agente/CamadaFluxoVenda.tsx` | Checkbox "Responder dúvidas durante a espera" no form do bloco `espera` |
| `docs/architecture/sales-flow.md` | Atualizar secção do bloco `espera` para refletir execução real (era "reservado para o futuro") |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `71f6dc6` | Schema + motor de decisão + dispatch (real e Playground) + checkbox no builder + doc de arquitetura |

**Detalhes do commit `71f6dc6`:**
- `backend-crm/database.py` — nova coluna `leads.sales_flow_wait TEXT NULL`
- `backend-executors/app/services/decision_engine.py` — `_load_sales_flow_wait()`, `_sales_flow_wait_timedelta()`; gate de pausa por escopo (root ou caminho de `condicao`) em `_evaluate_sales_flow_phases()`; força `suppress_llm_response` quando o checkbox está desmarcado; a segunda passagem de orientações críticas também respeita o gate
- `backend-crm/routes/executor.py` / `playground.py` — branches `sales_flow_pause_set`/`sales_flow_pause_clear` em `_dispatch_system_actions()` (espelhados — mutação de estado pura, roda de verdade também no Playground)
- `frontend-crm/src/types/agente.ts` / `CamadaFluxoVenda.tsx` — campo `allow_llm_during_wait` + checkbox "Responder dúvidas durante a espera" no form do bloco
- `docs/architecture/sales-flow.md` — nova seção "Pausa do Fluxo (espera / Smart Delay)" + atualizações nas tabelas relacionadas

### Relatório da Fase 1 — o que mudou na prática

**Antes:** o bloco "Espera (Smart Delay)" podia ser configurado no builder (tempo de espera, motivo), mas não tinha nenhum efeito real — os gatilhos/ações depois dele na mesma fase continuavam disparando normalmente, como se o bloco nem existisse.

**Agora:** quando o bloco `espera` dispara, ele pausa de fato o restante da fase pelo tempo configurado (minutos/horas/dias). Um novo checkbox "Responder dúvidas durante a espera" controla o que acontece se o lead escrever durante a pausa: marcado (padrão) — a IA continua respondendo normalmente, só as ações automáticas do Fluxo de Venda ficam paradas; desmarcado — pausa total, o bot não responde nada até o tempo passar. Depois de o tempo passar, tudo volta ao normal, incluindo a possibilidade do próprio bloco `espera` disparar de novo.

**Para validar:** Cenários P1, P2 e C1, abaixo.

---

## Checks de Validação

### Cenário P1 — Pausa com LLM ativa (checkbox marcado)
- [x] No builder, configurar fase com gatilho → bloco `espera` (1 minuto) com checkbox marcado → bloco de ação (ex. `mensagem`) depois dele
- [x] No Playground, disparar o gatilho
- [x] Confirmar: `sales_flow_wait` persistido no lead, bloco de ação depois do `espera` NÃO dispara neste turno nem nos seguintes durante a janela
- [x] Enviar nova mensagem ao bot dentro da janela de pausa — confirmar que a LLM responde normalmente (não é suprimida)
- [x] Esperar o tempo passar, enviar nova mensagem — confirmar que o bloco depois do `espera` volta a poder disparar
- **Validado em:** 25/08/2026 — testado ao vivo no Playground (perfil real `Daniel`/`hybrid_scheduler`, fase Apresentação, blocos de teste removidos depois). Confirmado: `espera` dispara e persiste `sales_flow_wait`; o gatilho/mensagem logo abaixo não disparou mesmo repetindo a palavra-chave dentro da janela; a IA continuou respondendo normalmente durante a pausa; após a janela expirar, o gatilho seguinte disparou normalmente e `sales_flow_wait` foi limpo.

### Cenário P2 — Pausa total (checkbox desmarcado)
- [x] Mesmo setup do P1, checkbox desmarcado
- [x] Disparar o gatilho, depois enviar mensagem ao bot dentro da janela de pausa
- [x] Confirmar: nenhuma resposta da LLM (silêncio total) enquanto a pausa está ativa
- **Validado em:** 25/08/2026 — com o checkbox desmarcado, uma mensagem enviada dentro da janela de pausa não gerou nenhuma resposta do bot (silêncio total), confirmando que `suppress_llm_response` é respeitado.

### Cenário C1 — Validação em WhatsApp real
- [ ] Repetir P1 num número de teste real
- [ ] Confirmar mesmo comportamento fora do Playground

---

## Ajustes Possíveis Pós-Implementação

- Nenhum identificado até o momento — revisar após os testes.
