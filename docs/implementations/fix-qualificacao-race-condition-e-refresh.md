# Fix: perda de dados de qualificação (race condition) + card sem auto-refresh

---

**Branch:** `fix/agendamento-nao-sincroniza-categoria-qualificacao`
**Status:** Em andamento

---

## Motivação

Usuário (gabrielsmith.original@gmail.com, ambiente de **produção no Railway**) reportou
que o bot de WhatsApp confirmou uma reunião real com um lead (compromisso criado no CRM,
sincronizado no Google Calendar, bot desativado), mas o card do lead no Kanban não
refletia isso: campos de "Critérios de Qualificação" apareciam "Não preenchido" mesmo o
lead tendo respondido no WhatsApp.

Investigação em produção (`railway ssh -s backend-crm`/`backend-core`, somente leitura,
autorizado pelo usuário), lead confirmado `+5547992163692` (lead_id=10, user_id=3):

- A hipótese inicial (gate de qualificação por score bloqueando avanço de categoria,
  `can_advance_score_gate`) **não se confirmou** — os `prospection_logs` mostram a
  categoria avançando sem bloqueio (`qualification→pre-agendamento` 12:26:27,
  `pre-agendamento→agendamento` 12:27:57, appointment real com `google_event_id` criado
  12:28:22, bot desativado 12:28:23). Os campos obrigatórios desse perfil
  (`custom_uso_do_produto`, `custom_pergunta_de_endereco`) são 100% customizados — o gate
  de score é pulado por design (não bate com nenhuma das 4 chaves pontuáveis).
- O usuário confirmou que precisou **editar manualmente** os campos de qualificação desse
  lead no card, porque a extração automática da IA não persistiu as respostas do lead.

Causa raiz confirmada no código: `upsert_qualification_state()`
(`backend-crm/services/qualification_state.py`) faz um read-modify-write **não atômico**
(lê em uma conexão, mescla em Python, grava em outra conexão/transação). É o único ponto
de gravação de `lead_qualification_state`, usado tanto pela extração automática do bot
quanto pela edição manual do card — duas chamadas próximas no tempo para o mesmo lead
(mensagens em sequência rápida, ou edição manual coincidindo com extração em andamento)
podem se sobrescrever, perdendo um campo já capturado. O `confidence_json` do lead no
banco tinha valores plausíveis de extração real (0.6, 0.9) — o bot viu e pontuou a
resposta, mas ela não sobreviveu em `data_json`.

Achado secundário (explica por que o card "parecia" travado mesmo com o backend correto):
nada no frontend re-busca dados automaticamente enquanto o bot trabalha em segundo plano —
`LeadsContext.reloadAllLeads()` só roda ao montar + após ações manuais; `useLeadAppointments`
e o carregamento de qualificação no `LeadCardDialog` só buscam ao montar o componente.

---

## Problemas Identificados (estado anterior)

1. **Race condition em `upsert_qualification_state()`** (`backend-crm/services/qualification_state.py:189`)
   — leitura (`get_qualification_state`) e escrita acontecem em conexões/transações
   separadas, com merge em Python no meio. Duas chamadas concorrentes para o mesmo
   `lead_id` podem causar lost-update, perdendo um campo de qualificação já capturado.

2. **Kanban sem auto-refresh** (`frontend-crm/src/contexts/LeadsContext.tsx:194-242`) —
   `reloadAllLeads()` só roda ao montar + após ação manual do operador; sem polling.

3. **Card do lead sem auto-refresh** (`frontend-crm/src/hooks/useAppointments.ts:104-119`,
   `frontend-crm/src/components/LeadCardDialog.tsx:300-310`) — compromissos e campos de
   qualificação só são buscados ao abrir o dialog, sem `refetchInterval`.

---

## Abordagem

Fix 1 (backend): mover a leitura de `lead_qualification_state` para dentro da mesma
transação `BEGIN IMMEDIATE` da escrita — mesmo padrão já usado em
`jobs_service.py::fetch_next_job()`. Elimina a janela entre leitura e gravação.

Fix 2 (frontend): polling leve (React Query `refetchInterval` onde já há
`useQuery`; `setInterval` onde é estado manual) para Kanban, compromissos do lead e
campos de qualificação, enquanto o componente correspondente está montado.

---

## Plano de Implementação

### Fase 1 — Backend: `upsert_qualification_state()` atômico

**Objetivo:** eliminar a perda de dados de qualificação por lost-update.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/qualification_state.py` | `upsert_qualification_state`: leitura movida para dentro da transação `BEGIN IMMEDIATE` da escrita |
| `backend-crm/tests/` | Novo teste de regressão: duas chamadas concorrentes-simuladas não podem perder campo já gravado |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(preencher após commit)_ | |

---

### Fase 2 — Frontend: auto-refresh do Kanban e do card do lead

**Objetivo:** refletir mudanças feitas pelo bot em segundo plano sem precisar de F5.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/contexts/LeadsContext.tsx` | Polling periódico de `reloadAllLeads()` |
| `frontend-crm/src/hooks/useAppointments.ts` | `refetchInterval` em `useLeadAppointments` |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Polling periódico do fetch de qualificação |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(preencher após commit)_ | |

---

## Checks de Validação

### Cenário P1 — Duas gravações concorrentes não perdem dado (backend, automatizado)
- [ ] Teste de regressão simula duas chamadas a `upsert_qualification_state` para o mesmo lead com campos diferentes
- [ ] Ambos os campos sobrevivem no `data_json` final
- **Pendente**

### Cenário F1 — Card atualiza sozinho (manual/browser)
- [ ] Abrir o card de um lead, deixar aberto, alterar o lead por fora (ex.: via API/outro fluxo)
- [ ] Confirmar que compromissos/qualificação atualizam sem F5
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

- Gate de qualificação por score (`can_advance_score_gate`) pode travar a categoria para
  perfis que usam os 4 campos padrão (`decision_role`/`urgency`/`budget_or_price_acceptance`/
  `availability_window`) mesmo com compromisso real confirmado — não foi a causa deste
  incidente, deixado de fora por decisão do usuário. Candidato a `docs/plans/`.
- `increment_attempt()` (`qualification_state.py`) tem uma janela de TOCTOU similar, menos
  crítica (afeta só contagem de tentativas, não perde resposta do lead) — não corrigido
  nesta fase.
