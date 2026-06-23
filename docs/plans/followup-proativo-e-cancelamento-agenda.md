# Follow-up Proativo — Persistência de Configuração, Disparo Automático e Camada Dedicada no AI Profile

> Contexto: identificado ao validar o roteiro de teste do agente demo
> (`docs/marketing/comercial/agente-demo.md`, secção "Roteiro de Teste no Playground")
> contra o estado real do código. O Cenário 3 (recuperação de paciente/lead inativo)
> "passa" no roteiro porque testa só a resposta textual da IA — mas o disparo
> automático do follow-up não existe, depende do operador arrastar o card manualmente.
>
> Meta original: ter a base deste item incorporada para que o Híbrido Agendador
> (ex.: massoterapia — pacientes recorrentes) e o SDR (ex.: leads frios) consigam
> performar de verdade como demonstrado, não só conversar como se performassem.
>
> Expansão: ao mapear, num levantamento posterior, os 10 tipos de follow-up de um guia
> de mercado (massoterapia BtoC/CtoC) contra a Central de Follow-ups real, ficou claro
> que o gatilho automático por si só não basta para entregar os tipos de follow-up "de
> maneira rica e clara" ao operador — falta também garantir que a configuração desses
> comportamentos *persiste no lugar certo* e que ela vive num lugar único e coerente do
> AI Profile em vez de espalhada.
>
> Nota: o item original deste documento sobre cancelamento/reagendamento real de
> compromisso (M1 antigo) já foi implementado e graduado para `docs/architecture/agenda.md`
> e `docs/architecture/agents.md` — itens deixados de fora dessa implementação estão
> em `docs/plans/cancelamento-reagendamento-melhorias-futuras.md`. A numeração abaixo foi
> reorganizada por ordem de execução (não por ordem de descoberta) e reaproveita o "M1"
> deixado livre por essa graduação.

**Ordem de execução:** M1 primeiro — M2 e M3 dependem dele para ter qualquer efeito
real. Construir o gatilho automático (M2) ou reorganizar a UI (M3) sobre uma gravação
que cai no lugar errado só reproduz o mesmo bug em campos novos.

---

## M1 — Sincronizar a tela do AI Profile com as colunas reais lidas pelo motor (campos de follow-up/agenda)

**Prioridade: ALTA** — bloqueia o M2 e o M3 terem qualquer efeito real.

**Estado actual:** confirmado em código (`frontend-crm/src/services/api.ts`,
`getConfig()`/`saveConfig()`, e `src/types/agente.ts:196` — comentário "Campos da
Camada 2 e 3 estendidos — armazenados em offer_pack") que os seguintes campos
relacionados a follow-up/agenda são lidos e gravados dentro do JSON auxiliar
`offer_pack`, e **não** nas colunas de topo do AI Profile que o motor real
(`backend-crm/services/followup_state.py`, `jobs_service.py`,
`backend-executors/app/services/decision_engine.py`,
`backend-crm/services/briefing_service.py`, `routes/appointments.py`) efetivamente
lê em runtime:

| Campo | UI grava em | Motor lê de |
|---|---|---|
| `followup_cadence` | `offer_pack.followup_cadence` | coluna `followup_cadence` |
| `followup_max_attempts` | `offer_pack.followup_max_attempts` | coluna `followup_max_attempts` |
| `appointment_reminder_offsets` | `offer_pack.appointment_reminder_h1`/`h2` (campos cosméticos diferentes) | coluna `appointment_reminder_offsets` |
| `briefing_enabled` / `briefing_channel` / `briefing_lead_time` | `offer_pack.*` | colunas equivalentes |
| `operator_whatsapp` | `offer_pack.operator_whatsapp` | coluna `operator_whatsapp` |
| `nurture_vs_discard_rule` | `offer_pack.nurture_vs_discard_rule` | coluna `nurture_vs_discard_rule` |

**Discrepância encontrada com outro plano:** `docs/plans/pipeline-configurable-fields.md`
marca as Etapas D (`appointment_reminder_offsets`), E (campos de briefing) e F
(`buying_signal_keywords`) como "✅ Implementado" — o que é verdade só do lado do
backend (coluna existe, API aceita). A tela nunca foi corrigida para escrever nesse
lugar; o status desse documento foi corrigido para reflectir isto (ver secção
"Relação com outros planos" abaixo).

**Risco concreto:** o operador preenche o campo na UI, salva, a tela não mostra erro
nenhum — mas o valor nunca chega ao motor. É um bug silencioso: parece que funcionou,
nunca funcionou. Qualquer campo novo do M2/M3 corre o mesmo risco se for implementado
seguindo o padrão actual do `AiProfile.tsx`.

**O que precisaria existir:**
- Corrigir `getConfig()`/`saveConfig()` em `api.ts` (e os tipos em `agente.ts`) para
  ler/escrever estes campos nas colunas de topo do AI Profile — são os mesmos nomes
  que o backend já aceita via `PUT /ai-profiles/me`, só o destino na tela está errado.
- Decidir se a correcção é feita de uma vez para todos os campos desta tabela (
  recomendado, já que é o mesmo padrão de bug repetido) ou campo a campo.
- **Validação end-to-end por campo corrigido:** preencher na UI → recarregar a
  página e confirmar que o valor persiste → confirmar no código/log que o motor real
  usa o valor (não o default). Sem este passo o bug pode "parecer" corrigido na tela
  sem de facto chegar ao motor.

**Fora de escopo deste documento:** o mesmo bug afecta campos fora do domínio de
follow-up/agenda — `qualification_score_threshold`, `objection_common`,
`hybrid_flow_style`, `origin_inbound_opener`/`origin_outbound_opener`,
`warming_social_proof`/`warming_session_preview`, `handoff_custom_text`,
`buying_signal_keywords` (ver tabela completa em
`docs/marketing/comercial/agente-demo.md`, secção "NOTA TÉCNICA"). Esses ficam fora
da prioridade deste plano — registar como item próprio se for decidido corrigi-los
todos de uma vez.

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
recorrentes. Sem isto, 3 dos 10 tipos de follow-up do guia de mercado de massoterapia
(cold outreach, check-in de cliente inativo, re-engagement) não funcionam de forma
autônoma — só por ação manual do operador.

**O que precisaria existir (a confirmar em Plan Mode na implementação):**
- Um critério de inatividade que crie o `followup_contract` automaticamente quando
  atingido (ex.: dias desde a última sessão concluída, ou desde a última mensagem),
  reaproveitando o conteúdo já configurável (`followup_postsession_instructions`,
  `followup_sdr_instructions`) para a mensagem em si — essa parte do mecanismo já
  funciona, só falta o gatilho.
- Provavelmente vive no mesmo reconciliador (ou um processo periódico análogo), já
  que ele já corre em loop assíncrono no lifespan do `backend-crm`.
- Um toggle dedicado (default desligado — é comportamento novo, não uma preservação
  de algo já em produção, diferente do precedente de `meeting_management_enabled`)
  e o(s) campo(s) de limiar de inatividade — devem nascer já como campos do M3
  (camada dedicada), não como mais um campo solto.
- Uma trava de repetição (cooldown) para não re-disparar a cada ciclo do
  reconciliador sobre o mesmo lead permanentemente inativo depois que o contrato
  automático anterior se encerrar.
- **Marca visível na Central de Follow-ups** distinguindo um follow-up iniciado
  automaticamente por inatividade de um iniciado manualmente pelo operador — sem
  isso, follow-ups vão aparecer na lista sem o operador entender a origem.

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

## M3 — Camada dedicada de Follow-up no AI Profile

**Prioridade: MÉDIA** — depende do M1 para ter efeito real (não adianta reorganizar
a UI se a gravação continuar quebrada), mas o desenho pode ser feito em paralelo.

**Estado actual:** a configuração de follow-up está hoje espalhada por abas
diferentes do AI Profile (Pipeline, Apresentação) sem um lugar único que reúna tudo
que afecta este comportamento — cadência, tentativas, instruções por variante
(`followup_sdr_instructions`/`followup_recovery_instructions`/
`followup_postsession_instructions`, já implementadas e funcionais), e os campos
novos do gatilho automático (M2). Resultado: o operador precisa de saber em qual aba
cada coisa está, sem visão de conjunto do que controla o follow-up.

**O que precisaria existir:**
1. **Auditoria** de todos os campos relacionados a follow-up hoje espalhados pela UI
   — em qual aba/componente cada um vive actualmente (`AiProfile.tsx`).
2. **Desenho de uma secção dedicada** que reúna esses campos num único lugar
   coerente, incluindo o toggle/limiar de inatividade do M2 — em vez de mais um
   campo solto, ele já nasce dentro desta camada.

**Pergunta de produto a decidir (não bloqueia o registo):** essa camada deveria
viver dentro da página `/ai-profile` (nova secção/aba), ou faz mais sentido
aproveitar a Central de Follow-ups já existente como o lugar de configuração
também, em vez de duplicar a superfície de UI?

---

## Relação com outros planos

- Diferente de `agentes-agenda-melhorias-futuras.md` (M3) — aquele item é sobre a
  **confiabilidade da decisão** de `meeting_scheduled` (a Mãe marcar confirmação sem
  o lead ter confirmado de fato); este documento é sobre **quem inicia** o
  follow-up e **onde a configuração é gravada**, não sobre se a IA decide certo.
- `docs/plans/pipeline-configurable-fields.md` — status das Etapas D, E e F
  corrigido de "✅ Implementado" para reflectir que a UI nunca grava no lugar
  certo (ver M1 acima); a correcção desses três campos passa a ser tratada aqui.
- `docs/architecture/followup.md` documenta o mecanismo atual (reconciliador,
  estados, cart recovery) que M2 estende.
- `docs/marketing/comercial/agente-demo.md`, secção "NOTA TÉCNICA", lista a versão
  completa do bug de persistência (inclui campos fora do escopo de follow-up/agenda,
  ver M1 acima).
