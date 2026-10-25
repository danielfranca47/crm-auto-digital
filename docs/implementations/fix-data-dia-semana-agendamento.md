# Marcação gravada no dia errado (dia da semana trocado) e confirmação pedida duas vezes

**Status:** Aguardando Plan Mode
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
- Possivelmente `backend-crm` (orchestrator / ContextBundle), se a correção precisar de dados
  novos no contexto — respeitar a paridade Playground ↔ WhatsApp real
  (`docs/architecture/playground-parity.md`).
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

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o contexto acima
como ponto de partida, responder as 3 perguntas do Passo 0, e só depois de aprovado seguir para
a criação de branch + worktree (Passo 1).
