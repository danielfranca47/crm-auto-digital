---
name: configuracao-personalizada
description: Missão completa para montar e entregar ao cliente final o agente de IA de WhatsApp já a funcionar. Trabalha na conta de teste de produção do colaborador, a partir de um pedido (o comportamento desejado, números de conversas de referência para ler no WhatsApp Web, ou prints), e pergunta o que faltar. Identifica o tipo de agente (01/02/03 da página Tipos de Agentes), configura o AI Profile e o treinamento, testa no Playground por API e, se for preciso, corrige o código sem prejudicar as outras contas. Valida no Playground de produção e com 1 conversa no WhatsApp real, e termina com a exportação do perfil (com ou sem treinamento) e a importação na conta do cliente. Usar quando pedirem "configuração personalizada", "montar/configurar o agente do cliente X", "pôr o bot do cliente Y a atender como nestas conversas", "preparar o bot para entregar ao cliente", ou para retomar essa missão. Se o pedido for só diagnosticar a conta de um cliente, sem montar nem entregar, basta a diagnosticar-agente.
---

# Configuração personalizada do agente de um cliente (da montagem à entrega)

**Objetivo:** entregar ao cliente final um agente que atende como ele quer. O agente é montado e
provado numa **conta de teste de produção** do colaborador, com números no Playground de produção e 1
conversa no WhatsApp real. Depois passa para a conta do cliente por exportação e importação.

É um trabalho **micro**: um cliente, um agente e um comportamento. Só se mexe no sistema quando a
configuração não chega, e sempre sem mudar o comportamento das outras contas.

**Quem usa:** o Daniel e os colegas autorizados do comercial e do suporte. Cada um tem a **sua** conta
de teste em produção. Não são programadores: fala-lhes em linguagem simples, faz perguntas de negócio
(nunca técnicas) e dá sempre uma opção recomendada. A mecânica fica nos ficheiros da bancada e nos
`.md` de implementações.

## Modo objetivo: o Claude trabalha para o consultor e entrega o agente pronto

Quem pede não é técnico e não deve ter de decidir nada técnico. A missão corre como um objetivo
fechado: **só acaba quando o agente está entregue e a funcionar** (ver "Paragem").

- **O Claude decide sozinho** o que é técnico ou de afinação: a versão de configuração, os exemplos
  de treinamento, se é código, a solução, a ordem, os cenários, o modo de exportação. Escolhe a opção
  recomendada e regista-a no README da bancada, em "Decisões tomadas": a decisão, as alternativas e o
  porquê. Nunca pede ao consultor que leia código, diffs ou logs.
- **Ao consultor, só se pede:** o que falta no pedido, numa única mensagem; a autorização da missão,
  uma vez; o que só uma pessoa pode fazer (ler um QR, enviar do telemóvel de teste, exportar e
  importar no ecrã, criar a conta do cliente); e uma dúvida de negócio que as referências não
  respondem, com a opção recomendada. Se ele não souber, segue a recomendada e marca-a como
  provisória.
- **Há dois pontos de paragem humana, e só esses:**
  1. o "sim" de quem corre a sessão para publicar uma correção numa categoria que sobe (regra 6);
  2. um risco real e irreversível de perda de dados.
- **Não há checkpoints de "queres que continue?"** nem a pergunta "queres teste automatizado?": os
  testes são sempre automáticos, por API.
- **Esperas longas** (deploy, bateria): corre em segundo plano e continua quando acabarem.
- **Se a sessão chegar ao limite de uso**, grava o estado no README ("Estado atual", "Onde
  retomamos") e entrega o prompt de retomada, para a conversa seguinte continuar sem perguntar de novo.

### Autorização da missão (fase 0)

Pede-a uma vez, em linguagem simples:

> Para te entregar o agente pronto vou, sem te voltar a perguntar:
> 1. mudar a configuração e o treinamento da tua conta de teste (sempre com cópia de segurança);
> 2. se a configuração não chegar, preparar e testar correções no sistema, incluindo com outras
>    contas, para garantir que nada piora para os outros clientes;
> 3. fazer 1 conversa de teste no WhatsApp real, a partir de um número de teste;
> 4. na entrega, fazer 1 conversa de teste no Playground da conta do cliente e apagá-la a seguir.
> Se uma correção mexer nas instruções da IA, no envio de mensagens, na base de dados ou em
> pagamentos, explico-te numa frase o que muda e o resultado dos testes, e só a publico com o teu
> "sim". Nunca envio mensagens a clientes reais e nunca apago dados de clientes sem perguntar.

**Vocabulário:** o da página Tipos de Agentes (`/agentes-info`): Agente 01 · SDR de Alto Ticket,
Agente 02 · Vendedor Autônomo, Agente 03 · Assistente Comercial; Inbound/Outbound, Fit, Dor,
Handoff, Aquecimento, Follow-up. Os nomes técnicos (`agent_mode`, `template_key`, p0–p5) ficam só
entre parênteses.

## As duas contas

| Conta | O que é | O que se faz nela |
|---|---|---|
| **Conta de trabalho** | a conta de teste de produção do colaborador que pediu (o email dele) | toda a configuração, o treinamento, os testes do Playground de produção e, se tiver WhatsApp ligado, o teste real |
| **Conta do cliente** | a conta do cliente final; pode já existir ou ser criada no fim | **só leitura** até à entrega. Recebe o agente por importação (fase 8) |

A conta de trabalho é **reutilizada** entre clientes. No início de cada missão tem de ficar limpa
(fase 1): sobras de outro cliente iriam parar à exportação.

## Dois modos: dono e colaborador

**O primeiro comando de qualquer missão** é
`python .claude/skills/diagnosticar-agente/scripts/verificar_ambiente.py`. Mostra à pessoa um
checklist simples (o projeto atualizado, o login e o plano da conta de teste) e diz o modo:

| | **Modo dono** (`MODO=dono`) | **Modo colaborador** (`MODO=colaborador`) |
|---|---|---|
| Quando | há Railway no PC (o Daniel) | não há Railway (colegas) — **nunca pedir Railway, `.env` nem acesso ao servidor** |
| Acesso à produção | `railway ssh` | as rotas públicas, com o login da conta de teste (`_acesso.json`) |
| Testes | bancada local e Playground de produção | **só o Playground de produção da conta de trabalho** (é de teste, não afeta ninguém) |
| Cliente simulado | chave local | gerado pelo servidor |
| Conversas de referência | CRM de produção ou WhatsApp Web | WhatsApp Web (no PC da pessoa) ou prints |
| Código (fase 6) | corrige pelo fluxo de implementação | **corrige também**, pelo mesmo fluxo: testes antes/depois no PC, publicação pelo GitHub (o deploy é automático), validação em produção depois do deploy |
| Confirmar o deploy | procurar o código no container | `--prod-acao versao` (commit de cada serviço) |
| Teste real (fase 7) | CRM e logs | CRM da conta de trabalho (mensagens do lead) |

O colaborador **não depende de ninguém**: o que só um dono do sistema pode fazer (segredos, variáveis
do servidor, serviços pagos, apagar dados de clientes) é o único caso que vira pedido de correção.

Tudo o que muda no modo colaborador está em
[references/modo-colaborador.md](references/modo-colaborador.md). Se o checklist falhar, diz à pessoa
a única coisa a fazer e, se for algo que o Claude possa fazer no PC (instalar o Python ou os pacotes,
atualizar o projeto, configurar o nome no git), faz-o com a autorização da pessoa.

## Base reutilizada (não duplicar)

Esta skill **orquestra**; o trabalho de cada fase vive noutros sítios. Lê o ficheiro indicado quando
chegares a essa fase.

| Precisas de | Onde está |
|---|---|
| Fases de leitura, bancada, versões de configuração, aplicar em produção | skill `diagnosticar-agente` (`.claude/skills/diagnosticar-agente/SKILL.md`), fases 0–7 |
| Ler conversas (CRM → WhatsApp Web) e escrever o comportamento esperado | `diagnosticar-agente/references/extrair-conversas.md` + `scripts/wa_extract.js` |
| Identificar o agente e a origem (inbound/outbound) | `diagnosticar-agente/references/classificar-processo.md` + skill `agente-0X-…` |
| Bancada isolada, cenários, cliente simulado, `--prod` | `diagnosticar-agente/references/bancada.md` + `scripts/` |
| Classificar cada falha (configuração, código, modelo, dados, negócio) | `diagnosticar-agente/references/triagem.md` |
| Prompts de investigação/implementação, relatório, retomada | `diagnosticar-agente/references/entregas.md` |
| **Pedido e perguntas iniciais** | [references/pedido.md](references/pedido.md) |
| **Corrigir código sem prejudicar as outras contas** | [references/codigo-sem-regressao.md](references/codigo-sem-regressao.md) |
| **Teste com 1 conversa no WhatsApp real** | [references/whatsapp-real.md](references/whatsapp-real.md) |
| **Exportar, importar e verificar a entrega** | [references/entrega-ao-cliente.md](references/entrega-ao-cliente.md) |
| **Modo colaborador (sem Railway): acesso, comandos, pedidos de correção** | [references/modo-colaborador.md](references/modo-colaborador.md) |

Na bancada, o `bancada.json` aponta `conta` para a **conta de trabalho** (é nela que os scripts leem,
testam e aplicam). A conta do cliente fica registada à parte, em `cliente`
(`{"email", "prod_user_id"}`), só para leitura e para a entrega.

Valem as regras fixas da `diagnosticar-agente`, **com três exceções desta missão**:
- a regra "sem alterações de código" não se aplica: o código corrige-se na fase 6, pelo fluxo de
  implementação do CLAUDE.md, no modo descrito na fase 6;
- a regra "nunca enviar WhatsApp" tem uma única exceção, a fase 7: 1 conversa, de um número de
  teste, com um "sim" explícito;
- na **conta de trabalho**, escrever configuração e treinamento faz parte do trabalho. Basta o "sim"
  dado uma vez no início da missão, e faz-se sempre backup antes. Na conta do cliente vale a regra
  original: só se escreve com um "sim" específico.

## Regras desta missão

1. **A ordem é configuração → treinamento → código.** Só se passa ao código quando a triagem prova que
   é código, ou quando 3 formulações não resolvem (regra das 3 formulações).
2. **Nunca prejudicar as outras contas.** Uma correção de código é genérica e não muda o
   comportamento de quem não a pediu. As regras e as provas exigidas estão em
   [codigo-sem-regressao.md](references/codigo-sem-regressao.md). Sem estas provas, nada vai para
   `main`.
3. **Testes por API do Playground, sempre primeiro**: a bancada local e depois o Playground de
   produção (`--prod`) na conta de trabalho. O browser serve só para ler o WhatsApp Web e para a
   fase 7.
4. **Medir em taxa.** Uma conversa boa não prova nada: corre a bateria e repete 3 vezes os cenários
   de conteúdo.
5. **Entrega só com tudo validado.** Só se diz ao utilizador que já pode exportar quando todos os
   critérios ⚠ passaram na bateria `--prod` e na conversa real.
6. **Categorias que sobem:** as instruções da IA, o envio real, a base de dados e o pagamento
   (`python scripts/fila/categorias_que_sobem.py`). Uma correção nestas categorias afeta todas as
   contas e **só vai para `main` com o "sim" explícito de quem corre a sessão** (o Daniel ou o
   colaborador; por decisão do Daniel, o colaborador não precisa do Daniel), dado nessa altura, para
   essa correção. A autorização do início da missão não o substitui. O Claude deixa a branch pronta e
   com as provas passadas e faz uma única pergunta, sem termos técnicos: o que muda, para quem, e o
   resultado dos testes. Enquanto espera, continua o resto da missão.
7. **Dados de clientes** ficam em `.claude/agentes/<slug>/` (no gitignore). Nos ficheiros
   versionados entram só números agregados e exemplos anonimizados.

## Fases

### 0. Pedido (nunca começar sem ele)
Segue [references/pedido.md](references/pedido.md). Confere a lista do mínimo necessário: o email da
**conta de trabalho**, o cliente, o objetivo e as referências. **O que faltar, pede-o numa única
mensagem**, com o modelo de pedido pronto a preencher, e junta-lhe a **autorização da missão**. Depois
disso trabalha até ao fim. Se `.claude/agentes/<slug>/README.md` já existir, é uma retomada: lê
"Estado atual", "Decisões tomadas" e "Onde retomamos" e salta para essa fase, sem pedir de novo a
autorização que já lá estiver registada.

### 1. Estado do repositório e das contas
- Fase 0 da `diagnosticar-agente`: worktrees e fixes recentes que mexem no comportamento pedido.
- **Conta de trabalho:** confirma que a conta existe e que é de teste (o email é o que o colaborador
  deu e não é a conta de um cliente). Faz o snapshot e o backup do AI Profile, do treinamento e da Base
  de Conhecimento. Se houver sobras de outro cliente (instruções, exemplos de treinamento, itens da
  Base de Conhecimento, ligação ao Google de outra pessoa), limpa-as depois do backup, antes de
  começar. Estão cobertas pela autorização da missão e a cópia fica guardada.
- **Conta do cliente**, se já existir: snapshot só de leitura. Resume ao utilizador **o que o cliente
  tem configurado hoje** em 5–8 linhas: o tipo de agente, o modelo, os horários, o Fluxo de Venda, o
  handoff e a ligação de WhatsApp/Google. É o ponto de partida mais provável.

### 2. Comportamento desejado
Junta as três fontes possíveis num só "comportamento esperado" no README da bancada (roteiro
observado, factos do negócio, limites, divergências, critérios de sucesso com os ⚠ críticos):
- **o prompt do utilizador**: a forma como quer que o agente atenda;
- **as conversas de referência**: primeiro no CRM e, se foram feitas à mão, no WhatsApp Web, só a
  ler (`extrair-conversas.md`);
- **os prints**: lê as imagens e transcreve-as para `referencias/print-NN.txt`.

Quando o prompt e as conversas se contradizem, vale o prompt do utilizador, porque é o pedido mais
recente. Regista a decisão. Só perguntas se a contradição for de negócio e mudar um critério ⚠.

### 3. Tipo de agente
Identifica qual dos 3 agentes corresponde ao processo e se os leads são inbound ou outbound, e cruza
com o que o cliente tem configurado, se tiver (`classificar-processo.md`). **Invoca a skill do
agente** (`agente-01-sdr-alto-ticket`, `agente-02-vendedor-autonomo` ou
`agente-03-assistente-comercial`) e junta os critérios e os cenários dela aos da fase 2. Escolhe o
tipo pelas evidências e regista o porquê. Só perguntas se as conversas apontarem para dois tipos com
peso igual.

### 4. Bancada e linha de base
Monta a bancada (`bancada.md`) com a conta de trabalho em `conta`. Na conta de trabalho, põe o ponto
de partida: o perfil atual do cliente, se existir, ou o preset do tipo de agente. Mete os dados do
negócio na Base de Conhecimento. Escreve os cenários (uma persona `p-*` por conversa real e os
cenários-limite da skill do agente) e corre a **linha de base `c00`**. Mostra a tabela das
divergências: critério → o que o agente faz hoje → classe da triagem.

### 5. Configuração e treinamento (na conta de trabalho)
1. **AI Profile:** fases 5–7 da `diagnosticar-agente`. Uma hipótese por versão `cNN`; confirmar no
   código que o campo chega à fase que o usa; medir cada versão; aplicar à conta de trabalho com
   backup; confirmar no **Playground de produção**.
2. **Treinamento** (secção Treinamento do Playground): quando o que falta é **tom ou formato** de
   resposta, acrescenta exemplos das conversas de referência como bons ("excelente"/"boa") e
   respostas erradas medidas como maus ("ruim"). Os exemplos só entram nas fases de qualificação,
   apresentação, follow-up e fecho, até 3 bons e 3 maus por fase; noutras fases não servem. Regista
   cada exemplo no README (fase, mensagem do lead, resposta, nota) e mede a bateria antes e depois.
3. O que continuar a falhar e a triagem disser que é código passa à fase 6.

### 6. Correções de código (só o que a configuração e o treinamento não resolvem)
Os dois modos corrigem o código pelo mesmo fluxo. A diferença está na forma de provar que nada piora
para as outras contas: no modo colaborador não há bancada local. Ver `modo-colaborador.md`, secção
"Corrigir código" e [references/codigo-sem-regressao.md](references/codigo-sem-regressao.md). Só vira
**pedido de correção** o que exige um dono do sistema (segredos, variáveis do servidor, serviços
pagos, apagar dados de clientes).

Segue [references/codigo-sem-regressao.md](references/codigo-sem-regressao.md):
1. Um ficheiro em `docs/implementations/` por correção, com a evidência medida e os cenários da
   bancada. Se 2 ou mais correções tocam o mesmo código, investiga primeiro e faz o quadro de
   sobreposição (`entregas.md`).
2. Fluxo do CLAUDE.md **em modo autónomo**, como na fila automática: o diagnóstico e o plano ficam no
   `.md`, sem esperar aprovação; worktree (nome `fix/<slug>` ou `feat/<slug>` sem confirmação);
   fases com commit e hash; o relatório da fase fica no `.md`, sem pergunta no fim; os testes são
   automáticos. As correções fazem-se **nesta conversa**, uma de cada vez, pela ordem do quadro de
   sobreposição.
3. Valida com o código da worktree na bancada (`preparar_bancada.py <slug> --codigo-de <branch>`):
   os cenários deste cliente e a **regressão das outras contas**. No modo colaborador, a validação é
   a da secção "Corrigir código" de `modo-colaborador.md`.
4. Com as 5 provas passadas (e, nas categorias que sobem, com o "sim" da regra 6): graduação, merge,
   push e deploy pelo fluxo normal. Se o merge tiver
   conflitos, resolve-os sozinho (`_guia-resolucao-conflitos.md`). Depois confirma que o deploy
   chegou: `--prod-acao versao` tem de mostrar o commit publicado em cada serviço tocado (no modo
   dono também se pode procurar o código no container). Por fim corre a bateria `--prod` completa.

Volta à fase 5 se a correção de código abrir espaço para simplificar a configuração.

### 7. Teste no WhatsApp real (1 conversa)
Só quando todos os critérios ⚠ passam na bateria `--prod`. Segue
[references/whatsapp-real.md](references/whatsapp-real.md): escolher a conta (a de trabalho, se
tiver WhatsApp ligado; senão, a do cliente, logo depois da importação), usar um número de teste que
nunca falou com essa conta, fazer **1 conversa** que percorra o objetivo inteiro, verificar o
resultado no CRM e nos logs, e limpar.

### 8. Entrega ao cliente (exportar → importar → verificar)
Segue [references/entrega-ao-cliente.md](references/entrega-ao-cliente.md):
1. Diz ao utilizador que **o agente está pronto a exportar** e recomenda o modo (**com** ou **sem
   treinamento**), com o porquê.
2. Dá os passos ao utilizador, clique a clique: exportar na conta de trabalho, criar a conta do
   cliente se ainda não existir, importar o ficheiro e refazer o que a exportação **não leva** (a Base
   de Conhecimento, o WhatsApp, o Google Calendar, o número do operador e os webhooks de pagamento),
   já com o conteúdo pronto a colar. Pede-lhe o **email da conta do cliente**.
3. Com esse email, o Claude **verifica** só a ler que o perfil, o treinamento e a Base de
   Conhecimento chegaram iguais e que as ligações estão feitas. Se faltar alguma coisa, diz
   exatamente o quê e onde.
4. Corre 1 cenário `--prod` na conta do cliente para confirmar que se comporta como a conta de
   trabalho, e apaga o lead e as marcações de teste.

### 9. Fecho
- Gradua as implementações (`_processo-graduacao-implementacao.md`): o que é arquitetura passa para
  `docs/architecture/`; a mudança de campos do AI Profile atualiza
  `docs/architecture/admin-agents-contract.md`.
- O que ficou por fazer vai para `docs/plans/` (procura duplicados antes de criar).
- Guarda o ficheiro exportado em `.claude/agentes/<slug>/entrega/` (fica no gitignore). Assim o
  cliente pode ser reposto mais tarde.
- Atualiza o README da bancada ("Estado atual", "Onde retomamos") e entrega o relatório
  (`entregas.md`): uma frase de estado; o que funciona, com as taxas; o que se mudou na configuração,
  no treinamento e no código; o que ficou na conta do cliente; o que fica a faltar; o prompt de
  retomada.

## Paragem

A missão acaba quando o agente **está na conta do cliente**, com os critérios ⚠ a passar na bateria
`--prod` e na conversa real, e cada falha que sobra está registada como plan, com uma decisão do
utilizador. Só um ⚠ que exige um dono do sistema (segredos, variáveis do servidor, serviços pagos)
fica como pedido de correção aberto: a missão pára aí, com o estado do pedido no "Onde retomamos".
Se o que falta depender só do cliente (dados, negócio, WhatsApp desligado), pára e diz
exatamente o que falta e a quem pedir.
