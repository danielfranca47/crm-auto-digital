# Follow-up Proativo — Disparo Automático e Camada Dedicada no AI Profile

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
> Nota: este documento já passou por duas graduações de "M1". A primeira
> (cancelamento/reagendamento real de compromisso) foi implementada e graduada para
> `docs/architecture/agenda.md` e `docs/architecture/agents.md` — itens deixados de
> fora estão em `docs/plans/cancelamento-reagendamento-melhorias-futuras.md`. A segunda
> (sincronizar a tela do AI Profile com as colunas reais lidas pelo motor, para os
> campos de follow-up/agenda) também foi implementada e graduada para
> `docs/architecture/agents.md` — os dois ajustes que sobraram dessa correcção foram
> registados em `docs/plans/pipeline-configurable-fields.md` (Etapa J e nota de dados
> legados). M2 e M3 abaixo mantêm a numeração original — o "M1" em falta é intencional.

**Estado:** M2 implementado e testado (`docs/implementations/followup-auto-trigger-inatividade.md`,
Fases 1–4b) — pendente apenas o passo de graduação (migrar para `docs/architecture/`
e remover o arquivo de implementação). M3 ainda não iniciado — pode avançar.

> ⚠️ **Lembrete de manutenção — repetir ao finalizar M2 e M3:** ao graduar cada um
> destes itens, voltar a `docs/marketing/comercial/agente-demo.md`, secção "NOTA
> TÉCNICA"/"PLANO — Agente Demo v1", e verificar se o que mudou afecta o que está
> documentado lá (igual foi feito ao graduar o "M1" de persistência — ver tabela
> "✅ Campos corrigidos" e as notas "⚠️ revisitável" nessa secção). Especificamente:
> - **M2 (disparo automático):** quando implementado, o Cenário 3 do roteiro de teste
>   deixa de depender só de `custom_instructions` — actualizar a frase final de
>   "Ajuste de expectativa no roteiro de teste" nesse documento.
> - **M3 (camada dedicada):** se mudar onde os campos de follow-up vivem na UI, o
>   "Passo a passo para aplicar" (import do `agente-demo-contrato.json`) pode precisar
>   de ajuste.

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

**Prioridade: MÉDIA**

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

**Nota (adicionada após a implementação do M2, Fases 1–4b):** em palavras simples —
o M2 já nasceu seguindo esta recomendação: os campos novos (toggle/dias de
"Follow-up automático" e de "Check-in automático de clientes") foram colocados numa
caixinha própria e isolada na tela, de propósito, em vez de soltos entre os campos
antigos — exactamente para serem absorvidos por este M3 quando ele avançar. Nada a
decidir agora; só confirmar, ao desenhar o M3, que esses dois cards entram na auditoria
do passo 1. Ver `docs/implementations/followup-auto-trigger-inatividade.md` (Fases
1–4b) e `docs/plans/followup-auto-trigger-melhorias-futuras.md` para os itens que
ficaram fora do M2.

---

## Relação com outros planos

- Diferente de `agentes-agenda-melhorias-futuras.md` (M3) — aquele item é sobre a
  **confiabilidade da decisão** de `meeting_scheduled` (a Mãe marcar confirmação sem
  o lead ter confirmado de fato); este documento é sobre **quem inicia** o
  follow-up, não sobre se a IA decide certo.
- `docs/plans/pipeline-configurable-fields.md` — as Etapas D e E (campos de
  follow-up/agenda) já reflectem o fix graduado; a Etapa J (nova) trata os campos
  fora desse domínio (`qualification_score_threshold`, `buying_signal_keywords`) que
  têm o mesmo bug e ficaram fora do escopo desta correcção.
- `docs/architecture/followup.md` documenta o mecanismo atual (reconciliador,
  estados, cart recovery) que M2 estende.
