# Marcação gravada no dia errado (dia da semana trocado) e confirmação pedida duas vezes

**Branch:** `fix/data-dia-semana-agendamento`
**Status:** Em andamento
**Autonomia:** manual
**Origem:** `docs/plans/agentes-agenda-melhorias-futuras.md` — M11 (promovido a urgente pelo utilizador em 25/10/2026, depois dos testes do agente Sensi Vitae)

---

## Motivação

**Comportamento atual — data errada.** Quando o cliente pede um dia da semana ("sexta",
"sábado", "terça", "amanhã"), a IA de agendamento escreve e grava uma data que não
corresponde a esse dia. Exemplos reais do Playground de produção (25/10/2026, um domingo,
conta Sensi Vitae, `gpt-4o-mini`):

| Cliente pediu | A IA escreveu / gravou | Dia real dessa data |
|---|---|---|
| sexta às 11h | "Dia: 28/10 (sexta-feira)" → appointment 2026-10-28 | quarta |
| sábado às 15h | "Dia: 29/10 (sábado)" → 2026-10-29 | quinta |
| terça às 15h | "Dia: 31/10 (terça-feira)" → 2026-10-31 | sábado |
| amanhã às 11h | "quarta-feira, 28/10" → 2026-10-28 | quarta (devia ser segunda 26/10) |

Medição: **6 de 15 marcações no dia errado** no Playground de produção; 2 de ~20 no
Playground local. A tabela de dias (`_calendar_lookup_table_pt()`) está correta e chega às
Filhas que marcam, mas a IA ignora-a e usa o calendário "de memória". Instruções no
`custom_instructions` da conta (procurar sempre a linha da tabela, propor só com o dia da
semana) não reduziram o erro. O cliente recebe a confirmação com o dia da semana certo e a
data errada — e a sessão fica gravada na agenda (e nos lembretes) no dia errado.

**Comportamento atual — confirmação pedida duas vezes.** Quando o cliente já diz "pode
confirmar" ao aceitar o horário, a Mãe marca `meeting_scheduled=true` e o appointment é
criado, mas a Filha responde no mesmo turno com o resumo + "Posso confirmar?" — o cliente vê
um pedido de confirmação de algo que já ficou gravado e às vezes nunca recebe a mensagem final
de confirmação.

**Comportamento desejado.**
- A data gravada (`meeting_datetime_candidate`) e a data escrita na mensagem correspondem
  sempre ao dia que o cliente pediu. Se a IA escrever um dia da semana que não bate com a data,
  o sistema não grava o appointment com a data errada.
- No turno em que a marcação fica gravada, a Filha envia a confirmação final em vez de voltar a
  perguntar.

**Por que agora:** a conta Sensi Vitae (Agente 03) está ligada a clientes reais desde
25/10/2026 com o agente a marcar sozinho; uma data errada faz o cliente aparecer no dia errado.

---

## Área do sistema

- `backend-executors` — Filhas que propõem/confirmam horário (apresentação, pré-agendamento,
  agendamento, gestão pós-confirmação/reagendamento) e a criação do appointment
  (`meeting_scheduler`).
- Não precisa de dados novos no ContextBundle: a correção vive toda dentro de `decide()`, que
  serve igualmente o Playground e o WhatsApp real (paridade mantida).
- Toca em instruções da IA → categoria que sobe sempre (`scripts/fila/categorias_que_sobem.py`).

---

## Como reproduzir

Bancada de testes da conta Sensi Vitae em `.claude/agentes/sensi-vitae/` (fora do git; ver o
`README.md` dessa pasta): `python simular.py <cenário> <rótulo>` corre conversas com um cliente
simulado por IA no Playground local isolado (portas 8100–8102); com `--prod` corre no Playground
de produção da conta (nada é enviado por WhatsApp, marcações de teste apagadas no fim).
Cenários que mais expõem o erro: `p-cedo-tarde`, `p-ricardo`, `pos-marcacao`, `p-ruben`.
Transcrições com o erro: `tentativas/*PROD02*`, `tentativas/*PROD03*`.

---

## Problemas Identificados (estado anterior)

1. **Nenhuma verificação "dia da semana ↔ data":** `backend-executors/app/services/decision_engine.py`
   — `_normalize_scheduler_child_signals()` só normaliza `meeting_proposed`/candidato, e
   `meeting_scheduler.parse_meeting_candidate()` só faz parse ISO e recusa datas no passado. A data
   que a Filha devolve vai direta para o appointment.
2. **O erro está na conversão, não na intenção:** nas transcrições PROD02/PROD03 o dia da semana
   escrito bate quase sempre com o que o cliente pediu (sexta, sábado, terça); a data ao lado é que
   está errada. Só o caso "amanhã" tem os dois errados.
3. **Tabela de dias em UTC:** `_calendar_lookup_table_pt()` usa `datetime.utcnow()`, não o fuso do
   perfil — perto da meia-noite o "hoje" da tabela pode não ser o "hoje" do cliente.
4. **Filhas de pré-agendamento e agendamento não sabem que a marcação já foi gravada:** só a
   apresentação tem o bloco "CONFIRMAÇÃO ESTRUTURADA OBRIGATÓRIA" quando `meeting_scheduled=true`
   (`decision_engine.py`, `_build_child_prompt_apresentation`). Nas outras duas, as instruções da
   conta ("resumo + Posso confirmar?") vencem, mesmo com o cliente a ter dito "pode confirmar".

---

## Abordagem

```
Filha devolve message_text + meeting_datetime_candidate (+ novo meeting_day_reference)
  → meeting_date_guard.reconcile_meeting_date()
     referência do dia: meeting_day_reference  ou  dia da semana escrito junto da data
     ├─ "hoje/amanhã/depois de amanhã" → hoje+0/1/2 (fuso do perfil)
     ├─ dia da semana → data já cai nesse dia? mantém : próxima ocorrência (amanhã…+7)
     ├─ "dd/mm" explícito → essa data
     └─ sem referência → não mexe
     se corrigiu: troca a data do candidato (mantém a hora) e reescreve a data/dia no texto
  → appointment gravado com a data corrigida; cliente vê a mesma data
```

---

## Plano de Implementação

### Fase 1 — Guardrail de data em código

**Objetivo:** a data gravada e a data escrita correspondem sempre ao dia que o cliente pediu.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_date_guard.py` | Novo: resolve a referência do dia, corrige candidato e texto |
| `backend-executors/app/services/decision_engine.py` | Chama o guardrail depois da Filha (pipeline normal e gestão pós-marcação); novo sinal `meeting_day_reference` nos schemas das Filhas que marcam; tabela de dias no fuso do perfil |
| `backend-executors/tests/test_meeting_date_guard.py` | Novo: casos reais das transcrições |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `48bd050` | guardrail de data + sinal `meeting_day_reference` + tabela no fuso do perfil |

**Detalhes do commit `48bd050`:**
- `meeting_date_guard.py` — `reconcile_meeting_date()`: referência do dia (sinal da Filha, ou dia da semana/"amanhã" colado à data na mensagem; "segunda" sozinho e "até amanhã!" não contam) → data; corrige candidato (mantém hora/offset) e reescreve `dd/mm`, "dd de mês" e o dia da semana errado no texto.
- `decision_engine.py` — `_apply_meeting_date_guard()` chamado em `compose_decision_output()` (depois de `_apply_mode_guardrails`) e em `_decide_post_meeting_management()`, antes de o `meeting_scheduler` ler `child_signals_structured`; `_MEETING_DAY_REFERENCE_RULE` nos schemas de apresentação, agendamento e gestão pós-marcação; `_calendar_lookup_table_pt(tz_name=...)`.
- `tests/test_meeting_date_guard.py` — 17 casos (sexta→30/10, sábado→31/10, terça dita num domingo→27/10, amanhã→26/10 com dia e data errados, remarcação quinta→29/10, datas já certas não mudam, "segunda opção", data por extenso, ligação ao decision_engine).

### Relatório da Fase 1 — o que mudou na prática

**Antes:** a data que a IA escrevia ia direta para a agenda — "Dia: 28/10 (sexta-feira)" gravava a sessão numa quarta.
**Agora:** antes de gravar, o sistema confere a data contra o dia que o cliente pediu (sexta, sábado, amanhã…). Se não bater, corrige a data na agenda e na mensagem que o cliente recebe — "Dia: 30/10 (sexta-feira)". Quando a IA já acertou, nada muda.
**Para validar:** Cenários U1, P1 e P3.

### Fase 2 — Prompt: tabela mais fácil de consultar + "marcação já gravada"

**Objetivo:** menos datas erradas à partida e nenhuma confirmação pedida duas vezes.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Tabela com `dd/mm` e marcas `[hoje]`/`[amanhã]`; bloco "MARCAÇÃO JÁ GRAVADA NESTE TURNO" em pré-agendamento e agendamento quando `meeting_scheduled=true` |
| `docs/prompts_llms.md` | Reflete os blocos novos |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `55d6ede` | bloco "marcação já gravada" + novo formato da tabela de dias + `docs/prompts_llms.md` |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** quando o cliente dizia "pode confirmar" ao aceitar o horário, a marcação ficava gravada mas a IA respondia com o resumo e "Posso confirmar?" — às vezes o cliente nunca recebia a "Experiência Agendada". A tabela de dias vinha num formato (`2026-10-30 (sexta-feira)`) diferente do que a IA escreve.
**Agora:** nesse turno a IA recebe a indicação de que a marcação já está gravada e envia logo a confirmação final no formato da conta. A tabela passa a ter as linhas como a IA as escreve (`sexta-feira, 30/10 → 2026-10-30`) e marca hoje/amanhã/depois de amanhã.
**Para validar:** Cenário P2 (e P1, que mede se há menos correções precisas).

### Fase 3 — Validação na bancada + ajustes que ela revelou + docs de arquitetura

**Objetivo:** medir na bancada Sensi Vitae com o código da worktree; atualizar `docs/architecture/`.

A bancada (código de `backend-executors` da worktree copiado para `ambiente/codigo/`, depois reposto o de `main`) revelou três problemas no que as Fases 1–2 tinham feito, corrigidos nesta fase:

| Rodada | Problema visto | Ajuste |
|---|---|---|
| F3r (18 conversas) | 2 confirmações duplas, ambas na rota de apresentação: o bloco "marcação já gravada" ficava a meio do prompt e a regra sales "peça confirmação" + as instruções da conta vinham depois | Bloco passa para o **fim** do prompt da apresentação |
| F3b (6) | Na **entrada** da fase o `meeting_scheduler` adia a criação (gate M3), mas o bloco dizia "já gravada" → "Experiência Agendada" enviada **sem marcação** (2×) | Bloco só entra quando não é entrada de fase (`_compute_is_phase_entry`) |
| F3b (6) | A IA pôs em `meeting_day_reference` a data que ela calculou ("27/10") em vez de "amanhã" | `dd/mm` no sinal só vale se o lead o escreveu; senão vale a última palavra de dia do lead |
| F3c (18) | A Lara propôs só horários de terça, o lead disse "Sim, confirmo", a IA confirmou "quarta-feira 28/10" (dia nunca falado) | No turno de confirmação, um dia nunca falado na conversa é trocado pelo último dia falado |

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_date_guard.py` | `lead_messages`, `earlier_messages`, `is_confirmation`; `_written_by_lead`, `_day_mentioned`, `_latest_lead_day_word` |
| `backend-executors/app/services/decision_engine.py` | `_apply_meeting_date_guard` passa as mensagens recentes; bloco no fim da apresentação e só fora da entrada de fase; regra do sinal reescrita |
| `backend-executors/tests/` | casos F3b1, F3c3, proposta de dia novo, entrada de fase, posição do bloco |
| `docs/architecture/pipeline-phases.md` | "Resolução de datas relativas e nomes de dia da semana" reescrita |
| `docs/prompts_llms.md` | 1.4.4 e mapa de injeções |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `0c14b78` | ajustes do guardrail e do bloco revelados pela bancada + docs de arquitetura |

**Resultados (contagem por script sobre os `.json` das tentativas):**

| | Antes (PROD02+PROD03, `main`) | Depois (F3c+F3d, código final menos a última regra / final) |
|---|---|---|
| Marcações | 15 | 20 + 13 |
| Data escrita ≠ data gravada | 5 | 0 + 0 |
| Dia gravado ≠ dia pedido | 6 | 1 (F3c3, corrigido pela última regra) + 0 |
| Confirmação pedida no turno em que já ficou gravada | 5 | 1 + 0 |
| "Experiência Agendada" sem marcação gravada | 0 | 0 + 0 |

Os "Posso confirmar?" restantes na F3d (2) são turnos de entrada de fase, em que a marcação ainda não é gravada (gate M3) — a marcação foi criada no "sim" seguinte, como deve.

### Relatório da Fase 3 — o que mudou na prática

**Antes (depois das Fases 1–2):** a data já não saía errada na maioria dos casos, mas a bancada mostrou buracos: às vezes a IA anunciava "Experiência Agendada" sem a marcação estar gravada, inventava um dia que ninguém tinha dito, ou punha como "palavras do cliente" uma data que ela própria tinha calculado.
**Agora:** em 31 conversas simuladas (33 marcações), todas ficaram no dia que o cliente pediu e com a mesma data na mensagem e na agenda; nenhuma confirmação sem marcação. Quando o cliente já disse "pode confirmar" e a marcação é gravada nesse turno, a IA envia logo a confirmação final; só volta a perguntar no turno em que o sistema ainda não grava (entrada na fase de agendamento).
**Para validar:** Cenários P1–P3 (marcados abaixo). Falta o teste com o Playground de produção (`--prod`) depois do merge.

---

## Checks de Validação

### Cenário U1 — Testes unitários do guardrail
- [x] `pytest backend-executors/tests` passa (novos casos + existentes)
- **Validado em:** 25/10/2026 — 341 passed (precisa do `.env` copiado para a worktree)

### Cenário P1 — Dia da semana pedido = dia gravado (bancada local)
- [x] Correr `p-cedo-tarde`, `p-ricardo`, `pos-marcacao`, `p-ruben`, `p-micas`, `p-joaquim` com o código da worktree até ~15 marcações
- [x] Confirmar: 0 marcações com data que não cai no dia pedido; a data escrita na "Experiência Agendada" = data gravada
- **Validado em:** 26/10/2026 — rodada final F3d: 12 conversas, 13 marcações, 0 dia errado, 0 texto ≠ gravado (rodada F3c: 20 marcações, 1 dia errado que motivou a última regra)

### Cenário P2 — Sem confirmação dupla
- [x] Nos mesmos cenários, quando o cliente diz "pode confirmar" ao aceitar, a resposta desse turno é a confirmação final (sem "Posso confirmar?")
- **Validado em:** 26/10/2026 — F3d: 0 turnos com marcação gravada + "Posso confirmar?"; 0 "Experiência Agendada" sem marcação. Exceção esperada: na entrada da fase (gate M3) a IA ainda pergunta e a marcação é criada no "sim" seguinte

### Cenário P3 — Remarcação
- [x] `pos-marcacao`: "remarcar para quinta às 15h" → nova data cai numa quinta
- **Validado em:** 26/10/2026 — F3c e F3d: todas as remarcações gravadas a 29/10 (quinta)

### Cenário C1 — Playground de produção depois do merge
- [x] `python simular.py <cenário> <rótulo> --prod` nos mesmos cenários, com o código já em produção
- [x] Confirmar: 0 marcações no dia errado (antes: 6 de 15)
- **Validado em:** 26/10/2026 — rodada PROD04 (9 conversas, código `1966761` confirmado nos serviços `backend-executors` e `worker backend-executors`): 9 marcações + 1 remarcação, todas no dia pedido e com a data escrita = data gravada; 0 falhas de validação da IA. Fora do âmbito deste fix (configuração da conta): uma sessão da Val marcada às 17h (acaba depois das 17h) e "horário indisponível" inventado em 3 conversas.

---

## Ajustes Possíveis Pós-Implementação

- "terça da próxima semana" com a IA a escrever uma terça errada é corrigido para a terça mais próxima (não há forma determinística de distinguir sem perceber a frase). Fica no log `event=meeting_date_corrected`.
- O rasto `decision_trace.meeting_date_guard` não aparece na resposta do Playground (que só devolve um subconjunto do trace) — as correções só se veem no log do executors. Expor no Playground ajudaria a medir em produção.
- Na entrada da fase de agendamento a IA continua a pedir confirmação mesmo quando o cliente já disse "pode confirmar" (o gate M3 adia a criação). Resolver isso é mexer no gate M3, fora do âmbito.
