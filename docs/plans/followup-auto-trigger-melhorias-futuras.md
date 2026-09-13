# Follow-up Automático por Inatividade — Melhorias Futuras

> Contexto: identificado durante a implementação e testes de
> `docs/implementations/followup-auto-trigger-inatividade.md` (M2 do plano
> `docs/plans/followup-proativo-e-cancelamento-agenda.md` — disparo automático de
> follow-up por inatividade em `apresentation`/`agendamento`, e check-in automático de
> cliente inativo em `client-list`). Itens deixados deliberadamente fora do escopo
> dessa implementação, ou descobertos como efeito colateral dos testes — registados
> aqui para retomar quando fizer sentido.

---

## M1 — O sistema pode achar que um cliente está "ativo" por engano

**Em palavras simples:** para decidir se um lead ou cliente está "calado há muito
tempo", o sistema olha a última mensagem que essa pessoa mandou. Quando ela nunca
mandou nenhuma mensagem (só recebeu), o sistema usa como substituto a última vez que
o card dela foi movido no quadro. O problema: se o operador só editar alguma coisa
no card (sem o lead/cliente ter feito nada), isso conta como "sinal de vida" e atrasa
o disparo automático sem necessidade.

**Prioridade: BAIXA** (risco já documentado e aceito na implementação original — sem
caso de uso reportado em produção)

**Estado actual:** `scan_inactive_leads_for_auto_followup()` e
`scan_inactive_clients_for_checkin()` (`backend-crm/services/followup_reconciler.py`)
calculam o sinal de "última atividade" como o máximo entre a última mensagem inbound
e `leads.lastMovement` — este último é tocado por qualquer `UPDATE` no card, incluindo
edições manuais do operador sem relação com uma resposta real do lead/cliente.

**Risco concreto:** um lead/cliente genuinamente inativo pode ter o disparo automático
postergado indefinidamente se o operador continuar a editar o card periodicamente (ex.:
atualizar uma nota), mesmo sem nenhuma interação real da outra parte.

**O que precisaria existir:** um sinal mais específico de "resposta real" (ex.: um
timestamp dedicado, atualizado só por `save_inbound_message()`, em vez de reaproveitar
`lastMovement` como fallback genérico).

---

## M3 — Check-in automático de clientes não cobre o agente de Fechamento Direto (Agent 2)

**Em palavras simples:** dos três tipos de agente do sistema, o check-in automático
de cliente inativo (`client-list`) só funciona para dois deles. O terceiro tipo —
o que fecha vendas diretamente — funciona de um jeito fundamentalmente diferente: o
robô dele nunca é desligado automaticamente depois da venda, então a lógica que eu
construí (religar o robô durante o check-in, desligar de novo se não der resposta)
não se aplica a ele sem um desenho próprio.

**Prioridade: BAIXA** (decisão deliberada de escopo, não um bug — sem pedido de
utilizador reportado)

**Estado actual:** `scan_inactive_clients_for_checkin()`
(`backend-crm/services/followup_reconciler.py`) restringe a elegibilidade a
`agent_type IN ('agent_1', 'agent_3')`. Agent 2 (`closer_agressivo`) não passa pelo
mesmo side-effect de `bot_disabled` ao entrar em `closing`/`client-list`
(`apply_closing_bot_disable_side_effect`, `backend-crm/services/lead_category_policy.py`)
— o bot dele já fica ativo nesse estado por padrão.

**Risco concreto:** clientes convertidos via Agent 2 nunca recebem o check-in
automático de reengajamento, mesmo que o operador queira essa função para esse tipo
de agente também.

**O que precisaria existir:** desenhar a variante equivalente para Agent 2 — sem a
parte de "religar/desligar o bot" (já que ele não se aplica), provavelmente reaproveitando
a variante `client_checkin` só na parte de conteúdo/cadência.

---

## M4 — O processo que envia mensagens automáticas não isola contas de teste de contas reais

**Em palavras simples:** durante o teste desta funcionalidade, liguei o processo que
de fato manda as mensagens automáticas (não fazia parte do ambiente usado nas fases
anteriores deste M2). Descobri que esse processo pega qualquer mensagem pendente de
**qualquer conta no banco de dados**, não só da conta de teste — em poucos segundos,
ele já tinha pegado uma mensagem de um lead real de outra conta, sem relação com o meu
teste. Não chegou a enviar nada (a mensagem já estava com erro antes), mas o risco
era real: se houvesse uma mensagem válida na fila de outra conta, ela teria sido
enviada de verdade. É um risco só em ambiente de desenvolvimento local com banco
compartilhado — em produção não existe essa distinção entre "conta de teste" e
"conta real".

**Prioridade: MÉDIA** (risco operacional de testes locais, não um bug de produção)

**Estado actual:** `backend-executors/app/workers/whatsapp_worker.py` faz polling de
`GET /internal/jobs/next` sem nenhum filtro por `user_id` — processa o primeiro job
pendente de qualquer conta presente na base de dados ligada. Detalhe completo do
incidente (contido, sem envio real) em
`docs/implementations/followup-auto-trigger-inatividade.md`, secção "Fase 4b".

**Risco concreto:** qualquer pessoa que ligue este worker localmente contra uma cópia
do banco de produção (ou um banco partilhado com dados reais) corre o risco de
despachar mensagens reais para clientes reais, mesmo que a intenção fosse só testar
uma conta específica.

**O que precisaria existir:** um modo sandbox/teste para o worker — ex.: filtro por
`user_id` via variável de ambiente, ou um sinalizador que restrinja o polling a contas
marcadas como teste — antes de recomendar ligar este processo livremente em ambientes
locais com banco partilhado.

---

## Relação com outros planos

- `docs/plans/followup-proativo-e-cancelamento-agenda.md` (M3 — Camada dedicada de
  Follow-up no AI Profile) já antecipava que os campos do gatilho automático (M2)
  deveriam nascer dentro dessa camada dedicada em vez de soltos — os campos da Fase 4
  (`followup_checkin_*`) seguem exactamente o mesmo padrão e entram no mesmo M3 quando
  ele avançar (nota adicionada lá referenciando este documento).
