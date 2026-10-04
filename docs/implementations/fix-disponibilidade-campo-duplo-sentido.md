# Separar "janela de resposta do agente" de "horários de atendimento do profissional"

**Branch:** `worktree-fix+disponibilidade-campo-duplo-sentido` (worktree `.claude/worktrees/fix+disponibilidade-campo-duplo-sentido` — a ferramenta de worktree troca `fix/<slug>` por este formato)
**Status:** Em andamento — Fases 1 e 2 implementadas; Cenários P1–P4 validados (04/10/2026); C1 por validar — a simulação local mostrou que a janela de resposta é ignorada quando o buffer de mensagens está ligado (ver "Fase 3 — Diagnóstico")
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
| 1 | `4060db5` | Telas ligadas a campos distintos + docs de arquitetura |

**Detalhes do commit `4060db5`:**
- `frontend-crm/src/types/agente.ts`, `src/services/api.ts` — campo `professional_availability` no `AgentConfig`, lido e gravado no AI Profile
- `frontend-crm/src/components/agente/CamadaApresentacao.tsx` — caixa de texto passa a gravar em `professional_availability`; aviso "Não configurado"
- `frontend-crm/src/components/agente/CamadaPipeline.tsx` — texto de ajuda da Janela de horário
- `docs/architecture/humanization.md`, `agents.md`, `agenda.md`, `admin-agents-contract.md` — os dois campos documentados

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
- [x] Abrir Configurar Agente → Apresentação numa conta que já existia
- [x] Confirmar: "Horários de atendimento do profissional" mostra "Seg a Sex: 09:00–18:00" (ou o texto que a conta já tinha), nunca `{"mon":…}`
- **Validado em:** 04/10/2026 — conta de teste (grade seg–sex 09–20, sáb–dom 09–18 antes da migração): a caixa mostra "Seg a Sex: 09:00–20:00 / Sáb a Dom: 09:00–18:00", sem código e sem o aviso "Não configurado". No arranque, as outras contas com grade ficaram com "Seg a Sex: 09:00–18:00" e as sem grade ficaram vazias.

### Cenário P2 — Uma tela não desfaz a outra
- [x] Escrever horários de atendimento na Apresentação e salvar
- [x] Em Pipeline → Janela de horário, escolher "Personalizado", definir uma grade e salvar
- [x] Confirmar: de volta à Apresentação, o texto continua igual; reabrindo a Janela de horário, a grade continua igual
- **Validado em:** 04/10/2026 — texto "Ter e Qui: 14h, 16h" salvo na Apresentação; grade alterada para segunda 10:00–16:00 e salva no Pipeline. Depois de recarregar a página, o texto e a grade continuavam iguais (conferido também no banco: cada valor no seu campo).

### Cenário P3 — A IA usa os horários do profissional
- [x] Horários de atendimento "Ter e Qui: 14h, 16h"; Janela de horário "24 horas"
- [x] No Playground, pedir um agendamento
- [x] Confirmar: a Lara propõe horários de terça/quinta
- **Validado em:** 04/10/2026 — duas conversas. Na primeira, ao pedir "dias e horários esta semana", a Lara propôs "quinta-feira às 14h ou 16h". Na segunda, ao pedir "terça-feira à tarde", respondeu "às 14h e 16h". Nunca propôs horários da grade da janela de resposta (09–20h).
- **Observação:** na primeira conversa, depois de já ter proposto quinta, a Lara disse que não havia horário na terça quando o lead perguntou "na quarta de manhã ou na terça?" — a agenda estava vazia e a terça estava nos horários. Numa conversa nova, perguntando só pela terça, ofereceu-a corretamente. É variação da IA perante uma pergunta ambígua, não do campo; fica registado caso se repita.

### Cenário P4 — Conta sem horários
- [x] Apagar os horários de atendimento e salvar
- [x] No Playground, pedir um agendamento
- [x] Confirmar: a Lara pergunta que horário o cliente prefere, em vez de propor
- **Validado em:** 04/10/2026 — com a caixa vazia aparece o aviso "Não configurado — o bot pergunta ao lead que horário prefere". No Playground a Lara perguntou "qual dia você tem em mente?" e, escolhido o dia, "Que horário você prefere? Vou verificar a agenda para confirmar." — sem propor horários concretos.

### Cenário C1 — Janela de resposta real
- [x] Janela de horário "Personalizado" com uma grade que exclui a hora atual
- [ ] Enviar uma mensagem real pelo WhatsApp
- [ ] Confirmar: a resposta fica agendada para a próxima abertura (não sai de imediato)
- **Tentado em:** 04/10/2026 — **não validado.** O envio real não foi feito: a ligação WhatsApp da conta de teste local está desligada e as mensagens reais chegam ao servidor de produção, não ao ambiente local. Em substituição, a chegada da mensagem foi simulada no ambiente local (domingo 03:04, janela de domingo 09:00–18:00, ou seja, fechada):
  - **Buffer de mensagens em 8s (como a conta estava, e como nasce toda conta nova):** a resposta ficou agendada para 8 segundos depois — a janela foi ignorada. ❌
  - **Buffer desligado:** a resposta ficou agendada para segunda às 10:00 — a janela foi respeitada e leu a grade nova. ✅ (Mas saltou a abertura do próprio domingo às 09:00 — é o problema já anotado em "Ajustes Possíveis".)
  - Ver "Fase 3 — Diagnóstico", abaixo. O C1 só deve ser repetido com WhatsApp real depois dessa correção.

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

---

## Fase 3 — Diagnóstico (04/10/2026) — aguarda plano aprovado

### Problema identificado

O teste do Cenário C1 (simulação local) mostrou dois defeitos na janela de
resposta. Nenhum foi criado pelas Fases 1 e 2 — o código da janela não foi
alterado — mas ambos impedem validar o C1.

1. **Com o buffer de mensagens ligado, a janela de horário não é aplicada.**
   Em `backend-crm/services/whatsapp_inbound/inbound_handler.py:543-566`, quando
   `multi_message_buffer_seconds > 0` a resposta é agendada para "agora + buffer"
   e `compute_scheduled_at()` (a única chamada que consulta a janela) fica no
   ramo `else`, só para buffer igual a zero. O buffer nasce em 8s em toda conta
   (`backend-core/app/db.py:276`, `frontend-crm/src/types/agente.ts:436`), por
   isso, na prática, a "Janela de horário" não tem efeito a menos que o
   utilizador desligue o buffer. Medido: janela fechada + buffer 8s → resposta
   agendada para 8s depois.
2. **A abertura do próprio dia é saltada** (já anotado em "Ajustes Possíveis").
   Medido com buffer desligado: mensagem de domingo às 03:04, janela de domingo
   09:00–18:00 → resposta agendada para segunda às 10:00, em vez de domingo às
   09:00. Causa: `humanization.py::next_available_at` começa a procurar em
   `delta_days = 1`.

### Correção

Por definir em Plan Mode. O ponto a decidir é como combinar buffer e janela
(ex.: aplicar a janela ao instante "agora + buffer", mantendo a acumulação de
mensagens) e incluir o dia corrente na procura da próxima abertura.
