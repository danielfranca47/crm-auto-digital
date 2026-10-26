# A IA diz que um horário livre "não está disponível"

**Branch:** `fix/horario-livre-recusado`
**Status:** Em andamento
**Autonomia:** manual
**Origem:** `docs/plans/agentes-agenda-melhorias-futuras.md` — M12 (promovido pelo utilizador em 26/10/2026, depois dos testes PROD05/PROD06 do agente Sensi Vitae)

---

## Motivação

**Comportamento atual.** Quando o cliente pede serviço + dia + hora na mesma mensagem (ex.: "Lomi
Lomi de 60 min, sábado às 11h"), a Filha de agendamento responde em ~metade dos casos
"infelizmente esse horário não está disponível" e propõe outro — sem nenhum compromisso em
`calendar_busy_slots` e dentro do horário do terapeuta. Conta Sensi Vitae (Agente 03, produção
user_id 4), `scheduling_offer_style=confirm_exact`, agenda vazia a partir de 26/10/2026.

Exemplos do Playground de produção (26/10/2026, PROD05/PROD06):

| Cliente pediu | A IA respondeu | Devia |
|---|---|---|
| Lomi Lomi 60 min, sábado às 11h | "não podemos marcar no sábado às 11h… a primeira vaga é às 15h" | confirmar (Val sáb 11h–17h) |
| Lomi Lomi 90 min, terça às 14h | "o horário de terça às 14h já não está disponível" | confirmar |
| remarcar para quinta às 15h | "a Val não tem disponibilidade na quinta às 15h, mas às 16h" | remarcar |

Recusas corretas na mesma rodada (não podem deixar de acontecer): Val às 17h para 1h (17h é a hora
de ACABAR as sessões da Val); 21h (fora de qualquer horário).

Três formulações no `custom_instructions` (aceitar o pedido livre; "HORÁRIOS JÁ OCUPADOS" como única
fonte; o custo de perder o cliente) baixaram mas não eliminaram o comportamento (3 em 6 conversas
na última rodada). Remarcações e pedidos feitos em passos separados são quase sempre aceites.

**Horários do profissional hoje:** no `custom_instructions` da conta — Val seg–sáb 11h–17h (17h é a
hora de acabar); Daniel seg–sex 11h–19h30; sem domingo. O campo próprio para isto
(`professional_availability`) está em `fix-disponibilidade-campo-duplo-sentido`, ainda fora de
`main`, e também é texto livre.

**Comportamento desejado.** Se o horário pedido não tem nenhum compromisso e cabe no horário do
profissional, a IA confirma-o (ou pede só o dado que falta). Recusa só quando há conflito real ou o
horário está fora do horário de atendimento — e diz esse motivo.

---

## Área do sistema

- `backend-executors` — Filha de agendamento (`_build_child_prompt_agendamento`) e gestão
  pós-marcação (`_build_child_prompt_meeting_management`); `calendar_busy_slots` e
  `meeting_scheduler._has_conflict` já existem.
- Toca em instruções da IA → categoria que sobe sempre (`scripts/fila/categorias_que_sobem.py`).

---

## Como reproduzir

Bancada `.claude/agentes/sensi-vitae/` (ver `README.md`): `python simular.py <cenário> <rótulo>
[--prod]`. Cenários que expõem o erro: `p-ricardo`, `p-relax90`, `pos-marcacao`. Transcrições:
`tentativas/*PROD05*`, `tentativas/*PROD06*`.

---

## Problemas Identificados (estado anterior)

Diagnóstico feito reconstruindo offline o prompt real da Filha de agendamento no turno da recusa
(perfil de produção + config c13, conversa PROD05 `p-ricardo`):

1. **Nenhum facto sobre o horário pedido:** `_build_child_prompt_agendamento`
   (`backend-executors/app/services/decision_engine.py`) traz `HORÁRIOS JÁ OCUPADOS: nenhum
   compromisso encontrado` e a regra `confirm_exact` ("livre → confirme"), mas é a IA que tem de
   ligar "sábado às 11h" a essa lista e concluir que está livre.
2. **Três fontes de horário que se contradizem:** a regra `confirm_exact` manda verificar "contra a
   disponibilidade"; o bloco `DISPONIBILIDADE DO PROFISSIONAL` desta conta é a grelha 08:00–22:00
   (janela de resposta — campo de duplo sentido, `fix-disponibilidade-campo-duplo-sentido`); as
   instruções da conta mandam ignorá-la e usar Val 11h–17h / Daniel 11h–19h30.
3. **A hora pedida perde-se:** nas recusas, `meeting_datetime_candidate` já é a alternativa
   inventada (15h) ou null — nada guarda a hora que o cliente pediu.
4. **Achado lateral:** as instruções da conta entram 3 vezes no prompt (identidade, JSON `ai_profile`,
   bloco de instruções) — ~25 KB. Fora do âmbito (ver "Ajustes possíveis").

**Limite:** o horário de atendimento do profissional é texto livre (no `custom_instructions`, e o
campo novo `professional_availability` também é texto). O código só pode afirmar "a agenda está
livre"; "cabe no horário do terapeuta" continua a ser decisão da IA.

---

## Abordagem

```
Mensagem do lead (fase de agendamento ou remarcação)
  → requested_slot.find_requested_slot()
     hora: uma hora inequívoca na mensagem atual ("às 11h", "14h30", "15:00");
           não contam durações ("de 1h") nem limites ("depois das 19h", "a partir das")
     dia:  palavra de dia na mensagem atual, senão o último dia falado na conversa
           (meeting_date_guard.latest_day_word / resolve_day_reference)
     agenda: calendar_busy_slots + _has_conflict (duração por omissão do perfil)
  ├─ sem hora/dia inequívocos → nada muda
  ├─ livre   → bloco no FIM do prompt: "o lead pediu sábado, 31/10, às 11h; a agenda NÃO tem
  │            nenhum compromisso; só recuse se não couber no horário de atendimento, e diga isso"
  └─ ocupado → bloco: "colide com o compromisso das X às Y — diga que está ocupado e proponha outro"
```

---

## Plano de Implementação

### Fase 1 — Facto da agenda no prompt

**Objetivo:** a Filha recebe do sistema, como facto, se o horário pedido está livre na agenda.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/requested_slot.py` | Novo: `requested_time`, `find_requested_slot`, `build_agenda_fact_block` |
| `backend-executors/app/services/meeting_date_guard.py` | `latest_day_word` e `resolve_day_reference` públicos (mesma leitura de dias do guardrail de datas) |
| `backend-executors/app/services/decision_engine.py` | `_recent_conversation()` (partilhado com `_apply_meeting_date_guard`); `_build_agenda_fact_block()` no fim dos prompts de agendamento e de gestão pós-marcação |
| `backend-executors/tests/test_requested_slot.py` | Novo: frases reais das transcrições + ligação aos prompts |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f3046bd` | `requested_slot.py` + bloco "agenda livre" nos prompts de agendamento e gestão pós-marcação |

### Fase 2 — Nova tentativa quando a IA recusa um horário livre — [⏭️] não necessária

Ficou condicionada à bancada: com o veredicto completo da Fase 3 (agenda + horário de
atendimento decididos em código) houve 0 recusas erradas, por isso não se acrescentou a chamada
extra.

### Fase 3 — Horário de atendimento decidido em código + validação na bancada + docs

A bancada mostrou que só a agenda não chega:

| Rodada (15 conversas) | O que a Filha recebia | Horário livre recusado | Fora do horário aceite |
|---|---|---|---|
| Antes (PROD05+PROD06, produção) | nada | 8 de 22 | 1 de 4 |
| M12a | "a agenda está livre; aceite se cabe no horário de atendimento" | 2 de 15 | **3 de 3** (Val às 17h para 1h) |
| M12b | "confira primeiro o horário de atendimento (a sessão acabaria às X)" | 8 de 24 | 0 de 9 |
| **M12c** | veredicto completo, decidido em código | **0 de 19** | **0 de 7** |

Com o prompt sozinho era uma gangorra: empurrar para aceitar fazia aceitar fora do horário;
pedir para conferir o horário fazia a IA errar a conta ("não temos sessões aos sábados"; "a sessão
de 90 min terminará às 15h30", e recusava com a Val até às 17h). Decisão do utilizador (26/10/2026):
a IA lê o texto dos horários uma vez e o código decide.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/professional_hours.py` | Novo: lê o horário de atendimento do texto do perfil numa tabela (1 chamada por texto, cache em memória), `check()` cabe / não cabe + início sugerido |
| `backend-executors/app/services/llm_service.py` | `generate_professional_hours()` |
| `backend-executors/app/services/requested_slot.py` | Duração dita pelo lead (`requested_duration`); bloco com veredicto (livre e cabe / fora / dia sem atendimento) e o texto sem tabela como recurso |
| `backend-executors/app/services/decision_engine.py` | `_build_agenda_fact_block` consulta a tabela; bloco também no pré-agendamento (era de lá a recusa que sobrava no M12a) |
| `backend-executors/tests/conftest.py` | Nos testes nunca há chamada real para ler horários |
| `backend-executors/tests/test_professional_hours.py`, `test_requested_slot.py` | Tabela da Sensi Vitae, 17h/21h/9h/domingo, cache, falhas, ligação ao prompt |
| `docs/architecture/pipeline-phases.md`, `docs/prompts_llms.md` | "Verificação do horário pedido"; 1.4.5 e mapa de injeções |

Tabela lida pela IA na bancada (texto de produção, c13): Val seg–sáb 11h–17h, Daniel seg–sex
11h–19h30 — igual às instruções. Uma única leitura em toda a rodada M12c.

### Relatório da Fase 3 — o que mudou na prática

**Antes:** com serviço + dia + hora na mesma mensagem, a Lara dizia "esse horário não está
disponível" em cerca de metade dos pedidos, com a agenda vazia; e às vezes aceitava uma sessão que
acabava depois de a Val sair.
**Agora:** o sistema lê uma vez os horários da Val e do Daniel a partir das instruções da conta e,
a cada pedido com dia e hora, decide sozinho se está livre e se cabe. A Lara recebe a decisão
pronta: em 15 conversas simuladas aceitou todos os 19 pedidos válidos e recusou os 7 inválidos
(Val às 17h, 21h, 9h) com o motivo certo e uma alternativa que cabe.
**Para validar:** Cenários P1 e P2 (marcados abaixo); C1 no Playground de produção depois do merge.

---

## Checks de Validação

### Cenário U1 — Testes unitários
- [x] `pytest backend-executors/tests` passa
- **Validado em:** 26/10/2026 — 401 passed

### Cenário P1 — Horário livre pedido de uma vez é aceite (bancada local)
- [x] `p-ricardo`, `p-relax90`, `pos-marcacao` ×3 com o código da worktree (perfil local = c13 de produção)
- [x] Confirmar: nenhum "não está disponível / sem vaga / ocupado" para um horário livre dentro do horário do terapeuta (antes: ~metade)
- **Validado em:** 26/10/2026 — rodada M12c: 0 de 19 pedidos válidos recusados (antes 8 de 22)

### Cenário P2 — Recusas corretas continuam
- [x] `p-val-17h` (Val às 17h para 1h) e `p-cedo-tarde` (21h) ×3
- [x] Confirmar: continua a recusar, com o motivo do horário de atendimento
- **Validado em:** 26/10/2026 — rodada M12c: 7 de 7 recusados com "fora do horário de atendimento" e alternativa que cabe (16h com a Val; 18h30 com o Daniel)

### Cenário C1 — Playground de produção depois do merge
- [ ] Mesmos cenários com `--prod`

---

## Ajustes Possíveis Pós-Implementação

- As instruções da conta entram 3 vezes no prompt da Filha de agendamento (identidade,
  `ai_profile` em JSON e bloco "INSTRUÇÕES PERSONALIZADAS") — ~25 KB por chamada; tirar a cópia do
  JSON reduziria custo e ruído.
- O horário de atendimento é lido do texto por IA (uma vez por texto). Um campo estruturado por
  profissional no AI Profile tiraria essa leitura e o risco de uma tabela mal lida.
- A agenda continua a ser uma só por conta: um compromisso da Val bloqueia o mesmo horário do
  Daniel (plans: agentes-agenda M1).
- A cache da tabela de horários é por processo: cada arranque do backend-executors volta a ler o
  texto uma vez.
