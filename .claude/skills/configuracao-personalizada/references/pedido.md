# Pedido — o mínimo para começar e o que perguntar

Quem aciona a skill pode não a conhecer e esquecer-se de coisas. Antes de qualquer leitura de
produção, confere esta lista. **Pede tudo o que faltar numa única mensagem**, com o modelo abaixo
pronto a preencher. Não faças perguntas uma a uma.

## Mínimo necessário

| # | O quê | Obrigatório? | Se faltar |
|---|---|---|---|
| 1 | **Conta de trabalho**: o email da conta de teste de produção do colaborador, onde o agente vai ser montado e testado | sim | perguntar; sem ela não há onde configurar. Nunca usar a conta de um cliente como conta de trabalho. **Modo colaborador:** também a senha dessa conta (ver `modo-colaborador.md`, secção 1) |
| 1b | **Cliente**: o nome da empresa e, se já tiver conta, o email dela (só para ler o que tem hoje e para a entrega) | o nome, sim; o email, se existir | perguntar se o cliente já tem conta; se não tiver, a conta é criada na entrega (fase 8) |
| 2 | **Como o agente deve atender**: o objetivo e o estilo ("da abordagem até à marcação confirmada", "até pagar", "até passar ao vendedor") | sim | perguntar o objetivo final da conversa e o que **não** pode acontecer |
| 3 | **Referências do atendimento bom**: os **números de telefone** de 2–5 conversas que correram bem (preferido), prints ou um prompt descritivo | pelo menos uma | pedir os números; explicar que é a forma mais fiel |
| 4 | **Onde estão essas conversas**: no WhatsApp do cliente (WhatsApp Web) ou no CRM | se forem números | assumir "procura primeiro no CRM, depois no WhatsApp Web" e avisar que pode ser preciso ler o QR |
| 5 | **Tipo de agente** (01/02/03), se a pessoa souber | não | deduz-se nas fases 2–3 e confirma-se com ela |
| 6 | **Número de teste para o WhatsApp real** (um telemóvel que nunca falou com a conta) | só na fase 7 | pedir só quando chegar lá; avisar já no início que vai ser preciso |
| 7 | **Restrições**: o que não se pode mudar na conta (ex.: "o cliente não quer que mexam nos preços") | não | perguntar uma vez: "há alguma coisa na configuração que não se pode mudar?" |

Antes de perguntar, resolve sozinho o que der: o `user_id` e o `ai_profile_id` de cada conta vêm do
email (leitura em produção); o nome do agente e o nicho vêm do perfil do cliente, se existir; o tipo de
agente configurado vem do `template_key`/`agent_mode`.

Se o email da conta de trabalho for de uma conta com leads reais ou com plano de cliente pago, **pára
e confirma**: pode ser a conta de um cliente dada por engano.

## Modelo de mensagem para pedir o que falta

Adapta e envia só as linhas que faltam:

```
Para configurar o agente, preciso de:
1. O email da tua conta de teste (a conta de produção onde vou montar e testar o agente).
   E o cliente: o nome da empresa e, se já tiver conta no CRM, o email dela.
2. Em 1–2 frases: até onde o agente deve levar a conversa (ex.: "até a marcação ficar confirmada")
   e o que nunca pode fazer.
3. Os números de telefone de 2 a 5 conversas que correram bem — com indicativo (ex.: +351 912 345 678).
   Se não tiveres números, servem prints das conversas.
   [Se as conversas foram feitas à mão no WhatsApp do cliente: vou abrir o WhatsApp Web no Chrome e
   só ler; pode ser preciso leres o QR com o telemóvel da conta.]
4. (Opcional) Há alguma coisa na configuração que não se pode mudar?
No fim vou pedir-te um telemóvel de teste que nunca tenha falado com a conta, para uma conversa real.
Quando estiver tudo validado, digo-te como exportar o agente e passá-lo para a conta do cliente.
```

## Retomada

Se existir `.claude/agentes/<slug>/README.md`, não peças o que já lá está. Lê "Estado atual" e "Onde
retomamos". Confirma só o que pode ter mudado entretanto, como as correções feitas noutras conversas
(placeholder `[preencher …]` do prompt de retomada). Depois segue "Retomar depois de correções feitas
noutras conversas" da `diagnosticar-agente`.

## Slug da bancada

É o nome da empresa em minúsculas com hífens (ex.: `sensi-vitae`). Antes de criar uma bancada nova,
confirma se já existe uma em `.claude/agentes/` para a mesma conta.
