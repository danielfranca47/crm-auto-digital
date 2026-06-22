# Follow-up Proativo — Disparo Automático por Inatividade (Híbrido Agendador e SDR)

> Contexto: identificado ao validar o roteiro de teste do agente demo
> (`docs/marketing/comercial/agente-demo.md`, secção "Roteiro de Teste no Playground")
> contra o estado real do código. O Cenário 3 (recuperação de paciente/lead inativo)
> "passa" no roteiro porque testa só a resposta textual da IA — mas o disparo
> automático do follow-up não existe, depende do operador arrastar o card manualmente.
>
> Meta: ter a base deste item incorporada para que o Híbrido Agendador
> (ex.: massoterapia — pacientes recorrentes) e o SDR (ex.: leads frios) consigam
> performar de verdade como demonstrado, não só conversar como se performassem.
>
> Nota: o item original deste documento sobre cancelamento/reagendamento real de
> compromisso (M1) já foi implementado e graduado para `docs/architecture/agenda.md`
> e `docs/architecture/agents.md` — itens deixados de fora dessa implementação estão
> em `docs/plans/cancelamento-reagendamento-melhorias-futuras.md`.

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
  o lead ter confirmado de fato); este documento é sobre **quem inicia** o
  follow-up, não sobre se a IA decide certo.
- `docs/architecture/followup.md` documenta o mecanismo atual (reconciliador,
  estados, cart recovery) que M2 estende.
