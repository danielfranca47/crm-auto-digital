# Diagnóstico do agente de um cliente — guia para onboarding e suporte

Para quando o agente de IA de uma conta não atende como devia, ou quando se configura o agente de um
cliente novo a partir de conversas que já correram bem. O trabalho é feito pelo Claude com a skill
`diagnosticar-agente`; este guia diz como pedir, o que esperar e o que fica para ti decidir.

---

## Como pedir

Numa conversa do Claude Code na pasta do projeto:

> O agente da conta **email@cliente.com** não está a atender como nestas conversas:
> **+351 9xx xxx xxx**, **+351 9xx xxx xxx**. Quero que faça desde a abordagem até **[o objetivo:
> agendamento e confirmação / pagamento / passagem ao vendedor]**.

Dá 2 a 5 números de conversas que correram bem (feitas por uma pessoa ou por uma versão anterior do
agente). Se faltar alguma coisa, o Claude pergunta tudo de uma vez.

Para retomar um cliente já trabalhado: "retoma o diagnóstico do agente do cliente X". A pasta dele em
`.claude/agentes/<cliente>/` guarda tudo, incluindo o ponto onde se parou.

---

## O que acontece

1. **Lê as conversas.** Primeiro no CRM; se foram feitas à mão, no WhatsApp Web (pode pedir-te para ler o QR
   code com o telemóvel da conta). Só lê — nunca envia nada.
2. **Escreve o roteiro real:** os passos, as frases usadas, os preços, os limites, e o que não bate certo
   com a Base de Conhecimento.
3. **Identifica o tipo de agente** de que o cliente precisa — Agente 01 (SDR de Alto Ticket), 02 (Vendedor
   Autônomo) ou 03 (Assistente Comercial), como na página Tipos de Agentes — e se os contactos chegam
   (inbound) ou são abordados (outbound). Se o agente configurado for de outro tipo, avisa-te primeiro.
4. **Testa num ambiente isolado** com clientes simulados por IA, que conversam como as pessoas das
   conversas reais.
5. **Afina a configuração** uma mudança de cada vez e mede cada versão em números ("9 de 9 marcações no dia
   certo").
6. **Confirma no Playground de produção:** o sistema real, sem mandar mensagens a ninguém.
7. **Aplica em produção** — só com o teu "sim", com cópia de segurança antes.
8. **Regista o que precisa de código** nos planos do projeto, com prompts prontos para outra conversa.

---

## O que recebes

- Um relatório em linguagem simples: o que já funciona, o que falta e porquê.
- Perguntas de negócio quando as conversas não chegam para decidir (ex.: "às 17h a sessão tem de acabar ou
  pode começar?"), sempre com uma opção recomendada.
- Prompts prontos para corrigir no código o que a configuração não resolve.
- Um prompt de retomada que diz exatamente onde continuar.

## O que fica sempre contigo

- O "sim" para aplicar em produção e para mudar o tipo de agente.
- O teste final no WhatsApp real, a partir de um número que nunca falou com a conta.
- As decisões de negócio do cliente.

---

## Dados e privacidade

As conversas, os testes e as cópias de segurança de cada cliente ficam em `.claude/agentes/<cliente>/`, fora
do repositório. Nos documentos do projeto entram só números agregados e exemplos sem dados pessoais.

---

## Onde está cada coisa

| O quê | Onde |
|---|---|
| Como o Claude faz o diagnóstico (passos e scripts) | `.claude/skills/diagnosticar-agente/` |
| O que medir em cada tipo de agente | `.claude/skills/agente-01-sdr-alto-ticket/`, `agente-02-vendedor-autonomo/`, `agente-03-assistente-comercial/` |
| O que o sistema faz em cada agente | [`docs/architecture/agentes/`](../architecture/agentes/) |
| Dados de cada cliente | `.claude/agentes/<cliente>/` (fora do git) |

## Porquê está assim

- **Cada informação num só sítio.** Os passos vivem na skill, os factos do sistema em
  `docs/architecture/agentes/`, e este guia só explica o uso. As skills apontam para os docs em vez de os
  copiar, para nada ficar desatualizado em duplicado.
- **Uma skill de entrada que encaminha para 3 especialistas.** Uma só porta para quem pede; o conhecimento
  de cada tipo de agente fica separado e só se carrega quando é preciso.
- **Os nomes da página Tipos de Agentes**, para o time, os clientes e o Claude falarem da mesma coisa.
- **Skills versionadas, dados de clientes fora.** As skills chegam a qualquer máquina e sessão; as
  conversas reais nunca entram no repositório.
