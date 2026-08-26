# WhatsApp Inbound — Melhorias Futuras

> Contexto: item deixado de fora da graduação de
> `docs/implementations/bot-disable-desqualificados.md` (desativação
> automática do bot ao mover lead para "Desqualificados"/"Prospecção
> Recusada").

## M1 — Bloqueio proativo por número de telefone (contatos pessoais)

**Prioridade: BAIXA**

Um cliente relatou que contatos pessoais (não-leads) escrevem no mesmo
número usado pelo bot (ele usa o número tanto para uso pessoal quanto
profissional), e o bot responde a eles como se fossem leads.

Hoje não existe bloqueio por número de telefone — `find_or_create_lead_by_phone()`
(`backend-crm/services/whatsapp_inbound/guardrail.py`) cria automaticamente
um lead para qualquer número novo que escreva, e o bot responde a menos que
esse lead específico já tenha `bot_disabled=1`. A mitigação atual (desativar
o bot ao mover o lead para "Desqualificados"/"Prospecção Recusada" — ver
[`docs/architecture/agents.md`](../architecture/agents.md#toggle-de-bot-por-lead))
é reativa: o bot ainda responde à primeira mensagem, e o operador precisa
lembrar de arquivar o lead depois.

A solução definitiva seria uma lista de números "ignorados" por usuário
(ex.: novo campo no AI Profile ou tabela própria), verificada no guardrail
**antes** de criar o lead — nesse caso a mensagem não geraria lead nem job,
descarte silencioso desde o primeiro contato.
