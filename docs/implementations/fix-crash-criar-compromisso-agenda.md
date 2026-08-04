# Fix: crash de tela branca ao criar compromisso na Agenda

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

Durante a validação da Fase 2 de `feat-dual-fuso-agenda.md` (legenda de fuso no
formulário de compromisso), criar um compromisso via Agenda → aba "Mensal"
(`ScheduleView.tsx`) travava a aplicação inteira com tela branca, de forma 100%
reproduzível. O app não tem error boundary, então qualquer exceção não capturada
durante o render desmonta a árvore React inteira — o utilizador perdia a tela sem
nenhuma mensagem de erro, só recarregando a página conseguia voltar a usar a Agenda.

O bug é anterior à feature de dual-fuso (existe desde a reorganização do repositório,
commit `a19bdcf`) e não depende de fuso horário — ocorreria também com o fuso do
negócio igual ao do navegador. Foi descoberto incidentalmente ao validar a regressão
"gravação continua correta" daquela feature.

Causa raiz: duplo mapeamento da resposta do backend ao criar um compromisso (ver
"Problemas Identificados" abaixo).

---

## Problemas Identificados (estado anterior)

1. **Duplo mapeamento da resposta de criação (causa do crash):**
   `frontend-crm/src/services/api.ts:759` — `api.createAppointment()` já transformava
   a resposta crua do backend com `mapAppointment(data)`, que devolvia um objeto com a
   chave `startTime` (camelCase). Em seguida,
   `frontend-crm/src/hooks/useAppointments.ts:135` (`useCreateAppointment`) chamava
   **de novo** `normalizeAppointment(res)` sobre esse objeto já mapeado.
   `normalizeAppointment()` só reconhece `start_at ?? start_time ?? startAt ?? start` —
   nenhuma dessas chaves bate com `startTime`, então `result.startTime` virava `""`.
   `ScheduleView.tsx`'s `onSuccess` fazia `setSelectedDate(new Date(appointment.startTime))`
   → Invalid Date; no próximo render, `monthRange()` (`ScheduleView.tsx:52`) chamava
   `.toISOString()` nessa data inválida → `RangeError: Invalid time value` sem
   tratamento.

   Só afetava o caminho de **criação**: `api.updateAppointment()` (`api.ts:762`) nunca
   usou `mapAppointment()` — sempre devolveu a resposta crua do backend diretamente, por
   isso editar um compromisso nunca reproduziu o crash.

2. **Bug irmão, sem crash (mesma causa):**
   `frontend-crm/src/contexts/LeadsContext.tsx:450` (`createAppointment`) também chamava
   `api.createAppointment()` e passava o resultado para `mapRawAppointment()`
   (`LeadsContext.tsx:101`), que reconhece `start_at`/`startAt` mas não `startTime` —
   caía no fallback `new Date()` (hora atual), gravando localmente um `startAt` errado
   até a próxima sincronização (`reloadAllLeads()`). Não crashava porque
   `mapRawAppointment` sempre tem um fallback de data válida, mas o resultado ficava
   temporariamente incorreto na UI.

---

## Abordagem

```
api.createAppointment() (POST /leads/{id}/appointments)
  ANTES: resposta crua do backend → mapAppointment() → { startTime, leadId, ... }
         → normalizeAppointment()/mapRawAppointment() não reconhecem "startTime"
         → data vira "" ou fallback errado
  DEPOIS: resposta crua do backend devolvida sem transformação
         → normalizeAppointment()/mapRawAppointment() reconhecem "start_at" (chave
           nativa do backend) de primeira — funciona corretamente
```

`api.createAppointment()` passa a devolver a resposta crua do backend, igual a
`api.updateAppointment()` e às demais funções de `api.ts` (`api.appointments.create/
update`, `api.getAppointments`) — a normalização já é responsabilidade exclusiva das
camadas consumidoras, que já sabiam lidar com o formato cru.

---

## Plano de Implementação

### Fase 1 — Remover o mapeamento duplicado

**Objetivo:** `api.createAppointment()` devolve a resposta crua do backend, consistente
com o resto de `api.ts`.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `createAppointment()`: `return mapAppointment(data)` → `return data`; função `mapAppointment()` removida (ficou sem uso — só era chamada aqui) |

```ts
// ANTES
    const data = await apiClient.post(`/leads/${leadId}/appointments`, { ... });
    return mapAppointment(data);
  },

// DEPOIS
    const data = await apiClient.post(`/leads/${leadId}/appointments`, { ... });
    return data;
  },
```

Nenhuma outra chamada foi afetada — busca por `api.createAppointment`/`mapAppointment`
confirma só 2 call sites (`useAppointments.ts:128`, `LeadsContext.tsx:450`), ambos já
preparados para o formato cru (`normalizeAppointment`/`mapRawAppointment` têm
`raw?.start_at` como primeira opção de fallback). Sem mudança de payload de request, sem
impacto em backend.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(pendente)* | fix: remove duplo mapeamento da resposta ao criar compromisso |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** criar um compromisso pela Agenda (aba Mensal → "Novo") travava a tela inteira
(ficava branca), sem nenhuma mensagem de erro — só recarregar a página resolvia.
**Agora:** criar um compromisso funciona normalmente, sem travar, em qualquer uma das
vistas da Agenda (Mensal, Semanal, Diária) e no card do lead.
**Para validar:** Cenários P1 e P2, abaixo.

---

## Checks de Validação

### Cenário P1 — Criar compromisso via Agenda → Mensal não crasha
- [ ] Abrir Agenda → aba "Mensal" → "Novo", selecionar um lead, preencher horário,
  Agendar
- [ ] Confirmar: sem tela branca / sem erro no console; compromisso aparece na
  listagem com o horário correto

### Cenário P2 — Outros pontos de entrada continuam funcionando
- [ ] Criar compromisso via Semanal, via Diária, e via `LeadCardDialog` (card do lead)
- [ ] Confirmar: sem crash em nenhum, compromisso aparece corretamente

### Regressão — Editar e excluir continuam funcionando
- [ ] Editar um compromisso existente (Reagendar → Salvar alterações) — sem crash,
  horário atualizado corretamente
- [ ] Excluir um compromisso — sem crash, some da listagem

---

## Ajustes Possíveis Pós-Implementação

- O app não tem error boundary — qualquer exceção futura não tratada num render vai
  continuar desmontando a árvore inteira (tela branca) em vez de mostrar um fallback
  amigável. Fora do escopo deste fix (que remove a causa pontual), mas fica registrado
  como risco estrutural para uma iteração futura.
