// ─────────────────────────────────────────────────────────────
// Tipos do módulo de Agente (dashboard + configuração)
// ─────────────────────────────────────────────────────────────

/** Contrato unificado de qualificação — Fase 3/4 */
export interface QualificationField {
  key: string;                    // "availability_window" | "custom_nome_do_pet" | ...
  label: string;                  // "Disponibilidade" | "Nome do pet"
  question?: string;              // Pergunta para modo ativo: "Qual horário funciona?"
  passive_hint?: string;          // Dica para modo passivo: "Inferir se lead mencionar horário"
  closing_question?: string;      // Pergunta estratégica de fechamento — alternativa binária ou confirmação
  allow_closing_question?: boolean; // Habilita closing_question para este campo
  qualify_if?: string;            // Critério avançado: descreve o que é uma resposta que qualifica o lead
  disqualify_if?: string;         // Critério avançado: descreve o que é uma resposta que não qualifica
  mode: 'required' | 'optional' | 'off';
  group?: 'f1' | 'f2' | 'f3';   // APENAS para SDR — filtro ao qual este campo pertence
}

// ─── Fluxo de Venda ───────────────────────────────────────────

export type SalesFlowTriggerType =
  | 'phase_entered'
  | 'signal'
  | 'keyword'
  | 'qualification_field';

export type SalesFlowSignalKey =
  | 'price_acceptance'
  | 'intent_level'
  | 'meeting_proposed'
  | 'handoff_requested';

export type SalesFlowPhase = 'qualification' | 'apresentation' | 'follow-up' | 'closing';

export interface SalesFlowNode {
  id: string;
  label: string;
  enabled: boolean;
  trigger_phases: SalesFlowPhase[];
  trigger_type: SalesFlowTriggerType;
  trigger_signal: SalesFlowSignalKey | null;
  trigger_value: string | null;
  trigger_keywords: string[];
  trigger_field_key: string | null;
  trigger_field_value: string | null;
  action_instruction: string;
  action_media_category: string | null;
  priority: number;
}

export interface SalesFlow {
  enabled: boolean;
  nodes: SalesFlowNode[];
  phases?: SalesFlowPhaseData[];
}

// ─── Blocos Tipados (novo sistema) ───────────────────────────

export type SalesFlowBlockTypeId =
  | 'kw_trigger' | 'phase_trigger' | 'no_reply_trigger' | 'intent_trigger'
  | 'orientacao' | 'mensagem' | 'midia' | 'avancar_fase' | 'webhook'
  | 'condicao' | 'espera';

export type SalesFlowPhaseId = 'p0' | 'p1' | 'p2' | 'p3a' | 'p3b' | 'p4' | 'p5';

export interface SalesFlowBlock {
  id: string;
  typeId: SalesFlowBlockTypeId;
  qual_opener?: boolean;          // true = bloco de abertura de qualificação (injetado antes da 1ª pergunta)
  // triggers
  keywords?: string;
  match?: string;
  intent?: string;
  wait_value?: string;
  wait_unit?: string;
  fire_once?: boolean;
  suppress_llm_response?: boolean;
  // actions
  content?: string;
  priority?: string;
  channel?: string;
  media_type?: string;
  media_item_id?: number;
  media_url?: string;
  caption?: string;
  target_phase?: SalesFlowPhaseId;
  url?: string;
  method?: string;
  // logic
  condition?: string;
  branch_yes?: string;
  branch_no?: string;
  note?: string;
}

export interface SalesFlowPhaseData {
  id: SalesFlowPhaseId;
  blocks: SalesFlowBlock[];
}

export const SALES_FLOW_PHASE_ID_LABELS: Record<SalesFlowPhaseId, string> = {
  p0:  'Recepção',
  p1:  'Qualificação',
  p2:  'Apresentação',
  p3a: 'Pré-Agendamento',
  p3b: 'Agendamento',
  p4:  'Follow Up',
  p5:  'Fechamento',
};

export const SALES_FLOW_PHASES_BY_AGENT_MODE: Record<string, SalesFlowPhaseId[]> = {
  consultivo: ['p0', 'p1', 'p2', 'p4', 'p5'],
  direto:     ['p0', 'p1', 'p2', 'p5'],
  agenda:     ['p0', 'p1', 'p2', 'p3a', 'p3b', 'p4', 'p5'],
};

export const SALES_FLOW_BLOCK_TYPE_LABELS: Record<SalesFlowBlockTypeId, string> = {
  kw_trigger:      'Palavra-chave',
  phase_trigger:   'Fase iniciada',
  no_reply_trigger:'Sem resposta',
  intent_trigger:  'Intenção detectada pela IA',
  orientacao:      'Orientação ao Agente',
  mensagem:        'Mensagem fixa',
  midia:           'Enviar Mídia',
  avancar_fase:    'Avançar Fase',
  webhook:         'Webhook / API',
  condicao:        'Condição (Bifurcação)',
  espera:          'Espera (Smart Delay)',
};

export const SALES_FLOW_BLOCK_CATEGORIES: {
  id: 'trigger' | 'action' | 'logic';
  label: string;
  types: SalesFlowBlockTypeId[];
}[] = [
  {
    id: 'trigger',
    label: '⚡ Gatilho',
    types: ['phase_trigger', 'kw_trigger', 'no_reply_trigger', 'intent_trigger'],
  },
  {
    id: 'action',
    label: '🎯 Ação',
    types: ['orientacao', 'mensagem', 'midia', 'avancar_fase', 'webhook'],
  },
  {
    id: 'logic',
    label: '🔀 Lógica',
    types: ['condicao', 'espera'],
  },
];

export const SALES_FLOW_TRIGGER_LABELS: Record<SalesFlowTriggerType, string> = {
  phase_entered:       'Fase iniciada',
  signal:              'Sinal detectado',
  keyword:             'Palavra-chave dita pelo lead',
  qualification_field: 'Campo de qualificação preenchido',
};

export const SALES_FLOW_SIGNAL_LABELS: Record<SalesFlowSignalKey, string> = {
  price_acceptance:  'Aceitação de preço',
  intent_level:      'Nível de intenção',
  meeting_proposed:  'Reunião proposta',
  handoff_requested: 'Pedido de atendimento humano',
};

export const SALES_FLOW_SIGNAL_VALUES: Record<SalesFlowSignalKey, { value: string; label: string }[]> = {
  price_acceptance:  [{ value: 'yes', label: 'Aceitou' }, { value: 'no', label: 'Recusou' }, { value: 'unsure', label: 'Indeciso' }],
  intent_level:      [{ value: 'high', label: 'Alto' }, { value: 'medium', label: 'Médio' }, { value: 'low', label: 'Baixo' }],
  meeting_proposed:  [{ value: 'true', label: 'Proposta feita' }],
  handoff_requested: [{ value: 'true', label: 'Solicitado' }],
};

export const SALES_FLOW_PHASE_LABELS: Record<SalesFlowPhase, string> = {
  qualification: 'Qualificação',
  apresentation: 'Apresentação',
  'follow-up':   'Follow-up',
  closing:       'Fechamento',
};

/** Resposta de GET /api/agents/ (agente local / runner)
 *  A API serializa com alias: o campo JSON é "id", não "agent_id"
 */
export interface AgenteRunner {
  id: string;
  name: string | null;
  capabilities: string[] | null;
  status: 'online' | 'offline' | 'disabled' | null;
  last_seen_at: string | null;
  revoked: boolean;
  online: boolean;
}

// ─── Configuração central do agente ──────────────────────────

/** Campos da Camada 2 e 3 estendidos — armazenados em offer_pack */
export interface OfferPackExtra {
  // Camada 2 — Contexto do negócio
  ticket_range?: string;
  main_pain?: string;
  main_objection?: string;
  f1_questions?: string[];
  f2_questions?: string[];
  f3_questions?: string[];

  // Camada 3 — Comportamento por evento
  media_fallback?: string;
  media_fallback_msg?: string;
  opt_out_keywords?: string[];
  opt_out_disable?: boolean;
  opt_out_notify?: boolean;
  opt_out_confirm?: boolean;
  opt_out_confirm_msg?: string;
  lgpd_mode?: string;
  lgpd_msg?: string;
  reactivation_mode?: string;
  reactivation_msg?: string;

  // Camada 3 — Cadência
  daily_limit?: number;
  interval_min?: number;
  interval_max?: number;
}

/** Estado completo do formulário de configuração do agente */
export interface AgentConfig {
  // ── Camada 1 — Identidade ────────────────────────────────
  name: string;
  brand_name: string;
  tone_of_voice: string;
  agent_mode: 'sdr_scheduler' | 'closer' | 'consultivo' | 'agenda' | 'direto';
  identity_mode: 'human_agent' | 'virtual_assistant' | 'user_clone';
  template_key: string;
  handoff_policy: 'disable_bot' | 'keep_active_notify' | 'ignore';
  handoff_custom_text: string;
  requires_handoff: boolean;
  human_in_loop: boolean;
  timezone: string;
  custom_instructions: string;
  response_style: 'active' | 'passive';

  // ── Camada 1 — Contexto de abertura ──────────────────────
  origin_inbound_opener: string;
  origin_outbound_opener: string;
  warming_social_proof: string;
  warming_session_preview: string;

  // ── Camada 2 — Qualificação ──────────────────────────────
  niche: string;
  target_audience: string;
  offer_description: string;
  goals: string;
  ticket_range: string;
  main_pain: string;
  main_objection: string;
  f1_questions: string[];
  f2_questions: string[];
  f3_questions: string[];

  // ── Camada 2 — Qualificação avançada ─────────────────────
  qualification_score_threshold: number;
  nurture_vs_discard_rule: boolean;
  qualification_extraction_tolerance: 'flexivel' | 'equilibrado' | 'rigoroso';
  buying_signal_keywords: string[];
  // Contrato unificado (Fase 3) — substitui f1/f2/f3 + qualification_required_fields conceitualmente
  qualification_fields: QualificationField[];
  // Legado — mantidos para backward compat; derivados de qualification_fields ao salvar
  qualification_required_fields: string[] | null;

  // ── Camada 3 — Pipeline ──────────────────────────────────
  audio_transcription_enabled: boolean;
  media_fallback: string;
  media_fallback_msg: string;
  opt_out_keywords: string[];
  opt_out_disable: boolean;
  opt_out_notify: boolean;
  opt_out_confirm: boolean;
  opt_out_confirm_msg: string;
  lgpd_mode: string;
  lgpd_msg: string;
  reactivation_mode: string;
  reactivation_msg: string;
  daily_limit: number;
  interval_min: number;
  interval_max: number;
  first_reply_delay_min_seconds: number;
  first_reply_delay_max_seconds: number;
  reply_delay_min_seconds: number;
  reply_delay_max_seconds: number;
  multi_message_buffer_seconds: number;

  // ── Camada 3 — Follow-up avançado ────────────────────────
  followup_max_attempts: number;
  followup_first_offset: number;
  followup_cadence: string;
  followup_allowed_hours: string;
  followup_auto_trigger_enabled: boolean;
  followup_auto_trigger_inactivity_days: number;
  followup_checkin_auto_trigger_enabled: boolean;
  followup_checkin_inactivity_days: number;
  followup_sdr_instructions: string | null;
  followup_recovery_instructions: string | null;
  followup_postsession_instructions: string | null;
  followup_checkin_instructions: string | null;
  followup_goal_instructions: Record<string, string> | null;
  cart_recovery_attempt_instructions: [string | null, string | null, string | null] | null;
  followup_outcome_instructions: Record<string, string> | null;

  // ── Apresentação e agendamento ───────────────────────────
  appointment_mode: 'commercial' | 'exploratory';
  appointment_reminder_h1: number;
  appointment_reminder_h2: number;
  briefing_enabled: boolean;
  briefing_channel: string;
  briefing_lead_time: number;
  operator_whatsapp: string;
  calendar_integration: string;
  availability_mode: 'business_hours' | '24h' | 'custom';
  availability_schedule: string;
  scheduling_offer_style: 'offer_alternatives' | 'confirm_exact';
  default_session_duration_minutes: number;
  meeting_management_enabled: boolean;

  // ── Oferta e pagamento ───────────────────────────────────
  offer_media_url: string;
  offer_media_type: string;
  offer_anchor_price: string;
  offer_guarantee_text: string;
  offer_upsell_message: string;
  payment_gateway: string;
  payment_webhook_url: string;
  payment_webhook_secret: string;

  // ── Variáveis personalizadas ─────────────────────────────────
  custom_variables: Record<string, string>;

  // ── Fluxo de Venda (apenas modo ativo) ──────────────────────
  sales_flow: SalesFlow | null;
}

/** Valores padrão para o estado inicial (antes de carregar da API) */
export const DEFAULT_AGENT_CONFIG: AgentConfig = {
  name: '',
  brand_name: '',
  tone_of_voice: 'equilibrado',
  agent_mode: 'sdr_scheduler',
  identity_mode: 'human_agent',
  template_key: 'sdr_padrao',
  handoff_policy: 'keep_active_notify',
  handoff_custom_text: '',
  requires_handoff: false,
  human_in_loop: false,
  timezone: 'America/Sao_Paulo',
  custom_instructions: '',
  response_style: 'active',

  origin_inbound_opener: '',
  origin_outbound_opener: '',
  warming_social_proof: '',
  warming_session_preview: '',

  niche: '',
  target_audience: '',
  offer_description: '',
  goals: '',
  ticket_range: '',
  main_pain: '',
  main_objection: '',
  f1_questions: [],
  f2_questions: [],
  f3_questions: [],

  qualification_score_threshold: 6,
  nurture_vs_discard_rule: false,
  qualification_extraction_tolerance: 'equilibrado',
  buying_signal_keywords: [],
  qualification_fields: [],
  qualification_required_fields: null,

  audio_transcription_enabled: false,
  media_fallback: 'continuar',
  media_fallback_msg: 'Oi! Não consegui abrir o que você enviou. Pode me responder em texto? Assim consigo te ajudar melhor 😊',
  opt_out_keywords: ['PARAR', 'STOP', 'SAIR', 'CANCELAR', 'NÃO QUERO'],
  opt_out_disable: true,
  opt_out_notify: true,
  opt_out_confirm: true,
  opt_out_confirm_msg: 'Entendido! Você foi removido da nossa lista e não receberá mais mensagens. Se quiser retomar o contato, é só nos enviar uma mensagem. 😊',
  lgpd_mode: '',
  lgpd_msg: 'Olá! Para continuar, preciso da sua confirmação: você aceita receber mensagens nossas por este canal? Responda SIM para confirmar.',
  reactivation_mode: '',
  reactivation_msg: 'Que bom te ver de volta! Lembro que conversamos antes. O que mudou desde então?',
  daily_limit: 200,
  interval_min: 3,
  interval_max: 8,
  first_reply_delay_min_seconds: 0,
  first_reply_delay_max_seconds: 0,
  reply_delay_min_seconds: 0,
  reply_delay_max_seconds: 0,
  multi_message_buffer_seconds: 8,

  followup_max_attempts: 3,
  followup_first_offset: 60,
  followup_cadence: '60,1440,4320',
  followup_allowed_hours: '08:00-20:00',
  followup_auto_trigger_enabled: false,
  followup_auto_trigger_inactivity_days: 3,
  followup_checkin_auto_trigger_enabled: false,
  followup_checkin_inactivity_days: 30,
  followup_sdr_instructions: null,
  followup_recovery_instructions: null,
  followup_postsession_instructions: null,
  followup_checkin_instructions: null,
  followup_goal_instructions: null,
  cart_recovery_attempt_instructions: null,
  followup_outcome_instructions: null,

  appointment_mode: 'exploratory',
  appointment_reminder_h1: 24,
  appointment_reminder_h2: 2,
  briefing_enabled: false,
  briefing_channel: 'whatsapp',
  briefing_lead_time: 1,
  operator_whatsapp: '',
  calendar_integration: 'none',
  availability_mode: '24h',
  availability_schedule: '{"mon":"09:00-18:00","tue":"09:00-18:00","wed":"09:00-18:00","thu":"09:00-18:00","fri":"09:00-18:00","sat":"","sun":""}',
  scheduling_offer_style: 'offer_alternatives',
  default_session_duration_minutes: 30,
  meeting_management_enabled: true,

  offer_media_url: '',
  offer_media_type: 'image',
  offer_anchor_price: '',
  offer_guarantee_text: '',
  offer_upsell_message: '',
  payment_gateway: '',
  payment_webhook_url: '',
  payment_webhook_secret: '',

  custom_variables: {},

  sales_flow: null,
};

// ─── Dashboard ────────────────────────────────────────────────

/** Estatísticas computadas a partir dos leads para o dashboard */
export interface DashboardStats {
  leadsAtivos: number;
  qualificados: number;
  agendamentos: number;
  taxaResposta: number | null;
}

/** Item do funil para FunilAgente */
export interface FunilItem {
  stage: string;
  label: string;
  count: number;
  pct: number;
  color: string;
}

/** Lead "quente" para LeadsQuentes */
export interface LeadQuente {
  id: string | number;
  name: string;
  initials: string;
  stage: string;
  score: number;
  temp: 'hot' | 'warm' | 'cold';
}

/** Entrada do log de atividade */
export interface ActivityEntry {
  time: string;
  text: string;
  boldText?: string;
  color: string;
}

// ─── Labels legíveis ─────────────────────────────────────────

export const AGENT_MODE_LABELS: Record<string, string> = {
  sdr_scheduler: 'SDR · Agendamento',
  closer:        'Closer · Direto',
  consultivo:    'Consultivo',
  agenda:        'Foco em Agenda',
  direto:        'Vendedor Direto',
};

export const IDENTITY_MODE_LABELS: Record<string, string> = {
  human_agent:       'Humano do time',
  virtual_assistant: 'Assistente Virtual',
  user_clone:        'Clone do usuário',
};

export const TEMPLATE_KEY_LABELS: Record<string, string> = {
  sdr_padrao:           'SDR Padrão',
  consultor_especialista: 'Consultor Especialista',
  closer_agressivo:     'Closer Agressivo',
  hybrid_scheduler:     'Híbrido Agendador',
};

export const HANDOFF_LABELS: Record<string, string> = {
  disable_bot:        'Desabilitar bot',
  keep_active_notify: 'Manter ativo e notificar',
  ignore:             'Ignorar',
};

export const RESPONSE_STYLE_LABELS: Record<string, string> = {
  active:  'Ativo — faz perguntas de qualificação',
  passive: 'Passivo — responde primeiro, qualifica depois',
};

// ─── Presets de agente (mapeiam os 3 arquétipos de /agentes-info) ──
export const AGENT_PRESETS = [
  {
    key: 'a1',
    chip: 'Agente 01 · Robusto',
    title: 'SDR de Alto Ticket',
    subtitle: '+ Follow-up Pós-Apresentação',
    desc: 'Qualifica profundamente antes de acionar o humano. Ideal para ciclos longos e alto ticket.',
    useCases: ['Imóveis · Advocacia', 'Clínicas estéticas', 'Consultorias B2B', 'Alto ticket'],
    template_key: 'sdr_padrao',
    agent_mode: 'sdr_scheduler' as const,
  },
  {
    key: 'a2',
    chip: 'Agente 02 · Direto',
    title: 'Vendedor Autônomo',
    subtitle: 'Low Ticket',
    desc: '100% automatizado — qualifica, apresenta e fecha sem intervenção humana.',
    useCases: ['Infoprodutos', 'E-commerce', 'Cursos · Assinaturas'],
    template_key: 'closer_agressivo',
    agent_mode: 'direto' as const,
  },
  {
    key: 'a3',
    chip: 'Agente 03 · Híbrido',
    title: 'Assistente Comercial',
    subtitle: 'com Agendamento Inteligente',
    desc: 'Qualifica, agenda e entrega o lead preparado para o profissional. Não fecha — mas faz tudo antes.',
    useCases: ['Coaches · Terapeutas', 'Personal Trainers', 'Consultores solo'],
    template_key: 'hybrid_scheduler',
    agent_mode: 'agenda' as const,
  },
] as const;

/** Retorna o preset ativo com base nos valores atuais, ou null se for combinação customizada */
export function getActivePreset(template_key: string, agent_mode: string) {
  return AGENT_PRESETS.find(
    p => p.template_key === template_key && p.agent_mode === agent_mode,
  ) ?? null;
}

export const LGPD_LABELS: Record<string, string> = {
  inbound:  'Inbound implícito',
  explicit: 'Confirmação explícita',
  outbound: 'Apenas no outbound',
};

export const REATIVACAO_LABELS: Record<string, string> = {
  'reativar-notificar': 'Reativar e notificar operador',
  reiniciar:            'Reativar e reiniciar do início',
  retomar:              'Reativar e retomar do ponto exato',
  'notificar-somente':  'Manter arquivado e notificar',
};

export const MEDIA_FALLBACK_LABELS: Record<string, string> = {
  continuar: 'Responder e continuar',
  pausar:    'Responder e pausar',
  ignorar:   'Ignorar silenciosamente',
};

export const CALENDAR_INTEGRATION_LABELS: Record<string, string> = {
  none:            'Sem integração',
  google_calendar: 'Google Calendar',
  calendly:        'Calendly',
};

export const SCHEDULING_OFFER_STYLE_LABELS: Record<string, string> = {
  offer_alternatives: 'Sempre oferecer alternativas',
  confirm_exact:       'Confirmar horário exato quando disponível',
};

// ─── Camada 4: Categorias de Conhecimento por Preset ─────────

export interface KnowledgeCategory {
  key: string;
  label: string;
  description: string;
  hint: string;
  placeholder: string;
  importance: 'critical' | 'recommended' | 'optional';
  when_used?: string;
  /** Se true, a categoria aceita múltiplos itens (várias "tabelas" nomeadas pelo título) em vez de um único item. */
  allowMultiple?: boolean;
}

const CAT_SOCIAL_PROOF_SDR: KnowledgeCategory = {
  key: 'social_proof',
  label: 'Prova Social',
  description: 'Casos de sucesso com resultados concretos para usar no F3 e no aquecimento.',
  hint: 'Escreva 2–4 casos reais de [PÚBLICO] em [NICHO]: perfil do cliente, problema que tinha, resultado obtido em números. Ex: "[Perfil do cliente] — reduziu [métrica] em X% em Y meses."',
  placeholder: 'Cliente 1: [PÚBLICO] — Problema: [...] — Resultado: [...]\nCliente 2: [perfil similar] — Problema: [...] — Resultado: [...]',
  importance: 'critical',
  when_used: 'Aquecimento · Follow-up',
};

const CAT_OBJECTIONS_SDR: KnowledgeCategory = {
  key: 'objections_faq',
  label: 'Objeções e Respostas',
  description: 'As objeções mais comuns antes de aceitar uma reunião e como o agente deve responder.',
  hint: 'Liste cada objeção e a resposta recomendada. Foque em: preço ("está caro"), timing ("não é o momento"), decisor ("preciso consultar meu sócio"), concorrência ("já uso outra solução").',
  placeholder: 'Objeção: "Está caro para o nosso momento."\nResposta: "Entendo. Muitos dos nossos clientes disseram o mesmo antes — e descobrimos que o custo de não resolver isso costuma ser maior. Posso te mostrar como calculamos isso?"\n\nObjeção: "Preciso falar com meu sócio."\nResposta: "Faz todo sentido. Para facilitar, posso montar um resumo de 1 página para você apresentar — ou podemos incluí-lo na próxima conversa diretamente?"',
  importance: 'critical',
  when_used: 'Apresentação · Follow-up',
};

const CAT_COMPANY_PROFILE: KnowledgeCategory = {
  key: 'company_profile',
  label: 'Perfil da Empresa',
  description: 'Quem é a empresa, o que oferece, diferenciais e mercado de atuação.',
  hint: 'Descreva quem é a empresa em [NICHO]: nome oficial, segmento, o que entrega para [PÚBLICO], e o principal diferencial competitivo. O agente usa isso para responder "quem vocês são?" durante a qualificação.',
  placeholder: 'Nome: [Empresa]\nSegmento: [NICHO]\nO que entrega: [Descreva a solução principal]\nPara quem: [PÚBLICO]\nDiferencial: [O que torna vocês únicos nesse mercado]',
  importance: 'critical',
  when_used: 'Qualificação',
};

const CAT_QUALIFICATION_CRITERIA: KnowledgeCategory = {
  key: 'qualification_criteria',
  label: 'Critérios de Qualificação',
  description: 'O que define um lead qualificado: setor, porte, budget mínimo, cargo do decisor.',
  hint: 'Defina os critérios que aprovam ou descartam um lead de [PÚBLICO] em [NICHO] para F1 e F3. O agente usa isso para decidir se avança ou encerra a conversa.',
  placeholder: 'Aprovado se:\n- Faturamento acima de R$ 2M/ano\n- Setor: [indústria, logística, varejo B2B]\n- Decisor: sócio, CEO, CFO ou diretor\n- Budget: mínimo R$ 3.000/mês\n- Timing: necessidade nos próximos 90 dias\n\nDesqualificado se:\n- Empresa com menos de 10 funcionários\n- Apenas operacional tomando a decisão',
  importance: 'recommended',
  when_used: 'Qualificação',
};

const CAT_PRE_MEETING_FAQ: KnowledgeCategory = {
  key: 'pre_meeting_faq',
  label: 'FAQ Pré-Reunião',
  description: 'Perguntas frequentes que o lead faz antes de aceitar agendar uma reunião.',
  hint: 'Liste perguntas e respostas curtas. Ex: duração, formato (presencial/online), o que precisa preparar, se é uma venda ou uma conversa exploratória.',
  placeholder: '"Quanto tempo dura a reunião?" → 30–40 minutos.\n"É presencial ou online?" → Online via Google Meet, com link enviado na confirmação.\n"Vou ser pressionado a comprar?" → Não — é uma conversa de diagnóstico. Você só decide se fizer sentido.\n"Preciso preparar algo?" → Não é necessário, mas se puder, nos diga o maior desafio atual.',
  importance: 'recommended',
  when_used: 'Qualificação',
};

const CAT_PRICE_POLICY: KnowledgeCategory = {
  key: 'price_policy',
  label: 'Política de Preço',
  description: 'O que o agente pode e não pode dizer sobre preço antes da reunião com o vendedor.',
  hint: 'Defina se o agente deve citar faixas de preço, dizer que o preço é apresentado na reunião, ou dar uma âncora de valor. Seja específico para evitar que o agente improvise.',
  placeholder: 'O agente NÃO deve citar preços específicos antes da reunião.\nSe perguntado, responder: "O investimento varia conforme o tamanho e as necessidades da sua operação — por isso a reunião existe, para entendermos o que faz sentido para vocês."\nFaixa de referência (para citar apenas se o lead insistir): a partir de R$ X/mês.',
  importance: 'recommended',
  when_used: 'Apresentação',
};

const CAT_PITCH_SCRIPT: KnowledgeCategory = {
  key: 'pitch_script',
  label: 'Script de Pitch',
  description: 'A apresentação completa do produto que o agente usa para fechar a venda.',
  hint: 'Escreva o pitch de [OFERTA] para [PÚBLICO] seguindo a estrutura: 1) Dor (eco da dor do lead), 2) Solução (o que é o produto), 3) Benefícios (3 resultados concretos), 4) Prova social (1 caso de sucesso rápido), 5) Oferta (preço, o que inclui), 6) Urgência (por que agir agora).',
  placeholder: '🔴 Dor: "Você me disse que [dor]. Isso é exatamente o que [OFERTA] resolve."\n\n✅ Solução: [OFERTA] é [descrição em 1 frase].\n\n📈 Benefícios:\n1. [Resultado concreto 1]\n2. [Resultado concreto 2]\n3. [Resultado concreto 3]\n\n⭐ Prova social: "[Perfil de [PÚBLICO]] conseguiu [resultado] em [tempo]."\n\n💰 Oferta: [Preço] por [período]. Inclui: [lista rápida].\n\n⏰ Urgência: [Ex: "Essa condição é válida até [data] / Restam X vagas com esse preço."]',
  importance: 'critical',
  when_used: 'Apresentação',
};

const CAT_OBJECTIONS_CLOSER: KnowledgeCategory = {
  key: 'objections_faq',
  label: 'FAQ de Objeções',
  description: 'As 5–10 objeções mais comuns durante o pitch e as respostas que o bot deve usar.',
  hint: 'Liste cada objeção e a resposta exata (ou roteiro de resposta) que o agente deve dar. Seja direto — em low ticket a conversa é rápida e o agente precisa de respostas prontas.',
  placeholder: '"Está caro." → "Entendo. Para te dar um parâmetro: clientes nossos costumam recuperar o valor em [X dias/semanas] com [benefício específico]. Faz sentido?"\n\n"Vou pensar." → "Sem problema! Só lembrando que [urgência/condição especial] termina [data/condição]. Posso reservar sua vaga enquanto você decide?"\n\n"Já tentei algo parecido antes." → "O que não funcionou naquela época? [Aguardar resposta] — entendo. Nosso diferencial em relação a isso é [diferencial específico]."',
  importance: 'critical',
  when_used: 'Apresentação · Follow-up',
};

const CAT_SOCIAL_PROOF_CLOSER: KnowledgeCategory = {
  key: 'social_proof',
  label: 'Depoimentos e Provas Sociais',
  description: 'Depoimentos e resultados que o bot pode citar durante o pitch para reduzir resistência.',
  hint: 'Escreva depoimentos reais (ou compostos) com resultado específico. O bot os cita naturalmente durante o pitch. Inclua: perfil do cliente, resultado obtido, tempo para resultado.',
  placeholder: '"Consegui [resultado] em [X semanas] depois de [ação]. Simplesmente funcionou." — [Perfil: ex. mãe de 2 filhos, 34 anos]\n\n"Eu estava cético no início, mas em [X dias] já vi [resultado concreto]." — [Perfil: ex. professor de educação física]\n\n"Melhor investimento que fiz esse ano." — [Perfil]',
  importance: 'critical',
  when_used: 'Aquecimento · Follow-up',
};

const CAT_PRODUCT_DETAILS: KnowledgeCategory = {
  key: 'product_details',
  label: 'Detalhes do Produto',
  description: 'O que está incluído na compra: módulos, bônus, formato de entrega.',
  hint: 'Descreva tudo que o cliente recebe ao comprar. O agente usa isso para responder "o que vem junto?" durante o pitch.',
  placeholder: 'O produto inclui:\n- [Módulo/item 1]: [descrição breve]\n- [Módulo/item 2]: [descrição breve]\n- Bônus: [nome do bônus] (valor: R$ X)\n- Acesso: [Ex: vitalício / 12 meses / imediato após pagamento]\n- Suporte: [Ex: grupo no WhatsApp / e-mail / sem suporte]',
  importance: 'recommended',
  when_used: 'Apresentação',
};

const CAT_GUARANTEE: KnowledgeCategory = {
  key: 'guarantee_policy',
  label: 'Política de Garantia',
  description: 'Como funciona a garantia, prazo e como o cliente solicita reembolso.',
  hint: 'Descreva a garantia de forma clara. O agente usa isso para reduzir o risco percebido antes do pagamento.',
  placeholder: 'Garantia de X dias. Se não ficar satisfeito por qualquer motivo, basta enviar um e-mail para [contato] dentro do prazo e o reembolso é feito em até [X dias úteis]. Sem perguntas, sem burocracia.',
  importance: 'recommended',
  when_used: 'Apresentação',
};

const CAT_URGENCY_OFFER: KnowledgeCategory = {
  key: 'urgency_offer',
  label: 'Condição Atual da Oferta',
  description: 'Prazo, vagas, desconto ou bônus vigente — a urgência real que o bot comunica.',
  hint: 'Descreva a condição especial atual com precisão. IMPORTANTE: mantenha atualizado. O agente só cria urgência real se a informação for verdadeira.',
  placeholder: 'Condição vigente até [data]: preço de R$ X (de R$ Y cheio).\nVagas disponíveis nessa condição: [número ou "últimas unidades"].\nBônus exclusivo para quem comprar até [data]: [nome do bônus].',
  importance: 'recommended',
  when_used: 'Apresentação',
};

const CAT_UPSELL: KnowledgeCategory = {
  key: 'upsell_content',
  label: 'Conteúdo de Upsell',
  description: 'O próximo produto a oferecer imediatamente após a compra ser confirmada.',
  hint: 'Descreva o produto de upsell, o argumento para oferecê-lo e o preço especial. O bot apresenta logo após confirmar o pagamento.',
  placeholder: 'Upsell: [Nome do produto]\nArgumento: "Clientes que levaram [produto principal] normalmente levam isso junto porque [benefício complementar]."\nPreço especial pós-compra: R$ X (normal: R$ Y)\nLink: [URL do upsell]',
  importance: 'optional',
  when_used: 'Pós-venda',
};

const CAT_CART_RECOVERY: KnowledgeCategory = {
  key: 'cart_recovery_scripts',
  label: 'Script de Recuperação de Carrinho',
  description: 'As mensagens de follow-up para leads que não finalizaram a compra.',
  hint: 'Escreva 3 mensagens com ângulos diferentes para os intervalos de 2h, 24h e 48h após o abandono. Cada mensagem deve ter um gancho diferente: urgência, benefício ou prova social.',
  placeholder: 'Mensagem 1 (2h depois):\n"Oi [nome]! Vi que você ficou de olho no [produto]. Ainda dá tempo de garantir com [condição especial]. Posso te ajudar com alguma dúvida?"\n\nMensagem 2 (24h depois):\n"[Nome], uma coisa que os nossos clientes mais elogiam é [benefício principal]. Você ainda tem a chance de garantir o seu com [desconto/bônus]. Válido até [data]."\n\nMensagem 3 (48h depois):\n"Última chance! A condição de R$ X termina hoje à meia-noite. [Prova social rápida]. Quer garantir antes que acabe?"',
  importance: 'recommended',
  when_used: 'Follow-up',
};

const CAT_FIT_QUESTIONS: KnowledgeCategory = {
  key: 'fit_questions',
  label: 'Perguntas de Fit',
  description: 'As 1–2 perguntas de qualificação mínima que o bot faz antes de iniciar o pitch.',
  hint: 'Defina as 1–2 perguntas que filtram quem de [PÚBLICO] tem ou não tem a dor que [OFERTA] resolve. O objetivo é confirmar o fit antes do pitch — não é uma qualificação profunda.',
  placeholder: 'Pergunta 1: "[Pergunta que confirma a dor principal de [PÚBLICO]]"\nEx: "Você já tentou [solução alternativa] antes?"\n\nPergunta 2 (opcional): "[Pergunta que confirma o perfil]"\nEx: "Você está buscando resultado em quanto tempo?"',
  importance: 'recommended',
  when_used: 'Qualificação',
};

const CAT_POST_PURCHASE_ONBOARDING: KnowledgeCategory = {
  key: 'post_purchase_onboarding',
  label: 'Onboarding Pós-Compra',
  description: 'Mensagem de boas-vindas e próximos passos enviados automaticamente após pagamento confirmado.',
  hint: 'Escreva a mensagem que o bot envia imediatamente após a compra ser confirmada. Deve passar: boas-vindas, como acessar o produto, o que fazer primeiro e onde pedir ajuda.',
  placeholder: 'Bem-vindo ao [produto], [nome]! 🎉\n\nSeu acesso foi liberado. Veja o que fazer agora:\n1️⃣ Acesse em: [LINK]\n2️⃣ Comece por: [módulo/etapa inicial]\n3️⃣ Dúvidas? Escreva aqui mesmo ou entre no grupo: [LINK DO GRUPO]\n\nQualquer coisa, é só chamar. Vamos juntos!',
  importance: 'optional',
  when_used: 'Pós-venda',
};

const CAT_PROFESSIONAL_BIO: KnowledgeCategory = {
  key: 'professional_bio',
  label: 'Bio do Profissional',
  description: 'Quem é o profissional, formação, especialidade e o que o torna único.',
  hint: 'Escreva como o agente deve se apresentar em nome do profissional que atua em [NICHO]. Inclua: nome, especialidade, formação relevante, anos de experiência, tipo de cliente atendido ([PÚBLICO]), diferencial.',
  placeholder: '[Nome] é [especialidade] com [X anos] de experiência em [NICHO]. Formado em [formação] e especializado em [área específica]. Atende [PÚBLICO] que querem [resultado]. Seu diferencial é [o que o torna único — método, abordagem, resultado recorrente].',
  importance: 'critical',
  when_used: 'Apresentação',
};

const CAT_SOCIAL_PROOF_HYBRID: KnowledgeCategory = {
  key: 'social_proof',
  label: 'Histórias de Transformação',
  description: 'Casos de clientes com perfil similar ao lead, usados no aquecimento antes do agendamento.',
  hint: 'Escreva 2–3 histórias de transformação de [PÚBLICO] em [NICHO]: perfil (sem nome completo), situação inicial, o que mudou após trabalhar com o profissional, e o resultado em detalhes. O agente as cita para aquecer o lead antes de propor o agendamento.',
  placeholder: 'História 1: [PÚBLICO] — Chegou com [situação inicial em [NICHO]]. Depois de [período] trabalhando com [Nome do profissional], [resultado concreto]. Hoje [situação atual].\n\nHistória 2: [perfil similar] — [Situação inicial]. O principal avanço foi [resultado específico].',
  importance: 'critical',
  when_used: 'Aquecimento · Follow-up',
};

const CAT_SESSION_PREVIEW: KnowledgeCategory = {
  key: 'session_preview',
  label: 'Preview da Sessão',
  description: 'Como funciona a 1ª sessão: duração, formato e o que o lead pode esperar.',
  hint: 'Descreva a sessão do ponto de vista do lead de [PÚBLICO] em [NICHO]. O agente usa isso para reduzir ansiedade antes do agendamento e aumentar o comparecimento.',
  placeholder: 'A sessão dura [X minutos] e acontece [online via Google Meet / presencialmente em X].\nNo encontro, [Nome] vai: 1) Entender sua situação em [NICHO], 2) Identificar os principais bloqueios, 3) Mostrar o caminho mais direto para [resultado esperado por [PÚBLICO]].\nNão é uma consulta de vendas — é um diagnóstico real. Você sai com [entregável concreto].',
  importance: 'critical',
  when_used: 'Apresentação',
};

const CAT_PAIN_QUESTIONS: KnowledgeCategory = {
  key: 'pain_questions',
  label: 'Roteiro de Perguntas de Dor',
  description: 'Perguntas abertas que o agente usa para aprofundar o problema e compor o briefing ao profissional.',
  hint: 'Escreva as perguntas que o agente deve fazer para entender o problema do lead de [PÚBLICO]. As respostas viram o briefing enviado ao profissional antes da sessão. Foque em perguntas abertas, não binárias.',
  placeholder: '"Qual é o seu principal desafio em relação a [NICHO] no momento?"\n"Como isso impacta o seu [dia a dia / resultados / bem-estar]?"\n"O que você já tentou fazer para resolver isso?"\n"O que mudaria na sua vida se você resolvesse isso nos próximos 3 meses?"',
  importance: 'recommended',
  when_used: 'Qualificação',
};

const CAT_SCHEDULING_POLICY: KnowledgeCategory = {
  key: 'scheduling_policy',
  label: 'Política de Agendamento',
  description: 'Regras de cancelamento, reagendamento e no-show.',
  hint: 'Defina as regras com clareza para que o agente comunique ao lead durante e após o agendamento.',
  placeholder: 'Cancelamento: até [X horas antes], pelo WhatsApp ou pelo link da confirmação.\nReagendamento: possível uma vez sem custo. Para reagendar, responder esta mensagem.\nNo-show: se o lead não comparecer sem avisar, o agente reagenda automaticamente e envia uma mensagem de retorno.',
  importance: 'recommended',
  when_used: 'Agendamento',
};

const CAT_SERVICE_FAQ: KnowledgeCategory = {
  key: 'service_faq',
  label: 'FAQ do Serviço',
  description: 'Perguntas frequentes sobre preço, formato, frequência e o que está incluído.',
  hint: 'Antecipe as perguntas mais comuns que o lead faz antes de agendar. O agente responde com essas informações diretamente na conversa.',
  placeholder: '"Qual o valor da sessão?" → R$ X por [duração]. Pacotes a partir de [X sessões].\n"É online ou presencial?" → [Resposta]\n"Quantas sessões precisarei?" → Depende do objetivo — na 1ª sessão [Nome] faz o diagnóstico e indica o melhor formato.\n"Você aceita plano de saúde?" → [Resposta]',
  importance: 'recommended',
  when_used: 'Apresentação · Follow-up',
};

const CAT_PRE_SESSION_MATERIAL: KnowledgeCategory = {
  key: 'pre_session_material',
  label: 'Material Pré-Sessão',
  description: 'Formulário ou tarefa que o lead recebe antes da 1ª sessão.',
  hint: 'Descreva o que o lead precisa fazer antes de comparecer — e o texto exato que o agente envia. Pode ser um link de formulário, perguntas por texto ou uma tarefa simples.',
  placeholder: 'Texto que o agente envia 24h antes:\n"Antes da nossa sessão, [Nome do profissional] gostaria que você respondesse rapidinho 3 perguntas — leva menos de 5 minutos e deixa a sessão muito mais aproveitada: [LINK DO FORMULÁRIO]"',
  importance: 'optional',
  when_used: 'Agendamento',
};

const CAT_HANDOFF_BRIEFING: KnowledgeCategory = {
  key: 'handoff_briefing_template',
  label: 'Script de Dossiê',
  description: 'Modelo do resumo que o bot envia ao vendedor antes da reunião com o lead.',
  hint: 'Defina quais campos devem constar no dossiê entregue ao vendedor. O agente preenche automaticamente com as respostas coletadas durante a qualificação.',
  placeholder: 'DOSSIÊ DO LEAD — [Nome]\n\nPerfil:\n- Empresa: [resposta]\n- Setor: [resposta]\n- Porte / Faturamento: [resposta]\n- Cargo do decisor: [resposta]\n\nDor principal: [resposta F1]\nMomento: [urgência declarada]\nBudget confirmado: [sim/não + valor]\n\nObjeções levantadas: [se houver]\nNível de urgência (1–10): [resposta]\n\nLink da agenda: [se agendado via bot]',
  importance: 'recommended',
  when_used: 'Handoff ao vendedor',
};

const CAT_COMPETITIVE_DIFFERENTIALS: KnowledgeCategory = {
  key: 'competitive_differentials',
  label: 'Diferenciação Competitiva',
  description: 'Respostas para quando o lead menciona que já usa ou está avaliando um concorrente.',
  hint: 'Liste os concorrentes mais comuns e o argumento de diferenciação para cada um. O agente usa quando o lead diz "já uso X" ou "estou avaliando Y também".',
  placeholder: 'Concorrente A: "[Nome]"\nDiferencial: "[O que nos torna melhor ou diferente nesse caso específico]"\n\nConcorrente B: "[Nome]"\nDiferencial: "[O que nos torna melhor ou diferente nesse caso específico]"\n\nResposta padrão (concorrente não listado):\n"Conheço [nome]. O que costumamos ouvir de quem migrou para nós é que [diferencial principal]. Mas cada caso é diferente — por isso a reunião existe."',
  importance: 'optional',
  when_used: 'Qualificação · Apresentação',
};

const CAT_NURTURE_CONTENT: KnowledgeCategory = {
  key: 'nurture_content',
  label: 'Mensagens de Nurture',
  description: 'Conteúdo para leads que não qualificaram agora mas têm potencial futuro.',
  hint: 'Escreva 2–3 mensagens para manter contato com leads fora do timing ideal. O objetivo não é vender — é manter a relação quente para uma conversa futura.',
  placeholder: 'Mensagem 1 (imediata — após descarte suave):\n"Entendo que não é o momento certo agora. Quando fizer sentido revisitar, é só me chamar — vou estar aqui."\n\nMensagem 2 (30 dias depois):\n"Oi [nome], passando para dizer que [novidade relevante / insight do setor]. Acho que pode ser útil para o momento que você está. Qualquer coisa, é só falar."\n\nMensagem 3 (90 dias depois):\n"[Nome], faz um tempo! Como estão as coisas em [área]? Nosso [produto] teve algumas melhorias recentes que podem mudar o cálculo do que conversamos."',
  importance: 'optional',
  when_used: 'Follow-up',
};

const CAT_WARMING_SCRIPT: KnowledgeCategory = {
  key: 'warming_script',
  label: 'Script de Aquecimento',
  description: 'Texto que conecta a dor do lead com o que o profissional resolve, usado antes de propor o agendamento.',
  hint: 'Escreva o texto que o agente usa para criar conexão emocional com [PÚBLICO] em [NICHO] e gerar desejo pelo agendamento. Deve soar natural, não como pitch. Use a dor do lead como ponto de partida.',
  placeholder: 'Roteiro de aquecimento:\n\n"[Nome], muitas pessoas que chegam até [profissional] estão passando exatamente pelo que você descreveu — [eco da dor]. O que elas costumam descobrir nas primeiras sessões é que [insight transformador].\n\n[História de transformação resumida — 2 linhas].\n\nA [Nome do profissional] tem uma abordagem diferente para isso: [diferencial do método]. Não é mais do mesmo — é [o que é único].\n\nVocê teria interesse em uma conversa rápida para ver se faz sentido para o seu caso?"',
  importance: 'recommended',
  when_used: 'Aquecimento',
};

const CAT_POST_SESSION_FOLLOWUP: KnowledgeCategory = {
  key: 'post_session_followup',
  label: 'Follow-up Pós-Sessão',
  description: 'Mensagens para clientes que vieram à sessão mas não retornaram para marcar novamente.',
  hint: 'Escreva 2–3 mensagens para reconectar com clientes que participaram da sessão mas sumiram. O objetivo é propor uma nova marcação sem soar insistente.',
  placeholder: 'Mensagem 1 (3 dias após sessão sem retorno):\n"Oi [nome]! Esperamos que a sessão tenha sido boa. Como você está se sentindo desde então? Se quiser marcar o próximo encontro, é só me falar."\n\nMensagem 2 (10 dias após):\n"[Nome], [Nome do profissional] estava pensando em você. Tem alguma questão específica que ficou em aberto da nossa última sessão? Às vezes um ajuste pequeno faz toda a diferença."\n\nMensagem 3 (30 dias após):\n"Faz um tempo! Quando estiver pronto para continuar, a agenda de [Nome do profissional] está disponível. Qualquer dia é um bom dia para retomar."',
  importance: 'optional',
  when_used: 'Follow-up',
};

const CAT_REFERRAL_SCRIPT: KnowledgeCategory = {
  key: 'referral_script',
  label: 'Script de Indicação',
  description: 'Pedido de indicação enviado a clientes satisfeitos após uma sessão bem avaliada.',
  hint: 'Escreva a mensagem que o agente envia para pedir indicação. O momento ideal é logo após o cliente confirmar que a sessão foi boa. Deve soar natural, não como solicitação comercial.',
  placeholder: '"[Nome], fico feliz que a sessão tenha sido proveitosa! Uma coisa que ajuda muito [Nome do profissional] a ajudar mais pessoas é a indicação de quem já viveu a experiência.\n\nSe você conhece alguém que está passando por [dor / situação similar], eu adoraria bater um papo com essa pessoa. Pode ser uma mensagem simples apresentando a [Nome do profissional].\n\nE se quiser, posso preparar uma mensagem pronta para você encaminhar — leva 30 segundos. O que acha?"',
  importance: 'optional',
  when_used: 'Pós-atendimento',
};

// ─── Categorias comerciais do hybrid_scheduler (sub-modo 'commercial') ───────

const CAT_SERVICE_PRICING_TABLE: KnowledgeCategory = {
  key: 'service_pricing_table',
  label: 'Tabela de Serviços e Preços',
  description: 'Lista de serviços, pacotes e valores que o agente pode apresentar ao lead. Se os serviços tiverem durações diferentes, o agente também usa esta lista para agendar com a duração certa.',
  hint: 'Liste todos os serviços e pacotes disponíveis com seus respectivos valores e duração. O agente usa para apresentar opções ao lead de [PÚBLICO] em [NICHO], conduzir a escolha de um serviço, e bloquear o tempo certo na agenda ao confirmar o horário.',
  placeholder: 'Sessão avulsa — [duração]: R$ [valor]\nPacote [X] sessões: R$ [valor] (economia de [%])\nPacote [Y] sessões: R$ [valor]\n\nSe houver diferença entre modalidades (ex: presencial vs. online), especifique aqui também.',
  importance: 'critical',
  when_used: 'Apresentação comercial · Agendamento',
  allowMultiple: true,
};

const CAT_COMMERCIAL_OBJECTIONS: KnowledgeCategory = {
  key: 'commercial_objections',
  label: 'Objeções Comerciais e Respostas',
  description: 'Respostas prontas para objeções de preço e comprometimento que surgem antes de fechar o pacote.',
  hint: 'Liste as objeções mais comuns de [PÚBLICO] antes de fechar um pacote em [NICHO] e a resposta ideal para cada uma. O agente usa isso para tratar objeções e manter o lead avançando rumo ao compromisso.',
  placeholder: '"Está caro" → [Resposta que reformula o valor entregue e compara com o custo do problema não resolvido]\n"Vou pensar" → [Resposta que cria urgência real ou remove o risco da decisão]\n"Deixa eu ver minha agenda" → [Resposta que acelera o comprometimento propondo uma data imediatamente]\n"Não tenho certeza se vai funcionar pra mim" → [Resposta com prova social de perfil similar]',
  importance: 'critical',
  when_used: 'Apresentação comercial',
};

const CAT_SERVICE_DIFFERENTIALS: KnowledgeCategory = {
  key: 'service_differentials',
  label: 'Diferenciais do Serviço',
  description: 'Por que escolher este profissional vs. alternativas. Usado quando o lead compara ou questiona.',
  hint: 'Descreva o que torna este serviço em [NICHO] único: técnica, formação, ambiente, resultados comprovados, abordagem. O agente usa isso quando o lead menciona comparar com outro profissional ou questionar o diferencial.',
  placeholder: 'Técnica: [método ou abordagem exclusiva]\nFormação: [certificações, especializações relevantes para [PÚBLICO]]\nAmbiente: [localização, estrutura, comodidades]\nResultados: [métricas ou histórico comprovável]\nDiferencial central: [o que nenhum concorrente entrega da mesma forma]',
  importance: 'recommended',
  when_used: 'Apresentação comercial',
};

const CAT_ACTIVE_PROMOTION: KnowledgeCategory = {
  key: 'active_promotion',
  label: 'Condição Especial Vigente',
  description: 'Desconto, bônus ou condição limitada atual. Atualizar sempre que a promoção mudar.',
  hint: 'Descreva a condição especial ativa no momento (se houver). O agente só cita se for real — não inventa urgência. Mantenha atualizado: quando a promoção terminar, remova ou edite este conteúdo.',
  placeholder: 'Condição vigente até [data]: [descrição da promoção — ex: "pacote de 4 sessões por R$X (antes R$Y)" ou "bônus de sessão extra para quem fechar até sexta"]\n\nRegra de comunicação: mencionar apenas se o lead estiver em dúvida entre fechar ou esperar.',
  importance: 'recommended',
  when_used: 'Apresentação comercial',
};

const CAT_PAYMENT_POLICY: KnowledgeCategory = {
  key: 'payment_policy',
  label: 'Política de Pagamento Presencial',
  description: 'Formas de pagamento aceitas na marcação e regras de sinal ou entrada.',
  hint: 'Informe como o pagamento funciona na prática. O agente comunica isso ao lead após fechar o compromisso, para que ele chegue preparado.',
  placeholder: 'Formas aceitas: [Pix / Dinheiro / Cartão de débito ou crédito — especificar quais]\nSinal para reservar vaga: [valor ou percentual, se aplicável]\nPagamento integral: na chegada, antes da sessão.\n\nObs: nenhum link de pagamento digital é enviado — tudo presencialmente.',
  importance: 'recommended',
  when_used: 'Apresentação comercial',
};

const CAT_PRE_COMMITMENT_FAQ: KnowledgeCategory = {
  key: 'pre_commitment_faq',
  label: 'FAQ Pré-Compromisso',
  description: 'Perguntas frequentes antes de fechar o pacote: vigência, pausa, transferência.',
  hint: 'Antecipe as dúvidas que travam o "sim" final de [PÚBLICO]. O agente responde com essas informações durante a negociação.',
  placeholder: '"As sessões do pacote vencem?" → [Resposta]\n"Posso pausar ou trancar o pacote?" → [Resposta]\n"Consigo transferir para outra pessoa?" → [Resposta]\n"E se eu não gostar da primeira sessão?" → [Política de reembolso ou garantia]\n"Posso parcelar no cartão?" → [Resposta]',
  importance: 'recommended',
  when_used: 'Apresentação comercial',
};

// CAT_SERVICE_PRICING_TABLE não entra aqui — já está na lista padrão de hybrid_scheduler
// (KNOWLEDGE_CATEGORIES_BY_TEMPLATE.hybrid_scheduler), disponível em qualquer appointment_mode.
export const KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL: KnowledgeCategory[] = [
  CAT_COMMERCIAL_OBJECTIONS,
  CAT_SERVICE_DIFFERENTIALS,
  CAT_ACTIVE_PROMOTION,
  CAT_PAYMENT_POLICY,
  CAT_PRE_COMMITMENT_FAQ,
];

export const KNOWLEDGE_CATEGORIES_BY_TEMPLATE: Record<string, KnowledgeCategory[]> = {
  sdr_padrao: [
    CAT_COMPANY_PROFILE,
    CAT_SOCIAL_PROOF_SDR,
    CAT_OBJECTIONS_SDR,
    CAT_QUALIFICATION_CRITERIA,
    CAT_PRE_MEETING_FAQ,
    CAT_PRICE_POLICY,
    CAT_HANDOFF_BRIEFING,
    CAT_COMPETITIVE_DIFFERENTIALS,
    CAT_NURTURE_CONTENT,
  ],
  consultor_especialista: [
    CAT_COMPANY_PROFILE,
    CAT_SOCIAL_PROOF_SDR,
    CAT_OBJECTIONS_SDR,
    CAT_QUALIFICATION_CRITERIA,
    CAT_PRE_MEETING_FAQ,
    CAT_PRICE_POLICY,
    CAT_HANDOFF_BRIEFING,
    CAT_COMPETITIVE_DIFFERENTIALS,
    CAT_NURTURE_CONTENT,
  ],
  closer_agressivo: [
    CAT_PITCH_SCRIPT,
    CAT_OBJECTIONS_CLOSER,
    CAT_SOCIAL_PROOF_CLOSER,
    CAT_PRODUCT_DETAILS,
    CAT_GUARANTEE,
    CAT_URGENCY_OFFER,
    CAT_FIT_QUESTIONS,
    CAT_CART_RECOVERY,
    CAT_UPSELL,
    CAT_POST_PURCHASE_ONBOARDING,
  ],
  hybrid_scheduler: [
    CAT_PROFESSIONAL_BIO,
    CAT_SOCIAL_PROOF_HYBRID,
    CAT_SESSION_PREVIEW,
    CAT_WARMING_SCRIPT,
    CAT_PAIN_QUESTIONS,
    CAT_SCHEDULING_POLICY,
    CAT_SERVICE_PRICING_TABLE,
    CAT_SERVICE_FAQ,
    CAT_POST_SESSION_FOLLOWUP,
    CAT_PRE_SESSION_MATERIAL,
    CAT_REFERRAL_SCRIPT,
  ],
};

export const KNOWLEDGE_IMPORTANCE_LABELS: Record<KnowledgeCategory['importance'], string> = {
  critical: 'Crítico',
  recommended: 'Recomendado',
  optional: 'Opcional',
};

export const PAYMENT_GATEWAY_LABELS: Record<string, string> = {
  hotmart:  'Hotmart',
  kiwify:   'Kiwify',
  stripe:   'Stripe',
  generico: 'Link genérico',
};

export const OFFER_MEDIA_TYPE_LABELS: Record<string, string> = {
  image: 'Imagem',
  video: 'Vídeo',
  audio: 'Áudio',
};

export const BRIEFING_CHANNEL_LABELS: Record<string, string> = {
  whatsapp: 'WhatsApp',
  internal: 'Interno (CRM)',
};

// ─── Exportação / Importação de agente ───────────────────────

/** Um item de treinamento exportável (sem IDs internos nem dados do usuário) */
export interface TrainingItem {
  agent_mode: string | null;
  phase: string | null;
  mother_route: string | null;
  lead_message: string | null;
  bot_message: string;
  rating: 'ruim' | 'regular' | 'boa' | 'excelente';
  comment: string | null;
}

/** Contrato JSON de exportação de agente */
export interface AgentExportPayload {
  version: '1.0';
  schema: 'crm-agent-export';
  exported_at: string;
  agent_name: string;
  includes_training: boolean;
  profile: Partial<AgentConfig>;
  training: TrainingItem[];
}
