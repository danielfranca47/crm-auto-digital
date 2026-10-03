# Levantamento — Acompanhamento do cliente depois do agendamento

**Data:** 03/10/2026
**Origem:** pedido do utilizador em conversa, falando como utilizador do produto
(conta própria de massoterapia, Agente 3 — Híbrido Agendador). Texto abaixo é o
pedido original, só com o email da conta removido.

---

Falando como usuário, estou com um empecilho e receio de ter a Lara rodando em meu
WhatsApp, pois percebi uma necessidade que ela não está suprindo. Ou, particularmente
falando, não vejo na experiência do usuário uma visualização com clareza desta entrega.

Que é relacionado ao acompanhamento, um tipo de follow-up após o agendamento. Falando
mais especificamente dos agentes 1 e 3, que são os que utilizam o modelo com
agendamento de compromissos. E mais especificamente sobre o que eu realizo, que é
agendamento para massagem.

O usuário, após realizar um agendamento de sessão, precisa que o seu cliente receba
algumas coisas depois disso.

**1 — Confirmação do agendamento**, logo quando feito, em formato personalizado. Eu
como usuário gosto de enviar assim:

```
✅Experiência Agendada
Massagem Relaxante 60 min

Horário: 14:30 h
Dia 06/10 (terça)

Terapeuta: (Nome da Terapeuta)
```

Possível que outros usuários gostem de enviar de outra maneira. Estas informações
podem ser dinâmicas de acordo com o dia e horário do agendamento, mas se já estão
prontas não precisa botar a IA para pensar ou ver histórico da conversa — podemos
fornecer os dados já do banco.

**2 — Morada no primeiro agendamento.** Se for o primeiro agendamento de algum
cliente novo, envio logo após isso a morada do estabelecimento ("Morada: Rua … -
Centro comercial …", por exemplo).

**3 — Outros eventos de "primeira vez" + funcionalidade de tag.** Outros eventos como
o (2) também podem ser acionados numa primeira vez de agendamento. Estou em transição
para automatizar o atendimento. Se quiser registrar que o cliente já recebeu aquele
evento, campanha ou outra coisa que eu queira pontuar, eu "carimbo" ele com uma tag
(`#morada_primeiro_agendamento`, por exemplo) — assim poderia registrar e terceirizar
os contatos que já são meus clientes sem me preocupar, pois o agente saberia quando
acionar. Isso deve ser alinhado com a funcionalidade similar que existe no fluxo de
venda (disparar apenas uma vez por lead) — talvez uma complemente a outra ou possa ser
adaptada. O facto é que a funcionalidade atual dispara mesmo que eu cadastre um contato
que já é meu cliente e bote a IA para atender, pois ela vai entender que aquele contato
é novo e tratá-lo como cliente novo.

**4 — Disponibilidade e/ou follow-up próximo do horário do atendimento.**

a) Se o cliente agendou um atendimento para mais de 48h, cerca de 12h antes (numa
janela configurável, padrão entre as 08h e as 18h) deve ser enviada uma mensagem de
lembrete/confirmação da sessão com as variáveis do atendimento. A mensagem poderá ser
customizada pelo usuário. É importante ter as variáveis manipuláveis e fáceis de
acessar no front, como já existe em alguns lugares do AI Profile. Mapear as variáveis
mais frequentes; pesquisar como as plataformas de CRM e agendamento definem isso.

b) Se o cliente tiver marcado um atendimento e estiver próximo do horário (janelas
customizáveis), o agente poderá ficar disponível novamente para responder caso o
cliente precise de suporte, ou disparar mais um lembrete personalizado. Exemplo: 60 min
antes eu gosto de enviar um vídeo e um texto explicando como encontrar o gabinete. E
2 min antes, se não receber a confirmação do massagista de que o cliente chegou,
gostaria de acionar uma mensagem "já chegou, nome_do_cliente?".

c) Após o horário da sessão. Quando receber a confirmação de que a sessão foi
realizada (pode ser movendo para uma coluna no CRM, uma tag, ou ligar uma à outra), é
enviada uma mensagem ao cliente perguntando o que achou da experiência e, se for a
primeira vez, um follow-up dizendo que aguardamos o agendamento da próxima sessão e
pedindo para avaliar o nosso espaço.

Estas funcionalidades podem ser ligadas ao fluxo de venda para configurar esses
fluxos. A funcionalidade de tag, o fluxo de vendas e o CRM Kanban podem colaborar para
juntos promoverem essa dinâmica. Estudar cada cenário, ver como as ferramentas mais
conhecidas do mercado fazem, imaginá-los no nosso sistema e avaliar como promover.

---

## Complemento do utilizador (mesmo dia, depois de ler a primeira análise)

Em vez de criar uma "jornada de atendimento", poderia ser um novo workflow similar
ao padrão que é o fluxo de vendas, mas com gatilhos personalizáveis em cima dessas
variáveis — os horários de atendimento, ou algum outro que eu queira configurar,
como "cliente entrou na lista de clientes (pós-venda)". Em resumo, gostaria das
funcionalidades mais similares ao ManyChat, onde a gente consegue configurar cenários
para diversos tipos de gatilhos, sendo o principal e padrão o fluxo de venda dos
agentes.

Também gostaria de alterar a visualização desses workflows para algo de ligar nós,
mais livre ao usuário. Tanto na horizontal como na vertical. Algo mais personalizável
e customizável.

---

## Gaps derivados

| Gap | Destino |
|---|---|
| Cenários 1, 2, 4a, 4b, 4c — o que o cliente recebe entre o agendamento e o pós-sessão (solução: workflows por gatilho) | [`jornada-pos-agendamento.md`](../jornada-pos-agendamento.md) |
| Cenário 3 — tags de contato e relação com "disparar uma vez por lead" | [`tags-de-contato.md`](../tags-de-contato.md) |
| Complemento — tela de nós ligados livremente (canvas) | [`workflows-canvas-de-nos.md`](../workflows-canvas-de-nos.md) |
