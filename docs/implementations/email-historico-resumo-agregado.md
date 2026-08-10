# Resumo agregado no painel Histórico (email + WhatsApp)

**Branch:** *(definir no Plan Mode)*
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/email-cold-outreach-historico-analytics.md` (histórico/analytics de emails
enviados). Nessa implementação, o painel "Histórico" (agent-local) e "Leads do Agente"
(frontend-crm, `Pesquisa.tsx`) passaram a mostrar canal (Email/WhatsApp), contacto e estado
(`Enfileirado`/`Enviado`/`Falhou`) por linha — mas continuam sem nenhum resumo agregado
("X enviados / Y falharam / Z enfileirados"). O utilizador confirmou, na graduação dessa
implementação, que quer avançar já com este resumo.

Ideia original (registada na implementação graduada, secção "Fase E — proposta"): cards/labels de
contagem calculados **client-side** sobre a lista já carregada pela UI (`self._historico_entries`
no agent-local, `entries` no `Pesquisa.tsx`), sem rota nova — trade-off conhecido: é uma
aproximação sobre a janela de `limit=200` registos, não um total histórico exacto (um total exacto
exigiria uma rota nova com `GROUP BY channel, action` sobre `prospection_logs`, decisão a validar
no Plan Mode desta implementação).

Contexto arquitectural relevante:
[`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md#histórico) (colunas e
os dois consumidores da rota `GET /api/prospeccao/history`) e
[`docs/architecture/agents.md`](../architecture/agents.md#dois-caminhos-de-report-de-job--agente-local-vs-backend-executors)
(pipeline que alimenta `prospection_logs`).

**Este arquivo ainda não tem plano.** O diagnóstico (o que já existe, o que construir, riscos:
client-side vs rota agregada nova) e a aprovação do utilizador acontecem no Plan Mode, antes de
qualquer código — ver `_guia-documentar-implementacao.md`.
