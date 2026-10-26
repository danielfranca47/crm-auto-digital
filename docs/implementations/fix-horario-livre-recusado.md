# A IA diz que um horário livre "não está disponível"

**Status:** Aguardando Plan Mode
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

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`.
