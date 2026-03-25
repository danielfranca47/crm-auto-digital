3. Tarefas de implementação — Backend
Tarefa 3.1 — Origem inbound/outbound no LLM [P0 — ~0,5 dia]
IMPACTO IMEDIATO EM TODOS OS AGENTES
Sem esta tarefa, o LLM aplica o mesmo tom e abordagem para leads que vieram te procurar e leads que foram abordados. É o gap mais barato de resolver e o de maior impacto transversal.


Arquivos: backend-crm/services/ai_orchestrator/orchestrator.py, frontend-crm (página Prospecção)

Em orchestrator.py, no método que monta o ContextBundle, adicionar lead.origin:
# orchestrator.py — _build_context_bundle()
context_bundle['lead_origin'] = lead.origin or 'inbound'
context_bundle['lead_origin_label'] = (
    'INBOUND (lead veio te procurar)'
    if lead.origin in ('WhatsApp', 'inbound', None)
    else 'OUTBOUND (lead foi abordado — não te conhecia)'
)


Em decision_engine.py, injetar no prompt:
# Inserir no bloco de contexto do lead no prompt
f'Origem do lead: {ctx["lead_origin_label"]}'
f'Abertura recomendada: {ai_profile.origin_inbound_opener if inbound else ai_profile.origin_outbound_opener}'


Na página Prospecção do frontend (frontend-crm/src/pages/Prospeccao.tsx), garantir que a criação de lead inclui origin='outbound' no payload do POST /leads.
No modelo Lead (backend-crm/models.py), adicionar valor 'outbound' como opção válida além de 'Manual', 'Planilha', 'WhatsApp'.
No AI Profile, adicionar campos origin_inbound_opener e origin_outbound_opener com defaults baseados no template_key do agente.

Tarefa 3.2 — Score dos 4Ps para Agent 1 [P0 — ~1,5 dias]
Arquivos: backend-crm/services/qualification_state.py, backend-crm/services/qualification_guardrails.py, backend-executors/app/services/decision_engine.py

Adicionar campos de score em lead_qualification_state:
# qualification_state.py — novos campos
power_score: int = 0        # 0-3: quem decide
priority_score: int = 0     # 0-3: urgência do problema
price_score: int = 0        # 0-3: verba disponível
timing_score: int = 0       # 0-3: prazo definido
qualification_total_score: int = 0  # soma dos 4


Criar lógica de scoring em qualification_state.py — extrair sinais dos campos já coletados (urgency, budget_or_price_acceptance, decision_role, availability_window) e converter em score 0–3 por dimensão.
Em qualification_guardrails.py, substituir a validação atual por:
# can_advance_from_qualification() — novo critério
threshold = ai_profile.qualification_score_threshold or 6  # default: 6/12
if lead_qual_state.qualification_total_score < threshold:
    return False, f'Score {lead_qual_state.qualification_total_score}/12 abaixo do mínimo {threshold}'
return True, None

No AI Profile, expor qualification_score_threshold (int, 0–12, default 6) e nurture_vs_discard_rule (enum: 'nurture' | 'discard', default 'discard').
Criar categoria 'nurture' no Kanban além de 'disqualified' — leads com score baixo mas não zero vão para nurture quando a regra for 'nurture'.

Tarefa 3.3 — Lembretes de appointment [P0 — ~1 dia]
Arquivos: backend-crm/services/jobs_service.py, backend-crm/services/followup_state.py (ou novo appointment_state.py), backend-crm/routes/leads.py

Adicionar constante em jobs_service.py:
TYPE_WHATSAPP_APPOINTMENT_REMINDER = 'whatsapp.appointment.reminder'


Ao criar um appointment (qualquer agente com agendamento), agendar os jobs de lembrete baseados no AI Profile:
# Ao confirmar appointment
offsets = ai_profile.appointment_reminder_offsets or [-1440, -60]  # -24h, -1h
# Para Agent 3, default: [-1440, -120]  — -24h, -2h
for offset_minutes in offsets:
    send_at = appointment.start_at + timedelta(minutes=offset_minutes)
    if send_at > datetime.utcnow():
        create_job(type=TYPE_WHATSAPP_APPOINTMENT_REMINDER,
                   lead_id=lead.id, scheduled_at=send_at)


O worker do backend-executors processa appointment.reminder: busca o appointment, gera mensagem de lembrete (template fixo ou LLM leve), envia via WhatsApp.
No AI Profile, expor appointment_reminder_offsets como array de inteiros em minutos com sinal negativo (ex: [-1440, -60]). Interface: dois campos de texto com label 'horas antes da reunião'.

Tarefa 3.4 — Dossiê/briefing pré-reunião [P0 — ~1 dia]
Arquivos: novo backend-crm/services/briefing_service.py, backend-crm/routes/leads.py

Criar briefing_service.py com função generate_and_send_briefing(lead_id):
Busca dados do lead: nome, origem, qualificação completa, score dos 4Ps, histórico resumido da conversa, nota do operador
Formata em mensagem estruturada com emojis para facilitar leitura rápida no WhatsApp
Envia para ai_profile.briefing_channel (WhatsApp do operador se briefing_channel='whatsapp', ou notificação interna se 'internal')

Disparar o briefing quando appointment.start_at estiver dentro de briefing_lead_time minutos (default: 120 min = 2h antes). Implementar como parte do reconciliador de appointments ou como job separado do tipo whatsapp.appointment.briefing.
No AI Profile, expor:
briefing_enabled: boolean (default true para A1 e A3)
briefing_channel: enum 'whatsapp' | 'internal' (default 'whatsapp')
briefing_lead_time: int em minutos (default 120 — 2h antes da reunião)
operator_whatsapp: string — número do operador para receber o briefing (se briefing_channel='whatsapp')

Tarefa 3.5 — Webhook de pagamento — Agent 2 [P0 — ~2 dias]
DESBLOQUEADOR ESTRUTURAL DO AGENT 2 Sem webhook de pagamento, o Agent 2 nunca fecha automaticamente. O closing depende do operador mover o lead manualmente — contradição com o design 100% autônomo.
Arquivo novo: backend-crm/routes/webhooks.py
1. Pré-requisito no fluxo do bot — antes de enviar o link
Antes de enviar o link de pagamento, o bot deve:
Solicitar o email do lead: "Para enviar seu acesso, qual é o seu melhor e-mail?"
Salvar em lead.email
Gerar o link com token único: https://pay.hotmart.com/PRODUTO?src=ld_{lead.id}
Salvar o token em lead.checkout_token
Isso garante identificação confiável independente do gateway.
2. Criar endpoint POST /webhooks/payment/{gateway} autenticado por token secreto no header X-Webhook-Secret.
3. Lógica de identificação do lead — em camadas, por ordem de confiabilidade:
python
# 1. Token do link — gerado pelo sistema, 100% confiável
lead = find_by_checkout_token(payload.src or payload.metadata.get("lead_id"))


# 2. Phone normalizado — coletado pelo bot na qualificação
if not lead:
    lead = find_by_phone(normalize_phone(payload.buyer.phone))


# 3. Email — coletado pelo bot antes do envio do link
if not lead:
    lead = find_by_email(payload.buyer.email)


# 4. CPF/documento — gateways brasileiros (Hotmart)
if not lead:
    lead = find_by_document(payload.buyer.document)


# 5. Nenhum match → fila de revisão manual — nunca perder o evento
if not lead:
    save_unmatched_payment_event(payload)
    notify_operator("Pagamento confirmado sem lead vinculado — revisão necessária")
    return 200  # Sempre 200 — gateway não deve retentar
4. Ações após identificar o lead:
Mover para client-list → dispara STOP_DEAL_CLOSED no follow-up
Criar job whatsapp.onboarding — boas-vindas + entrega do produto
Agendar job whatsapp.upsell para +30 min
Agendar job whatsapp.nps para +7 dias
5. Mapeamento de campos por gateway:
Gateway
Token/src
Phone
Email
Documento
Hotmart
data.purchase.src
data.buyer.phone
data.buyer.email
data.buyer.document
Kiwify
tracking_source
Customer.mobile
Customer.email
—
Stripe
metadata.lead_id
—
customer_email
—
Genérico
src ou ref
phone
email
document

6. No AI Profile (Seção 5), expor:
payment_gateway: select (Hotmart / Kiwify / Stripe / Genérico)
payment_webhook_url: readonly — URL gerada automaticamente para o usuário cadastrar no gateway (ex: https://app.orion.com/webhooks/payment/hotmart?token=XXX)
payment_webhook_secret: auto-gerado, exibido apenas uma vez, botão 'regenerar'


Tarefa 3.6 — Mídia rica no pitch — Agent 2 [P1 — ~1 dia]
Arquivos: backend-core/app/models/ai_profile.py, backend-executors/app/services/decision_engine.py

Adicionar campos ao offer_pack (já existe como JSON):
# offer_pack JSON — novos campos
{
  'items': [...],           # existente
  'checkout_link': '...',   # existente
  'media_url': 'https://...', # NOVO — imagem, vídeo ou áudio do pitch
  'media_type': 'image',    # NOVO — 'image' | 'video' | 'audio'
  'anchor_price': 'R$ 997', # NOVO — preço âncora ('de X por Y')
  'guarantee_text': '...',  # NOVO — texto da garantia
  'upsell_message': '...',  # NOVO — mensagem pós-compra
}


Em decision_engine.py, ao montar o pitch do Agent 2: se offer_pack.media_url está preenchido, enfileirar envio de mídia antes do texto. O job de envio de mídia deve preceder o texto do pitch no mesmo turn.
No AI Profile (Seção 5), expor os campos com upload de arquivo ou input de URL, campo de preço âncora, textarea de garantia e textarea de mensagem de upsell.

Tarefa 3.7 — Detecção de sinal de compra — Agent 1 [P1 — ~1 dia]
Arquivo: backend-executors/app/services/decision_engine.py, novo backend-crm/services/buying_signal_service.py

Criar função detect_buying_signals(message_text, keywords_list) que retorna True se o texto contém alguma keyword configurada.
Defaults por template (usados se AI Profile não tem buying_signal_keywords):
BUYING_SIGNAL_DEFAULTS = [
    'quanto custa', 'qual o valor', 'como assino', 'qual o contrato',
    'como faço para contratar', 'aceita cartão', 'tem parcelamento',
    'quando começa', 'qual o prazo', 'me manda a proposta',
]


Ao detectar sinal: criar notificação para o operador (tabela notifications, type='buying_signal_detected') + badge no card do lead no Kanban.
Se offer_pack.checkout_link está preenchido e sinal detectado: bot inclui o link na próxima mensagem automaticamente.
No AI Profile (Seção 4, Agent 1), expor buying_signal_keywords como textarea com uma keyword por linha, com botão 'Usar defaults do template'.

Tarefa 3.8 — Passo de aquecimento — Agent 3 [P1 — ~1 dia]
Arquivo: backend-crm/services/ai_playbooks/__init__.py, backend-executors/app/services/decision_engine.py

Adicionar estágio 'warming' no playbook hybrid_scheduler entre qualificação e proposta de agenda:
# hybrid_scheduler playbook — novo estágio
'warming': {
    'trigger': 'after_qualification_approved',
    'steps': [
        'social_proof',   # resultado de cliente com perfil similar
        'session_preview' # o que vai acontecer na sessão
    ],
    'social_proof_template': ai_profile.warming_social_proof or DEFAULT_SOCIAL_PROOF,
    'session_preview_template': ai_profile.warming_session_preview or DEFAULT_SESSION_PREVIEW,
}


No AI Profile (Camada 2 — Qualificação, seção de contexto), adicionar campos opcionais:
warming_social_proof: textarea — exemplo de resultado de cliente similar (ex: 'A Ana, personal trainer como você, dobrou sua agenda em 2 meses')
warming_session_preview: textarea — descrição do que acontece na sessão (ex: 'Na sessão de 1h vamos mapear seus objetivos e montar seu plano')

4. Tarefas de implementação — AI Profile Frontend
Todas as adições seguem o padrão de card já estabelecido: label em monospace + valor em destaque + badge de status. Não criar novo padrão visual.

Tarefa 4.1 — Camada 2 (Qualificação) — novos campos de contexto
Arquivo: frontend-crm/src/pages/AiProfile.tsx (ou componente de qualificação)

Adicionar na seção 'Contexto do Negócio' (abaixo dos cards existentes):
Campo
UI e comportamento
origin_inbound_opener
Textarea · Placeholder: 'Oi! Vi que você veio pelo anúncio de X...' · Badge: Configurado / Usando default do template
origin_outbound_opener
Textarea · Placeholder: 'Oi [Nome], sou assistente da [Empresa]...' · Badge: Configurado / Usando default do template
objection_common
Input text · Placeholder: 'Preciso pensar mais' · Badge: Configurado / Não configurado


Adicionar abaixo dos 3 filtros de qualificação:
Campo
UI e comportamento
qualification_score_threshold
Slider 0–12 com label 'Score mínimo para avançar ao agendamento' · Default: 6 · Exibir '6/12 pontos' como valor atual
nurture_vs_discard_rule
Toggle: Nurture passivo / Descarte · Tooltip: 'Nurture: lead vai para lista de reaquecimento futuro. Descarte: arquivado permanentemente.'


Tarefa 4.2 — Camada 3 (Pipeline) — Seção 4 NOVA: Apresentação e agendamento
VISIBILIDADE CONDICIONAL
Esta seção aparece apenas para Agent 1 (sdr_scheduler) e Agent 3 (hybrid_scheduler). Para Agent 2, exibir card desabilitado com texto 'Não aplicável — Agent 2 não realiza agendamentos.'


Campo
UI e comportamento
appointment_reminder_offsets
Dois inputs numéricos com label 'horas antes' · Default A1: 24h e 1h · Default A3: 24h e 2h · Badge mostra valor atual ex: '-24h · -1h'
briefing_enabled
Toggle · Default: ativo · Controla visibilidade dos campos abaixo
briefing_channel
Select: WhatsApp / Notificação interna · Padrão: WhatsApp
briefing_lead_time
Input numérico em horas · Placeholder: 2h antes da reunião
operator_whatsapp
Input tel · Aparece apenas se briefing_channel = WhatsApp · Badge: Configurado / Crítico se vazio com briefing ativo
calendar_integration
Select: Nenhum / Google Calendar / Calendly · Badge: Integrado / Não configurado · Botão 'Conectar' abre OAuth
buying_signal_keywords
Textarea com 1 keyword por linha · Só para Agent 1 · Botão 'Usar defaults do template' · Badge mostra contagem: '10 palavras'


Tarefa 4.3 — Camada 3 (Pipeline) — Seção 5 NOVA: Oferta e pagamento
VISIBILIDADE CONDICIONAL
Esta seção aparece apenas para Agent 2 (closer_agressivo). Para Agent 1 e Agent 3, exibir card desabilitado com texto 'Não aplicável ao seu tipo de agente.'


Campo
UI e comportamento
payment_gateway
Select: Hotmart / Kiwify / Stripe / Genérico · Badge: Configurado / Crítico se não configurado
payment_webhook_url
Readonly — URL gerada automaticamente para o usuário cadastrar no gateway · Botão 'Copiar URL'
payment_webhook_secret
Readonly mascarado (••••••) com botão 'Revelar' e 'Regenerar token' · Badge: Ativo
offer_media_url
Input URL ou upload de arquivo · Tipos: imagem, vídeo (até 16MB), áudio · Preview após upload
offer_media_type
Select inferido do arquivo: image / video / audio · Editável manualmente
anchor_price
Input text · Placeholder: 'R$ 997' (preço cheio) · Aparece junto com checkout_link existente
guarantee_text
Textarea curta · Placeholder: '7 dias de garantia incondicional'
upsell_message
Textarea · Mensagem enviada automaticamente após confirmação de pagamento


Tarefa 4.4 — Resumo — novos alertas críticos
Arquivo: frontend-crm/src/pages/AiProfile.tsx (componente do Resumo)

Adicionar ao sistema de alertas existente:
Condição
Texto do alerta no Resumo
Agent 2 sem payment_gateway
Crítico — sem gateway de pagamento, o closing nunca fecha automaticamente
Agent 2 sem operator_whatsapp (se briefing ativo)
Crítico — briefing ativo mas sem número do operador configurado
Agent 1/3 sem appointment_reminder_offsets
Aviso — lembretes de reunião com defaults do sistema (24h e 1h). Configure se precisar de prazos diferentes.
Qualquer agente sem origin_inbound_opener
Aviso — usando abertura genérica para leads inbound. Personalize para seu nicho.

6. Prompts para o Claude Code — por tarefa
Copiar cada bloco diretamente no Claude Code. Cada prompt referencia os arquivos relevantes e o comportamento esperado.

TAREFA 3.1 — ORIGEM INBOUND/OUTBOUND
Leia backend-crm/services/ai_orchestrator/orchestrator.py e backend-executors/app/services/decision_engine.py. Adicione lead.origin ao ContextBundle em orchestrator.py. No decision engine, injete no prompt: se origin é 'outbound' use o campo ai_profile.origin_outbound_opener como abertura; se inbound use origin_inbound_opener. Verifique frontend-crm/src/pages/Prospeccao.tsx e confirme que o POST de criação de lead inclui origin='outbound'. No modelo Lead (backend-crm/models.py), certifique que 'outbound' é valor aceito. Adicione origin_inbound_opener e origin_outbound_opener ao model ai_profile.py com defaults baseados no template_key.


TAREFA 3.2 — SCORE DOS 4PS
Leia backend-crm/services/qualification_state.py e qualification_guardrails.py. Adicione campos power_score, priority_score, price_score, timing_score (int, 0-3) e qualification_total_score (int, 0-12) em lead_qualification_state. Crie lógica de scoring a partir dos campos já coletados: urgency→priority_score, budget_or_price_acceptance→price_score, decision_role→power_score, availability_window→timing_score. Em can_advance_from_qualification(), adicione critério: total_score >= ai_profile.qualification_score_threshold (default 6). Adicione qualification_score_threshold e nurture_vs_discard_rule ao ai_profile model. Crie categoria 'nurture' como opção de destino além de 'disqualified'.


TAREFA 3.3 — LEMBRETES DE APPOINTMENT
Leia backend-crm/services/jobs_service.py. Adicione TYPE_WHATSAPP_APPOINTMENT_REMINDER = 'whatsapp.appointment.reminder'. Na lógica de criação de appointment (busque onde appointments são criados), adicione criação de jobs de lembrete baseados em ai_profile.appointment_reminder_offsets (array de inteiros em minutos, negativo = antes). Default: [-1440, -60] para Agent 1 e [-1440, -120] para Agent 3. O job deve buscar o appointment, gerar mensagem de lembrete e enviar ao lead via WhatsApp. Adicione appointment_reminder_offsets ao ai_profile model com defaults por template_key.


TAREFA 3.5 — WEBHOOK DE PAGAMENTO
Crie backend-crm/routes/webhooks.py com endpoint POST /webhooks/payment/{gateway} autenticado por X-Webhook-Secret. Implemente normalização de payload para Hotmart (data.buyer.email), Kiwify (Customer.email), Stripe (data.object.customer_email) e Genérico (campo email ou phone no body). Ao confirmar pagamento: encontre o lead pelo email/phone do comprador, mova para 'client-list' (dispara STOP_DEAL_CLOSED no follow-up), crie job onboarding, agendie upsell em +30min e NPS em +7 dias. Adicione payment_gateway, payment_webhook_url (gerada automaticamente: /webhooks/payment/{gateway}?token={secret}), e payment_webhook_secret ao ai_profile model. O secret deve ser gerado no cadastro e ter endpoint de regeneração.


TAREFAS 3.4, 3.6, 3.7, 3.8 + TAREFAS 4.X — INSTRUÇÃO GERAL
Para as tarefas 3.4 (dossiê), 3.6 (mídia rica), 3.7 (sinal de compra) e 3.8 (aquecimento Agent 3), consulte as seções 3.4–3.8 deste documento para a especificação completa. Para as tarefas de frontend 4.1–4.4, implemente os campos novos seguindo o padrão de card existente em AiProfile.tsx: label em monospace + valor em destaque + badge de status. Todos os campos novos devem ter fallback para default do template quando não configurados pelo usuário. Campos condicionais: Seção 4 apenas para Agent 1/3, Seção 5 apenas para Agent 2.

