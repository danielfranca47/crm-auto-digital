# Duração configurável de sessão no agendamento via IA

**Branch:** `main`
**Status:** Fase 1 e Fase 2 validadas via Playground (P1–P4, C2) — pendente apenas C1 (teste real via WhatsApp)

---

## Motivação

O utilizador testou o agendamento real via WhatsApp (agente híbrido agendador) e o
compromisso foi criado com apenas 30 minutos de duração. Como ele trabalha com
sessões de duração variável (ex.: 30, 60 e 90 min dependendo do serviço), queria
entender por que o sistema sempre agenda 30 min e como cadastrar durações
diferentes por tipo de serviço.

Causa raiz identificada: a duração é **hardcoded em 30 minutos** em
`backend-executors/app/services/meeting_scheduler.py:717` (criação) e `:841`
(reagendamento) — `signal.start_at + timedelta(minutes=30)` — sem nenhuma ligação
a configuração do negócio. Não existe hoje nenhum campo de duração de sessão em
lugar nenhum do sistema (AI Profile, `offer_pack`, catálogo).

---

## Problemas Identificados (estado anterior)

1. **Duração fixa na criação:** `meeting_scheduler.py:717` — `handle_meeting_scheduled()`
   sempre usa 30 min, independente do AI Profile ou do que foi negociado com o lead.
2. **Duração fixa no reagendamento:** `meeting_scheduler.py:841` —
   `handle_meeting_cancel_or_reschedule()` reaplica 30 min ao invés de preservar a
   duração original do compromisso ao mudar o horário.
3. **Sem dado de duração no sistema:** nenhum campo em `AIProfile`, `offer_pack` ou
   catálogo guarda duração de sessão.
4. **Filha de agendamento não sabe nada sobre serviços:** `decision_engine.py::_build_child_prompt_agendamento`
   (linha 3441) só recebe disponibilidade e horários ocupados.
5. **Categoria de conhecimento quase pronta mas não usada no agendamento:**
   `CAT_SERVICE_PRICING_TABLE` (`frontend-crm/src/types/agente.ts:887`, key
   `service_pricing_table`) já tem placeholder com duração por linha, mas:
   - só aparece na UI quando `template_key=hybrid_scheduler` E
     `appointment_mode='commercial'` (`CamadaConhecimento.tsx:1046-1047`);
   - o conteúdo só é injetado no prompt da filha de **qualificação**
     (`decision_engine.py:2442-2477`), nunca chega à filha de agendamento;
   - mesmo quando o lead "fecha" um serviço específico nesse fluxo comercial,
     isso nunca é capturado como dado estruturado.
6. **`ScheduleAppointmentDialog.tsx` (UI manual) não tem gap** — já suporta hora de
   início/fim livres e já envia ambos no payload. A doc `docs/architecture/agenda.md`
   estava desatualizada nesse ponto (só descrevia `startTime`).

---

## Abordagem

Dividido em duas fases independentes e testáveis, para não acoplar o fix do bug
relatado a uma feature maior de múltiplos serviços:

```
Fase 1 — duração única configurável por conta (resolve o bug relatado)
  AI Profile ganha default_session_duration_minutes
  → meeting_scheduler usa esse valor em vez de 30 fixo
  → reagendamento preserva a duração original do compromisso

Fase 2 — múltiplos serviços com durações diferentes (ex. 30/60/90 min)
  Profissional cadastra na Base de Conhecimento → categoria "Tabela de Serviços e Preços"
  → filha de agendamento lê essa tabela e identifica a duração certa
  → fallback: default_session_duration_minutes (Fase 1) se a tabela não existir
    ou não houver correspondência clara (e nesse caso pergunta antes de assumir)
```

---

## Plano de Implementação

### Fase 1 — Duração padrão configurável por conta

**Objetivo:** substituir os 30 min fixos por um valor configurável pelo
profissional, e fazer o reagendamento preservar a duração original.

| Arquivo | O que muda |
|---|---|
| `backend-core/app/models/ai_profile.py` | Nova coluna `default_session_duration_minutes` |
| `backend-core/app/db.py` (`ensure_ai_profile_columns`) | Migração idempotente da nova coluna |
| `backend-core/app/api/ai_profiles.py` | Novo campo em `AIProfileBase`/`AIProfileUpdate` (`AIProfileOut` herda) |
| `frontend-crm/src/types/agente.ts` | Campo `default_session_duration_minutes` no tipo `AgentConfig` + default (30) |
| `frontend-crm/src/services/api.ts` | Mapear o novo campo no fetch/patch do AI Profile |
| `frontend-crm/src/components/agente/CamadaApresentacao.tsx` | Novo card "Duração da sessão" (seção "Disponibilidade de horários", ao lado de "Estilo de oferta de horário") + modal `ModalSessionDuration` com `SliderField` (15–180 min, passo 15) — não em `CamadaPipeline.tsx` como o plano original previa: essa camada já concentra `appointment_mode`/`scheduling_offer_style`, os campos mais próximos conceitualmente |
| `backend-executors/app/services/meeting_scheduler.py` | Novas funções `_resolve_default_duration_minutes()` e `_original_duration_minutes()`; usadas na criação (antiga linha 717) e no reagendamento (antiga linha 841, que agora preserva a duração original do appointment em vez de reaplicar 30 min) |

```python
# ANTES (meeting_scheduler.py:717)
end_dt = signal.start_at + timedelta(minutes=30)

# DEPOIS
ai_profile = context.get("ai_profile") or {}
duration_minutes = _resolve_default_duration_minutes(ai_profile)
end_dt = signal.start_at + timedelta(minutes=duration_minutes)
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e56a8c8` | Coluna `default_session_duration_minutes`, prompt/cálculo de duração no meeting_scheduler, card "Duração da sessão" no frontend |

**Detalhes do commit `e56a8c8`:**
- `backend-core/app/models/ai_profile.py` — nova coluna `default_session_duration_minutes`
- `backend-core/app/db.py` — migração idempotente em `ensure_ai_profile_columns()`
- `backend-core/app/api/ai_profiles.py` — campo em `AIProfileBase` e `AIProfileUpdate`
- `backend-executors/app/services/meeting_scheduler.py` — `_resolve_default_duration_minutes()`
  usada na criação; `_original_duration_minutes()` usada no reagendamento para preservar a
  duração original em vez de reaplicar 30 min
- `frontend-crm/src/types/agente.ts` — campo `default_session_duration_minutes` em `AgentConfig`
- `frontend-crm/src/services/api.ts` — mapeamento no fetch/patch do AI Profile
- `frontend-crm/src/components/agente/CamadaApresentacao.tsx` — card "Duração da sessão" +
  `ModalSessionDuration` (slider 15–180 min)

### Relatório da Fase 1 — o que mudou na prática

**Antes:** todo agendamento confirmado pela IA (WhatsApp real ou Playground) criava o
compromisso com exatamente 30 minutos de duração, sempre — não havia nenhuma forma de
configurar isso, e remarcar um horário também voltava para 30 min mesmo que o compromisso
original fosse mais longo.

**Agora:** em "Configurar Agente → Apresentação → Disponibilidade de horários → Duração
da sessão", o profissional define a duração padrão (15 a 180 min). A IA passa a usar esse
valor ao confirmar um agendamento, e ao remarcar um compromisso existente a duração
original é preservada (não volta para 30 min).

**Para validar:** Cenários P1, C1 e C2, na seção "Checks de Validação" abaixo.

---

### Fase 2 — Tabela de serviços/durações na Base de Conhecimento

**Objetivo:** quando o profissional tiver mais de um tipo de sessão, a IA lê a
tabela cadastrada na Camada de Base de Conhecimento e confirma a duração certa.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` (`CAT_SERVICE_PRICING_TABLE`) | Passa a integrar a lista **padrão** de `hybrid_scheduler` (não só o modo comercial); `when_used` atualizado para `'Apresentação comercial · Agendamento'`; removida da lista `KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL` para não duplicar (já herdada da lista padrão) |
| `backend-executors/app/services/decision_engine.py::_build_child_prompt_agendamento` | Novo bloco "SERVIÇOS E DURAÇÕES DISPONÍVEIS" lendo `context["knowledge_items"]["service_pricing_table"]`; `meeting_duration_minutes` adicionado ao schema de `signals_structured` e às regras de sinalização obrigatória |
| `backend-executors/app/services/meeting_scheduler.py` (`MeetingSignal`, `_extract_meeting_signal`) | Novo campo `duration_minutes`, lido de `structured_signals["meeting_duration_minutes"]` (validado como inteiro positivo) |
| `backend-executors/app/services/meeting_scheduler.py:756` (linha atual) | `handle_meeting_scheduled()`: prioridade `signal.duration_minutes or _resolve_default_duration_minutes(ai_profile)` |

**Desvios em relação ao plano original (simplificações encontradas durante a implementação):**
- **Não foi preciso tocar em `orchestrator.py`:** `_load_knowledge_items()` (backend-crm) já carrega TODAS as categorias do usuário para `context["knowledge_items"]` independente da fase — não há filtro por `when_used` no backend, isso é só um hint de UI. A tabela de preços já estava acessível em qualquer prompt, bastava lê-la.
- **Não foi preciso tocar em `CamadaConhecimento.tsx`:** a condição que troca para `KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL` em modo comercial faz uma **concatenação** (lista padrão + lista comercial), não uma substituição. Adicionar `CAT_SERVICE_PRICING_TABLE` à lista padrão já a torna visível em qualquer `appointment_mode`; foi preciso, sim, **remover** essa categoria da lista exclusiva comercial para não aparecer duplicada quando `appointment_mode='commercial'`.
- **Reagendamento (linha 841) não foi alterado nesta fase:** a Fase 1 já faz `handle_meeting_cancel_or_reschedule()` preservar a duração original do appointment — isso já é o comportamento correto mesmo com múltiplos serviços (reagendar não deveria trocar silenciosamente a duração). Estender o sinal de duração da IA ao reagendamento exigiria levar a tabela de serviços também ao prompt de gestão pós-confirmação (`_build_child_prompt_meeting_management`), que é um prompt separado — fora do escopo descrito para esta fase.

**Onde o profissional cadastra (resultado final):** Camada de Base de Conhecimento →
"Tabela de Serviços e Preços" → uma linha por serviço, formato `Nome — duração: preço`
(ex.: `Sessão avulsa - 30min: R$120`). Disponível em qualquer `appointment_mode`.

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `e285a46` | Categoria de conhecimento disponível fora do modo comercial, bloco de prompt na filha de agendamento, sinal `meeting_duration_minutes` no meeting_scheduler |

**Detalhes do commit `e285a46`:**
- `frontend-crm/src/types/agente.ts` — `CAT_SERVICE_PRICING_TABLE` na lista padrão de
  `hybrid_scheduler`; removida de `KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL` (evita duplicar)
- `backend-executors/app/services/decision_engine.py` — bloco "SERVIÇOS E DURAÇÕES
  DISPONÍVEIS" em `_build_child_prompt_agendamento`; `meeting_duration_minutes` no
  schema de `signals_structured`
- `backend-executors/app/services/meeting_scheduler.py` — `MeetingSignal.duration_minutes`,
  lido em `_extract_meeting_signal`; usado com prioridade em `handle_meeting_scheduled()`

### Relatório da Fase 2 — o que mudou na prática

**Antes:** mesmo com múltiplos tipos de sessão cadastrados, o sistema sempre aplicava
a mesma duração (a configurada na Fase 1, ou 30 min fixo). Não havia onde cadastrar
"este serviço dura X, aquele dura Y", nem a IA tinha como saber qual o lead pediu.

**Agora:** o profissional cadastra cada serviço com sua duração em "Base de
Conhecimento → Tabela de Serviços e Preços" (ex.: "Sessão avulsa - 30min: R$120").
Quando o lead pede um serviço específico, a IA identifica a linha certa e agenda com
essa duração. Se o lead não especificar qual serviço quer e houver mais de uma
opção, a IA pergunta antes de confirmar — não assume.

**Para validar:** Cenários P2, P3 e P4, na seção "Checks de Validação" abaixo.

---

## Checks de Validação

### Cenário P1 — Playground respeita a duração configurada
- [x] Configurar `default_session_duration_minutes=60` numa conta de teste
- [x] No Playground, pedir um agendamento e confirmar horário
- [x] Confirmar via API que `end_at - start_at` = 60 min
- **Validado em:** 27/06/2026 — via browser (chrome-devtools MCP), conta de teste
  (`autodigital157@gmail.com`, AI Profile id=5, `hybrid_scheduler`/`agenda`). Configurado
  "Duração da sessão" = 60 min em Apresentação. Sessão de Playground (lead #299):
  "Oi, gostaria de agendar uma sessão para amanhã às 15h" → bot ofereceu 09:00/11:00 →
  "Pode ser às 11h então, fica confirmado" → "Perfeito, a sessão está agendada para
  amanhã às 11h." `GET /api/appointments/lead/299` confirmou
  `start_at=2026-06-28T11:00:00Z`, `end_at=2026-06-28T12:00:00Z` — exatamente 60 min.

### Cenário C1 — WhatsApp real respeita a duração configurada
- [ ] Repetir o teste real que o utilizador já fez (agente híbrido agendador)
- [ ] Confirmar que a duração reflete o valor configurado (não mais 30 min fixo)
- **Pendente:** requer envio real via WhatsApp (UazAPI) — fora do alcance do browser
  automatizado; aguardando o utilizador repetir o teste e reportar.

### Cenário C2 — Reagendamento preserva a duração original
- [x] Pedir reagendamento de um compromisso de 60 min para outro horário
- [x] Confirmar que a duração se mantém 60 min (não volta a 30)
- **Validado em:** 27/06/2026 — na mesma sessão do Playground (lead #299, appointment
  id=44), mensagem "Na verdade, preciso remarcar. Pode ser às 14h no mesmo dia?" →
  "A sessão foi remarcada para amanhã às 14h." `GET /api/appointments/lead/299`
  confirmou `start_at=2026-06-28T14:00:00Z`, `end_at=2026-06-28T15:00:00Z` — duração
  de 60 min preservada (não voltou para 30 min).

### Cenário P2 — IA identifica o serviço certo e usa a duração correta
- [x] Cadastrar 2 linhas na "Tabela de Serviços e Preços" com durações distintas
- [x] Lead pede explicitamente um serviço específico → IA confirma com a duração certa
- **Validado em:** 27/06/2026 — cadastrado via API (`POST /api/knowledge`, category
  `service_pricing_table`): `"Sessão avulsa - 30min: R$120\nSessão estendida de
  massagem - 90min: R$220"`.
  - Lead #301: "quero marcar a sessão estendida de massagem" → bot ofereceu 09:00/16:00
    → "Pode ser às 09h então, fica confirmado" → "A sessão estendida de massagem está
    agendada para amanhã, 28 de junho, às 09:00." `GET /api/appointments/lead/301`:
    `start_at=09:00:00Z`, `end_at=10:30:00Z` — **90 min**, igual à linha "estendida".
  - Lead #302: "quero marcar a sessão avulsa de massagem" → bot ofereceu 10:30/15:00 →
    "Fica confirmado às 15h então" → confirmado. `GET /api/appointments/lead/302`:
    `start_at=15:00:00Z`, `end_at=15:30:00Z` — **30 min**, igual à linha "avulsa".
  - Confirma que a IA distingue corretamente entre os dois serviços na mesma tabela,
    não aplica sempre o mesmo valor.

### Cenário P3 — Ambiguidade: IA pergunta em vez de assumir
- [x] Lead pede "uma sessão" sem especificar qual, havendo mais de uma opção
- [x] Confirmar que a IA pergunta qual serviço antes de confirmar (não assume)
- **Validado em:** 27/06/2026 — lead #303: "quero marcar uma sessão de massagem para
  amanhã às 10h" (sem nomear o serviço) → bot respondeu "Amanhã às 10h já está
  reservado. Que tal agendar para amanhã às 11h ou às 15h? **Preciso saber qual
  serviço você prefere, se a sessão avulsa ou a sessão estendida.** Aguardo sua
  resposta!" — não confirmou nem assumiu uma duração.

### Cenário P4 — Sem tabela configurada, comportamento igual à Fase 1
- [x] Conta sem nenhuma linha em "Tabela de Serviços e Preços" → usa
  `default_session_duration_minutes`, sem quebrar
- **Validado em:** 27/06/2026 — coberto retroativamente pelo teste do Cenário P1
  (lead #299), executado **antes** de qualquer linha existir na tabela de serviços
  desta conta: resultou em 60 min (o `default_session_duration_minutes` configurado),
  sem erro e sem pedir esclarecimento — confirma o fallback correto quando a tabela
  não existe.

**Nota sobre um efeito colateral observado (não é bug desta feature):** durante o
primeiro teste do Cenário P2 (antes do teste final acima), um turno isolado expôs a
race condition já documentada em `docs/plans/agentes-agenda-melhorias-futuras.md`
(item M3) — a Mãe marcou `meeting_scheduled=true` no mesmo turno em que a filha de
agendamento respondeu "não está disponível" e ofereceu alternativas, criando um
appointment com horário de início incorreto (fallback para "agora"). A duração
calculada nesse appointment problemático já saiu correta (90 min) — confirma que a
extração de duração funciona independente do bug de horário —, mas o appointment foi
cancelado (`id=45`) por ter `start_at` inválido. Este é um problema pré-existente e
já registado para decisão futura (não corrigido aqui, por decisão já tomada pelo
utilizador no M3).

---

## Ajustes Possíveis Pós-Implementação

- Fase 2 ainda não tem tela própria — depende da categoria de conhecimento
  `service_pricing_table` ficar disponível fora do modo comercial.
- `docs/architecture/agenda.md` será corrigida na graduação (hoje só documenta
  `startTime` no payload do `ScheduleAppointmentDialog`, mas `endTime` já é
  enviado).
