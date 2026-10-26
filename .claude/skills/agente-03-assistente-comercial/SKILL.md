---
name: agente-03-assistente-comercial
description: Especialista no Agente 03 · Híbrido — Assistente Comercial com Agendamento Inteligente do Orion CRM (preset template_key=hybrid_scheduler, agent_mode=agenda). Traz as etapas da página Tipos de Agentes (Entrada / Confirma o Público Certo, Prospecção com Tom Pessoal, Aprofunda a Dor + Coleta Contexto, Aquecimento — Ancora Valor, Agendamento Automático com lembretes 24h/2h e briefing, Você Faz a Sessão, Follow-up Pós-Sessão Fechou/Não fechou/Reagendar, Retenção e Renovação de Pacote), os critérios de sucesso, a biblioteca de cenários, os campos que pesam, os limites de código já medidos e o que a página promete face ao que o código faz. Normalmente acionada pela skill diagnosticar-agente quando o processo do cliente é de sessão/hora com um profissional (coaches, terapeutas, personal trainers, consultores solo, clínicas e espaços de serviços); use também quando o utilizador pedir diretamente para diagnosticar ou testar o agendamento, a confirmação, a remarcação, os lembretes ou o follow-up pós-sessão do Agente 03 de uma conta.
---

# Agente 03 · Híbrido — Assistente Comercial com Agendamento Inteligente

Faz parte do fluxo da skill `diagnosticar-agente`: as regras fixas, a bancada, a triagem e as entregas
estão lá. Os nomes das etapas são os da página Tipos de Agentes (`/agentes-info`).

**Promessa da página:** funciona como uma recepcionista comercial inteligente. Qualifica, agenda e
entrega o lead preparado ao profissional. Não apresenta nem fecha, mas faz tudo antes e trata do
follow-up depois.

## Etapas da página → o que o sistema faz → o que medir

| Etapa (página) | Quem | No sistema | Critério de sucesso (⚠ = crítico) |
|---|---|---|---|
| **Inbound:** Entrada — Interesse Ativo Demonstrado | bot | p0; `origin_inbound_opener`; `identity_mode` | apresenta-se como assistente do profissional, em tom próximo; usa o que o lead já disse |
| **Inbound:** Confirma que é o Público Certo | bot | p1, 2–3 perguntas de contexto | quem não se encaixa recebe uma indicação alternativa, e ninguém fica sem resposta |
| **Outbound:** Prospecção com Tom Pessoal | bot | `origin_outbound_opener` | "o [Profissional] pediu-me para entrar em contacto…" |
| **Outbound:** Desperta a Dor com Pergunta Leve | bot | p1 | pergunta aberta, sem mencionar o serviço |
| **Outbound:** Valida o Fit Dentro do Diálogo | bot | p1 | valida o perfil sem parecer um formulário |
| **Aprofunda a Dor + Coleta Contexto** | bot | p1/p2; resposta guardada para o briefing | pergunta aberta + breve validação empática; não salta logo para a marcação |
| **Aquecimento — Ancora Valor** | bot | p2; estágio de aquecimento e `appointment_mode` (`exploratory` / `commercial`, só `hybrid_scheduler`); Base de Conhecimento (prova social, como é a sessão); tabela ou catálogo por gatilho | prova social de um cliente parecido; explica a sessão; liga a dor ao que o profissional resolve |
| **Agendamento Automático** | bot | p3a/p3b; Google Calendar; `scheduling_offer_style`; horários do profissional; lembretes 24h e 2h (padrão do template); briefing ao profissional | ⚠ data e hora gravadas = aceites pelo cliente; ⚠ grava a **última** proposta; ⚠ nunca diz "marcado" sem marcação gravada; ⚠ dentro do horário do profissional e sem sobreposição; aceita um horário livre sem inventar escassez |
| **Você Faz a Sessão** | humano | bot pausado (`meeting_scheduled`); resultado registado (`appointment_outcomes`: completed / no_show / rescheduled) | o bot só responde ao pós-marcação (preço, morada, remarcar, "já cheguei") sem reabrir a venda |
| **Follow-up Pós-Sessão** | bot | `followup_state.py` por resultado: Fechou / Não fechou / Reagendar | Fechou → onboarding e link; Não fechou → 2–3 dias de reforço; Reagendar → nova data |
| **Retenção e Renovação de Pacote** | bot + humano | `client_checkin` (check-in de cliente inativo) | confirmar o que existe (ver a tabela abaixo) |

## Biblioteca de cenários (adaptar à conta)

| Cenário | Persona | Esperado |
|---|---|---|
| `p-<real>` | uma por conversa de referência | o roteiro observado |
| `p-pedido-direto` | serviço + dia + hora numa só mensagem | aceita se estiver livre e grava |
| `p-aceita-2a` | recusa a 1.ª proposta e aceita a 2.ª | grava a 2.ª |
| `p-fora-horario` | domingo, antes da abertura, depois do fecho | motivo verdadeiro + alternativa válida |
| `p-ultimo-horario` | última hora com uma duração que passa o fecho | propõe a hora que cabe |
| `p-ocupado` (setup: evento ocupado) | horário ocupado e depois o seguinte | recusa o primeiro; aceita sessões seguidas |
| `p-sem-tipo` | pedido ambíguo | pergunta qual antes de marcar |
| `p-varias-perguntas` | 3 perguntas numa só mensagem | responde a todas e depois avança |
| `p-relativo` | "amanhã", "sexta" | data certa |
| `pos-marcacao` | marca e depois pergunta o preço, remarca e diz "já cheguei" | respostas certas; remarcação só depois de o cliente aceitar |
| `p-saudacao` | de manhã e à noite | cumprimento do período certo |
| `p-out-pessoal` | outbound, desconfiado | tom pessoal, desperta a dor, sem vender |

O `--resumo` assinala o dia divergente: escrito, proposto ou pedido face ao gravado.

## Campos que mais pesam

`scheduling_offer_style` · horários do profissional (confirmar se já existe campo próprio:
`fix-disponibilidade-campo-duplo-sentido`; senão, no `custom_instructions`, lidos por
`professional_hours.py`) · `availability_mode` / `availability_schedule` · `appointment_mode` ·
`appointment_reminder_offsets` · `briefing_enabled` · Google Calendar com o scope `calendar.events` ·
`qualification_required_fields` · `handoff_policy` · `identity_mode` · blocos do Fluxo de Venda em
p2 (confirmar com grep se p3a/p3b já chamam `_build_sales_flow_phases_block`).

## Onde olhar no código (triagem)

`decision_engine.py` (Filhas de pré-agendamento e agendamento, blocos de facto da agenda) ·
`meeting_scheduler.py` · `meeting_date_guard.py` · `requested_slot.py` · `professional_hours.py` ·
`backend-crm/routes/appointments.py` · `orchestrator.py::_load_calendar_busy_slots` ·
`google_calendar_sync.py` · `appointment_outcomes.py`.

## Prometido na página vs. código (confirmar antes de concluir)

| Promessa | Estado conhecido |
|---|---|
| Lembretes 24h e 2h | ✅ padrão de `hybrid_scheduler` (`jobs_service._REMINDER_DEFAULTS_BY_TEMPLATE`) |
| Briefing ao profissional | ✅ `briefing_service.py` |
| Calendário em tempo real — Google Calendar | ✅ sincronização automática antes de propor horários |
| Calendário em tempo real — Calendly | ❌ sem código no backend |
| Confirmação dupla WhatsApp + e-mail | ❓ confirmar o envio de e-mail na marcação |
| Agendamento recorrente, materiais pré-sessão, renovação de pacote | ❓ não encontrado; existe só o `client_checkin` |

## Limites já medidos (verificar se ainda valem)

Diagnóstico da Sensi Vitae, 25 e 26/10/2026 (estado em `docs/plans/plano-sprint-2026-10-26-agenda-sensi-vitae.md`
e `docs/implementations/`):
- **Corrigidos:** datas de memória, horário livre recusado, horários comparados como texto e 409 não
  tratado, Google sem permissão e sem sincronização automática.
- **Pendentes à data:** grava uma proposta antiga, saudação sem a hora local, p3a/p3b ignoram o Fluxo
  de Venda, margem entre sessões, remarcação grava a contraproposta, campo de disponibilidade com duplo
  sentido.
- **Agenda única por conta:** profissionais na mesma sala partilham os conflitos de horário (pode ser o
  desejado, como na Sensi Vitae).

## Exemplo trabalhado

`.claude/agentes/sensi-vitae/README.md`: espaço de massagens, 2 terapeutas, tabela por imagens,
13 versões de configuração e 7 baterias em produção. Serve de referência para o nível de detalhe, não
como regra para outras contas.
