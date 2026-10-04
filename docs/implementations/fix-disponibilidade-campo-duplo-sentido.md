# Separar "janela de resposta do agente" de "horários de atendimento do profissional"

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Autonomia:** manual
**Origem:** `docs/implementations/feat-workflows-por-gatilho.md` — "Evidência no código", ponto 7 (análise comparativa de janelas de horário pedida pelo utilizador em 03/10/2026)

---

## Motivação

Duas telas diferentes de "Configurar Agente" gravam no **mesmo campo** do AI
Profile (`availability_schedule`), com significados e formatos diferentes:

| Tela | O que o utilizador acha que está a configurar | Formato gravado |
|---|---|---|
| Pipeline → "Janela de horário" (`CamadaPipeline.tsx:331-378`) | Quando o agente **responde** — mensagens fora do horário ficam agendadas para a próxima abertura | JSON por dia da semana (`{"mon":"09:00-18:00",…}`), lido por `backend-crm/services/humanization.py:84-158` junto com `availability_mode` |
| Apresentação → "Disponibilidade de horários" (`CamadaApresentacao.tsx:241-261`) | Em que horários o **profissional atende**, para a IA propor horários de sessão | Texto livre ("Seg-Sex: 14h, 16h, 18h"), injetado no prompt de agendamento como "DISPONIBILIDADE DO PROFISSIONAL" (`backend-executors/app/services/decision_engine.py:4319, 4376`) |

Consequências:

- Definir uma janela de resposta personalizada faz a IA receber JSON cru como
  "disponibilidade do profissional" (e a caixa de texto da Apresentação passa a
  mostrar esse JSON).
- Escrever os horários de atendimento em texto livre faz a janela de resposta
  personalizada deixar de funcionar (`_parse_schedule` não consegue ler o texto
  e devolve "sem janela").
- O valor de fábrica do campo é um JSON "seg–sex 09:00–18:00"
  (`frontend-crm/src/types/agente.ts:462`), que chega ao prompt de agendamento
  como se o profissional tivesse declarado essa disponibilidade — mesmo em
  contas que nunca configuraram nada.

Comportamento desejado: dois campos distintos, com nomes distintos na tela —
"Quando o agente responde" e "Horários de atendimento do profissional" — e uma
migração que preserve o que cada conta já tem gravado (JSON → janela de
resposta; texto livre → horários de atendimento).

## Área do sistema

- `backend-core/app/models/ai_profile.py` (`availability_schedule`, `availability_mode`) + `app/db.py` + `app/api/ai_profiles.py`
- `backend-crm/services/humanization.py` (janela de resposta)
- `backend-executors/app/services/decision_engine.py` (`_build_child_prompt_agendamento`, bloco "DISPONIBILIDADE DO PROFISSIONAL")
- `frontend-crm/src/components/agente/CamadaPipeline.tsx`, `CamadaApresentacao.tsx`, `src/types/agente.ts`, `src/services/api.ts`
- Docs a atualizar: `docs/architecture/humanization.md`, `agents.md`, `agenda.md`, `admin-agents-contract.md` (campo novo no AI Profile)

Diagnóstico (Plan Mode) ainda não feito — próximo passo é seguir o Passo 0 de
`_guia-documentar-implementacao.md` antes de qualquer código. A verificar nesse
passo: que formato cada conta de produção tem hoje no campo (decide a migração)
e se `followup_allowed_hours` deve passar a ser a "janela geral de envios por
iniciativa própria" usada também pelos workflows por gatilho.
