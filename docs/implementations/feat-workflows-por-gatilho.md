# Workflows por gatilho — acompanhamento do cliente depois do agendamento

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Origem:** docs/discovery (investigação `jornada-pos-agendamento`, graduada em 2026-10-03) — levantamento em `docs/discovery/levantamentos/2026-10-03-acompanhamento-pos-agendamento.md`
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (nicho inicial: massoterapia com o agente agendador); secundária M2

---

## Motivação

O dono do produto, falando como cliente-tipo do nicho de massoterapia (Agente 3),
não confia em ligar a Lara no próprio WhatsApp: depois que ela marca uma sessão, o
cliente final não recebe o que um bom atendimento humano enviaria — confirmação no
formato do negócio, morada, lembrete com o texto do dono, instruções de chegada,
mensagem pós-sessão — e o dono não vê nem configura isso com clareza.

**Solução aprovada (ver "Opção D" abaixo):** workflows por gatilho, no modelo do
ManyChat. O Fluxo de Venda continua a ser o workflow principal; os novos
workflows disparam por evento ou relógio (agendamento criado, X antes/depois do
horário, estado do agendamento, entrada em coluna, tag) e usam os mesmos blocos.
Vêm com modelos prontos. O profissional da sessão é uma variável do contato.

**Começar pela fase 1** (lista de fases na Opção D) — depois de
`fix-disponibilidade-campo-duplo-sentido.md`, do qual a janela de envios depende.

## Área do sistema

backend-crm (appointments, jobs, variáveis, dispatch de ações) / backend-executors
(runner de lembrete, prompt pós-agendamento, Fluxo de Venda) / backend-core (AI
Profile) / frontend-crm (Configurar Agente, Agenda, card do lead)

## Estado atual por cenário

Resposta curta: **existe uma parte, mas escondida, pouco configurável e escrita pela
IA em vez de pelo dono do negócio.** Cenário a cenário:

| Cenário pedido | Hoje | Onde |
|---|---|---|
| 1. Confirmação logo ao agendar, em formato próprio | **Parcial.** Existe um "recibo de reserva", mas o formato está fixo no código, é a IA que o escreve a partir do histórico da conversa (não dos dados gravados), e só existe num dos dois caminhos que confirmam agendamento | `decision_engine.py:3472-3494` |
| 2. Morada no primeiro agendamento | **Não existe.** O recibo diz à IA que "pode acrescentar a morada"; não há noção de "primeiro agendamento" | `decision_engine.py:3490` |
| 4a. Lembrete antes da sessão, texto personalizável, com variáveis | **Parcial.** Lembretes existem (24h e 2h antes no Agente 3), mas o texto é gerado pela IA (máx. 2 frases), sem modelo editável, sem variáveis, sem mídia, sem janela de horário | `jobs_service.py:608-679`, `meeting_scheduler.py:520-604` |
| 4b. Perto do horário: agente disponível + vídeo de como chegar + "já chegou?" | **Não existe.** Depois de agendar, o bot fica em "modo silencioso": só trata cancelar/remarcar; qualquer outra pergunta recebe 1 frase mínima | `decision_engine.py:4453-4512` |
| 4c. Depois da sessão: "o que achou?", pedir avaliação, convidar à próxima | **Não existe de forma automática.** Marcar "realizada" só regista o resultado e religa o bot; nenhuma mensagem sai | `appointment_outcomes.py:37-166`, `LeadCardDialog.tsx:634-656` |

---

## Evidência no código

**1. Confirmação (recibo de reserva).**
- O bloco "CONFIRMAÇÃO ESTRUTURADA OBRIGATÓRIA" só é injetado na filha de
  **apresentação** com `presentation_variant == "scheduler"`
  (`decision_engine.py:3478`). A filha de **agendamento** — a que o Agente 3
  usa nas fases pré-agendamento → agendamento — não tem esse bloco (já registado
  em `docs/plans/agentes-agenda-melhorias-futuras.md`, M3).
- O formato é fixo no código, incluindo a palavra "Massagista"
  (`decision_engine.py:3485-3489`) — num produto que serve outros nichos.
- A IA preenche com `extracted_fields` e, na falta, "o que estiver no histórico
  ou em custom_instructions" (`decision_engine.py:3482-3483`) — ou seja, gasta
  raciocínio e pode errar um dado que o sistema já tem.
- O recibo é escrito **antes** de o compromisso ser gravado. Se a gravação
  falhar por conflito de horário, o cliente pode receber um texto incoerente
  (caso real documentado no mesmo M3).
- O compromisso gravado **não guarda o nome do serviço nem o profissional**: a
  tabela `appointments` só tem `title` (gerado pela IA, ex.: "Sessão de
  Massagem"), `start_at`, `end_at`, `location` (`docs/architecture/agenda.md`,
  "Tabela appointments"; `meeting_scheduler.py:799-813`). Sem esses dois campos,
  nenhuma mensagem "pronta do banco" consegue dizer "Massagem Relaxante 60 min ·
  Terapeuta: X".

**2. Variáveis.** O sistema de variáveis `{{chave}}` com atalho `/` já existe
(`docs/architecture/dynamic-variables.md`). Para agendamento só há
`{{reuniao.horario}}` (formato fixo "dd/mm às HH:MM") e `{{reuniao.titulo}}`;
`{{negocio.local}}` já resolve a morada cadastrada. Faltam: serviço, duração,
data e hora separadas, dia da semana, profissional.

**3. Lembretes.**
- Agendados na criação do compromisso, cancelados/recriados ao remarcar
  (`routes/appointments.py:283-290, 402-409`; `jobs_service.py:574-605`) — a
  infraestrutura de "mensagem agendada em relação ao horário da sessão" já está
  pronta e testada.
- A tela ("Configurar Agente → Follow-up → Lembretes automáticos") só permite
  **exatamente 2 lembretes em horas inteiras** (`api.ts:1543-1550, 1703-1706`;
  `CamadaFollowup.tsx:315-336`). O backend já aceita uma lista livre em minutos.
- Lembrete cujo horário de envio já passou é simplesmente pulado
  (`jobs_service.py:649-650`) — sessão marcada para daqui a 3h não recebe o de 24h.
  Não existe a regra "só se agendou com mais de 48h de antecedência".
- **Sem janela de horário:** `followup_allowed_hours` só é lido pelo reconciliador
  de follow-up (`followup_reconciler.py`); os lembretes ignoram-no. Uma sessão às
  08:00 com lembrete de 2h dispara às 06:00.
- Texto: `generate_appointment_reminder_message()` pede à IA "no máximo 2 frases
  curtas" com tom "early"/"final" (`meeting_scheduler.py:560-591`). Não aceita
  texto do utilizador nem mídia.

**4. Perto do horário.** Ao agendar, `bot_disabled=1` com motivo
`meeting_scheduled` (`meeting_scheduler.py:814`). Com `meeting_management_enabled`
ligado, as mensagens do cliente passam por um prompt dedicado cuja regra é: "para
qualquer outra mensagem… responda de forma mínima e cordial (1 frase)… SEM
perguntas" (`decision_engine.py:4508-4510`). "Onde estaciono?" 1h antes da sessão
recebe uma frase vazia. Não existe estado "cliente chegou" — os estados são
`pending/completed/canceled` e os resultados `completed/no_show/rescheduled`.

**5. Pós-sessão.** Os botões "Realizada"/"Não compareceu" no card do lead chamam
`apply_outcome()`, que grava o resultado, um log, e religa o bot
(`reactivate_bot: true` fixo em `LeadCardDialog.tsx:643`). Nenhuma mensagem é
enviada. O que existe hoje de pós-sessão é manual (arrastar o card para Follow-up
e responder ao modal "Como terminou a sessão?") ou tardio (check-in automático de
cliente inativo após N dias, padrão 30 — `docs/architecture/followup.md`).

**6. Por que o Fluxo de Venda atual não resolve sozinho.** O motor do Fluxo de
Venda só corre **quando o cliente manda uma mensagem** (`_evaluate_sales_flow_phases`
é chamado dentro da construção da resposta — `decision_engine.py:2781, 3125, 3698`).
O gatilho "Sem resposta" é só um marcador de tela, nunca avaliado
(`decision_engine.py:823`). Tudo o que foi pedido aqui é disparado **pelo relógio
ou por um evento** (agendou, faltam 60 min, sessão realizada, entrou na Lista de
Clientes), não por uma mensagem recebida. São duas naturezas de execução:

| | Fluxo de Venda (hoje) | Workflow por evento (novo) |
|---|---|---|
| Quando corre | Dentro da resposta da IA, a cada mensagem do lead | Quando o evento acontece ou o relógio chega |
| Onde fica o estado | Carimbos no lead (`triggers_fired`, `sales_flow_wait`…) | Precisa de registo próprio: em que passo cada contato está, e até quando espera |
| Uma "Espera" | Só é reavaliada na próxima mensagem do lead | Tem de acordar sozinha na hora marcada |
| Base já existente | `_evaluate_sales_flow_phases` | Fila de jobs com `scheduled_at` — a que hoje envia lembretes e o webhook do Fluxo de Venda (`jobs_service.py`, `sales_flow_webhook_worker.py`) |

O vocabulário de blocos (mensagem, mídia, orientação, espera, condição, webhook),
as variáveis e os formulários de edição são reaproveitáveis; o **motor** dos
workflows por evento é novo, apoiado na fila de jobs.

**7. Janelas de horário que já existem — e uma colisão.** Hoje há três conceitos
de horário no AI Profile, guardados em só dois campos:

| O que controla | Onde se configura | Campo | Quem lê |
|---|---|---|---|
| Quando a Lara **responde** a quem escreve (fora do horário, a resposta fica agendada para a próxima abertura) | Pipeline → "Janela de horário" (24h / comercial / personalizado) | `availability_mode` + `availability_schedule` (JSON por dia da semana) | `humanization.py:84-158` |
| Em que horários o **profissional atende** (para a Lara propor horários de sessão) | Apresentação → "Disponibilidade de horários" (texto livre) | **o mesmo** `availability_schedule` | `decision_engine.py:4319, 4376` ("DISPONIBILIDADE DO PROFISSIONAL") |
| Quando a Lara pode enviar **follow-ups** por iniciativa própria | Follow-up → "Follow-up avançado" | `followup_allowed_hours` (padrão 08:00–20:00) | `followup_reconciler.py` |

As duas primeiras linhas escrevem no **mesmo campo com formatos diferentes**
(`CamadaPipeline.tsx:334-346` grava JSON; `CamadaApresentacao.tsx:254-259` grava
texto livre). Uma tela desfaz a outra: quem define a janela de resposta
personalizada passa a mostrar JSON cru à IA como "disponibilidade do profissional";
quem escreve os horários de atendimento em texto inutiliza a janela de resposta
personalizada. O valor de fábrica do campo já é um JSON "seg–sex 09:00–18:00"
(`types/agente.ts:462`), que chega ao prompt de agendamento como se o profissional
tivesse declarado essa disponibilidade. É um defeito confirmado, independente desta
investigação — registado em
`docs/implementations/fix-disponibilidade-campo-duplo-sentido.md`.

Os lembretes de sessão não respeitam nenhuma das três janelas (ponto 3). Criar uma
quarta janela só para lembretes aumentaria a confusão; o natural é que tudo o que a
Lara envia **por iniciativa própria** (follow-ups e workflows) partilhe uma janela
geral da conta, com possibilidade de cada workflow definir a sua.

**8. Profissionais e dados por contato.**
- **Não existe cadastro de profissionais com disponibilidade individual.** O que
  há na Base de Conhecimento é: "Bio do Profissional" (um texto único,
  `types/agente.ts:809`), e a "Tabela de Serviços e Preços", que admite várias
  tabelas com título próprio — pensada para "Ana — Hipnoterapia", "Fernanda —
  Estética" (`docs/architecture/knowledge-base.md`, "Categorias com múltiplos
  itens"). A disponibilidade é uma só por conta (linha 2 da tabela acima) e a
  agenda trata a conta como um único profissional
  (`docs/plans/agentes-agenda-melhorias-futuras.md`, M1).
- **Variáveis personalizadas atuais são da conta, não do contato:**
  `ai_profile.custom_variables` guarda um valor igual para todos os clientes
  (`variable_resolver.py:100-103`).
- **Já existe onde guardar um valor por contato:** os campos de qualificação.
  O dono define campos próprios em `qualification_fields` (obrigatórios ou
  opcionais), a IA extrai o valor da conversa e grava-o por lead em
  `lead_qualification_state` (`qualification_state.py:123-144, 189`). Esses
  valores **não estão disponíveis como variável** `{{…}}` nas mensagens, e não
  há bloco no Fluxo de Venda para gravar um valor de forma fixa ("neste caminho,
  terapeuta = Ana").

**9. Uso real (produção, 03/10/2026, só leitura, agregado).** 1 compromisso real
criado em todo o sistema (agosto/2026), 2 lembretes enviados, 0 resultados de sessão
registados. O fluxo pós-agendamento praticamente nunca rodou com clientes reais —
coerente com o receio do utilizador de ligar a Lara no próprio WhatsApp, e significa
que mudar este comportamento tem risco baixo de quebrar hábito de alguém.

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| **ManyChat** (referência indicada pelo utilizador) | Cada **automação** tem um "passo inicial" com um ou mais **gatilhos** e, a seguir, passos ligados entre si: enviar mensagem, ações (ex.: aplicar tag), espera inteligente (por duração **ou até uma data**), condição, iniciar outra automação. As **Regras** acrescentam gatilhos que não dependem de mensagem: *data/hora* (X antes ou depois de uma data guardada no contato, no fuso do contato), *tag aplicada/removida*, *campo alterado* | **Sim — é o modelo a seguir.** "X antes do horário da sessão" é exatamente o gatilho de data/hora; "entrou na Lista de Clientes" é o gatilho de campo alterado. A diferença: no ManyChat o utilizador monta tudo do zero; os nossos clientes precisam de modelos prontos |
| **Fresha** (salões/spas) | Lista de "mensagens automáticas" por momento: novo agendamento (data, hora, morada, direções, serviço, preço, política de cancelamento), até 3 lembretes com antecedência escolhida, boas-vindas a cliente novo, agradecimento + pedido de avaliação depois do *checkout* (não é enviado se o checkout for feito mais de 24h depois). Envio por SMS ou WhatsApp | **Sim** — é o nicho. Mostra **quais** automações um negócio de sessões espera encontrar prontas, e que o pós-sessão depende de alguém marcar a sessão como concluída |
| **Calendly Workflows** | Regra "quando isto acontecer → faça isto": *evento agendado*, *X antes de começar*, *X depois de terminar*, *cancelado*. Botão "Variáveis" no editor: nome do evento, data, hora, local, nome do convidado | **Sim** — lista de gatilhos de compromisso e de variáveis de referência |
| **Acuity Scheduling** | Modelos editáveis com etiquetas `%first%`, `%time%`, `%type%` (serviço), `%calendar%` (profissional), `%location%`, inseridas por menu | **Sim** — conjunto mínimo de variáveis: cliente, data/hora, **serviço**, **profissional**, local |
| **GoHighLevel** | Gatilho "estado do compromisso mudou" (confirmado, compareceu, faltou, cancelado), espera "até X antes do compromisso", ramos Se/Senão por tag ou estado, ação "adicionar tag" | **Parcial** — confirma os estados do compromisso como gatilho e a tag como condição |
| Guias de redução de faltas | Padrão recorrente: lembrete ~24h antes + outro 2–3h antes, com pedido de confirmação por resposta | **Sim** — o nosso padrão (24h/2h) já está alinhado; falta o conteúdo ser do dono do negócio |

Variáveis mais frequentes no mercado → o que proporíamos:

| Variável proposta | Exemplo | Já existe? |
|---|---|---|
| `{{lead.nome}}` | Maria | Sim |
| `{{agendamento.servico}}` | Massagem Relaxante | Não — falta guardar o serviço no compromisso |
| `{{agendamento.duracao}}` | 60 min | Não (dado existe: fim − início) |
| `{{agendamento.data}}` | 06/10 | Não (hoje só junto com a hora) |
| `{{agendamento.dia_semana}}` | terça | Não |
| `{{agendamento.hora}}` | 14:30 | Não |
| Variável do contato, com o nome que o dono escolher (ex.: `{{contato.terapeuta_atendimento}}`) | Ana | Não — hoje só há variáveis da conta, iguais para todos os contatos |
| `{{negocio.local}}` | Rua …, 101 | Sim |
| `{{negocio.nome}}` | Espaço X | Sim |

## Opções avaliadas — aprovada a Opção D

### Opção A — Não fazer nada / adiar
- **Prós:** zero esforço; lembretes de 24h/2h continuam a sair.
- **Contras:** o próprio dono do produto, que é o cliente-tipo do nicho-alvo, não
  confia em ligar o agente no seu WhatsApp. Sem isto, a promessa "a Lara agenda
  por você" termina no momento em que o trabalho de acompanhamento começa.

### Opção B — Remendos pontuais nos pontos existentes
- **O que é:** tornar o texto do recibo e dos 2 lembretes editável (campos novos
  no AI Profile), levar o recibo também à filha de agendamento, respeitar a janela
  de horário.
- **Prós:** rápido (~2 fases); resolve 1 e 4a.
- **Contras:** continua espalhado por várias telas; não cobre morada na 1ª vez,
  vídeo antes da sessão, "já chegou?", nem pós-sessão. Cada pedido novo vira mais
  um campo solto.
- **Esforço:** ~2 fases

### Opção C — Linha do tempo fixa do agendamento
- **O que é:** uma secção com momentos pré-definidos (ao agendar → lembrete →
  perto do horário → na hora → sessão realizada), cada um com blocos.
- **Prós:** simples de entender; cobre os 5 cenários.
- **Contras:** só serve para agendamento. Qualquer outro cenário ("entrou na Lista
  de Clientes", "recebeu a tag X", aniversário) exigiria outra tela e outro motor.
  **Descartada por direção do utilizador (03/10/2026)**, que prefere o modelo
  genérico abaixo.
- **Esforço:** ~5 fases

### Opção D — Workflows por gatilho (modelo ManyChat), com o Fluxo de Venda como workflow principal
- **O que é:** "Configurar Agente" passa a ter uma lista de **workflows**. O
  primeiro, sempre presente, é o **Fluxo de Venda** (conduz a conversa, fase a
  fase — continua a funcionar como hoje). Os outros são criados pelo utilizador
  ou ligados a partir de modelos prontos; cada um começa por um **gatilho** e
  segue com os mesmos blocos do Fluxo de Venda.

  **Gatilhos** (por evento ou relógio):

  | Gatilho | Exemplo de uso |
  |---|---|
  | Agendamento criado | Confirmação no formato do negócio; morada se for a 1ª vez |
  | X antes / X depois do horário do agendamento | Lembrete 12h antes; vídeo de como chegar 60 min antes; "já chegou?" 2 min antes |
  | Agendamento mudou de estado (realizada, não compareceu, cancelado, remarcado) | "O que achou da experiência?"; pedido de avaliação |
  | Contato entrou numa coluna do Kanban | "Entrou na Lista de Clientes (pós-venda)" |
  | Tag adicionada / removida | Campanha para quem recebeu `#pack_10_sessoes` |

  **Passos:** Mensagem fixa (texto do utilizador, com variáveis, sem IA), Mídia,
  Orientação à IA (quando quiser texto gerado), Espera (por duração ou até uma
  hora), Condição (tem/não tem tag, primeira vez, agendou com mais de X de
  antecedência, chegada não confirmada), Ações (adicionar tag, mover de coluna,
  ligar/desligar o bot, webhook).

  **Regras de envio de cada workflow:** uma vez por contato ou a cada ocorrência;
  cancelamento automático quando o agendamento é cancelado ou remarcado; e
  **janela de envio** — por omissão "usar a janela geral de envios da conta" (a
  mesma dos follow-ups), ou uma janela própria do workflow. Fica assim separado,
  com nomes distintos na tela: *quando a Lara responde* (janela de resposta),
  *quando a Lara envia por iniciativa própria* (janela de envios) e *quando o
  profissional atende* (horários de sessão).

  **Variáveis do contato** (direção do utilizador, 03/10/2026): além das variáveis
  da conta e do agendamento, cada contato passa a ter variáveis próprias, com o
  nome que o dono quiser (ex.: `terapeuta_atendimento`; noutro nicho, `consultor`,
  `unidade`, `plano_escolhido`). São preenchidas de três formas — um passo
  **"Definir variável"** no workflow (valor fixo, no momento em que o cliente
  escolhe um caminho), a **IA** ao captar o valor na conversa (mecanismo dos
  campos de qualificação, que já existe), ou **à mão** no card do contato — e
  ficam disponíveis no seletor `/` para qualquer mensagem posterior. O
  profissional da sessão deixa de ser um campo fixo do sistema: é a variável que
  o dono escolher. A lista de profissionais do estabelecimento vive na Base de
  Conhecimento, para a IA saber quem são e oferecê-los.

  **Modelos prontos** ("Confirmação de agendamento", "Lembrete antecipado", "Como
  chegar", "Pós-sessão + avaliação") já vêm na conta, por nicho — quem não quiser
  montar nada só liga e edita o texto.

  Por trás: o motor do Fluxo de Venda não é reescrito. Os workflows por evento
  ganham um motor próprio apoiado na fila de jobs que hoje envia os lembretes
  (ver "Evidência", ponto 6). O recibo e os lembretes atuais são **substituídos**
  pelos modelos equivalentes, para não haver mensagens em dobro.
- **Prós:** um só conceito para todos os cenários atuais e futuros; é o padrão
  que o utilizador (e o mercado) já conhece; a lista de workflows dá a
  visibilidade pedida ("vejo o que o meu cliente vai receber"); reaproveita
  blocos, variáveis e fila de jobs.
- **Contras / riscos a tratar no desenho:**
  - Um construtor livre é mais difícil para um terapeuta sem perfil técnico —
    por isso os modelos prontos não são opcionais, são parte da entrega.
  - **Envios em massa por engano:** carimbar 200 contatos com uma tag que tem
    gatilho, ou arrastar muitos cards para uma coluna, dispararia 200 mensagens
    de uma vez num WhatsApp ligado por API não oficial (risco de bloqueio do
    número). **Decisão do utilizador (03/10/2026):** o sistema pergunta antes
    ("isto vai enviar para N contatos — confirmar?") e envia aos poucos, com
    intervalo entre mensagens para não parecer spam.
  - **Ciclos:** workflow A adiciona tag → dispara workflow B → que adiciona outra
    tag → dispara A. Precisa de trava.
  - Dois workflows a enviar ao mesmo contato no mesmo minuto — precisa de ordem
    e intervalo mínimo.
  - "Já chegou?" e pós-sessão dependem de alguém marcar chegada/realização.
- **Esforço:** ~6 fases
  1. Base: workflows por evento (modelo de dados + motor na fila de jobs), gatilhos
     "agendamento criado" e "X antes/depois do horário", passos Mensagem e Mídia,
     variáveis `{{agendamento.*}}` (serviço guardado no compromisso) e variáveis
     do contato (passo "Definir variável" + valores captados pela IA disponíveis
     no seletor). Entregue como **modelos prontos com formulário simples**
     (ligar/desligar, texto, antecedência, janela) — substitui o recibo e os
     lembretes atuais. Lembrete antecipado de fábrica: só se agendou com mais de
     48h, enviado ~12h antes, entre 08h e 18h — tudo editável.
  2. Lista de workflows em Configurar Agente + criar workflow próprio escolhendo
     gatilho e passos.
  3. Gatilhos "agendamento mudou de estado" e "entrou numa coluna"; condição
     "primeira vez"; ação "mover de coluna"; aviso ao dono de sessões por marcar.
  4. Ligação com tags (gatilho, condição, ação) — depende de
     [`feat-tags-de-contato.md`](feat-tags-de-contato.md).
  5. Espera e Condição dentro dos workflows por evento + travas (ritmo, ciclos,
     confirmação de envio em massa).
  6. Perto do horário: a Lara volta a responder dúvidas práticas com sessão
     marcada; marcação "cliente chegou" e condição "chegada não confirmada".

## Porquê a Opção D

**Opção D, entregue por fatias, começando pela fase 1.** É o mesmo trabalho de
motor que a linha do tempo fixa exigiria, mas fica a servir qualquer cenário
futuro — e a linha do tempo fixa passa a ser simplesmente o conjunto de modelos
prontos que vem na conta. A fase 1 sozinha já dá confirmação no formato do
utilizador, morada na primeira vez e lembretes com o texto dele dentro do horário
certo — o suficiente para ligar a Lara com confiança.

Sobre a tela: a edição livre em nós ligados é tratada em
[`feat-workflows-canvas-de-nos.md`](feat-workflows-canvas-de-nos.md). Para não construir
duas telas, a fase 1 usa só formulários simples nos modelos prontos; o editor
completo (fase 2) já nasce no formato que for decidido lá.

## Decisões do utilizador e pontos por decidir

Já decidido (03/10/2026): envios em massa com confirmação e intervalo; o
profissional da sessão é uma variável do contato criada no workflow (a plataforma
é multinicho — não fixar "terapeuta"); lembrete antecipado de fábrica como
sugerido, editável pelo utilizador; **agenda separada por profissional** quando a
conta declara que trabalha com mais de um (com um só, tudo fica como hoje), em
todos os planos — é uma entrega própria, descrita em
`docs/plans/agentes-agenda-melhorias-futuras.md`, M1, e não faz parte das fases
deste arquivo.

Por decidir — nenhuma trava a fase 1, cada uma pode esperar pela fase respetiva:

1. **Dúvidas depois de agendar:** a Lara pode responder dúvidas práticas (morada,
   como chegar, o que levar) **sempre** que o cliente já tem sessão marcada, ou só
   numa janela perto do horário? Sugestão: sempre — nunca deixa o cliente sem
   resposta; as janelas ficam só para as mensagens que a Lara envia por iniciativa
   própria.
2. **"Cliente chegou":** hoje, como o profissional avisa que o cliente chegou?
   (Isso decide onde pôr o botão: no telemóvel, no CRM, ou responder a uma
   mensagem no WhatsApp.)
3. **Sessão realizada:** se ninguém marcar a sessão como realizada, prefere que a
   mensagem pós-sessão **não saia** (como faz a Fresha) ou que saia sozinha X horas
   depois, a menos que alguém marque "não compareceu"?

## Em aberto

- Configuração atual do Fluxo de Venda e dos lembretes da conta do utilizador em
  produção não foi lida (está no backend-core) — verificar no Plan Mode da fase 1
  para não gerar mensagens em dobro com blocos que ele já tenha configurado.
- Onde os workflows ficam guardados (junto do AI Profile, como o Fluxo de Venda,
  ou em tabela própria no CRM, perto da fila de jobs) — decisão técnica do Plan Mode.
- O follow-up por inatividade e o check-in de clientes (`docs/architecture/followup.md`)
  são, na prática, workflows com gatilho de tempo. Migrá-los para este modelo não
  está no escopo — avaliar depois de o motor novo estar validado.
- Agenda por profissional (`docs/plans/agentes-agenda-melhorias-futuras.md`, M1)
  é uma entrega à parte. Quando existir, a variável do contato com o
  profissional da sessão deve poder ser preenchida automaticamente a partir do
  profissional do compromisso — prever isso no desenho das variáveis da fase 1.
- Variável do contato vs. agendamento: se o profissional mudar de uma sessão para
  a outra, a variável do contato guarda só o último valor. Avaliar no Plan Mode
  se o compromisso deve guardar uma cópia dos valores no momento da marcação.
- Linha de mensagem com variável vazia (ex.: "Terapeuta: " sem nome) — o
  resolvedor atual só remove o marcador; decidir se a linha inteira deve sumir.
- Unificar a janela de envios por iniciativa própria (follow-up + workflows)
  depende da correção do campo de disponibilidade com duplo sentido.

## Próximo passo

Diagnóstico (Plan Mode) ainda não feito — seguir o Passo 0 de
`_guia-documentar-implementacao.md` para a **fase 1** antes de qualquer código.
Ordem de execução acordada com o utilizador (03/10/2026):

1. `fix-disponibilidade-campo-duplo-sentido.md`
2. Este arquivo, fase 1 (motor + modelos prontos + variáveis do contato)
3. `feat-tags-de-contato.md`
4. Agenda por profissional (`docs/plans/agentes-agenda-melhorias-futuras.md`, M1)
5. `feat-workflows-canvas-de-nos.md` e as fases 2–6 deste arquivo

## Fontes

- [ManyChat — How to set custom rules with Triggers, Conditions, and Actions](https://help.manychat.com/hc/en-us/articles/14281170185628-How-to-set-custom-rules-with-Triggers-Conditions-and-Actions)
- [ManyChat — How to build a Manychat automation](https://help.manychat.com/hc/en-us/articles/14281166306332-How-to-build-a-Manychat-automation)
- [ManyChat — Smart Delay](https://help.manychat.com/hc/en-us/articles/14281197046812-Smart-Delay)
- [Fresha — Automated messages overview](https://www.fresha.com/help-center/knowledge-base/marketing/125-automated-messages-overview)
- [Fresha — Send appointment reminders](https://www.fresha.com/help-center/knowledge-base/calendar/167-send-appointment-reminders)
- [Calendly — How to customize emails and texts for Workflows (variáveis)](https://help.calendly.com/hc/en-us/articles/4405711728023-Using-variables-and-event-types-in-Workflows)
- [Calendly — Workflows: automate reminders, emails, and follow-ups](https://calendly.com/learn/calendly-workflows)
- [Acuity Scheduling — Personalizing email and text messages with tags](https://help.acuityscheduling.com/hc/en-us/articles/17949540611213-Personalizing-email-and-text-messages-with-tags)
- [GoHighLevel — Appointment scenarios in Workflow](https://help.gohighlevel.com/support/solutions/articles/155000002697-appointment-scenarios-in-workflow)
- [GoHighLevel — If/Else: Appointment filter options](https://help.gohighlevel.com/support/solutions/articles/155000004050-if-else-workflow-action-appointment-filter-options)
- [Acuity — The Ultimate Guide to Appointment Reminders](https://acuityscheduling.com/learn/appointment-reminders-guide)
- [Appointment Reminder — How to Reduce No-Shows](https://appointmentreminder.com/guides/reduce-no-shows/)
