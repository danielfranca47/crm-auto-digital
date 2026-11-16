---
name: agente-01-sdr-alto-ticket
description: Agente 01 · SDR de Alto Ticket — critérios de sucesso e cenários de teste para diagnosticar o agente de uma conta deste tipo (Filtros 1–3 com 4Ps, reunião com o vendedor, dossiê, follow-up por temperatura). Chamada pela diagnosticar-agente, ou quando se pede para testar a qualificação, o agendamento com o vendedor ou o follow-up de um Agente 01.
---

# Agente 01 · Robusto — SDR de Alto Ticket

Parte do fluxo da skill `diagnosticar-agente` (regras fixas, bancada, triagem e entregas estão lá).

**Factos do sistema** — preset, normalização do modo, etapas da página ↔ código, guardrails, prometido vs.
código, ficheiros: [`docs/architecture/agentes/agente-01-sdr-alto-ticket.md`](../../../docs/architecture/agentes/agente-01-sdr-alto-ticket.md).
Lê-o antes de escrever critérios ou instruções; a tabela "prometido vs. código" separa o que se afina na
configuração do que é achado de produto.

## Critérios-padrão (juntar aos da conta; ⚠ = crítico)

- Inbound: usa a dor que o lead já declarou, sem a perguntar de novo.
- ⚠ Sem fit (`disqualify_if`), encerra com educação ou manda para nurture, sem insistir.
- Uma pergunta por turno; ⚠ nunca repergunta um campo já respondido (`missing_fields` só desce no `.json`).
- Filtro 3: abaixo do score não agenda; acima avança (`qualification_advance_blocked` no trace).
- ⚠ Reunião gravada no dia e hora aceites (`--resumo`, coluna de dia divergente).
- ⚠ O bot não tenta fechar; durante a fase humana fica calado.
- Dossiê com nome, empresa, dor, 4Ps e canal.
- Outbound: o Filtro 2 desperta a dor sem vender; sem dor, encerra.
- Follow-up: tom e cadência da temperatura escolhida; sinal de compra notifica o vendedor.

## Cenários (adaptar à conta)

| Cenário | Persona | Esperado |
|---|---|---|
| `p-<real>` | uma por conversa de referência | o roteiro observado |
| `p-in-fit-ok` | inbound, perfil certo | F1 → F3 → reunião + dossiê |
| `p-in-sem-fit` | porte ou setor fora | encerra ou nurture |
| `p-tudo-de-uma-vez` | dá setor, verba, prazo e decisor na 1.ª mensagem | não repergunta; avança |
| `p-preco-cedo` | "quanto custa?" antes do F3 | responde e continua sem loop |
| `p-nao-decide` | "tenho de falar com o sócio" | trata o Poder; reunião com quem decide |
| `p-score-baixo` | sem verba nem prazo | nurture, sem agendar |
| `p-out-frio` | outbound, desconfiado | desperta a dor; descarta sem dor |
| `p-agenda` | aprovado, pede horário específico | gravado no horário aceite |
| `p-quer-humano` | "quero falar com uma pessoa" | handoff conforme `handoff_policy` |

Follow-up por temperatura: avançar o tempo com `POST /api/playground/leads/{lead_id}/skip-wait`.

## Atenção neste agente

- Com `human_in_loop`/`requires_handoff` ligados, o executor trata-o como `consultivo` (sem agendamento) e o
  CRM como `agenda` — confirma no trace (`agent_mode`) antes de concluir sobre o comportamento.

## Exemplo trabalhado

Ainda não há nenhum. Regista aqui a pasta da bancada do primeiro diagnóstico.
