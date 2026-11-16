# Teste no WhatsApp real — 1 conversa

É a única fase em que se envia WhatsApp a sério. **Uma conversa chega**: é a prova de que o que
passou no Playground também passa pelo caminho real (webhook → executor → UazAPI), que tem peças que
o Playground não usa.

## Em que conta

- **Conta de trabalho**, se tiver um WhatsApp ligado (o número de teste do colaborador a fazer de bot).
  É a opção recomendada, porque não toca no cliente.
- Senão, **conta do cliente, logo a seguir à importação** (fase 8), avisando o cliente se for
  preciso. Assim prova também que a importação ficou certa.
- Se nenhuma das duas tiver WhatsApp ligado, o teste fica pendente no "Onde retomamos", com o
  gatilho "quando o WhatsApp do cliente for ligado".

Abaixo, "a conta" é a que se escolheu.

## Pré-requisitos (todos)

- [ ] Todos os critérios ⚠ passam na última bateria `--prod`, com a versão de configuração e o
      código que estão em produção.
- [ ] **A ligação de WhatsApp da conta está ativa**: o estado da instância em `whatsapp_connections`
      no backend-core (só leitura). Se estiver desligada, pára: o cliente tem de voltar a ler o QR.
- [ ] **O número de teste nunca falou com a conta**: procura o telefone (só os dígitos, com e sem
      indicativo) nos leads da conta no `crm.db` de produção, só a ler. Se já existir, pede outro
      número de teste.
- [ ] O bot está ligado para leads novos e a hora atual está dentro da janela de resposta da conta.
      Fora dela, o agente não responde, e isso não é uma falha.
- [ ] A autorização da missão (item 3) foi dada. Antes de começar, diz à pessoa quem envia, de que
      número e o roteiro.

## Quem envia

Por omissão, a opção 1. A 2 só se usa quando a pessoa a pede:

1. **A pessoa envia** do telemóvel de teste, seguindo o roteiro que lhe dás (as mensagens do cenário
   `p-*` que melhor representa o objetivo). O Claude acompanha e diz-lhe quando enviar a mensagem
   seguinte.
2. **O Claude escreve no WhatsApp Web**, mas só se o Chrome tiver aberto o WhatsApp **do número de
   teste**. Usa o claude-in-chrome ou o chrome-devtools, uma mensagem de cada vez, e só para o número
   da conta do cliente.

**Nunca** envies nada pelo WhatsApp Web **da conta do cliente** (o que se usou para ler as
referências): esse continua a ser só de leitura. Antes de escrever, confirma no topo do WhatsApp Web de
quem é a sessão. Nunca escrevas para outro contacto que não seja o número da conta.

## Roteiro

- Uma única conversa que percorra o **objetivo inteiro**: entrada → qualificação → oferta ou
  agendamento → confirmação, e um pedido pós-objetivo (preço, morada, remarcar) se fizer parte dos
  critérios.
- Usa um horário ou uma oferta reais e válidos, e evita o que possa confundir o negócio do cliente:
  por exemplo, marca para um dia em que se possa cancelar sem prejuízo e avisa o cliente se for
  preciso.

## O que verificar, turno a turno

| Onde | O quê |
|---|---|
| CRM (produção, só leitura) | o lead novo, as mensagens, a categoria e o estágio, `bot_disabled` |
| `railway logs -s "worker backend-executors"` | a decisão da Mãe, a fase, as falhas da IA, as novas tentativas; o backend-crm não regista eventos de negócio no stdout |
| Marcação / pagamento / handoff | o que o objetivo pede foi gravado com os dados aceites pelo cliente (dia, hora, serviço, valor) |
| Efeitos secundários | o evento no Google Calendar, os lembretes agendados (os jobs de follow-up), a notificação ao profissional ou vendedor |
| O telemóvel de teste | o texto que chegou é o mesmo que o CRM registou; não houve mensagens duplicadas nem cortadas |

Mede com os mesmos critérios de sucesso do README. Um ⚠ falhado aqui e não no Playground é quase
sempre paridade (`enrich_context_bundle`) ou o caminho de envio: volta à triagem e, se for código, à
fase 6.

## Limpeza (coberta pela autorização da missão; nunca apagar o que não foi criado no teste)

- Cancela a marcação de teste (e o evento no Google), ou anula o pedido ou o link de pagamento de
  teste.
- Arquiva o lead de teste ou marca-o como teste, para não contar nas métricas do cliente.
- Regista no README da bancada: a data, o número de teste (só os últimos 3 dígitos), o resultado por
  critério e o que se limpou.

Não esperes pelos lembretes da véspera dentro da sessão. Confirma que o job ficou agendado para a hora
certa e põe a verificação real no "Onde retomamos".
