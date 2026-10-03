# Separar "janela de resposta do agente" de "horários de atendimento do profissional"

**Branch:** `worktree-fix+disponibilidade-campo-duplo-sentido` (worktree `.claude/worktrees/fix+disponibilidade-campo-duplo-sentido` — a ferramenta de worktree troca `fix/<slug>` por este formato)
**Status:** Em andamento — Fases 1 e 2 implementadas; Cenários P1–P4 e C1 por validar
**Origem:** `docs/implementations/feat-workflows-por-gatilho.md` — "Evidência no código", ponto 7 (análise comparativa de janelas de horário pedida pelo utilizador em 03/10/2026)

---

## Motivação

Duas telas diferentes de "Configurar Agente" gravam no **mesmo campo** do AI
Profile (`availability_schedule`), com significados e formatos diferentes:

| Tela | O que o utilizador acha que está a configurar | Formato gravado |
|---|---|---|
| Pipeline → "Janela de horário" | Quando o agente **responde** — mensagens fora do horário ficam agendadas para a próxima abertura | Grade por dia da semana em JSON (`{"mon":"09:00-18:00",…}`) |
| Apresentação → "Disponibilidade de horários" | Em que horários o **profissional atende**, para a IA propor horários de sessão | Texto livre ("Seg-Sex: 14h, 16h, 18h") |

Comportamento desejado: um campo para cada coisa, com nomes distintos na tela,
e os dados já gravados preservados. É o passo 1 da ordem acordada em
`feat-workflows-por-gatilho.md` — a janela de envios dos workflows e a agenda
por profissional dependem desta separação.

---

## Problemas Identificados (estado anterior)

1. **Um campo, dois sentidos:** `CamadaPipeline.tsx:331-378` (`DrawerHorarioTrabalho`)
   grava a grade JSON em `availability_schedule`; `CamadaApresentacao.tsx:254-259`
   grava texto livre no mesmo campo. Cada tela sobrescreve o que a outra gravou.
2. **A IA recebe a janela de resposta como se fosse a agenda do profissional:**
   `decision_engine.py::_build_child_prompt_agendamento` injetava
   `availability_schedule` no bloco "DISPONIBILIDADE DO PROFISSIONAL" — incluindo
   o JSON cru da janela de resposta.
3. **Texto livre desliga a janela personalizada em silêncio:**
   `humanization.py::_parse_schedule` não consegue ler texto livre, devolve "sem
   janela" e nada é bloqueado, embora a tela continue a mostrar "Personalizado".
4. **Disponibilidade inventada:** o valor de fábrica do campo
   (`frontend-crm/src/types/agente.ts:462`, JSON seg–sex 09:00–18:00) é gravado no
   perfil a cada "Salvar" (`api.ts:1557, 1679`) e chega à IA como disponibilidade
   declarada, mesmo em contas que nunca configuraram nada. Na caixa de texto da
   Apresentação aparece como código.

---

## Abordagem

`availability_mode` + `availability_schedule` ficam só com a **janela de
resposta** (os nomes já formam par e é o que `humanization.py` lê). Os horários
de atendimento ganham um campo próprio, `professional_availability` (texto).

```
Perfil existente (arranque do backend-core, uma vez por perfil)
  availability_schedule preenchido e professional_availability ainda NULL
    ├─ é a grade JSON por dia da semana
    │     → fica onde está (janela de resposta)
    │     → cópia legível em professional_availability ("Seg a Sex: 09:00–18:00")
    │       — a IA continua a ver a mesma disponibilidade, sem ser código
    └─ é texto livre
          → movido para professional_availability; availability_schedule = NULL
          → availability_mode "custom" → "24h" (era o comportamento real: nada
            era bloqueado)

Fase de agendamento (backend-executors)
  professional_availability → bloco "DISPONIBILIDADE DO PROFISSIONAL"
  vazio → "DISPONIBILIDADE: não configurada" (a IA pergunta o horário preferido)

Janela de resposta (backend-crm, humanization.py) — sem mudança de lógica
  availability_mode + availability_schedule (grade JSON)
```

Decisão: converter a grade para texto em vez de deixar o campo novo vazio nas
contas existentes — vazio mudaria o comportamento da IA (deixaria de propor
horários) em contas que hoje funcionam com "seg–sex 09–18". Contas novas nascem
com o campo vazio e um aviso de "não configurado" (Fase 2).

---

## Plano de Implementação

### Fase 1 — Backend: campo novo, migração e leitura pela IA

**Objetivo:** criar `professional_availability`, migrar os dados existentes e
fazer a filha de agendamento ler só esse campo.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | Coluna `professional_availability` |
| `backend-core/app/db.py` | Entrada em `ensure_ai_profile_columns()`; `ensure_professional_availability_backfill()` + `_parse_weekday_schedule()` / `_format_weekday_schedule_pt()` |
| `backend-core/app/main.py` | Chama o backfill no arranque, depois de `ensure_ai_profile_columns()` |
| `backend-core/app/api/ai_profiles.py` | Campo em `AIProfileBase` e `AIProfileUpdate` |
| `backend-core/tests/test_professional_availability_backfill.py` (novo) | Grade → texto; grade com intervalos; texto livre + `custom`; texto livre + outro modo; perfis já separados/vazios; idempotência |
| `backend-executors/app/services/decision_engine.py` | `_build_child_prompt_agendamento` lê `professional_availability`; perfil sem a chave (core ainda sem a coluna, durante o deploy) cai no campo antigo |
| `backend-executors/tests/test_scheduling_offer_style.py` | Usa o campo novo; grade da janela de resposta não aparece como disponibilidade; recuo para o campo antigo |
| `backend-crm/tests/test_humanization_availability_window.py` (novo) | Primeira cobertura da janela de resposta: 24h, horário comercial, grade personalizada, texto livre não bloqueia |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `ecf6bdc` | Campo `professional_availability`, migração no arranque, leitura pela filha de agendamento, testes |

**Detalhes do commit `ecf6bdc`:**
- `backend-core/app/db.py` — `ensure_professional_availability_backfill()` separa os dados existentes (só toca perfis com `professional_availability` ainda NULL)
- `backend-core/app/models/ai_profile.py`, `app/api/ai_profiles.py`, `app/main.py` — coluna, schemas e chamada no arranque
- `backend-executors/app/services/decision_engine.py` — `_build_child_prompt_agendamento` usa `professional_availability`
- Testes: 6 de migração (core), 7 do prompt de agendamento (executors), 6 da janela de resposta (crm)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** os horários em que o profissional atende e os horários em que a Lara
responde viviam no mesmo campo. A Lara recebia a janela de resposta (em código)
como se fosse a agenda do profissional.
**Agora:** por baixo, cada coisa tem o seu campo, e os dados de cada conta são
separados sozinhos no próximo arranque do sistema — sem mudar o que a Lara já
propunha. As telas ainda não mudaram (Fase 2): até lá, a caixa de texto da
Apresentação continua ligada ao campo antigo.
**Para validar:** nesta fase só há testes automáticos (19 novos/atualizados,
todos a passar; a suíte completa do backend-executors, 324 testes, continua verde). Os Cenários P1–P4 e C1, abaixo, validam-se depois da Fase 2.

### Fase 2 — Telas e documentação

**Objetivo:** cada tela passa a gravar no seu campo, com nomes que não se confundem.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | `professional_availability` em `AgentConfig`, valor de fábrica vazio |
| `frontend-crm/src/services/api.ts` | Ler e gravar o campo novo |
| `frontend-crm/src/components/agente/CamadaApresentacao.tsx` | Caixa de texto ligada ao campo novo; título "Horários de atendimento do profissional"; aviso de "não configurado" |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | Texto de ajuda da Janela de horário ("quando o agente responde") |
| `docs/architecture/humanization.md`, `agents.md`, `agenda.md`, `admin-agents-contract.md` | Refletir os dois campos |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(a registar)_ | Telas ligadas a campos distintos + docs de arquitetura |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** a caixa "Disponibilidade de horários" (Apresentação) e a "Janela de
horário" (Pipeline) gravavam no mesmo sítio — configurar uma apagava ou
estragava a outra, e a caixa podia mostrar código.
**Agora:** a Apresentação tem "Horários de atendimento do profissional" (quando
o profissional atende) e o Pipeline tem "Janela de horário" (quando a Lara
responde); cada uma guarda o seu valor, com um aviso em cada tela a dizer que
não é a outra. Com os horários de atendimento vazios aparece "Não configurado".
**Para validar:** Cenários P1, P2, P3, P4 e C1, abaixo.

---

## Checks de Validação

### Cenário P1 — A caixa mostra texto, não código
- [ ] Abrir Configurar Agente → Apresentação numa conta que já existia
- [ ] Confirmar: "Horários de atendimento do profissional" mostra "Seg a Sex: 09:00–18:00" (ou o texto que a conta já tinha), nunca `{"mon":…}`

### Cenário P2 — Uma tela não desfaz a outra
- [ ] Escrever horários de atendimento na Apresentação e salvar
- [ ] Em Pipeline → Janela de horário, escolher "Personalizado", definir uma grade e salvar
- [ ] Confirmar: de volta à Apresentação, o texto continua igual; reabrindo a Janela de horário, a grade continua igual

### Cenário P3 — A IA usa os horários do profissional
- [ ] Horários de atendimento "Ter e Qui: 14h, 16h"; Janela de horário "24 horas"
- [ ] No Playground, pedir um agendamento
- [ ] Confirmar: a Lara propõe horários de terça/quinta

### Cenário P4 — Conta sem horários
- [ ] Apagar os horários de atendimento e salvar
- [ ] No Playground, pedir um agendamento
- [ ] Confirmar: a Lara pergunta que horário o cliente prefere, em vez de propor

### Cenário C1 — Janela de resposta real
- [ ] Janela de horário "Personalizado" com uma grade que exclui a hora atual
- [ ] Enviar uma mensagem real pelo WhatsApp
- [ ] Confirmar: a resposta fica agendada para a próxima abertura (não sai de imediato)

---

## Ajustes Possíveis Pós-Implementação

- **Mensagem recebida antes da abertura do dia só é respondida no dia seguinte**
  (encontrado ao escrever os testes da janela, 03/10/2026). Com janela
  seg 10:00–16:00, uma mensagem de segunda às 07:00 fica agendada para **terça**
  às 10:00, não para segunda às 10:00 — `humanization.py::next_available_at` só
  procura a próxima abertura a partir do dia seguinte (o ciclo começa em
  `delta_days = 1`). Afeta os modos "Horário comercial" e "Personalizado"; é
  independente do campo com duplo sentido. Proposta: Fase 3 deste arquivo.
- Testes antigos a falhar sem relação com esta mudança: 8 em
  `backend-core/tests` (`test_ai_profile_agent_mode.py`,
  `test_ai_profile_timezone_persistence.py` — chamam `create_or_replace_ai_profile`
  sem o argumento `background_tasks`, e um bloqueio de arquivo temporário no
  Windows) e 4 em `backend-crm/tests/test_meeting_management_gate.py`. Ver
  `docs/plans/testes-backend-melhorias-futuras.md`.
- A janela geral de envios por iniciativa própria (follow-up + workflows) e o
  cadastro de profissionais com disponibilidade individual ficam para
  `feat-workflows-por-gatilho.md` e `docs/plans/agentes-agenda-melhorias-futuras.md`, M1.
- O recuo para o campo antigo em `_build_child_prompt_agendamento` (perfil sem
  a chave nova) só serve a janela de deploy — pode ser removido depois de o
  backend-core em produção já servir `professional_availability`.
