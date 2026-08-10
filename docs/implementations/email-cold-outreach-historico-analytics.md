# Histórico/analytics de emails enviados (cold outreach)

**Branch:** *(definir no Plan Mode)*
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/etapa-agent-local-v3-email-cold-outreach.md` (email cold outreach v1,
SMTP-only). Hoje não existe nenhum registo ou estatística dos emails de prospecção fria já
enviados — o utilizador não tem forma de ver quantos emails foram disparados, para quem, quando,
nem o resultado (`sent`/`failed`) fora da tabela `jobs` bruta.

Contexto arquitectural relevante (ver
[`docs/architecture/auth-email.md`](../architecture/auth-email.md#conta-smtp-do-utilizador-cold-outreach-por-email)
e [`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md#conta-de-email-smtp)):
- Job type `email.send.cold`, processado por `backend-executors/app/workers/email_worker.py` +
  `app/runners/email.py`
- Painel "Histórico" do agent-local (`_build_historico` em `main_screen.py`) já existe para
  WhatsApp (`GET /api/prospeccao/history`, JOIN `prospection_logs` + `leads`) — candidato natural
  a estender para email, se for essa a direcção escolhida no Plan Mode

**Este arquivo ainda não tem plano.** O diagnóstico (o que já existe, o que construir, riscos) e
a aprovação do utilizador acontecem no Plan Mode, antes de qualquer código — ver
`_guia-documentar-implementacao.md`.
