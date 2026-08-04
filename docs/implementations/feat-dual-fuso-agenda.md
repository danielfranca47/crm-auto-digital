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

### Fase 2 — Legenda de fuso no formulário de criar/editar compromisso

**Objetivo:** fechar o ajuste registrado em "Ajustes Possíveis Pós-Implementação" — o
`ScheduleAppointmentDialog.tsx` continuava salvando sempre no fuso do negócio sem indicar
isso visualmente, criando risco de desvio silencioso de horário para quem preenche o
formulário num fuso diferente (ex.: digitar "17h" pensando no próprio relógio, mas o sistema
interpretar como 17h do negócio — 4h de diferença sem aviso nenhum na tela).

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/ScheduleAppointmentDialog.tsx` | Extrai `combineDateTimeInTimezone` (dedup da conversão já usada em `handleSubmit`); `useMemo` calcula o horário digitado convertido para o fuso do navegador; legenda abaixo dos campos Início/Fim, visível só quando `businessTimezone !== browserTimezone` |

```tsx
// ANTES — campos sem qualquer indicação de fuso
<Label>Horário</Label>
<Input id="time" type="time" value={time} onChange={...} />
<Input id="endTime" type="time" value={endTime} onChange={...} />

// DEPOIS — legenda condicional abaixo dos campos
{timezonePreview && (
  <p className="text-[11px] text-muted-foreground">
    Horário em {getTimezoneCityLabel(businessTimezone)} (fuso do negócio) —
    equivale a {timezonePreview.start}–{timezonePreview.end} no seu fuso (
    {getTimezoneCityLabel(browserTimezone)})
  </p>
)}
```

Não altera `handleSubmit` além de reusar o novo helper — payload e comportamento de
gravação continuam idênticos. Sem mudança quando os fusos coincidem.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `a0495be` | feat: mostra legenda de fuso no formulario de agendar/editar compromisso |

**Detalhes do commit `a0495be`:** ver tabela de arquivos acima.

### Relatório da Fase 2 — o que mudou na prática

**Antes:** ao criar ou editar um compromisso, os campos "Início" e "Fim" não diziam em
nenhum lugar em qual fuso horário aquele valor seria gravado — quem preenche num fuso
diferente do negócio podia digitar um horário pensando no próprio relógio e o sistema
gravava outro, sem nenhum aviso.

**Agora:** quando o fuso do negócio é diferente do fuso de quem está a preencher o
formulário, aparece uma legenda abaixo dos campos de horário mostrando a que horas isso
equivale no fuso de quem está a ver a tela (ex. "Horário em São Paulo (fuso do negócio) —
equivale a 21:00–22:00 no seu fuso (Lisboa)"), atualizando conforme a hora/data digitada
muda. Quando os fusos coincidem, nada muda — formulário idêntico ao de antes.

**Para validar:** Cenário P3 e as regressões abaixo.

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

### Cenário P3 — Legenda de fuso no formulário de criar/editar
- [x] Com AI Profile de teste em `America/Sao_Paulo` e navegador em Londres (equivalente a
  Lisboa em agosto), abrir "Novo" na Agenda (ScheduleView) e digitar um horário — 04/08/2026
- [x] Confirmar: legenda aparece abaixo dos campos Início/Fim mostrando a conversão correta
  para o fuso do navegador, e atualiza ao mudar hora/data — 04/08/2026
- [x] Abrir "Reagendar" num compromisso existente — legenda aparece já preenchida com a
  conversão do horário atual — 04/08/2026

### Regressão — Sem mudança quando os fusos coincidem
- [x] Com AI Profile de teste em `Europe/London` (fusos iguais ao navegador), abrir "Novo" —
  confirmado que a legenda não aparece (form salta de "Horário" direto para "Data") —
  04/08/2026

### Regressão — Gravação continua correta
- [x] Criar um compromisso com a legenda visível (fusos diferentes) — confirmado, via
  request `POST /api/leads/{id}/appointments`, que o horário gravado (`start_at` em UTC)
  bate com o fuso do negócio digitado no formulário (09:30 São Paulo → `12:30:00.000Z`,
  equivalente a UTC−3), não com o fuso do navegador — 04/08/2026

**Validado em:** 04/08/2026 — testado ao vivo via browser (MCP), mesmo setup do Fase 1
(fuso do navegador resolvendo para `Europe/London`). Legenda verificada no "Novo" da
Agenda (ScheduleView) e no "Reagendar" de um compromisso existente, com atualização ao
digitar novo horário. Regressão de fusos iguais confirmada trocando o AI Profile de teste
para `Europe/London` e reconfirmando `America/Sao_Paulo` ao final. Gravação correta
confirmada inspecionando o payload de rede da criação (ver acima). Compromissos de teste
criados foram excluídos (soft-cancel, mesmo padrão do `Teste dual-fuso` da Fase 1) ao
final da validação.

**⚠️ Bug pré-existente encontrado durante a validação (fora do escopo desta feature):**
criar ou editar um compromisso pela Agenda → aba "Mensal" (`ScheduleView.tsx`) trava a
aplicação inteira com tela branca (`Uncaught RangeError: Invalid time value`, sem error
boundary, o React desmonta a árvore inteira). Reproduzido de forma consistente (2/2
tentativas). **Causa raiz:** `useCreateAppointment`/`useUpdateAppointment`
(`frontend-crm/src/hooks/useAppointments.ts`) chamam `normalizeAppointment(res)` sobre um
objeto que `api.createAppointment`/`api.updateAppointment` (`services/api.ts`) **já**
passou por `mapAppointment()` — que devolve a data no campo `startTime` (camelCase).
`normalizeAppointment()` só reconhece `start_at`/`start_time`/`startAt`/`start`, não
`startTime`, então o resultado fica com `startTime: ""`. `ScheduleView`'s `onSuccess`
(`setSelectedDate(new Date(appointment.startTime))`) grava uma Invalid Date em
`selectedDate`; no próximo render, `monthRange(selectedDate)` chama `.toISOString()` numa
data inválida e lança a exceção. Confirmado via stack trace capturada em runtime — bug
já existe desde a reorganização do repositório (commit `a19bdcf`), **não** foi introduzido
pela Fase 1 nem pela Fase 2 do dual-fuso, e independe do fuso horário (ocorreria também
com fusos iguais). Precisa de uma fase própria (fora deste arquivo) para corrigir — por
exemplo, fazer `normalizeAppointment()` também aceitar `raw.startTime`/`raw.endTime`, ou
não re-normalizar um objeto que `mapAppointment()` já normalizou.

---

## Ajustes Possíveis Pós-Implementação

- `ScheduleAppointmentDialog.tsx` (form de criar/editar) continua só no fuso do negócio —
  não foi pedido mostrar/editar nos dois fusos no formulário de escrita.
  **Endereçado na Fase 2:** o formulário continua gravando só no fuso do negócio (decisão
  mantida), mas agora mostra uma legenda com a conversão para o fuso do navegador — ver
  Fase 2 acima. Os campos em si continuam não-editáveis nos dois fusos (permanece fora de
  escopo).
