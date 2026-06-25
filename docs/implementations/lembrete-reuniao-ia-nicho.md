# Lembrete de reunião gerado por IA (tom + nicho + pedido de confirmação)

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

O lembrete automático de compromisso (`whatsapp.appointment.reminder`) é hoje um
template Python fixo (`backend-executors/app/runners/whatsapp.py:
_execute_appointment_reminder_pipeline`): sempre o mesmo texto, sem IA, sem ler
`tone_of_voice`/`custom_instructions`, e sem pedir confirmação ao lead — só avisa.

Num agente multi-nicho (ex.: demo de massoterapia), isso tem dois problemas:
1. Não pede confirmação de presença — só informa.
2. Mesmo trocando para IA, o vocabulário ainda sairia errado: quando a própria IA
   fecha o agendamento, o título do compromisso é hardcoded como `"Reunião
   agendada"` (`meeting_scheduler.py:574`), sem noção de nicho. Para uma
   massoterapeuta deveria ser "sessão", não "reunião".

---

## Problemas Identificados (estado anterior)

1. **Sem IA no lembrete** (`whatsapp.py:486-530`) — `reminder_text` é um f-string
   fixo, nunca chama `llm_service`.
2. **Título do compromisso genérico e fixo** (`meeting_scheduler.py:574`) —
   `"Reunião agendada"` sempre, sem ler `niche`/`offer_description` do AI Profile.
3. **`context` já tem tudo que falta e está sendo ignorado** — `ai_profile`
   completo (niche, tone_of_voice, custom_instructions, brand_name,
   offer_description) já chega em `_execute_appointment_reminder_pipeline` via
   `context.get("ai_profile")` (carregado genericamente para todo job em
   `backend-crm/routes/executor.py:439-440`), mas a função não usa nada disso.

---

## Abordagem

```
Job whatsapp.appointment.reminder dispara
  → _execute_appointment_reminder_pipeline(context já tem ai_profile completo)
       → meeting_scheduler.generate_appointment_reminder_message(ai_profile, lead, title, time_str)
            → monta prompt com tom + nicho + nome do lead (ou instrução de omitir)
            → instrui: se título for genérico, troca por termo do nicho
            → instrui: pedir confirmação de presença
            → llm_service.generate_appointment_reminder_message(prompt)  [texto puro, sem JSON]
       ├─ sucesso → usa texto gerado
       └─ falha/timeout/sem texto → cai no template fixo atual (nunca deixa de enviar)
```

Padrão reutilizado: `meeting_scheduler._generate_conflict_message` (já existe,
mesma forma — prompt com tom/brand/identity_mode, chamada a `llm_service`, nunca
propaga excepção, fallback fixo no caller). `llm_service.generate_conflict_message`
é a única das 4 funções de `llm_service.py` que não força JSON — por isso ganhou
uma irmã nova (`generate_appointment_reminder_message`) em vez de reusar o
schema `ChildResult` (pensado para routing de categoria, overkill aqui).

**Simplificação deliberada:** todo lembrete (1º mais distante, 2º mais próximo)
pede confirmação — não há lógica diferente por proximidade nesta fase, para não
precisar adicionar metadado novo ao payload do job. **Fora de escopo:** corrigir
o título na origem (`meeting_scheduler.py:574`) — maior blast radius (Kanban,
dossiê, agenda do operador), fica para uma melhoria futura separada.

---

## Plano de Implementação

### Fase única — IA no lembrete com fallback fixo

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/llm_service.py` | Nova função `generate_appointment_reminder_message(prompt)` — irmã de `generate_conflict_message`, texto puro sem JSON |
| `backend-executors/app/services/meeting_scheduler.py` | Nova função pública `generate_appointment_reminder_message(ai_profile, lead, *, appointment_title, time_str, logger)` — monta prompt com tom/nicho/nome, chama `llm_service`, nunca propaga excepção |
| `backend-executors/app/runners/whatsapp.py` | `_execute_appointment_reminder_pipeline` passa a chamar a função acima antes de montar o `reminder_text` fixo; usa o resultado da IA ou cai no fallback |

### Commits Fase única

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | _(preenchido após o commit)_ | |

---

## Checks de Validação

### Cenário P1 — Lembrete usa tom/nicho do AI Profile
- [ ] Configurar AI Profile de teste com `niche` específico (ex.: massoterapia) e `tone_of_voice` customizado
- [ ] Disparar um lembrete (offset próximo) e inspecionar o texto enviado
- [ ] Confirmar: não repete "reunião" genérica, usa termo do nicho; pede confirmação
- **Pendente**

### Cenário P2 — Lead sem nome não gera placeholder
- [ ] Lead de teste sem `contactName`/`name`
- [ ] Confirmar: mensagem não inventa nome nem usa "Cliente" genérico
- **Pendente**

### Cenário P3 — Fallback funciona se a IA falhar
- [ ] Simular falha (ex.: API key inválida/ausente temporariamente)
- [ ] Confirmar: lembrete ainda é enviado, com o template fixo de sempre
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

- Corrigir o título do compromisso na origem (`meeting_scheduler.py:574`) para já
  nascer niche-aware — beneficiaria Kanban, dossiê e agenda do operador, não só
  o lembrete.
- Diferenciar tom entre 1º lembrete (mais distante, aviso suave) e 2º (mais
  próximo, confirmação mais firme) — precisa de metadado novo no payload do job
  em `jobs_service.schedule_appointment_reminder_jobs`.
