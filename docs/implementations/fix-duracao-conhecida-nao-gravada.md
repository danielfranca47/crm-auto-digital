# A marcação fica com a duração padrão quando o cliente já disse a duração

**Branch:** `worktree-fix+duracao-conhecida-nao-gravada` (worktree `.claude/worktrees/fix+duracao-conhecida-nao-gravada`)
**Status:** Em andamento
**Autonomia:** manual
**Origem:** bateria PROD08 do agente Sensi Vitae (16/11/2026), cenário `p-relax90`
(`.claude/agentes/sensi-vitae/tentativas/20261116-1357-PROD08-p-relax90.*`).

---

## Motivação

O cliente pediu "massagem relaxante de 90 minutos" e marcou terça às 14h. O recibo
"Experiência Agendada" diz "Lomi Lomi - 90 min", mas a marcação ficou gravada **14h–15h** (60 min,
a `default_session_duration_minutes` da conta). Com sessões seguidas e a margem entre sessões, a
agenda deixa marcar outro cliente às 15h30 por cima da sessão real (que acaba às 15h30 + 30 min
de margem). O terapeuta só descobre o choque no dia.

---

## Problemas Identificados (estado anterior)

1. **A Filha não devolveu a duração:** no turno do resumo ("Pode confirmar?" = sim), a Filha
   devolveu `meeting_datetime_candidate` sem `meeting_duration_minutes`.
2. **A proteção sabia a duração mas não a passava:** `_apply_meeting_confirmation_guard`
   (`backend-executors/app/services/decision_engine.py`) usa `meeting_proposal.missing_duration`,
   que vê "90 minutos" no texto do lead e por isso deixa gravar — mas não escrevia essa duração no
   sinal. Nos caminhos `ok`/`skip` a função saía antes de mexer nos sinais.
3. **O scheduler caía no padrão:** `meeting_scheduler.handle_meeting_scheduled()` usa
   `signal.duration_minutes or _resolve_default_duration_minutes(ai_profile)` → 60.

A tabela de serviços da conta está certa (Base de Conhecimento, `structured_v1` com 20/30/45/60 e
Lomi Lomi 45/60/90).

---

## Abordagem

```
turno da confirmação (meeting_scheduled=true, lead já na fase)
  → reconcile_confirmation (como antes: candidato = horário aceite, ou bloqueia)
  → não bloqueado e Filha sem meeting_duration_minutes?
       known_duration(): mensagem atual do lead → proposta aceite (só se tiver 1 duração)
                         → mensagens anteriores do lead (mais recente primeiro)
                         com tabela de serviços, só vale uma duração que esteja nela
       → child_signals_structured.meeting_duration_minutes = essa duração
  → meeting_scheduler grava com ela
```

Decisões:
- **Filha contradiz o lead → fica a da Filha** (foi ela que escreveu o recibo; marcação e texto
  ficam iguais). A do lead só fica no rasto (`duration_lead`).
- **Remarcação não muda:** `handle_meeting_cancel_or_reschedule` já usa a duração do compromisso
  original — com a marcação original certa, a remarcação fica certa.
- Não muda prompts. O guard corre no mesmo caminho para Playground e WhatsApp real.

---

## Plano de Implementação

### Fase 1 — Preencher a duração já conhecida

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_proposal.py` | `known_duration(lead_texts, proposal_text, pricing_table)` → `(minutos, origem)` |
| `backend-executors/app/services/decision_engine.py` | `_lead_texts` / `_pricing_table` (partilhados com `_missing_booking_duration`); `_fill_known_duration` chamado em `_apply_meeting_confirmation_guard` também nos caminhos `ok`/`skip`; rasto `duration_filled` / `duration_source` / `duration_lead`; log `event=meeting_duration_filled` |
| `backend-executors/tests/test_meeting_confirmation_guard.py` | 4 testes novos (leitura da duração; preenche; mantém a da Filha; sem duração fica o padrão) |
| `docs/architecture/agenda.md` | "Turno da confirmação" e "Duração da sessão" |
| `docs/architecture/knowledge-base.md` | chaves do `structured_v1`: `nome`, `duracaoMinutos`, `preco`, `descricao` |

**Commit:** `5e47d62`

### Fase 2 — Três ajustes da validação PROD09 (16/11/2026)

Problemas vistos na validação da Fase 1:
1. **Combinação fora da tabela** (PROD09 `p-relax-sem-tipo`): a Lara confirmou "Relaxante
   Clássica - 90 min", e a Clássica só vai até 60 min. Decisão do Daniel: nesse caso, **handoff**
   — a equipa fecha a venda à mão (pode ser um orçamento personalizado).
2. **Duração no recibo:** sem `meeting_duration_minutes`, a duração escrita no recibo da Filha não
   era lida.
3. **"Como se chama?" depois de remarcar** (bancada `F1` `pos-marcacao`).

Só o código não sabe a que linha "Relaxante Clássica" se refere (as palavras batem em duas linhas):
a Filha diz a linha (`meeting_service`), o código confere se essa linha tem essa duração.

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/meeting_proposal.py` | `known_duration(..., reply_text)` com fonte `reply` primeiro; `pricing_rows()`, `service_fits()`, `OFF_TABLE` |
| `backend-executors/app/services/decision_engine.py` | `_booking_service_block` (bloco "SERVIÇO DA TABELA" nas variantes que confirmam); `_service_off_table` no `_apply_meeting_confirmation_guard` → handoff sem marcação; `_apply_meeting_reschedule_guard` tira a pergunta final quando a remarcação segue e o texto já a dá como feita |
| `backend-executors/tests/test_meeting_confirmation_guard.py` / `test_meeting_reschedule_guard.py` | 6 testes novos |
| `docs/architecture/agenda.md`, `docs/prompts_llms.md` | turno da confirmação (linha da tabela + handoff, ordem das fontes da duração), remarcação |

**Commit:** `c19531e`

Reforço depois da bancada (`F2` `p-classica-90`: marcou "Massagem Clássica - 90 min" e a Filha não
devolveu `meeting_service` — o pedido estava só no texto do bloco, não no schema que ela copia):
`meeting_service` passa a estar no schema do agendamento e no "SINAIS DA MARCAÇÃO" do
pré-agendamento; sem o campo, `meeting_proposal.service_in_text` lê a linha que o recibo nomeia sem
ambiguidade (3 testes novos).

**Commit do reforço:** `651e1ff`

Segundo reforço (bancada `F2b`):
- `pos-marcacao` e `p-micas`: **handoff errado** — a Filha devolveu "Massagem Relaxante Clássica"
  (o nome que as instruções da conta dão à Clássica), que não batia em nenhuma linha. Agora o bloco
  numera as linhas e pede o **número**; com um nome, um que bata em várias linhas só é off_table se
  nenhuma tiver a duração.
- `p-classica-90`: a Lara recusou bem a Clássica de 90 min, mas a cliente insistiu e a conversa
  ficou 14 turnos em círculo (o handoff só disparava ao gravar). Novo
  `_apply_off_table_insistence_guard`: a 2.ª vez que o lead pede, sem ambiguidade, uma combinação
  fora da tabela → handoff.

**Commit do 2.º reforço:** (a registar)

---

## Checks de Validação

### Testes automatizados
- [x] `pytest backend-executors/tests` — 531 passam (16/11/2026)

### Bancada local `.claude/agentes/sensi-vitae/` (código desta branch copiado para `ambiente/codigo`)
- [x] `p-relax90` — marcação gravada com 90 min (16/11/2026, `F1`: 14h–15h30; nesta corrida a
  própria Filha devolveu os 90 — o caminho em que ela os omite está coberto pelos testes)
- [x] `p-relax-sem-tipo` — marcação gravada com 90 min (16/11/2026, `F1`: 14h–15h30; idem)
- [x] Regressão `p-micas`, `pos-marcacao`, `p-seguidas` — sem pioras (16/11/2026, `F1`):
  `p-micas` quarta 15h Val 90 min; `pos-marcacao` 60 min e a remarcação manteve 60 min;
  `p-seguidas` 16h Daniel 60 min, sem erro

### Produção (`--prod`, depois do merge e deploy)
- [x] `p-relax90` e `p-relax-sem-tipo` com 90 min (16/11/2026, `PROD09`: 14h–15h30 nos dois)
- [x] Regressão `p-micas`, `pos-marcacao`, `p-seguidas` (16/11/2026, `PROD09`): `p-micas` quarta
  15h Val 90 min; `pos-marcacao` 60 min e remarcação com 60 min; `p-seguidas` 16h Daniel 60 min

### Fase 2
- [x] `pytest backend-executors/tests` — 541 passam (16/11/2026)
- [ ] Local: combinação fora da tabela (ex.: Clássica 90 min) → handoff, sem marcação
- [ ] Local: `p-relax90`, `p-relax-sem-tipo` (Lomi Lomi 90 → grava 90 min), `p-micas`,
  `pos-marcacao` (remarcação sem pergunta no fim), `p-seguidas`
- [ ] `--prod`: a mesma bateria depois do merge e deploy

---

## Ajustes Possíveis Pós-Implementação

(Os três da Fase 1 foram resolvidos na Fase 2.)

---

## Relatório da Fase 1 — o que mudou na prática

Quando um cliente diz quanto tempo quer ("90 minutos", "1h") e marca, a marcação passa a ficar
na agenda com essa duração, mesmo que a IA se esqueça de a passar ao sistema. Antes, nesse
esquecimento, ficava a duração padrão da conta (60 min) e a agenda podia aceitar outro cliente
por cima da sessão. Se a IA disser uma duração diferente da do cliente, fica a da IA (é a que
aparece no recibo que o cliente lê); a diferença fica registada para análise. Remarcar mantém a
duração da sessão original, como já era.
