# Follow-up Proativo e Ações Reais de Agenda — Híbrido Agendador e SDR

> Contexto: identificado ao validar o roteiro de teste do agente demo
> (`docs/marketing/comercial/agente-demo.md`, secção "Roteiro de Teste no Playground")
> contra o estado real do código. Os Cenários 2 (cancelamento) e 3 (recuperação de
> paciente/lead inativo) "passam" no roteiro porque testam só a resposta textual da
> IA — mas a ação real por trás da resposta não existe ou não é automática.
>
> Meta: ter a base destes dois itens incorporada para que o Híbrido Agendador
> (ex.: massoterapia — pacientes recorrentes) e o SDR (ex.: leads frios) consigam
> performar de verdade como demonstrado, não só conversar como se performassem.

---

## M1 — Ação real de cancelamento/reagendamento de compromisso

**Prioridade: ALTA**

**Estado actual:** `backend-executors/app/services/meeting_scheduler.py` só implementa
`handle_meeting_scheduled()` — criação de um novo appointment. Não existe nenhum
equivalente para cancelamento ou reagendamento. Quando o lead/paciente pede para
cancelar, a LLM responde no tom certo (reconhece, oferece reagendar — instrução de
`custom_instructions`), mas isso é só texto: o appointment original continua
`status="pending"` no banco, intocado. Se o lead aceitar um novo horário, o sistema
trata isso como uma nova marcação (`handle_meeting_scheduled` de novo) — o resultado
prático é dois appointments na agenda (o antigo "fantasma" + o novo), em vez de um só
atualizado.

**Risco concreto:**
- Lembretes (`whatsapp.appointment.reminder`) continuam agendados para a sessão
  "cancelada" porque nada marca o appointment como `canceled`.
- Push para o Google Calendar do utilizador (quando conectado) nunca remove/atualiza
  o evento original.
- Se o novo horário pedido coincidir com o horário que o operador esperava estar
  livre (porque a sessão antiga "ainda existe" para o sistema), pode gerar bloqueio
  de conflito (`409`) indevido em agendamentos futuros.

**Afecta:** qualquer agente em `agent_mode=agenda` com agendamento real ativo —
Híbrido Agendador (`hybrid_scheduler`) e SDR em modo agendamento (`sdr_padrao`).

**O que precisaria existir (a confirmar em Plan Mode na implementação):**
- Um sinal estruturado equivalente a `meeting_scheduled` para intenção de
  cancelamento/reagendamento, que a Mãe/Filha de agendamento consiga emitir.
- Uma ação correspondente no executor que efetivamente atualize o appointment
  original (`status="canceled"` ou um novo `start_at` no mesmo registo) em vez de
  apenas criar um novo — `routes/appointments.py` já tem os campos de `status`/
  `outcome` para isto, falta a ponte entre o sinal da IA e essa atualização real.

---

## M2 — Disparo automático de follow-up por inatividade (sem depender do operador arrastar o card)

**Prioridade: ALTA**

**Estado actual:** a única forma de iniciar um `followup_contract` para Agent 1
(`sdr_scheduler`) ou Agent 3 (`hybrid_scheduler`) é o operador arrastar manualmente o
card no Kanban para a coluna "follow-up" e preencher o `FollowUpTransitionModal`
(`frontend-crm/src/components/KanbanBoard.tsx` é o único ponto de entrada confirmado
no código). A página de Follow-up (`FollowUpCenter.tsx`/`FollowUpEdit.tsx`) e o
reconciliador (`backend-crm/services/followup_reconciler.py`) só atuam sobre
contratos **já criados** — não existe nenhuma varredura periódica que detecte
"paciente/lead sem atividade há N dias" e crie o contrato por conta própria.

**Comparação com o que já existe:** Agent 2 (`closer_agressivo`/cart recovery) já
tem exatamente esse padrão de disparo automático —
`followup_state.start_cart_recovery_followup()` dispara sozinho quando o bot envia
um link de pagamento, sem qualquer ação do operador. Falta o equivalente para
Agent 1/3, mas baseado em **inatividade** (ausência de evento) em vez de uma ação
do próprio bot.

**Risco concreto:** a promessa de "recuperação automática de paciente inativo"
(Híbrido Agendador) e o equivalente para SDR (reengajar lead frio sem follow-up
manual) não se sustenta sem isto — depende inteiramente de o operador lembrar de
mover manualmente cada card, o que não escala para uma base de pacientes/leads
recorrentes.

**O que precisaria existir (a confirmar em Plan Mode na implementação):**
- Um critério de inatividade que crie o `followup_contract` automaticamente quando
  atingido (ex.: dias desde a última sessão concluída, ou desde a última mensagem),
  reaproveitando o conteúdo já configurável (`followup_postsession_instructions`,
  `followup_sdr_instructions`) para a mensagem em si — essa parte do mecanismo já
  funciona, só falta o gatilho.
- Provavelmente vive no mesmo reconciliador (ou um processo periódico análogo), já
  que ele já corre em loop assíncrono no lifespan do `backend-crm`.

**Perguntas de produto a decidir antes de implementar (não bloqueiam este registo,
mas bloqueiam a priorização em sprint):**
- O critério de inatividade é "dias desde a última sessão" (Híbrido Agendador),
  "dias desde a última mensagem" (SDR), ou os dois — configurável por operador ou
  fixo pela plataforma?
- Dispara para todo lead/paciente nessa condição, ou só para os elegíveis (ex.: não
  para quem já está em `client-list`/`disqualified`/`prospect-refused`)?
- Quantas tentativas/cadência — reaproveita os defaults de `followup_cadence`/
  `followup_max_attempts` já existentes, ou precisa de um perfil próprio?

---

## Relação com outros planos

- Diferente de `agentes-agenda-melhorias-futuras.md` (M3) — aquele item é sobre a
  **confiabilidade da decisão** de `meeting_scheduled` (a Mãe marcar confirmação sem
  o lead ter confirmado de fato); este documento é sobre **ações que faltam por
  completo** no backend (cancelar/reagendar) e sobre **quem inicia** o follow-up
  (M2), não sobre se a IA decide certo.
- `docs/architecture/followup.md` documenta o mecanismo atual (reconciliador,
  estados, cart recovery) que M2 estende.
