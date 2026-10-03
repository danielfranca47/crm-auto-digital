# O que o cliente recebe entre o agendamento e o pós-sessão?

**Status:** Pronta para decisão
**Origem:** `levantamentos/2026-10-03-acompanhamento-pos-agendamento.md` — cenários 1, 2, 4a, 4b e 4c
**Meta ligada:** M1 — Conquistar os primeiros clientes pagantes (nicho inicial: massoterapia com o agente agendador); secundária M2
**Área do sistema:** backend-crm (appointments, jobs, variáveis) / backend-executors (runner de lembrete, prompt pós-agendamento) / backend-core (AI Profile) / frontend-crm (Configurar Agente, Agenda, card do lead)

---

## Pergunta a responder

Depois que a Lara marca uma sessão, o cliente final recebe tudo o que um bom
atendimento humano enviaria — confirmação no formato do negócio, morada, lembrete,
instruções de chegada, mensagem pós-sessão — e o dono da conta consegue ver e
configurar isso com clareza?

## O que já se sabe

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
ou por um evento do compromisso** (agendou, faltam 60 min, sessão realizada), não
por uma mensagem recebida. O que serve de base é a fila de lembretes; o que se
reaproveita do Fluxo de Venda é a **tela** (blocos de mensagem, mídia, variáveis).

**7. Uso real (produção, 03/10/2026, só leitura, agregado).** 1 compromisso real
criado em todo o sistema (agosto/2026), 2 lembretes enviados, 0 resultados de sessão
registados. O fluxo pós-agendamento praticamente nunca rodou com clientes reais —
coerente com o receio do utilizador de ligar a Lara no próprio WhatsApp, e significa
que mudar este comportamento tem risco baixo de quebrar hábito de alguém.

## Como o mercado faz

| Referência | Como resolve | Aplica-se a nós? |
|---|---|---|
| **Fresha** (salões/spas) | Lista de "mensagens automáticas" por momento: novo agendamento (data, hora, morada, direções, serviço, preço, política de cancelamento), até 3 lembretes com antecedência escolhida, boas-vindas a cliente novo, agradecimento + pedido de avaliação depois do *checkout* (não é enviado se o checkout for feito mais de 24h depois). Envio por SMS ou WhatsApp | **Sim** — é exatamente o nicho. Confirma o padrão "uma mensagem por momento do compromisso, cada uma liga/desliga e edita" e que o pós-sessão depende de alguém marcar a sessão como concluída |
| **Calendly Workflows** | Regra "quando isto acontecer → faça isto": gatilhos *evento agendado*, *X antes de começar*, *X depois de terminar*, *cancelado*. Botão "Variáveis" no editor: nome do evento, data, hora, local, nome do convidado, respostas do formulário | **Sim** — modelo mental simples (momento + mensagem) e lista de variáveis de referência |
| **Acuity Scheduling** | Modelos editáveis por tipo de mensagem (confirmação, lembrete, follow-up) com etiquetas `%first%`, `%time%`, `%type%` (tipo de serviço), `%calendar%` (profissional), `%location%`, inseridas por menu no editor | **Sim** — mostra o conjunto mínimo de variáveis: cliente, data/hora, **serviço**, **profissional**, local |
| **GoHighLevel** | Construtor de fluxos genérico: gatilho "estado do compromisso mudou" (confirmado, compareceu, faltou, cancelado), espera "até X antes do compromisso", ramos Se/Senão por tag ou estado, ação "adicionar tag" | **Parcial** — a potência é a que o utilizador imagina (compromisso + tag + fluxo), mas é um construtor livre, complexo para um terapeuta. Tirar daqui os estados do compromisso e a condição por tag, não a tela |
| Guias de redução de faltas | Padrão recorrente: lembrete ~24h antes + outro 2–3h antes, com pedido de confirmação por resposta | **Sim** — o nosso padrão (24h/2h) já está alinhado; o que falta é o conteúdo ser do dono do negócio |

Variáveis mais frequentes no mercado → o que proporíamos:

| Variável proposta | Exemplo | Já existe? |
|---|---|---|
| `{{lead.nome}}` | Maria | Sim |
| `{{agendamento.servico}}` | Massagem Relaxante | Não — falta guardar o serviço no compromisso |
| `{{agendamento.duracao}}` | 60 min | Não (dado existe: fim − início) |
| `{{agendamento.data}}` | 06/10 | Não (hoje só junto com a hora) |
| `{{agendamento.dia_semana}}` | terça | Não |
| `{{agendamento.hora}}` | 14:30 | Não |
| `{{agendamento.profissional}}` | Ana | Não — falta guardar o profissional |
| `{{negocio.local}}` | Rua …, 101 | Sim |
| `{{negocio.nome}}` | Espaço X | Sim |

## Opções de solução

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
- **Contras:** continua espalhado por várias telas (recibo num sítio, lembretes
  noutro, pós-sessão noutro); não cobre morada na 1ª vez, vídeo antes da sessão,
  "já chegou?", nem pós-sessão. Cada pedido novo vira mais um campo solto — o
  mesmo problema de "não vejo com clareza" continua.
- **Esforço:** ~2 fases

### Opção C — "Jornada do Agendamento": uma linha do tempo única, por momentos
- **O que é:** uma secção própria em Configurar Agente (junto ao Fluxo de Venda,
  mesmo visual) com os **momentos** do compromisso em ordem:

  ```
  Ao agendar → Lembrete antecipado → Perto do horário → Na hora → Sessão realizada / Não compareceu
  ```

  Em cada momento o utilizador empilha os mesmos blocos que já conhece do Fluxo de
  Venda — **Mensagem fixa** (texto dele, com variáveis, sem IA), **Mídia** (vídeo
  de como chegar), **Orientação à IA** (quando quiser texto gerado) — e define
  quando dispara (ex.: "60 min antes"), em que janela de horário pode sair, e
  condições simples ("só no primeiro agendamento deste cliente", "só se agendou
  com mais de 48h", "só se a chegada não foi confirmada"). Vem pré-preenchida com
  um modelo pronto por nicho, para funcionar sem configurar nada.

  Por trás: a fila que hoje envia os lembretes passa a enviar qualquer passo da
  jornada (já sabe agendar em relação ao horário da sessão e refazer tudo ao
  remarcar/cancelar). O compromisso passa a guardar serviço e profissional, e a
  confirmação sai **depois** de o compromisso estar gravado, com os dados do banco.
- **Prós:** responde aos 5 cenários com um só conceito; o utilizador vê numa tela
  tudo o que o cliente vai receber; reaproveita a tela de blocos, as variáveis e a
  fila de lembretes — não é um motor novo; entrega em fatias, cada uma já útil.
- **Contras:** é a opção maior; exige substituir (não duplicar) o recibo e os
  lembretes atuais para não haver mensagens em dobro; "já chegou?" e pós-sessão
  dependem de alguém marcar chegada/realização no CRM.
- **Esforço:** ~5 fases
  1. Dados e variáveis: guardar serviço/profissional no compromisso; variáveis
     `{{agendamento.*}}`; confirmação "Ao agendar" com texto do utilizador
     (substitui o recibo escrito pela IA) + morada no primeiro agendamento.
  2. Lembretes editáveis: N lembretes em minutos, texto/mídia do utilizador,
     janela de horário, regra de antecedência mínima.
  3. Tela da linha do tempo (momentos + blocos + modelo pronto por nicho).
  4. Pós-sessão: "Realizada"/"Não compareceu" disparam os blocos do momento;
     condição "primeira vez"; lembrete ao dono para marcar sessões por confirmar.
  5. Perto do horário: o agente volta a responder dúvidas práticas (morada, como
     chegar, estacionamento) sem reabrir venda; marcação "cliente chegou" e a
     mensagem "já chegou?" quando não marcada.

## Recomendação

**Opção C, entregue por fatias, começando pelas fases 1 e 2.** Só essas duas já
dão a confirmação no formato do utilizador, a morada na primeira vez e lembretes
com o texto dele dentro do horário certo — o suficiente para ligar a Lara com
confiança. A Opção B chegaria ao mesmo ponto um pouco antes, mas deixaria tudo
espalhado e obrigaria a refazer quando viesse o pós-sessão.

A condição "primeira vez" fica mais fiável com tags (um cliente antigo, cadastrado
agora, não tem histórico no sistema) — ver [`tags-de-contato.md`](tags-de-contato.md).
Ordem sugerida: Jornada fases 1–2 → Tags → Jornada fases 3–5.

## Pontuação RICE

| R | I | C | E | Score |
|---|---|---|---|---|
| 3 | 3 | 0.8 | 5 | **1.44** |

- **R = 3:** afeta todos os clientes dos agentes com agendamento (1 e 3), que são o nicho de entrada.
- **I = 3:** bloqueia a adoção pelo cliente-tipo (M1) e é onde o agente hoje responde pior — 1 frase vazia perto da sessão (M2).
- **C = 0.8:** lacunas confirmadas no código e padrão claro no mercado; mas a dor vem de um utilizador (o dono) e a produção quase não tem compromissos reais para medir.
- **E = 5:** cinco fases, cada uma entregável sozinha.

## Veredito proposto

**Implementations** — começar pelas fases 1–2 (confirmação + lembretes do
utilizador); fases 3–5 seguem depois das tags.

## Perguntas ao utilizador

1. **Terapeuta:** no seu negócio quem atende é sempre a mesma pessoa, ou varia
   por sessão? Se varia, como a Lara deveria saber quem vai atender — você define
   depois, ou o cliente escolhe? (Hoje o sistema assume 1 profissional por conta.)
2. **Dúvidas depois de agendar:** a Lara pode responder dúvidas práticas (morada,
   como chegar, o que levar) **sempre** que o cliente já tem sessão marcada, ou só
   numa janela perto do horário? Sugestão: sempre — é mais simples e nunca deixa o
   cliente sem resposta; as janelas ficam só para as mensagens que a Lara envia
   por iniciativa própria.
3. **"Cliente chegou":** hoje, como o massagista lhe avisa que o cliente chegou?
   (Isso decide onde pôr o botão: no telemóvel, no CRM, ou responder a uma
   mensagem no WhatsApp.)
4. **Sessão realizada:** se ninguém marcar a sessão como realizada, prefere que a
   mensagem pós-sessão **não saia** (como faz a Fresha) ou que saia sozinha X horas
   depois, a menos que alguém marque "não compareceu"?
5. **Lembrete antecipado:** confirma a regra "só se agendou com mais de 48h de
   antecedência, enviado ~12h antes, entre 08h e 18h" como padrão de fábrica?

## Em aberto

- Configuração atual do Fluxo de Venda e dos lembretes da conta do utilizador em
  produção não foi lida (está no backend-core) — verificar no Plan Mode da fase 1
  para não gerar mensagens em dobro com blocos que ele já tenha configurado.
- Como o resultado da sessão deve mover o card no Kanban (ex.: "Realizada" →
  Lista de Clientes) — decidir junto com a fase 4 e com as tags.
- Agentes com vários profissionais por conta continuam fora (ver
  `docs/plans/agentes-agenda-melhorias-futuras.md`, M1); a resposta à pergunta 1
  diz se isso sobe de prioridade.

## Fontes

- [Fresha — Automated messages overview](https://www.fresha.com/help-center/knowledge-base/marketing/125-automated-messages-overview)
- [Fresha — Send appointment reminders](https://www.fresha.com/help-center/knowledge-base/calendar/167-send-appointment-reminders)
- [Calendly — How to customize emails and texts for Workflows (variáveis)](https://help.calendly.com/hc/en-us/articles/4405711728023-Using-variables-and-event-types-in-Workflows)
- [Calendly — Workflows: automate reminders, emails, and follow-ups](https://calendly.com/learn/calendly-workflows)
- [Acuity Scheduling — Personalizing email and text messages with tags](https://help.acuityscheduling.com/hc/en-us/articles/17949540611213-Personalizing-email-and-text-messages-with-tags)
- [GoHighLevel — Appointment scenarios in Workflow](https://help.gohighlevel.com/support/solutions/articles/155000002697-appointment-scenarios-in-workflow)
- [GoHighLevel — If/Else: Appointment filter options](https://help.gohighlevel.com/support/solutions/articles/155000004050-if-else-workflow-action-appointment-filter-options)
- [Acuity — The Ultimate Guide to Appointment Reminders](https://acuityscheduling.com/learn/appointment-reminders-guide)
- [Appointment Reminder — How to Reduce No-Shows](https://appointmentreminder.com/guides/reduce-no-shows/)
