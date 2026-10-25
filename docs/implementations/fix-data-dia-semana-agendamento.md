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

### Fase 2 — Prompt: tabela mais fácil de consultar + "marcação já gravada"

**Objetivo:** menos datas erradas à partida e nenhuma confirmação pedida duas vezes.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | Tabela com `dd/mm` e marcas `[hoje]`/`[amanhã]`; bloco "MARCAÇÃO JÁ GRAVADA NESTE TURNO" em pré-agendamento e agendamento quando `meeting_scheduled=true` |
| `docs/prompts_llms.md` | Reflete os blocos novos |

### Fase 3 — Validação na bancada + docs de arquitetura

**Objetivo:** medir na bancada Sensi Vitae com o código da worktree; atualizar `docs/architecture/`.

---

## Checks de Validação

### Cenário U1 — Testes unitários do guardrail
- [ ] `pytest backend-executors/tests` passa (novos casos + existentes)

### Cenário P1 — Dia da semana pedido = dia gravado (bancada local)
- [ ] Correr `p-cedo-tarde`, `p-ricardo`, `pos-marcacao`, `p-ruben`, `p-micas`, `p-joaquim` com o código da worktree até ~15 marcações
- [ ] Confirmar: 0 marcações com data que não cai no dia pedido; a data escrita na "Experiência Agendada" = data gravada

### Cenário P2 — Sem confirmação dupla
- [ ] Nos mesmos cenários, quando o cliente diz "pode confirmar" ao aceitar, a resposta desse turno é a confirmação final (sem "Posso confirmar?")

### Cenário P3 — Remarcação
- [ ] `pos-marcacao`: "remarcar para quinta às 15h" → nova data cai numa quinta

---

## Ajustes Possíveis Pós-Implementação

- "terça da próxima semana" com a IA a escrever uma terça errada é corrigido para a terça mais próxima (não há forma determinística de distinguir sem perceber a frase). Fica no log `event=meeting_date_corrected`.
