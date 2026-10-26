# Margem entre sessões configurável (tempo para preparar a sala)

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** investigação do bug A da bateria PROD07 do agente Sensi Vitae (26/10/2026) — pedido do
utilizador para avaliar uma margem entre sessões (ex.: 15 min para a terapeuta preparar a sala).
**Depende de:** [`fix-conflito-horario-comparado-como-texto.md`](fix-conflito-horario-comparado-como-texto.md) (mesmas funções de conflito)
**Plano de execução:** [`docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md`](../plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md) — P5

---

## Motivação

Hoje duas sessões podem ficar coladas (uma acaba às 16h, a seguinte começa às 16h) — e, depois
do bug A corrigido, isso passa a ser aceite. Num espaço de massagem a terapeuta precisa de tempo
para mudar a marquesa, toalhas e arejar a sala. O dono do negócio deve poder dizer "deixe N
minutos livres entre sessões", e o agente só propõe/aceita horários que respeitem essa margem.

## O que existe hoje (26/10/2026)

- **Não existe** nenhum campo de margem no AI profile (`backend-core/app/models/ai_profile.py`
  tem `default_session_duration_minutes`, mas nada de intervalo entre sessões).
- A base de conhecimento da Sensi Vitae pede ao cliente para "chegar 10 minutos antes" — é outra
  coisa (tempo do cliente, não da sala).
- As verificações de ocupado vivem em 4 sítios: conflito do CRM ao gravar
  (`routes/appointments.py::_check_conflict`), ocupados carregados para o agente
  (`orchestrator.py::_load_calendar_busy_slots`), conflito no executor
  (`meeting_scheduler._has_conflict`) e verificação do horário pedido (`requested_slot.find_requested_slot`,
  que usa `_has_conflict`). O texto "HORÁRIOS JÁ OCUPADOS" mostrado à IA vem dos mesmos ocupados
  (`decision_engine._format_busy_slots_block`).

## Onde deve viver (recomendação)

| Sítio | Aplicar margem? | Porquê |
|---|---|---|
| `_load_calendar_busy_slots` (CRM, via `enrich_context_bundle`) | **Sim — ponto único** | Alargar cada ocupado com a margem aqui faz o executor, a verificação do horário pedido e o texto dado à IA respeitarem a margem sem tocar no `decision_engine` (paridade Playground ↔ WhatsApp garantida pela função partilhada) |
| `meeting_scheduler._has_conflict` / `requested_slot` | Automático (leem os ocupados já alargados) | — |
| `_check_conflict` do CRM (gravação) | **Não** | É a trava contra sobreposição real; o dono pode marcar à mão colado se quiser. Se o agente respeitar a margem, nunca chega lá |
| `professional_hours` | Não | Horário de atendimento é outra regra (início/fim do dia) |

Cuidado conhecido: `meeting_scheduler._original_duration_minutes` lê a duração de um ocupado do
próprio lead para remarcar — se o ocupado vier alargado, a remarcação ficaria mais longa. O Plan
Mode tem de decidir entre mandar o intervalo original + a margem em campos separados, ou só alargar
os ocupados de outros leads.

## Nasce junto com A ou depois?

**Depois.** A é uma correção urgente (sessões seguidas recusadas e o worker a cair) que não precisa
de decisão de produto; a margem é uma funcionalidade nova com campo novo no AI profile (estrutura da
base de dados → sobe sempre ao utilizador), ecrã de configuração e decisão de valor por omissão.
Juntar as duas atrasaria a correção. A ordem importa porque ambas mexem nas mesmas consultas de
ocupados — fazer a margem por cima das consultas já corrigidas.

## Área do sistema

- `backend-core`: `app/models/ai_profile.py` + `app/db.py` (coluna nova, ex.
  `session_buffer_minutes`, omissão 0) + `app/api/ai_profiles.py`
- `backend-crm`: `services/ai_orchestrator/orchestrator.py::_load_calendar_busy_slots`
- `frontend-crm`: ecrã do AI profile onde está a duração da sessão (`src/components/agente/…`,
  `src/types/agente.ts`, `src/services/api.ts`)
- `frontend-admin/src/pages/AdminAgents.tsx` + `docs/architecture/admin-agents-contract.md`
  (regra obrigatória do CLAUDE.md para campos novos do AI profile)
- Docs: `docs/architecture/agenda.md`, `docs/architecture/agents.md`

## Decisões de produto a fechar no Plan Mode

1. Valor por omissão (proposta: 0 = comportamento atual).
2. Margem só depois da sessão, ou antes e depois? (proposta: só depois — é o tempo de preparar a sala).
3. Uma margem por conta (a agenda hoje é única por conta — Val e Daniel não se distinguem, ver
   `docs/plans/agentes-agenda-melhorias-futuras.md` M1).

## Como validar

- Testes unitários: ocupado 15–16h com margem 15 → 16h recusado, 16h15 aceite; margem 0 = igual a hoje.
- Bancada: aplicar `session_buffer_minutes=15` na conta local e correr `python simular.py p-seguidas M1`
  → a IA propõe 16h15 (ou o horário seguinte válido) em vez de 16h.
- Regressão: `python simular.py pos-marcacao M1` (remarcação do próprio lead mantém a duração).
