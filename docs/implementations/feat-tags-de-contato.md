# Tags de contato

**Branch:** claude/feat-tags-de-contato
**Status:** Só plano — precisa da tua decisão
**Origem:** docs/discovery (investigação `tags-de-contato`, graduada em 2026-10-03) — levantamento em `docs/discovery/levantamentos/2026-10-03-acompanhamento-pos-agendamento.md`, cenário 3
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (quem adota o agente já tem uma carteira de clientes); secundária M2

---

## Motivação

Quando o dono de um negócio liga o agente numa carteira de clientes que já existe,
o agente trata clientes antigos como novos (manda morada, boas-vindas) — e o dono
não tem como "carimbar" um contato para registar o que ele já recebeu (morada,
campanha, primeira sessão).

**Solução aprovada (ver "Opção B" abaixo):** tags visíveis no contato, que
complementam — não substituem — o "disparar uma vez por lead": o dono vê, edita e
carimba em massa; os fluxos ganham a condição "tem / não tem a tag" e a ação
"adicionar tag".

## Área do sistema

backend-crm (leads, importação, dispatch de ações) / backend-executors (motor do
Fluxo de Venda) / frontend-crm (card do lead, Kanban, construtor do Fluxo de Venda)

## Estado atual

- **Não existe nenhuma funcionalidade de tag em leads.** Nenhuma coluna, rota ou
  componente (busca por `tags` no backend e no frontend só encontra etiquetas de
  rotas da API e as tags de feedback do Playground).
- **Existe um "carimbo" escondido**, usado pelo Fluxo de Venda para disparar uma
  vez por lead: `leads.phases_triggered`, `leads.triggers_fired`,
  `leads.branches_selected` (`docs/architecture/sales-flow.md`, "Armazenamento").
- **O problema descrito é real:** um contato cadastrado hoje nasce com esses
  carimbos vazios, portanto todo gatilho de "entrada na fase" dispara para ele
  como se fosse novo — mesmo sendo cliente há anos.

---

## Evidência no código

**Como funciona o "disparar uma vez" hoje.**
- `phase_trigger` dispara quando o id da fase ainda não está em
  `leads.phases_triggered`; `kw_trigger`/`intent_trigger` com `fire_once` e
  `block_trigger` consultam `leads.triggers_fired`, que guarda o **id interno do
  bloco** (`sales-flow.md`, "Avaliação por tipo de trigger").
- Esses carimbos são gravados pelo sistema (`mark_phase_triggered`,
  `mark_trigger_fired` em `routes/executor.py::_dispatch_system_actions`). Não
  aparecem em nenhuma tela e o utilizador não os pode pôr nem tirar.

**Limitações que resultam disso.**

| Limitação | Consequência prática |
|---|---|
| Invisível | O dono não consegue ver "este cliente já recebeu a morada" |
| Não editável | Não dá para carimbar à mão um cliente antigo antes de a IA o atender |
| Preso ao id do bloco | Apagar e recriar o bloco "enviar morada" faz todos voltarem a recebê-la |
| Só vale dentro de uma fase do Fluxo de Venda | Não serve para factos que atravessam fases ou vêm de fora (lembretes, pós-sessão, campanha, importação) |
| A IA não o lê | A IA não sabe que "este contato já é cliente" — só sabe em que fase do funil ele está |

**Entrada de clientes antigos.** Os pontos de criação de lead (manual, planilha,
WhatsApp inbound — `docs/architecture/leads-schema.md`) não têm nenhum campo para
dizer "já é cliente" além de escolher a coluna do Kanban. A importação por
planilha mapeia nome, telefone, canal de aquisição — nada equivalente a tags
(`automations/assistente_ia/processor.py::map_row_to_lead`).

**Uso real (produção, 03/10/2026, agregado).** Uma conta tem 5 contatos em "Lista
de Clientes"; nenhuma tem carteira importada em volume. O problema ainda não
aconteceu em escala — vai acontecer no dia em que um cliente pagante ligar o
agente na sua base existente.

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| **ManyChat** | Tags = etiquetas visíveis no contato para agrupar ("Cliente VIP", "Lead qualificado"); campos personalizados guardam dados. Os fluxos usam condições por tag, as campanhas filtram a audiência por tag, e as Regras têm os gatilhos "tag aplicada" / "tag removida" | **Sim** — é o modelo que o utilizador descreveu: etiqueta simples, usada como condição, ação e gatilho |
| **GoHighLevel** | Tag é ao mesmo tempo gatilho, condição (ramo Se/Senão "tem a tag") e ação ("adicionar/remover tag") dentro dos fluxos; convive com o estado do compromisso | **Sim** — confirma os três usos (ver, condicionar, carimbar). O construtor em si é mais complexo do que precisamos |
| **Fresha** | Tem uma mensagem automática própria de boas-vindas a clientes novos — é o sistema que reconhece quem é novo, sem o dono carimbar nada | **Parcial** — funciona quando todo o histórico do cliente nasce dentro da ferramenta. Nós recebemos clientes com histórico fora do sistema, por isso precisamos de um carimbo manual além do automático |

Padrão comum: a etiqueta é **do contato** (não do fluxo), **visível**, e os
fluxos podem **ler** ("tem / não tem") e **escrever** ("adicionar") etiquetas.

## Opções avaliadas — aprovada a Opção B

### Opção A — Não fazer nada / adiar
- **Prós:** zero esforço.
- **Contras:** quem migra uma carteira existente verá a Lara mandar morada e
  boas-vindas a clientes de anos — pior primeira impressão possível, e é
  exatamente o momento de entrada de um cliente pagante.

### Opção B — Tags visíveis que complementam o "disparar uma vez"
- **O que é:** cada contato ganha uma lista de etiquetas (ex.: `#cliente`,
  `#morada_enviada`). O dono vê e edita no card do lead, filtra o Kanban por
  etiqueta e pode carimbar vários de uma vez (seleção no Kanban ou coluna "tags"
  na planilha de importação). No Fluxo de Venda e nos workflows por gatilho
  entram três peças novas: a condição **"só se tem / não tem a tag X"**, a ação
  **"adicionar tag X"** e — só nos workflows por gatilho — o gatilho **"tag
  adicionada / removida"** (como no ManyChat). O "disparar uma vez"
  atual continua igual por baixo — automático, sem o utilizador ter de pensar
  nele. Opcionalmente, a IA passa a receber as etiquetas do contato numa linha
  de contexto ("já é cliente"), para ajustar o tom.
- **Prós:** resolve o caso do cliente antigo (carimba antes de ligar a IA);
  serve tanto ao Fluxo de Venda como aos workflows por gatilho e a futuras
  campanhas; não mexe no motor de "uma vez por lead", que está estável e
  coberto por testes; é o padrão que o utilizador já conhece de outras
  ferramentas.
- **Contras:** dois mecanismos a conviver (carimbo automático interno + tag
  visível) — precisa de uma explicação clara na tela ("uma vez por contato" é
  automático; tag é quando *você* quer controlar).
- **Esforço:** ~3 fases
  1. Etiquetas no contato: guardar, mostrar e editar no card; filtro no Kanban.
  2. Condição "tem / não tem tag" e ação "adicionar tag" no construtor e no motor.
  3. Carimbar em massa (seleção + importação por planilha) e contexto para a IA.

  O gatilho "tag adicionada / removida" não entra aqui — é a fase 4 de
  [`feat-workflows-por-gatilho.md`](feat-workflows-por-gatilho.md), porque depende do
  motor dos workflows por gatilho e das travas de envio em massa.

### Opção C — Substituir o "disparar uma vez" por tags
- **O que é:** todo o controlo de repetição passa a ser por tag visível; os
  carimbos internos deixam de existir.
- **Prós:** um mecanismo só; tudo visível.
- **Contras:** obriga o utilizador a inventar e gerir uma tag para cada bloco
  que hoje "simplesmente funciona"; exige migrar os dados de todos os leads e
  reescrever a parte mais sensível do motor (a ordem dos gatilhos e os
  bloqueios de avanço de fase dependem desses carimbos). Risco alto para ganho
  pequeno.
- **Esforço:** ~5 fases

## Porquê a Opção B

As duas coisas respondem a perguntas diferentes: "este bloco já
disparou para este contato?" (o sistema sabe sozinho) e "o que eu, dono, quero
registar sobre este contato?" (só o dono sabe — especialmente o que aconteceu
antes de o sistema existir). Juntar as duas (Opção C) tiraria a simplicidade da
primeira sem melhorar a segunda.

Para o pedido concreto: com `#cliente` aplicada à carteira antiga, o bloco
"enviar morada no primeiro agendamento" fica com a condição "não tem `#cliente`"
e, ao disparar, adiciona `#cliente` — clientes antigos nunca a recebem, novos
recebem uma vez.

**Tags e variáveis do contato são coisas diferentes e complementares** (como no
ManyChat): a tag responde sim/não ("já recebeu a morada?"); a variável guarda um
valor ("terapeuta = Ana"). As variáveis do contato entram pela fase 1 dos
workflows por gatilho ([`feat-workflows-por-gatilho.md`](feat-workflows-por-gatilho.md));
no card do contato as duas devem aparecer juntas, na mesma secção.

## Pontos por decidir (perguntar ao utilizador no Plan Mode)

1. **Quem cria as etiquetas:** lista livre (escreve e cria na hora, como
   hashtag) ou uma lista fechada que você define primeiro em Configurações?
   Sugestão: livre, com sugestão das já usadas para evitar duplicados.
2. **A Lara deve saber as etiquetas?** Ex.: tratar quem tem `#cliente` como
   cliente de casa (sem requalificar). Sugestão: sim, para um pequeno conjunto
   que você marca como "a IA deve ver".
3. **Etiquetas e colunas do Kanban:** quando a sessão é marcada como realizada,
   prefere que o contato vá para a coluna "Lista de Clientes", que receba
   `#cliente`, ou as duas coisas?

## Em aberto

- Onde guardar (lista no próprio lead vs. tabela própria) e como filtrar no
  Kanban — decisão técnica do Plan Mode.
- Ação "remover tag" — não pedida; deixar para depois de ver o uso real.

## Decisões em aberto

Escrito de noite, sem o utilizador presente. O plano abaixo está pronto, mas há
três decisões de produto (as que o próprio ficheiro já listava) sem resposta
óbvia no código ou nos docs. Cada uma traz a opção recomendada; basta responder
"segue as recomendadas" ou corrigir.

1. **Quem cria as etiquetas.** Recomendado: lista livre (escreves e cria na
   hora), com sugestão das já usadas para evitar duplicados.
2. **A Lara deve saber as etiquetas?** Recomendado: sim, mas só as que o dono
   marca como "a IA deve ver" — fica para a fase 3, para não tocar nas
   instruções da IA antes de decidires.
3. **Sessão realizada: coluna ou etiqueta?** Recomendado: as duas coisas — o
   contato vai para "Lista de Clientes" e recebe `#cliente`.

Depois destas respostas, a implementação segue a ordem das fases abaixo.

## Diagnóstico (turno da noite, 06/10/2026)

**Já existe?** Não. Confirmado: nenhuma coluna `tags` em `leads` (`backend-crm/database.py`),
nenhuma rota de tags em `routes/leads.py` e nenhum componente de tag em
`frontend-crm/src/components` (`LeadCard`, `LeadCardDialog`, `KanbanBoard`). Os
carimbos internos `phases_triggered` e `triggers_fired` existem em `leads`
(`database.py`, ~linha 801) e ficam como estão.

**O que construir (Opção B aprovada), em 3 fases:**

1. **Etiquetas no contato.** Coluna `leads.tags` (texto JSON, lista de
   etiquetas em minúsculas sem espaços) via `ensure_column`; campo `tags` lido e
   gravado nas rotas existentes `GET /api/leads` e `PATCH /api/leads/{id}`, sempre
   filtradas por `user_id`; lista das etiquetas já usadas pelo utilizador para
   sugestão; edição no `LeadCardDialog`, chip no `LeadCard`, filtro no Kanban
   (`LeadsContext`).
2. **Condição "tem / não tem tag" e ação "adicionar tag"** no construtor do
   Fluxo de Venda (frontend) e no motor (`routes/executor.py`,
   `_dispatch_system_actions`, e a avaliação de blocos descrita em
   `docs/architecture/sales-flow.md`). O "disparar uma vez" não é tocado.
3. **Carimbar em massa e contexto para a IA.** Seleção múltipla no Kanban,
   coluna `tags` na importação por planilha (`map_row_to_lead` em
   `automations/assistente_ia/processor.py`) e, só para as etiquetas marcadas
   "a IA deve ver", uma linha no contexto via `enrich_context_bundle()`
   (`services/ai_orchestrator/orchestrator.py`), para manter a paridade
   Playground ↔ WhatsApp real.

**Riscos:**
- Mexe em estrutura da base de dados (`ensure_column`), no motor do Fluxo de Venda
  e, na fase 3, em contexto da IA: a branch **sobe sempre** para o utilizador
  decidir (`docs/ops/fila-automatica.md`, "O que sobe sempre").
- Dois mecanismos a conviver (carimbo automático + etiqueta): a tela tem de
  explicar a diferença.
- Alterar o contexto da IA exige ler `docs/prompts_llms.md` e respeitar a regra
  de paridade; por isso a fase 3 espera a decisão 2.
- Docs a atualizar na implementação: `leads-schema.md`, `sales-flow.md`.

**Cabe numa noite?** As 3 fases cabem no limite, mas a decisão 2 e a ordem
acordada (depois da fase 1 de `feat-workflows-por-gatilho.md`, ainda por fazer)
justificam esperar pela tua resposta antes de gastar uma noite em código.

## Próximo passo

Responder às 3 decisões acima. Depois, a próxima noite (ou uma sessão contigo)
implementa a fase 1. Ordem completa em
[`feat-workflows-por-gatilho.md`](feat-workflows-por-gatilho.md), secção "Próximo passo".

## Fontes

- [ManyChat — How to set custom rules with Triggers, Conditions, and Actions](https://help.manychat.com/hc/en-us/articles/14281170185628-How-to-set-custom-rules-with-Triggers-Conditions-and-Actions)
- [Manychat — The 7 Best WhatsApp Automation Tools (tags e segmentação)](https://manychat.com/blog/best-whatsapp-automation-tools/)
- [Egrow — ManyChat WhatsApp Automation (tags vs. campos personalizados)](https://blog.egrow.com/en/post/manychat-whatsapp-automation-streamline-your-messaging)
- [GoHighLevel — If/Else: Appointment filter options](https://help.gohighlevel.com/support/solutions/articles/155000004050-if-else-workflow-action-appointment-filter-options)
- [GoHighLevel Workflows: Triggers, Actions & Recipes](https://hlgrowthpartner.com/post/gohighlevel-workflows-triggers-actions-2026)
- [Fresha — Automated messages overview](https://www.fresha.com/help-center/knowledge-base/marketing/125-automated-messages-overview)
