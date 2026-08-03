# Agenda mostra dois fusos quando o fuso do negócio difere do navegador

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Na Fase 3 de `fix-confirm-exact-agenda-vazia.md` (já graduada — ver
`docs/architecture/agenda.md`), a Agenda passou a exibir e salvar horários de compromisso
sempre no fuso configurado no AI Profile (`ai_profile.timezone`), em vez do fuso do
navegador de quem está a olhar a tela.

Isso corrigiu o bug original, mas criou uma confusão inversa possível: se o utilizador
administra a agenda de um negócio noutro fuso (ex.: ele em Lisboa, negócio configurado em
`America/Sao_Paulo`), ver só "17:00" sem indicação de fuso não deixa claro que é 17h de São
Paulo, não do relógio local. O utilizador pediu para a Agenda deixar isso explícito nas
listagens, e dar controlo (não substituição forçada) na grade visual — que por defeito
continua no fuso do navegador (útil para o próprio utilizador se planear), com um botão para
ver no fuso do negócio quando ele precisar raciocinar sobre o horário combinado com o lead.

Quando o fuso do negócio é igual ao do navegador, nada disto é necessário — o comportamento
actual (pós-Fase-3) já está correcto e não deve mudar.

---

## Problemas Identificados (estado anterior)

1. **Listagens mostram só o fuso do negócio, sem indicação de qual fuso é:**
   `ScheduleView.tsx`, `Dashboard.tsx`, `LeadCardDialog.tsx`, `ProspectionCardDialog.tsx` —
   todos formatam `startTime`/`endTime` só no fuso do negócio (`toBusinessTimezoneDate` +
   `format(..., "HH:mm")`), sem indicar a cidade/fuso nem oferecer o horário local de quem
   está a ver a tela.

2. **Grade visual (WeekView/DayView) força sempre o fuso do negócio, sem alternativa:**
   posicionamento dos eventos, indicador "agulha" de hora actual e agrupamento por dia usam
   sempre `businessTimezone` — não há forma de ver a grade no fuso do próprio navegador nem
   de alternar entre os dois.

---

## Abordagem

```
useBusinessTimezone() → { businessTimezone, browserTimezone }
  ├─ businessTimezone === browserTimezone → comportamento actual, sem UI nova
  └─ businessTimezone !== browserTimezone
       ├─ Listagens/resumos → AppointmentTimeLabel mostra os dois horários
       │    "17:00 (São Paulo) · 21:00 (Lisboa)"
       └─ Grade (WeekView/DayView) → useAgendaTimezoneMode (localStorage)
            ├─ por defeito: mode="browser" → grade/agulha no fuso do navegador
            └─ botão de alternância → mode="business" → grade/agulha no fuso do negócio
                 (persistido entre sessões, o utilizador troca quantas vezes quiser)
```

---

## Plano de Implementação

### Fase 1 — Utilitários + aplicação em listagens e grade

**Objetivo:** rótulo dual-fuso nas listagens e toggle de fuso na grade visual, sem alterar
nada quando os fusos coincidem.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/lib/timezone.ts` | Nova função `getTimezoneCityLabel(timeZone)` — mapa curado (São Paulo, Manaus, Fortaleza, Belém, Noronha, Lisboa, Londres, UTC) + fallback genérico a partir do próprio IANA string |
| `frontend-crm/src/hooks/useBusinessTimezone.ts` | Passa a exportar também `browserTimezone` |
| `frontend-crm/src/components/AppointmentTimeLabel.tsx` (novo) | Componente que renderiza um horário (fuso do negócio) ou dois (negócio + navegador, com cidade) conforme mismatch |
| `frontend-crm/src/hooks/useAgendaTimezoneMode.ts` (novo) | Estado do toggle da grade, persistido em `localStorage` (`agenda_grid_timezone_mode`), default `"browser"` |
| `frontend-crm/src/components/ScheduleView.tsx` | `event.time` → `AppointmentTimeLabel` (modo calendário + modo lista) |
| `frontend-crm/src/components/Dashboard.tsx` | Horário em "Reuniões de Hoje" → `AppointmentTimeLabel` |
| `frontend-crm/src/components/LeadCardDialog.tsx` | Só nos 4 pontos de horário de reunião (não em `createdAt`/`lastMovement`) → `AppointmentTimeLabel` |
| `frontend-crm/src/components/prospection/ProspectionCardDialog.tsx` | Listas "Próximos"/"Histórico" → `AppointmentTimeLabel` |
| `frontend-crm/src/components/WeekView.tsx` | `businessTimezone` → `activeTimezone` (via `useAgendaTimezoneMode`) no posicionamento, agulha e labels; botão de alternância na navbar, visível só quando `mismatched` |
| `frontend-crm/src/components/DayView.tsx` | Idem WeekView |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `4ad8f75` | feat: Agenda mostra dois fusos quando fuso do negocio difere do navegador |

**Detalhes do commit `4ad8f75`:** ver tabela de arquivos acima.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** a Agenda mostrava sempre só o horário do fuso do negócio, sem indicar de qual
fuso é — quem administra uma agenda de um negócio noutro fuso não tinha como saber, só de
olhar "17:00", se isso é hora local ou hora do negócio. Na grade semanal/diária não havia
opção nenhuma: era sempre o fuso do negócio.

**Agora:** quando o fuso do negócio é diferente do fuso de quem está a ver a tela, as
listagens (Agenda, Dashboard, card do lead, Prospecção) mostram os dois horários lado a
lado com o nome da cidade de cada um (ex. "17:00 (São Paulo) · 21:00 (Lisboa)"). Na grade
semanal/diária, aparece um botão para alternar entre ver no fuso do navegador (padrão) ou
no fuso do negócio — a escolha fica guardada entre sessões. Quando os fusos são iguais,
nada disso aparece — continua exatamente como antes.

**Para validar:** Cenários P1, P2 e C1, abaixo.

---

## Checks de Validação

### Cenário P1 — Listagens mostram os dois fusos quando há mismatch
- [x] Com AI Profile de teste em `America/Sao_Paulo` e navegador em Lisboa, abrir Agenda
  (modo calendário e modo lista), Dashboard, card de lead com reunião marcada,
  Prospecção (Próximos/Histórico) — 04/08/2026
- [x] Confirmar: todos mostram os dois horários com nome de cidade (ex. "17:00 (São
  Paulo) · 21:00 (Lisboa)") — 04/08/2026

### Cenário P2 — Grade com toggle de fuso
- [x] Abrir WeekView e DayView — botão de alternância visível — 04/08/2026
- [x] Por defeito, grade e agulha no fuso do navegador (Lisboa) — 04/08/2026
- [x] Clicar no botão → grade e agulha passam para o fuso do negócio (São Paulo);
  clicar de novo reverte — 04/08/2026
- [x] Recarregar a página → última escolha persistida (localStorage) — 04/08/2026

### Cenário C1 — Sem regressão quando os fusos coincidem
- [x] Definir o AI Profile de teste com `timezone` = `Europe/Lisbon` (ou `NULL`) — 04/08/2026
- [x] Confirmar: nenhum rótulo duplo em nenhuma listagem, botão de alternância some do
  WeekView/DayView — comportamento idêntico ao estado pós-Fase-3 — 04/08/2026
- [x] Restaurar o profile para `America/Sao_Paulo` — 04/08/2026

**Validado em:** 04/08/2026 — testado ao vivo via browser (MCP), com fuso do navegador
emulado para bater com o cenário (o SO local resolve para `Europe/London`, mesmo offset de
Lisboa em agosto — por isso os rótulos capturados mostram "Londres" em vez de "Lisboa", mas
o mecanismo de mismatch/label é o mesmo). Compromisso de teste criado no lead "DF FLOW
BARBERSHOP" (17:00–18:00 América/Sao_Paulo) via `ScheduleAppointmentDialog`, verificado em
todos os pontos do P1, alternado via toggle nos Cenários P2 (WeekView e DayView, incluindo
persistência pós-reload), e removido o dual-fuso trocando o timezone do AI Profile de teste
para `Europe/Lisbon` no Cenário C1 (nenhum rótulo duplo, botão de alternância ausente).
Compromisso de teste cancelado e AI Profile restaurado para `America/Sao_Paulo` ao final.

---

## Ajustes Possíveis Pós-Implementação

- `ScheduleAppointmentDialog.tsx` (form de criar/editar) continua só no fuso do negócio —
  não foi pedido mostrar/editar nos dois fusos no formulário de escrita.
