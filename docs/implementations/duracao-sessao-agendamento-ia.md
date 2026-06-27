# Duração configurável de sessão no agendamento via IA

**Branch:** `main`
**Status:** Fase 1 validada via Playground (P1, C2) — pendente apenas C1 (teste real via WhatsApp)

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

### Fase 2 — Tabela de serviços/durações na Base de Conhecimento (planeada, não iniciada)

**Objetivo:** quando o profissional tiver mais de um tipo de sessão, a IA lê a
tabela cadastrada na Camada de Base de Conhecimento e confirma a duração certa.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` (`CAT_SERVICE_PRICING_TABLE`) | Deixar de depender de `appointment_mode==='commercial'`; incluir na lista padrão de `hybrid_scheduler` |
| `frontend-crm/src/components/agente/CamadaConhecimento.tsx:1046-1047` | Relaxar a condição que só mostra a categoria em modo comercial |
| `backend-executors/app/services/decision_engine.py::_build_child_prompt_agendamento` | Injetar bloco "SERVIÇOS E DURAÇÕES DISPONÍVEIS" a partir de `knowledge_items["service_pricing_table"]`; novo campo `meeting_duration_minutes` em `signals_structured` |
| `backend-executors/app/services/meeting_scheduler.py` (`_extract_meeting_signal`) | Capturar `meeting_duration_minutes` |
| `backend-executors/app/services/meeting_scheduler.py:717,841` | Prioridade: sinal da IA → `default_session_duration_minutes` → 30 |

Só começa depois de a Fase 1 ser validada pelo utilizador.

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

---

## Ajustes Possíveis Pós-Implementação

- Fase 2 ainda não tem tela própria — depende da categoria de conhecimento
  `service_pricing_table` ficar disponível fora do modo comercial.
- `docs/architecture/agenda.md` será corrigida na graduação (hoje só documenta
  `startTime` no payload do `ScheduleAppointmentDialog`, mas `endTime` já é
  enviado).
